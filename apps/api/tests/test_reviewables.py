import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.v1.dependencies import get_session
from app.main import create_app
from app.models.moderation import Reviewable
from app.models.user import User
from tests.helpers import get_test_database_url, register_and_verify_user, reset_test_database


async def create_test_session() -> tuple[async_sessionmaker[AsyncSession], object]:
    engine = create_async_engine(get_test_database_url())
    async with engine.begin() as conn:
        await reset_test_database(conn)
    return async_sessionmaker(engine, expire_on_commit=False), engine


async def register_user(client: AsyncClient, username: str) -> dict[str, str]:
    data = await register_and_verify_user(client, username)
    return {
        "id": data["user"]["id"],
        "token": data["access_token"],
        "auth": f"Bearer {data['access_token']}",
    }


async def create_topic_fixture(client: AsyncClient, auth: str) -> dict[str, str]:
    board = await client.post(
        "/api/v1/boards",
        headers={"Authorization": auth},
        json={
            "slug": "engineering",
            "name": "Engineering Board",
            "description": "Board for engineering discussions.",
            "color": "#10B981",
        },
    )
    assert board.status_code == 201

    topic = await client.post(
        "/api/v1/boards/engineering/topics",
        headers={"Authorization": auth},
        json={
            "title": "Initial Engineering Discussion",
            "raw_md": "This is the first topic on the board.",
            "tags": ["engineering"],
        },
    )
    assert topic.status_code == 201
    topic_data = topic.json()["data"]

    reply = await client.post(
        f"/api/v1/topics/{topic_data['id']}/posts",
        headers={"Authorization": auth},
        json={"raw_md": "This is a reply post."},
    )
    assert reply.status_code == 201

    return {"topic_id": topic_data["id"], "post_id": reply.json()["data"]["id"]}


@pytest.mark.asyncio
async def test_reviewable_flag_lifecycle() -> None:
    session_factory, engine = await create_test_session()

    async def override_session():
        async with session_factory() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_session] = override_session

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        owner = await register_user(client, "owner")
        reporter = await register_user(client, "reporter")
        fixture = await create_topic_fixture(client, owner["auth"])

        reporter_headers = {"Authorization": reporter["auth"]}
        owner_headers = {"Authorization": owner["auth"]}

        # 1. Reporter flags the post
        flag = await client.post(
            "/api/v1/moderation/flags",
            headers=reporter_headers,
            json={
                "target_type": "post",
                "target_id": fixture["post_id"],
                "reason": "spam",
                "detail": "Please review this spam post.",
            },
        )
        assert flag.status_code == 201
        flag_id = flag.json()["data"]["id"]

        # Verify a Reviewable has been created
        async with session_factory() as session:
            reviewable = await session.scalar(
                select(Reviewable).where(Reviewable.flag_id == flag_id)
            )
            assert reviewable is not None
            assert reviewable.status == "pending"
            assert reviewable.type == "flag"
            reviewable_id = reviewable.id

        # 2. List reviewables queue as moderator (owner)
        queue = await client.get("/api/v1/moderation/reviewables", headers=owner_headers)
        assert queue.status_code == 200
        reviewables_list = queue.json()["data"]
        assert len(reviewables_list) >= 1
        assert reviewables_list[0]["id"] == reviewable_id
        assert reviewables_list[0]["status"] == "pending"

        # List reviewables as regular user (reporter) -> Forbidden
        forbidden_list = await client.get(
            "/api/v1/moderation/reviewables",
            headers=reporter_headers,
        )
        assert forbidden_list.status_code == 403

        other_mod = await register_user(client, "other_mod")
        async with session_factory() as session:
            moderator = await session.get(User, other_mod["id"])
            assert moderator is not None
            moderator.role = "moderator"
            await session.commit()

        # 3. Claim the reviewable
        claim = await client.post(
            f"/api/v1/moderation/reviewables/{reviewable_id}/claim",
            headers=owner_headers,
        )
        assert claim.status_code == 200
        assert claim.json()["data"]["status"] == "claimed"
        assert claim.json()["data"]["assigned_to_id"] == owner["id"]

        conflict_claim = await client.post(
            f"/api/v1/moderation/reviewables/{reviewable_id}/claim",
            headers={"Authorization": other_mod["auth"]},
        )
        assert conflict_claim.status_code == 409

        # Let's verify owner can release
        release = await client.post(
            f"/api/v1/moderation/reviewables/{reviewable_id}/release",
            headers=owner_headers,
        )
        assert release.status_code == 200
        assert release.json()["data"]["status"] == "pending"
        assert release.json()["data"]["assigned_to_id"] is None

        # Re-claim and decide (Approve)
        claim2 = await client.post(
            f"/api/v1/moderation/reviewables/{reviewable_id}/claim",
            headers=owner_headers,
        )
        assert claim2.status_code == 200

        decide = await client.post(
            f"/api/v1/moderation/reviewables/{reviewable_id}/decide",
            headers=owner_headers,
            json={
                "action": "approve",
                "note": "Content is fine. Resolving.",
            },
        )
        assert decide.status_code == 200
        assert decide.json()["data"]["status"] == "approved"
        assert decide.json()["data"]["resolved_by_id"] == owner["id"]

        # Verify flag status is resolved
        flag_status_check = await client.get(
            "/api/v1/moderation/queue",
            headers=owner_headers,
            params={"status": "resolved"},
        )
        assert flag_status_check.status_code == 200
        assert any(item["id"] == flag_id for item in flag_status_check.json()["data"])

    await engine.dispose()


@pytest.mark.asyncio
async def test_reviewable_appeal_workflow() -> None:
    session_factory, engine = await create_test_session()

    async def override_session():
        async with session_factory() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_session] = override_session

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        owner = await register_user(client, "owner")
        poster = await register_user(client, "poster")
        fixture = await create_topic_fixture(client, owner["auth"])

        poster_headers = {"Authorization": poster["auth"]}
        owner_headers = {"Authorization": owner["auth"]}

        # Create a reply from poster
        reply = await client.post(
            f"/api/v1/topics/{fixture['topic_id']}/posts",
            headers=poster_headers,
            json={"raw_md": "This reply will be flagged and hidden."},
        )
        assert reply.status_code == 201
        post_id = reply.json()["data"]["id"]

        # Flag post
        flag = await client.post(
            "/api/v1/moderation/flags",
            headers=owner_headers,  # flag it
            json={
                "target_type": "post",
                "target_id": post_id,
                "reason": "spam",
                "detail": "Test hide.",
            },
        )
        flag_id = flag.json()["data"]["id"]

        # Get the reviewable ID
        async with session_factory() as session:
            reviewable = await session.scalar(
                select(Reviewable).where(Reviewable.flag_id == flag_id)
            )
            assert reviewable is not None
            reviewable_id = reviewable.id

        # Decide: hide the content
        decide = await client.post(
            f"/api/v1/moderation/reviewables/{reviewable_id}/decide",
            headers=owner_headers,
            json={
                "action": "hide",
                "note": "Hiding this post.",
            },
        )
        assert decide.status_code == 200
        assert decide.json()["data"]["status"] == "hidden"

        # Verify post is hidden (deleted_at is set)
        post_check = await client.get(f"/api/v1/topics/{fixture['topic_id']}/posts")
        hidden_post = next(p for p in post_check.json()["data"] if p["id"] == post_id)
        assert hidden_post["deleted_at"] is not None

        # User checks their own moderation history (reviewables/me)
        me_queue = await client.get("/api/v1/moderation/reviewables/me", headers=poster_headers)
        assert me_queue.status_code == 200
        my_items = me_queue.json()["data"]
        assert len(my_items) >= 1
        assert my_items[0]["id"] == reviewable_id
        assert my_items[0]["status"] == "hidden"

        # User appeals
        appeal = await client.post(
            f"/api/v1/moderation/reviewables/{reviewable_id}/appeal",
            headers=poster_headers,
            json={"reason": "This is a false positive, please restore."},
        )
        assert appeal.status_code == 200
        assert appeal.json()["data"]["status"] == "appealed"

        # Verify status transitions to appealed in moderator view
        mod_queue = await client.get(
            "/api/v1/moderation/reviewables",
            headers=owner_headers,
            params={"status": "appealed"},
        )
        assert mod_queue.status_code == 200
        assert len(mod_queue.json()["data"]) >= 1
        assert mod_queue.json()["data"][0]["id"] == reviewable_id

    await engine.dispose()


@pytest.mark.asyncio
async def test_content_safety_queued_review() -> None:
    session_factory, engine = await create_test_session()

    async def override_session():
        async with session_factory() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_session] = override_session

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        owner = await register_user(client, "owner")
        user = await register_user(client, "user")

        # Setup board
        board = await client.post(
            "/api/v1/boards",
            headers={"Authorization": owner["auth"]},
            json={
                "slug": "safety",
                "name": "Safety Board",
                "description": "Safety test board.",
                "color": "#FF0000",
            },
        )
        assert board.status_code == 201

        # User posts topic containing review policy term "review-demo-term"
        queued_post = await client.post(
            "/api/v1/boards/safety/topics",
            headers={"Authorization": user["auth"]},
            json={
                "title": "A normal title",
                "raw_md": "This contains review-demo-term and should be queued.",
                "tags": ["safety"],
            },
        )
        # Expect 422 ValidationError with detail content_pending_review
        assert queued_post.status_code == 422
        error = queued_post.json()["error"]
        assert error["code"] == "content_pending_review"
        reviewable_id = error["details"]["reviewable_id"]
        assert reviewable_id is not None

        # Verify topic is not yet visible/published
        topics = await client.get("/api/v1/topics", params={"board": "safety"})
        assert topics.status_code == 200
        assert len(topics.json()["data"]) == 0

        # Moderator approves it
        approve = await client.post(
            f"/api/v1/moderation/reviewables/{reviewable_id}/decide",
            headers={"Authorization": owner["auth"]},
            json={
                "action": "approve",
                "note": "Content is safe.",
            },
        )
        assert approve.status_code == 200
        assert approve.json()["data"]["status"] == "approved"
        topic_id = approve.json()["data"]["topic_id"]
        assert topic_id is not None

        # Verify topic is now visible/published
        topics_after = await client.get("/api/v1/topics", params={"board": "safety"})
        assert topics_after.status_code == 200
        assert len(topics_after.json()["data"]) == 1
        assert topics_after.json()["data"][0]["id"] == topic_id

    await engine.dispose()

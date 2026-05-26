import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.v1.dependencies import get_session
from app.main import create_app
from app.models.user import User
from app.services.draft import DraftService
from tests.helpers import get_test_database_url, register_and_verify_user, reset_test_database


async def create_test_session() -> tuple[async_sessionmaker[AsyncSession], object]:
    engine = create_async_engine(get_test_database_url())
    async with engine.begin() as conn:
        await reset_test_database(conn)
    return async_sessionmaker(engine, expire_on_commit=False), engine


@pytest.mark.asyncio
async def test_draft_service_crud() -> None:
    session_factory, engine = await create_test_session()

    async with session_factory() as session:
        user = User(
            username="test_user_1",
            email="test_user_1@example.com",
            hashed_password="hashed",
        )
        session.add(user)
        await session.flush()
        user_id = user.id
        service = DraftService(session)

        # 1. Save new draft
        draft = await service.save_draft(
            user_id=user_id,
            target_type="new_topic",
            target_id="",
            draft_type="topic",
            data={"title": "Draft Title", "body": "Draft Body"},
            version=1,
        )
        assert draft.user_id == user_id
        assert draft.target_type == "new_topic"
        assert draft.target_id == ""
        assert draft.version == 1
        assert draft.data == {"title": "Draft Title", "body": "Draft Body"}

        # 2. Lookup draft
        lookup = await service.get_draft(user_id, "new_topic", "")
        assert lookup is not None
        assert lookup.id == draft.id

        # 3. Update draft with higher version
        updated = await service.save_draft(
            user_id=user_id,
            target_type="new_topic",
            target_id="",
            draft_type="topic",
            data={"title": "Draft Title v2", "body": "Draft Body v2"},
            version=2,
        )
        assert updated.id == draft.id
        assert updated.version == 2
        assert updated.data["title"] == "Draft Title v2"

        # 4. Version conflict check
        with pytest.raises(Exception) as exc_info:
            await service.save_draft(
                user_id=user_id,
                target_type="new_topic",
                target_id="",
                draft_type="topic",
                data={"title": "Stale draft"},
                version=2,
            )
        assert "A newer draft version exists on the server." in str(exc_info.value)

        # 5. List drafts
        drafts = await service.list_drafts_by_user(user_id)
        assert len(drafts) == 1
        assert drafts[0].id == draft.id

        # 6. Delete draft
        deleted = await service.delete_draft(user_id, "new_topic", "")
        assert deleted is True

        # 7. Check gone
        lookup_post_delete = await service.get_draft(user_id, "new_topic", "")
        assert lookup_post_delete is None

    await engine.dispose()


@pytest.mark.asyncio
async def test_draft_api_endpoints() -> None:
    session_factory, engine = await create_test_session()

    async def override_session():
        async with session_factory() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_session] = override_session

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        user_data = await register_and_verify_user(client, "draft_user")
        headers = {"Authorization": f"Bearer {user_data['access_token']}"}

        # 1. Lookup non-existent draft -> returns data: null
        lookup_resp = await client.get(
            "/api/v1/drafts/lookup?target_type=new_topic&target_id=",
            headers=headers,
        )
        assert lookup_resp.status_code == 200
        assert lookup_resp.json()["data"] is None

        # 2. Save draft
        save_resp = await client.put(
            "/api/v1/drafts",
            headers=headers,
            json={
                "target_type": "new_topic",
                "target_id": "",
                "draft_type": "topic",
                "data": {"title": "Hello Draft"},
                "version": 1,
            },
        )
        assert save_resp.status_code == 200
        assert save_resp.json()["data"]["version"] == 1
        assert save_resp.json()["data"]["data"] == {"title": "Hello Draft"}

        # 3. Save draft with lower version -> 409 Conflict
        save_conflict = await client.put(
            "/api/v1/drafts",
            headers=headers,
            json={
                "target_type": "new_topic",
                "target_id": "",
                "draft_type": "topic",
                "data": {"title": "Stale Hello"},
                "version": 1,
            },
        )
        assert save_conflict.status_code == 409
        assert save_conflict.json()["error"]["code"] == "draft_conflict"

        # 4. List user drafts
        list_resp = await client.get("/api/v1/drafts", headers=headers)
        assert list_resp.status_code == 200
        assert len(list_resp.json()["data"]) == 1

        # 5. Delete draft
        delete_resp = await client.delete(
            "/api/v1/drafts?target_type=new_topic&target_id=",
            headers=headers,
        )
        assert delete_resp.status_code == 200
        assert delete_resp.json()["data"] is True

        # 6. Lookup after delete
        lookup_resp_2 = await client.get(
            "/api/v1/drafts/lookup?target_type=new_topic&target_id=",
            headers=headers,
        )
        assert lookup_resp_2.status_code == 200
        assert lookup_resp_2.json()["data"] is None

    await engine.dispose()


@pytest.mark.asyncio
async def test_draft_deletion_on_topic_and_reply_creation() -> None:
    session_factory, engine = await create_test_session()

    async def override_session():
        async with session_factory() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_session] = override_session

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        user_data = await register_and_verify_user(client, "forum_draft_user")
        headers = {"Authorization": f"Bearer {user_data['access_token']}"}

        # Create board first
        board_resp = await client.post(
            "/api/v1/boards",
            headers=headers,
            json={
                "slug": "discussion",
                "name": "General Discussion",
                "description": "Any topic goes here.",
            },
        )
        assert board_resp.status_code == 201

        # 1. Save new_topic draft
        await client.put(
            "/api/v1/drafts",
            headers=headers,
            json={
                "target_type": "new_topic",
                "target_id": "",
                "draft_type": "topic",
                "data": {"title": "Discussion Title", "body": "Body"},
                "version": 1,
            },
        )

        # Confirm draft exists
        lookup_topic_draft = await client.get(
            "/api/v1/drafts/lookup?target_type=new_topic&target_id=",
            headers=headers,
        )
        assert lookup_topic_draft.json()["data"] is not None

        # 2. Create topic successfully
        topic_resp = await client.post(
            "/api/v1/boards/discussion/topics",
            headers=headers,
            json={
                "title": "Discussion Title",
                "raw_md": "This is body content",
                "tags": [],
            },
        )
        assert topic_resp.status_code == 201
        topic_id = topic_resp.json()["data"]["id"]

        # Confirm draft is deleted
        lookup_topic_draft_after = await client.get(
            "/api/v1/drafts/lookup?target_type=new_topic&target_id=",
            headers=headers,
        )
        assert lookup_topic_draft_after.json()["data"] is None

        # 3. Save reply draft
        await client.put(
            "/api/v1/drafts",
            headers=headers,
            json={
                "target_type": "topic",
                "target_id": topic_id,
                "draft_type": "reply",
                "data": {"body": "My reply draft"},
                "version": 1,
            },
        )

        # Confirm reply draft exists
        lookup_reply_draft = await client.get(
            f"/api/v1/drafts/lookup?target_type=topic&target_id={topic_id}",
            headers=headers,
        )
        assert lookup_reply_draft.json()["data"] is not None

        # 4. Create reply successfully
        reply_resp = await client.post(
            f"/api/v1/topics/{topic_id}/posts",
            headers=headers,
            json={"raw_md": "My reply content"},
        )
        assert reply_resp.status_code == 201

        # Confirm reply draft is deleted
        lookup_reply_draft_after = await client.get(
            f"/api/v1/drafts/lookup?target_type=topic&target_id={topic_id}",
            headers=headers,
        )
        assert lookup_reply_draft_after.json()["data"] is None

    await engine.dispose()


@pytest.mark.asyncio
async def test_draft_deletion_safety_review_and_block_policies() -> None:
    session_factory, engine = await create_test_session()

    async def override_session():
        async with session_factory() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_session] = override_session

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        user_data = await register_and_verify_user(client, "safety_draft_user")
        headers = {"Authorization": f"Bearer {user_data['access_token']}"}

        # Create board first
        await client.post(
            "/api/v1/boards",
            headers=headers,
            json={
                "slug": "sandbox",
                "name": "Sandbox",
                "description": "Sandbox for safety rules.",
            },
        )

        # CASE A: Blocked content policy -> draft must NOT be deleted.
        # Save draft
        await client.put(
            "/api/v1/drafts",
            headers=headers,
            json={
                "target_type": "new_topic",
                "target_id": "",
                "draft_type": "topic",
                "data": {"title": "blocked-demo-term title", "body": "Body"},
                "version": 1,
            },
        )
        # Create topic with blocked term
        blocked_resp = await client.post(
            "/api/v1/boards/sandbox/topics",
            headers=headers,
            json={
                "title": "blocked-demo-term topic",
                "raw_md": "This is blocked body",
            },
        )
        assert blocked_resp.status_code == 422
        assert blocked_resp.json()["error"]["details"]["action"] == "blocked"

        # Check draft STILL EXISTS
        lookup_blocked_draft = await client.get(
            "/api/v1/drafts/lookup?target_type=new_topic&target_id=",
            headers=headers,
        )
        assert lookup_blocked_draft.json()["data"] is not None

        # CASE B: Content pending review policy -> draft MUST be deleted.
        # Create topic with review-demo-term (review required)
        review_resp = await client.post(
            "/api/v1/boards/sandbox/topics",
            headers=headers,
            json={
                "title": "review-demo-term topic",
                "raw_md": "This requires moderator review",
            },
        )
        assert review_resp.status_code == 422
        assert review_resp.json()["error"]["details"]["action"] == "review"

        # Check draft IS DELETED
        lookup_review_draft = await client.get(
            "/api/v1/drafts/lookup?target_type=new_topic&target_id=",
            headers=headers,
        )
        assert lookup_review_draft.json()["data"] is None

    await engine.dispose()

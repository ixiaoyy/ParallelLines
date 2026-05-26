import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.v1.dependencies import get_session
from app.main import create_app
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
        "auth": f"Bearer {data['access_token']}",
    }


@pytest.mark.asyncio
async def test_private_board_visibility_and_invite_acceptance_flow() -> None:
    session_factory, engine = await create_test_session()

    async def override_session():
        async with session_factory() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_session] = override_session

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        owner = await register_user(client, "owner")
        invitee = await register_user(client, "invitee")
        stranger = await register_user(client, "stranger")
        owner_headers = {"Authorization": owner["auth"]}
        invitee_headers = {"Authorization": invitee["auth"]}
        stranger_headers = {"Authorization": stranger["auth"]}

        board = await client.post(
            "/api/v1/boards",
            headers=owner_headers,
            json={
                "slug": "private-lab",
                "name": "内部排障实验室",
                "description": "仅受邀成员可见的排障复盘空间。",
                "color": "#409EFF",
                "visibility": "private",
            },
        )
        assert board.status_code == 201
        board_data = board.json()["data"]
        assert board_data["visibility"] == "private"

        topic = await client.post(
            "/api/v1/boards/private-lab/topics",
            headers=owner_headers,
            json={
                "title": "私密主题不会出现在公开信息流",
                "raw_md": "这是一条只应该对成员可见的内部排障内容。",
                "tags": ["private-lab"],
            },
        )
        assert topic.status_code == 201
        topic_id = topic.json()["data"]["id"]

        public_boards = await client.get("/api/v1/boards")
        assert public_boards.status_code == 200
        assert "private-lab" not in {item["slug"] for item in public_boards.json()["data"]}

        stranger_boards = await client.get("/api/v1/boards", headers=stranger_headers)
        assert stranger_boards.status_code == 200
        assert "private-lab" not in {item["slug"] for item in stranger_boards.json()["data"]}

        owner_boards = await client.get("/api/v1/boards", headers=owner_headers)
        assert owner_boards.status_code == 200
        assert "private-lab" in {item["slug"] for item in owner_boards.json()["data"]}

        direct_stranger = await client.get("/api/v1/boards/private-lab", headers=stranger_headers)
        assert direct_stranger.status_code == 404
        topic_stranger = await client.get(f"/api/v1/topics/{topic_id}", headers=stranger_headers)
        assert topic_stranger.status_code == 404

        public_feed = await client.get("/api/v1/topics")
        assert topic_id not in {item["id"] for item in public_feed.json()["data"]}
        public_search = await client.get("/api/v1/search?q=内部排障")
        assert topic_id not in {item["id"] for item in public_search.json()["data"]}
        public_user_topics = await client.get("/api/v1/users/owner/topics")
        assert topic_id not in {item["id"] for item in public_user_topics.json()["data"]}

        invite = await client.post(
            "/api/v1/invites",
            headers=owner_headers,
            json={"board_id": board_data["id"], "username": "invitee"},
        )
        assert invite.status_code == 201
        invite_data = invite.json()["data"]
        assert invite_data["status"] == "pending"
        assert invite_data["board_slug"] == "private-lab"

        duplicate_invite = await client.post(
            "/api/v1/invites",
            headers=owner_headers,
            json={"board_id": board_data["id"], "username": "invitee"},
        )
        assert duplicate_invite.status_code == 201
        assert duplicate_invite.json()["data"]["id"] == invite_data["id"]

        invitee_invites = await client.get("/api/v1/invites", headers=invitee_headers)
        assert invitee_invites.status_code == 200
        assert [item["id"] for item in invitee_invites.json()["data"]["received"]] == [
            invite_data["id"]
        ]

        forbidden_revoke = await client.put(
            f"/api/v1/invites/{invite_data['id']}/revoke",
            headers=stranger_headers,
        )
        assert forbidden_revoke.status_code == 403

        accepted = await client.put(
            f"/api/v1/invites/{invite_data['id']}/accept",
            headers=invitee_headers,
        )
        assert accepted.status_code == 200
        assert accepted.json()["data"]["status"] == "accepted"

        accepted_again = await client.put(
            f"/api/v1/invites/{invite_data['id']}/accept",
            headers=invitee_headers,
        )
        assert accepted_again.status_code == 422
        assert accepted_again.json()["error"]["code"] == "board_invite_not_pending"

        invitee_board = await client.get("/api/v1/boards/private-lab", headers=invitee_headers)
        assert invitee_board.status_code == 200
        invitee_topic = await client.get(f"/api/v1/topics/{topic_id}", headers=invitee_headers)
        assert invitee_topic.status_code == 200
        invitee_search = await client.get(
            "/api/v1/search?q=内部排障",
            headers=invitee_headers,
        )
        assert topic_id in {item["id"] for item in invitee_search.json()["data"]}

    await engine.dispose()


@pytest.mark.asyncio
async def test_only_private_board_owner_can_manage_invites() -> None:
    session_factory, engine = await create_test_session()

    async def override_session():
        async with session_factory() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_session] = override_session

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        owner = await register_user(client, "owner2")
        member = await register_user(client, "member2")
        invitee = await register_user(client, "invitee2")
        owner_headers = {"Authorization": owner["auth"]}
        member_headers = {"Authorization": member["auth"]}
        invitee_headers = {"Authorization": invitee["auth"]}

        public_board = await client.post(
            "/api/v1/boards",
            headers=owner_headers,
            json={
                "slug": "public-support",
                "name": "公共支持",
                "description": "所有人可见的公开支持版块。",
                "color": "#10B981",
            },
        )
        assert public_board.status_code == 201
        public_invite = await client.post(
            "/api/v1/invites",
            headers=owner_headers,
            json={"board_id": public_board.json()["data"]["id"], "username": "invitee2"},
        )
        assert public_invite.status_code == 404

        private_board = await client.post(
            "/api/v1/boards",
            headers=owner_headers,
            json={
                "slug": "owner-only",
                "name": "Owner 私密版块",
                "description": "用于验证邀请权限边界。",
                "color": "#409EFF",
                "visibility": "private",
            },
        )
        assert private_board.status_code == 201
        board_id = private_board.json()["data"]["id"]

        non_owner_invite = await client.post(
            "/api/v1/invites",
            headers=member_headers,
            json={"board_id": board_id, "username": "invitee2"},
        )
        assert non_owner_invite.status_code == 403

        invite = await client.post(
            "/api/v1/invites",
            headers=owner_headers,
            json={"board_id": board_id, "username": "invitee2"},
        )
        assert invite.status_code == 201
        invite_id = invite.json()["data"]["id"]

        wrong_user_accept = await client.put(
            f"/api/v1/invites/{invite_id}/accept",
            headers=member_headers,
        )
        assert wrong_user_accept.status_code == 403

        declined = await client.put(f"/api/v1/invites/{invite_id}/decline", headers=invitee_headers)
        assert declined.status_code == 200
        assert declined.json()["data"]["status"] == "declined"

    await engine.dispose()

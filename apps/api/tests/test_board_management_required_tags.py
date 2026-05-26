import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.v1.dependencies import get_session
from app.main import create_app
from app.models.forum import Topic
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


async def create_board(
    client: AsyncClient,
    auth: str,
    slug: str,
    *,
    payload: dict[str, object] | None = None,
) -> dict[str, object]:
    response = await client.post(
        "/api/v1/boards",
        headers={"Authorization": auth},
        json={
            "slug": slug,
            "name": f"{slug} 版块",
            "description": "用于版块管理策略测试的公开版块。",
            "color": "#409EFF",
            **(payload or {}),
        },
    )
    assert response.status_code == 201
    return response.json()["data"]


@pytest.mark.asyncio
async def test_board_required_and_allowed_tags_gate_topic_creation() -> None:
    session_factory, engine = await create_test_session()

    async def override_session():
        async with session_factory() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_session] = override_session

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        owner = await register_user(client, "tag_owner")
        headers = {"Authorization": owner["auth"]}
        await create_board(
            client,
            owner["auth"],
            "tag-policy",
            payload={
                "required_tags": ["bug"],
                "allowed_tags": ["bug", "backend"],
                "post_template": "环境：\n复现步骤：\n实际结果：",
                "default_sort": "hot",
            },
        )

        missing_required = await client.post(
            "/api/v1/boards/tag-policy/topics",
            headers=headers,
            json={
                "title": "缺少必填标签的主题",
                "raw_md": "这条主题应该在写入前被版块策略拒绝。",
                "tags": ["backend"],
            },
        )
        assert missing_required.status_code == 422
        assert missing_required.json()["error"]["code"] == "required_tags_missing"
        assert missing_required.json()["error"]["details"]["missing_tags"] == ["bug"]

        disallowed_tag = await client.post(
            "/api/v1/boards/tag-policy/topics",
            headers=headers,
            json={
                "title": "包含不允许标签的主题",
                "raw_md": "这条主题包含未被该版块允许的标签。",
                "tags": ["bug", "frontend"],
            },
        )
        assert disallowed_tag.status_code == 422
        assert disallowed_tag.json()["error"]["code"] == "tag_not_allowed"
        assert disallowed_tag.json()["error"]["details"]["disallowed_tags"] == ["frontend"]

        created = await client.post(
            "/api/v1/boards/tag-policy/topics",
            headers=headers,
            json={
                "title": "带齐版块必填标签的主题",
                "raw_md": "这条主题符合版块策略，应该成功创建。",
                "tags": ["bug", "backend"],
            },
        )
        assert created.status_code == 201
        assert created.json()["data"]["tags"] == ["bug", "backend"]

    async with session_factory() as session:
        topic_count = await session.scalar(select(func.count(Topic.id)))
        assert topic_count == 1

    await engine.dispose()


@pytest.mark.asyncio
async def test_board_settings_permissions_and_child_board_visibility() -> None:
    session_factory, engine = await create_test_session()

    async def override_session():
        async with session_factory() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_session] = override_session

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        owner = await register_user(client, "hierarchy_owner")
        stranger = await register_user(client, "hierarchy_stranger")
        parent = await create_board(client, owner["auth"], "parent-board")
        child = await create_board(
            client,
            owner["auth"],
            "child-board",
            payload={"parent_board_slug": "parent-board", "default_notification_level": "tracking"},
        )
        assert child["parent_board_slug"] == "parent-board"

        forbidden = await client.put(
            "/api/v1/boards/child-board/settings",
            headers={"Authorization": stranger["auth"]},
            json={
                "required_tags": ["must"],
                "allowed_tags": ["must"],
                "default_notification_level": "normal",
                "default_sort": "latest",
            },
        )
        assert forbidden.status_code == 403
        assert forbidden.json()["error"]["code"] == "board_settings_forbidden"

        invalid_policy = await client.put(
            "/api/v1/boards/child-board/settings",
            headers={"Authorization": owner["auth"]},
            json={
                "parent_board_id": parent["id"],
                "required_tags": ["must"],
                "allowed_tags": ["other"],
                "default_notification_level": "normal",
                "default_sort": "latest",
            },
        )
        assert invalid_policy.status_code == 422
        assert invalid_policy.json()["error"]["code"] == "required_tags_not_allowed"

        parent_detail = await client.get("/api/v1/boards/parent-board")
        assert parent_detail.status_code == 200
        detail_data = parent_detail.json()["data"]
        assert [item["slug"] for item in detail_data["child_boards"]] == ["child-board"]

        board_list = await client.get("/api/v1/boards")
        assert board_list.status_code == 200
        child_from_list = next(
            item for item in board_list.json()["data"] if item["slug"] == "child-board"
        )
        assert child_from_list["parent_board_id"] == parent["id"]
        assert child_from_list["default_notification_level"] == "tracking"

    await engine.dispose()


@pytest.mark.asyncio
async def test_board_moderator_permission_is_scoped_to_one_board() -> None:
    session_factory, engine = await create_test_session()

    async def override_session():
        async with session_factory() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_session] = override_session

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        owner = await register_user(client, "scope_owner")
        moderator = await register_user(client, "scope_mod")
        owner_headers = {"Authorization": owner["auth"]}
        moderator_headers = {"Authorization": moderator["auth"]}
        await create_board(client, owner["auth"], "board-a")
        await create_board(client, owner["auth"], "board-b")

        promoted = await client.put(
            "/api/v1/boards/board-a/members/scope_mod",
            headers=owner_headers,
            json={"role": "moderator"},
        )
        assert promoted.status_code == 200
        assert promoted.json()["data"]["role"] == "moderator"

        topic_a = await client.post(
            "/api/v1/boards/board-a/topics",
            headers=owner_headers,
            json={"title": "A 版块里的主题", "raw_md": "只有 A 版主可以管理。"},
        )
        assert topic_a.status_code == 201
        topic_b = await client.post(
            "/api/v1/boards/board-b/topics",
            headers=owner_headers,
            json={"title": "B 版块里的主题", "raw_md": "A 版主不能管理这个主题。"},
        )
        assert topic_b.status_code == 201

        close_a = await client.put(
            f"/api/v1/topics/{topic_a.json()['data']['id']}/lifecycle",
            headers=moderator_headers,
            json={"status": "closed"},
        )
        assert close_a.status_code == 200
        assert close_a.json()["data"]["status"] == "closed"

        close_b = await client.put(
            f"/api/v1/topics/{topic_b.json()['data']['id']}/lifecycle",
            headers=moderator_headers,
            json={"status": "closed"},
        )
        assert close_b.status_code == 403
        assert close_b.json()["error"]["code"] == "moderation_forbidden"

    await engine.dispose()

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.v1.dependencies import get_session
from app.main import create_app
from app.models.moderation import AuditLog
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


async def create_board(client: AsyncClient, auth: str) -> None:
    response = await client.post(
        "/api/v1/boards",
        headers={"Authorization": auth},
        json={
            "slug": "support",
            "name": "支持与排障",
            "description": "安装、升级、报错定位，以及可复现问题的协作排查。",
            "color": "#10B981",
        },
    )
    assert response.status_code == 201


async def create_topic(client: AsyncClient, auth: str, raw_md: str) -> tuple[dict[str, str], str]:
    response = await client.post(
        "/api/v1/boards/support/topics",
        headers={"Authorization": auth},
        json={
            "title": "帖子版本历史能力测试",
            "raw_md": raw_md,
            "tags": ["revision"],
        },
    )
    assert response.status_code == 201
    topic = response.json()["data"]
    posts = await client.get(f"/api/v1/topics/{topic['id']}/posts")
    assert posts.status_code == 200
    return topic, posts.json()["data"][0]["id"]


@pytest.mark.asyncio
async def test_author_can_read_post_revision_history_and_stranger_cannot() -> None:
    session_factory, engine = await create_test_session()

    async def override_session():
        async with session_factory() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_session] = override_session

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        owner = await register_user(client, "owner")
        author = await register_user(client, "author")
        stranger = await register_user(client, "stranger")
        await create_board(client, owner["auth"])
        _, post_id = await create_topic(client, author["auth"], "原始首楼内容。")

        edit = await client.patch(
            f"/api/v1/posts/{post_id}",
            headers={"Authorization": author["auth"]},
            json={"raw_md": "作者更新后的内容。", "edit_reason": "补充排障结果"},
        )
        assert edit.status_code == 200

        revisions = await client.get(
            f"/api/v1/posts/{post_id}/revisions",
            headers={"Authorization": author["auth"]},
        )
        assert revisions.status_code == 200
        revision = revisions.json()["data"][0]
        assert revision["version_number"] == 1
        assert revision["raw_md"] == "原始首楼内容。"
        assert revision["edit_reason"] == "补充排障结果"
        assert revision["editor_name"] == "author"

        detail = await client.get(
            f"/api/v1/posts/{post_id}/revisions/{revision['id']}",
            headers={"Authorization": author["auth"]},
        )
        assert detail.status_code == 200
        assert detail.json()["data"]["cooked_html"] == "<p>原始首楼内容。</p>"

        forbidden = await client.get(
            f"/api/v1/posts/{post_id}/revisions",
            headers={"Authorization": stranger["auth"]},
        )
        assert forbidden.status_code == 403
        assert forbidden.json()["error"]["code"] == "permission_denied"

        async with session_factory() as session:
            actions = list(
                await session.scalars(
                    select(AuditLog.action).where(
                        AuditLog.target_type == "post",
                        AuditLog.target_id == post_id,
                    )
                )
            )
        assert "post_edited" in actions

    await engine.dispose()


@pytest.mark.asyncio
async def test_board_owner_can_restore_revision_and_search_uses_restored_body() -> None:
    session_factory, engine = await create_test_session()

    async def override_session():
        async with session_factory() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_session] = override_session

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        owner = await register_user(client, "owner")
        author = await register_user(client, "author")
        await create_board(client, owner["auth"])
        topic, post_id = await create_topic(client, author["auth"], "old-marker 原始内容。")

        edit = await client.patch(
            f"/api/v1/posts/{post_id}",
            headers={"Authorization": author["auth"]},
            json={"raw_md": "new-marker 更新内容。"},
        )
        assert edit.status_code == 200
        revisions = await client.get(
            f"/api/v1/posts/{post_id}/revisions",
            headers={"Authorization": owner["auth"]},
        )
        revision = revisions.json()["data"][0]

        author_restore = await client.post(
            f"/api/v1/posts/{post_id}/revisions/{revision['id']}/restore",
            headers={"Authorization": author["auth"]},
            json={"reason": "作者不能恢复"},
        )
        assert author_restore.status_code == 403
        assert author_restore.json()["error"]["code"] == "moderation_forbidden"

        restored = await client.post(
            f"/api/v1/posts/{post_id}/revisions/{revision['id']}/restore",
            headers={"Authorization": owner["auth"]},
            json={"reason": "恢复旧版"},
        )
        assert restored.status_code == 200
        assert restored.json()["data"]["raw_md"] == "old-marker 原始内容。"

        old_search = await client.get("/api/v1/search?q=old-marker")
        assert old_search.status_code == 200
        assert {item["id"] for item in old_search.json()["data"]} == {topic["id"]}

        new_search = await client.get("/api/v1/search?q=new-marker")
        assert new_search.status_code == 200
        assert [item["id"] for item in new_search.json()["data"]] == []

        revisions_after_restore = await client.get(
            f"/api/v1/posts/{post_id}/revisions",
            headers={"Authorization": owner["auth"]},
        )
        latest_revision = revisions_after_restore.json()["data"][0]
        assert latest_revision["version_number"] == 2
        assert latest_revision["raw_md"] == "new-marker 更新内容。"
        assert latest_revision["restored_from_revision_id"] == revision["id"]

        async with session_factory() as session:
            actions = list(
                await session.scalars(
                    select(AuditLog.action).where(
                        AuditLog.target_type == "post",
                        AuditLog.target_id == post_id,
                    )
                )
            )
        assert "post_revision_restored" in actions

    await engine.dispose()


@pytest.mark.asyncio
async def test_hidden_post_revision_history_is_limited_to_moderators() -> None:
    session_factory, engine = await create_test_session()

    async def override_session():
        async with session_factory() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_session] = override_session

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        owner = await register_user(client, "owner")
        author = await register_user(client, "author")
        await create_board(client, owner["auth"])
        topic, post_id = await create_topic(client, author["auth"], "隐藏前内容。")

        edit = await client.patch(
            f"/api/v1/posts/{post_id}",
            headers={"Authorization": author["auth"]},
            json={"raw_md": "隐藏前更新内容。"},
        )
        assert edit.status_code == 200

        hide = await client.put(
            f"/api/v1/moderation/topics/{topic['id']}/hide",
            headers={"Authorization": owner["auth"]},
            json={"note": "测试历史隐私边界"},
        )
        assert hide.status_code == 200

        author_history = await client.get(
            f"/api/v1/posts/{post_id}/revisions",
            headers={"Authorization": author["auth"]},
        )
        assert author_history.status_code == 404
        assert author_history.json()["error"]["code"] == "post_not_found"

        owner_history = await client.get(
            f"/api/v1/posts/{post_id}/revisions",
            headers={"Authorization": owner["auth"]},
        )
        assert owner_history.status_code == 200
        assert owner_history.json()["data"][0]["raw_md"] == "隐藏前内容。"

    await engine.dispose()

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.v1.dependencies import get_session
from app.db.base import Base
from app.main import create_app
from app.models.forum import Board, BoardMember
from tests.helpers import register_and_verify_user


async def create_test_session() -> tuple[async_sessionmaker[AsyncSession], object]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
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


async def create_topic(client: AsyncClient, auth: str, title: str, raw_md: str) -> dict[str, str]:
    response = await client.post(
        "/api/v1/boards/support/topics",
        headers={"Authorization": auth},
        json={"title": title, "raw_md": raw_md, "tags": ["api"]},
    )
    assert response.status_code == 201
    return response.json()["data"]


@pytest.mark.asyncio
async def test_public_user_profile_does_not_leak_email_and_filters_hidden_topics() -> None:
    session_factory, engine = await create_test_session()

    async def override_session():
        async with session_factory() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_session] = override_session

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        author = await register_user(client, "author")
        await create_board(client, author["auth"])
        visible = await create_topic(client, author["auth"], "可见主题用于资料页展示", "公开内容。")
        hidden = await create_topic(client, author["auth"], "隐藏主题不应返回", "隐藏内容。")

        hide = await client.put(
            f"/api/v1/moderation/topics/{hidden['id']}/hide",
            headers={"Authorization": author["auth"]},
            json={"note": "测试过滤隐藏主题。"},
        )
        assert hide.status_code == 200

        profile = await client.get("/api/v1/users/author")
        assert profile.status_code == 200
        profile_data = profile.json()["data"]
        assert profile_data["username"] == "author"
        assert profile_data["level"] == 0
        assert profile_data["topic_count"] == 1
        assert profile_data["post_count"] == 1
        assert "email" not in profile_data

        topics = await client.get("/api/v1/users/author/topics?limit=10")
        assert topics.status_code == 200
        topic_ids = {item["id"] for item in topics.json()["data"]}
        assert topic_ids == {visible["id"]}

        tags = await client.get("/api/v1/tags?limit=5")
        assert tags.status_code == 200
        tag_data = tags.json()["data"]
        assert tag_data[0]["name"] == "api"
        assert tag_data[0]["topic_count"] >= 1

        missing = await client.get("/api/v1/users/missing-user")
        assert missing.status_code == 404
        assert missing.json()["error"]["code"] == "user_not_found"

    await engine.dispose()


@pytest.mark.asyncio
async def test_post_edit_author_other_user_owner_and_board_moderator_permissions() -> None:
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
        moderator = await register_user(client, "boardmod")
        await create_board(client, owner["auth"])

        async with session_factory() as session:
            board = await session.scalar(select(Board).where(Board.slug == "support"))
            assert board is not None
            session.add(
                BoardMember(
                    board_id=board.id,
                    user_id=moderator["id"],
                    role="moderator",
                    notification_level="normal",
                )
            )
            await session.commit()

        topic = await create_topic(client, author["auth"], "帖子编辑权限边界测试", "原始首楼内容。")
        posts = await client.get(f"/api/v1/topics/{topic['id']}/posts")
        assert posts.status_code == 200
        first_post_id = posts.json()["data"][0]["id"]

        author_edit = await client.patch(
            f"/api/v1/posts/{first_post_id}",
            headers={"Authorization": author["auth"]},
            json={"raw_md": "作者更新后的内容。"},
        )
        assert author_edit.status_code == 200
        assert author_edit.json()["data"]["raw_md"] == "作者更新后的内容。"
        assert "<p>作者更新后的内容。</p>" == author_edit.json()["data"]["cooked_html"]

        forbidden = await client.patch(
            f"/api/v1/posts/{first_post_id}",
            headers={"Authorization": stranger["auth"]},
            json={"raw_md": "陌生人不能改。"},
        )
        assert forbidden.status_code == 403
        assert forbidden.json()["error"]["code"] == "permission_denied"

        owner_edit = await client.patch(
            f"/api/v1/posts/{first_post_id}",
            headers={"Authorization": owner["auth"]},
            json={"raw_md": "版主 Owner 更新内容。"},
        )
        assert owner_edit.status_code == 200
        assert owner_edit.json()["data"]["raw_md"] == "版主 Owner 更新内容。"

        moderator_edit = await client.patch(
            f"/api/v1/posts/{first_post_id}",
            headers={"Authorization": moderator["auth"]},
            json={"raw_md": "Board moderator 更新内容。"},
        )
        assert moderator_edit.status_code == 200
        assert moderator_edit.json()["data"]["raw_md"] == "Board moderator 更新内容。"

        empty = await client.patch(
            f"/api/v1/posts/{first_post_id}",
            headers={"Authorization": author["auth"]},
            json={"raw_md": "   "},
        )
        assert empty.status_code == 422
        assert empty.json()["error"]["code"] == "empty_post"

    await engine.dispose()


@pytest.mark.asyncio
async def test_reply_cannot_be_edited_but_author_can_delete_it() -> None:
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
        topic = await create_topic(client, author["auth"], "回复删除规则测试", "首楼可以继续编辑。")

        reply = await client.post(
            f"/api/v1/topics/{topic['id']}/posts",
            headers={"Authorization": author["auth"]},
            json={"raw_md": "这是一条只能删除、不能编辑的回复。"},
        )
        assert reply.status_code == 201
        reply_id = reply.json()["data"]["id"]

        edit_reply = await client.patch(
            f"/api/v1/posts/{reply_id}",
            headers={"Authorization": author["auth"]},
            json={"raw_md": "尝试编辑回复。"},
        )
        assert edit_reply.status_code == 422
        assert edit_reply.json()["error"]["code"] == "reply_edit_not_allowed"

        stranger_delete = await client.delete(
            f"/api/v1/posts/{reply_id}",
            headers={"Authorization": stranger["auth"]},
        )
        assert stranger_delete.status_code == 403
        assert stranger_delete.json()["error"]["code"] == "permission_denied"

        author_delete = await client.delete(
            f"/api/v1/posts/{reply_id}",
            headers={"Authorization": author["auth"]},
        )
        assert author_delete.status_code == 200
        deleted_reply = author_delete.json()["data"]
        assert deleted_reply["deleted_at"] is not None
        assert deleted_reply["raw_md"] == ""
        assert deleted_reply["cooked_html"] == ""

        posts = await client.get(f"/api/v1/topics/{topic['id']}/posts")
        assert posts.status_code == 200
        saved_reply = next(item for item in posts.json()["data"] if item["id"] == reply_id)
        assert saved_reply["deleted_at"] is not None
        assert saved_reply["raw_md"] == ""

    await engine.dispose()

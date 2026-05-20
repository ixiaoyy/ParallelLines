import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.v1.dependencies import get_session
from app.db.base import Base
from app.main import create_app
from app.services.content_safety import BLOCK_POLICY_TEST_TOKEN, MASK_POLICY_TEST_TOKEN
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


async def create_topic(client: AsyncClient, auth: str) -> dict[str, str]:
    response = await client.post(
        "/api/v1/boards/support/topics",
        headers={"Authorization": auth},
        json={
            "title": "FastAPI 内容安全规则回归测试",
            "raw_md": "这是一条不触发规则的首楼内容，用于后续回复和编辑。",
            "tags": ["safety"],
        },
    )
    assert response.status_code == 201
    return response.json()["data"]


@pytest.mark.asyncio
async def test_content_safety_blocks_normalized_topic_reply_and_edit() -> None:
    session_factory, engine = await create_test_session()

    async def override_session():
        async with session_factory() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_session] = override_session

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        author = await register_user(client, "safety_author")
        headers = {"Authorization": author["auth"]}
        await create_board(client, author["auth"])

        blocked_topic = await client.post(
            "/api/v1/boards/support/topics",
            headers=headers,
            json={
                "title": "FastAPI ＢＬＯＣＫＥＤ -- demo -- term 发布校验",
                "raw_md": "正文不含规则，只用于确认标题命中会被阻止。",
                "tags": ["safety"],
            },
        )
        assert blocked_topic.status_code == 422
        topic_error = blocked_topic.json()["error"]
        assert topic_error["code"] == "content_policy_violation"
        assert topic_error["details"] == {"action": "blocked", "fields": ["title"]}
        assert BLOCK_POLICY_TEST_TOKEN not in blocked_topic.text

        topic = await create_topic(client, author["auth"])
        blocked_reply = await client.post(
            f"/api/v1/topics/{topic['id']}/posts",
            headers=headers,
            json={"raw_md": "这里用 BＬＯＣＫＥＤ  demo  term 验证全半角与空白绕过。"},
        )
        assert blocked_reply.status_code == 422
        reply_error = blocked_reply.json()["error"]
        assert reply_error["code"] == "content_policy_violation"
        assert reply_error["details"] == {"action": "blocked", "fields": ["raw_md"]}
        assert BLOCK_POLICY_TEST_TOKEN not in blocked_reply.text

        posts = await client.get(f"/api/v1/topics/{topic['id']}/posts")
        assert posts.status_code == 200
        first_post_id = posts.json()["data"][0]["id"]
        blocked_edit = await client.patch(
            f"/api/v1/posts/{first_post_id}",
            headers=headers,
            json={"raw_md": "编辑时插入 blocked demo term 也必须被阻止。"},
        )
        assert blocked_edit.status_code == 422
        edit_error = blocked_edit.json()["error"]
        assert edit_error["code"] == "content_policy_violation"
        assert edit_error["details"] == {"action": "blocked", "fields": ["raw_md"]}
        assert BLOCK_POLICY_TEST_TOKEN not in blocked_edit.text

    await engine.dispose()


@pytest.mark.asyncio
async def test_content_safety_masks_configured_terms_before_storage() -> None:
    session_factory, engine = await create_test_session()

    async def override_session():
        async with session_factory() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_session] = override_session

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        author = await register_user(client, "safety_masker")
        headers = {"Authorization": author["auth"]}
        await create_board(client, author["auth"])

        topic = await client.post(
            "/api/v1/boards/support/topics",
            headers=headers,
            json={
                "title": "内容替换规则首楼存储测试",
                "raw_md": f"请确认 {MASK_POLICY_TEST_TOKEN} 会被替换后再渲染。",
                "tags": ["safety"],
            },
        )
        assert topic.status_code == 201
        topic_id = topic.json()["data"]["id"]

        posts = await client.get(f"/api/v1/topics/{topic_id}/posts")
        assert posts.status_code == 200
        first_post = posts.json()["data"][0]
        assert MASK_POLICY_TEST_TOKEN not in first_post["raw_md"]
        assert MASK_POLICY_TEST_TOKEN not in first_post["cooked_html"]
        assert "请确认 *** 会被替换后再渲染。" == first_post["raw_md"]
        assert "<p>请确认 *** 会被替换后再渲染。</p>" == first_post["cooked_html"]

    await engine.dispose()

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.v1.dependencies import get_session
from app.db.base import Base
from app.main import create_app
from app.models.moderation import AuditLog, Flag
from app.models.user import User
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
        "token": data["access_token"],
        "auth": f"Bearer {data['access_token']}",
    }


async def create_topic_fixture(client: AsyncClient, auth: str) -> dict[str, str]:
    board = await client.post(
        "/api/v1/boards",
        headers={"Authorization": auth},
        json={
            "slug": "support",
            "name": "支持与排障",
            "description": "安装、升级、报错定位，以及可复现问题的协作排查。",
            "color": "#10B981",
        },
    )
    assert board.status_code == 201

    topic = await client.post(
        "/api/v1/boards/support/topics",
        headers={"Authorization": auth},
        json={
            "title": "FastAPI 长任务通知如何设计？",
            "raw_md": "首楼内容用于测试审核隐藏与恢复。",
            "tags": ["fastapi", "moderation"],
        },
    )
    assert topic.status_code == 201
    topic_data = topic.json()["data"]

    reply = await client.post(
        f"/api/v1/topics/{topic_data['id']}/posts",
        headers={"Authorization": auth},
        json={"raw_md": "这条回复包含需要审核的具体内容。"},
    )
    assert reply.status_code == 201

    return {"topic_id": topic_data["id"], "post_id": reply.json()["data"]["id"]}


@pytest.mark.asyncio
async def test_report_queue_hide_post_and_audit_permissions() -> None:
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

        flag = await client.post(
            "/api/v1/moderation/flags",
            headers=reporter_headers,
            json={
                "target_type": "post",
                "target_id": fixture["post_id"],
                "reason": "spam",
                "detail": "重复刷屏内容。",
            },
        )
        assert flag.status_code == 201
        flag_data = flag.json()["data"]
        assert flag_data["status"] == "pending"
        assert flag_data["target"]["board_slug"] == "support"

        duplicate_flag = await client.post(
            "/api/v1/moderation/flags",
            headers=reporter_headers,
            json={
                "target_type": "post",
                "target_id": fixture["post_id"],
                "reason": "spam",
                "detail": "再次举报应合并到同一待处理记录。",
            },
        )
        assert duplicate_flag.status_code == 201
        assert duplicate_flag.json()["data"]["id"] == flag_data["id"]

        forbidden_queue = await client.get("/api/v1/moderation/queue", headers=reporter_headers)
        assert forbidden_queue.status_code == 403

        queue = await client.get("/api/v1/moderation/queue", headers=owner_headers)
        assert queue.status_code == 200
        assert [item["id"] for item in queue.json()["data"]] == [flag_data["id"]]

        hide = await client.put(
            f"/api/v1/moderation/posts/{fixture['post_id']}/hide",
            headers=owner_headers,
            json={"note": "隐藏刷屏回复。"},
        )
        assert hide.status_code == 200
        assert hide.json()["data"]["hidden"] is True

        posts = await client.get(f"/api/v1/topics/{fixture['topic_id']}/posts")
        assert posts.status_code == 200
        hidden_post = next(
            item for item in posts.json()["data"] if item["id"] == fixture["post_id"]
        )
        assert hidden_post["deleted_at"] is not None
        assert hidden_post["raw_md"] == ""
        assert hidden_post["cooked_html"] == ""

        hidden_search = await client.get("/api/v1/search?q=具体内容")
        assert hidden_search.status_code == 200
        assert fixture["topic_id"] not in {item["id"] for item in hidden_search.json()["data"]}

        resolved = await client.put(
            f"/api/v1/moderation/flags/{flag_data['id']}/status",
            headers=owner_headers,
            json={"status": "resolved", "resolution_note": "已隐藏。"},
        )
        assert resolved.status_code == 200
        assert resolved.json()["data"]["status"] == "resolved"

        audit_logs = await client.get("/api/v1/moderation/audit-logs", headers=owner_headers)
        assert audit_logs.status_code == 200
        actions = {item["action"] for item in audit_logs.json()["data"]}
        assert {"flag_created", "post_hidden", "flag_status_changed"}.issubset(actions)

    async with session_factory() as session:
        flag_count = await session.scalar(select(func.count(Flag.id)))
        audit_count = await session.scalar(select(func.count(AuditLog.id)))
        assert flag_count == 1
        assert audit_count >= 3

    await engine.dispose()


@pytest.mark.asyncio
async def test_hide_restore_topic_and_user_status_boundaries() -> None:
    session_factory, engine = await create_test_session()

    async def override_session():
        async with session_factory() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_session] = override_session

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        owner = await register_user(client, "owner")
        member = await register_user(client, "member")
        admin = await register_user(client, "admin")
        fixture = await create_topic_fixture(client, owner["auth"])
        owner_headers = {"Authorization": owner["auth"]}
        member_headers = {"Authorization": member["auth"]}
        admin_headers = {"Authorization": admin["auth"]}

        forbidden_hide = await client.put(
            f"/api/v1/moderation/topics/{fixture['topic_id']}/hide",
            headers=member_headers,
            json={"note": "普通用户不能隐藏。"},
        )
        assert forbidden_hide.status_code == 403

        hide = await client.put(
            f"/api/v1/moderation/topics/{fixture['topic_id']}/hide",
            headers=owner_headers,
            json={"note": "主题违规。"},
        )
        assert hide.status_code == 200
        assert hide.json()["data"] == {
            "target_type": "topic",
            "target_id": fixture["topic_id"],
            "hidden": True,
            "status": "hidden",
        }

        topic_after_hide = await client.get(f"/api/v1/topics/{fixture['topic_id']}")
        assert topic_after_hide.status_code == 404
        visible_topics = await client.get("/api/v1/topics")
        assert fixture["topic_id"] not in {item["id"] for item in visible_topics.json()["data"]}

        restore = await client.put(
            f"/api/v1/moderation/topics/{fixture['topic_id']}/restore",
            headers=owner_headers,
            json={"note": "确认误报。"},
        )
        assert restore.status_code == 200
        assert restore.json()["data"]["hidden"] is False
        topic_after_restore = await client.get(f"/api/v1/topics/{fixture['topic_id']}")
        assert topic_after_restore.status_code == 200

        non_admin_status = await client.put(
            f"/api/v1/moderation/users/{member['id']}/status",
            headers=owner_headers,
            json={"status": "silenced", "note": "版主不能禁言用户。"},
        )
        assert non_admin_status.status_code == 403

    async with session_factory() as session:
        admin_user = await session.get(User, admin["id"])
        assert admin_user is not None
        admin_user.role = "admin"
        await session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        admin_status = await client.put(
            f"/api/v1/moderation/users/{member['id']}/status",
            headers=admin_headers,
            json={"status": "silenced", "note": "重复灌水。"},
        )
        assert admin_status.status_code == 200
        assert admin_status.json()["data"] == {
            "user_id": member["id"],
            "username": "member",
            "status": "silenced",
        }

    await engine.dispose()

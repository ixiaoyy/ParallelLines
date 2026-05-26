import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.v1.dependencies import get_session
from app.main import create_app
from app.models.forum import Board, Topic
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


async def create_board(
    client: AsyncClient,
    auth: str,
    slug: str,
    name: str,
    *,
    visibility: str = "public",
) -> dict[str, str]:
    payload = {
        "slug": slug,
        "name": name,
        "description": f"{name} 的公开讨论版块。",
        "color": "#10B981",
    }
    if visibility != "public":
        payload["visibility"] = visibility
    response = await client.post(
        "/api/v1/boards",
        headers={"Authorization": auth},
        json=payload,
    )
    assert response.status_code == 201
    return response.json()["data"]


async def create_topic(
    client: AsyncClient,
    auth: str,
    board_slug: str,
    title: str,
    raw_md: str,
) -> dict[str, str]:
    response = await client.post(
        f"/api/v1/boards/{board_slug}/topics",
        headers={"Authorization": auth},
        json={"title": title, "raw_md": raw_md, "tags": ["life"]},
    )
    assert response.status_code == 201
    return response.json()["data"]


async def reply(
    client: AsyncClient,
    auth: str,
    topic_id: str,
    raw_md: str,
) -> dict[str, str]:
    response = await client.post(
        f"/api/v1/topics/{topic_id}/posts",
        headers={"Authorization": auth},
        json={"raw_md": raw_md},
    )
    assert response.status_code == 201
    return response.json()["data"]


@pytest.mark.asyncio
async def test_close_open_archive_and_pin_require_moderator_and_block_replies() -> None:
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
        await create_board(client, owner["auth"], "support", "支持与排障")
        topic = await create_topic(client, author["auth"], "support", "生命周期关闭测试", "首楼。")

        forbidden = await client.put(
            f"/api/v1/topics/{topic['id']}/lifecycle",
            headers={"Authorization": stranger["auth"]},
            json={"status": "closed"},
        )
        assert forbidden.status_code == 403
        assert forbidden.json()["error"]["code"] == "moderation_forbidden"

        closed = await client.put(
            f"/api/v1/topics/{topic['id']}/lifecycle",
            headers={"Authorization": owner["auth"]},
            json={"status": "closed", "pinned": True, "note": "已解决，暂时关闭"},
        )
        assert closed.status_code == 200
        assert closed.json()["data"]["status"] == "closed"
        assert closed.json()["data"]["pinned"] is True

        blocked_reply = await client.post(
            f"/api/v1/topics/{topic['id']}/posts",
            headers={"Authorization": author["auth"]},
            json={"raw_md": "关闭后不能回复。"},
        )
        assert blocked_reply.status_code == 422
        assert blocked_reply.json()["error"]["code"] == "topic_closed"

        archived = await client.put(
            f"/api/v1/topics/{topic['id']}/lifecycle",
            headers={"Authorization": owner["auth"]},
            json={"status": "archived"},
        )
        assert archived.status_code == 200
        assert archived.json()["data"]["status"] == "archived"

        reopened = await client.put(
            f"/api/v1/topics/{topic['id']}/lifecycle",
            headers={"Authorization": owner["auth"]},
            json={"status": "open", "pinned": False},
        )
        assert reopened.status_code == 200
        assert reopened.json()["data"]["status"] == "open"
        assert reopened.json()["data"]["pinned"] is False

        ok_reply = await client.post(
            f"/api/v1/topics/{topic['id']}/posts",
            headers={"Authorization": author["auth"]},
            json={"raw_md": "重新打开后可以回复。"},
        )
        assert ok_reply.status_code == 201

        async with session_factory() as session:
            actions = list(
                await session.scalars(
                    select(AuditLog.action).where(
                        AuditLog.target_type == "topic",
                        AuditLog.target_id == topic["id"],
                    )
                )
            )
        assert "topic_status_changed" in actions
        assert "topic_pinned_changed" in actions

    await engine.dispose()


@pytest.mark.asyncio
async def test_move_topic_updates_board_counts_and_old_id_resolves_new_board() -> None:
    session_factory, engine = await create_test_session()

    async def override_session():
        async with session_factory() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_session] = override_session

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        owner = await register_user(client, "owner")
        author = await register_user(client, "author")
        source_board = await create_board(client, owner["auth"], "support", "支持与排障")
        target_board = await create_board(client, owner["auth"], "general", "综合讨论")
        topic = await create_topic(client, author["auth"], "support", "移动主题测试", "首楼。")
        await reply(client, author["auth"], topic["id"], "回复一。")

        moved = await client.post(
            f"/api/v1/topics/{topic['id']}/move",
            headers={"Authorization": owner["auth"]},
            json={"board_slug": "general", "note": "移动到综合讨论"},
        )
        assert moved.status_code == 200
        moved_topic = moved.json()["data"]
        assert moved_topic["id"] == topic["id"]
        assert moved_topic["board_slug"] == "general"

        old_id_read = await client.get(f"/api/v1/topics/{topic['id']}")
        assert old_id_read.status_code == 200
        assert old_id_read.json()["data"]["board_slug"] == "general"

        async with session_factory() as session:
            source = await session.get(Board, source_board["id"])
            target = await session.get(Board, target_board["id"])
            assert source is not None
            assert target is not None
            assert source.topic_count == 0
            assert source.post_count == 0
            assert target.topic_count == 1
            assert target.post_count == 2

    await engine.dispose()


@pytest.mark.asyncio
async def test_split_topic_moves_replies_and_renumbers_both_topics() -> None:
    session_factory, engine = await create_test_session()

    async def override_session():
        async with session_factory() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_session] = override_session

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        owner = await register_user(client, "owner")
        author = await register_user(client, "author")
        await create_board(client, owner["auth"], "support", "支持与排障")
        topic = await create_topic(client, author["auth"], "support", "拆分主题测试", "首楼。")
        first_reply = await reply(client, author["auth"], topic["id"], "保留在原主题。")
        second_reply = await reply(client, author["auth"], topic["id"], "拆分回复一。")
        third_reply = await reply(client, author["auth"], topic["id"], "拆分回复二。")

        split = await client.post(
            f"/api/v1/topics/{topic['id']}/split",
            headers={"Authorization": owner["auth"]},
            json={
                "title": "拆分出来的新主题",
                "post_ids": [second_reply["id"], third_reply["id"]],
                "note": "提取为独立讨论",
            },
        )
        assert split.status_code == 200
        split_data = split.json()["data"]
        new_topic = split_data["target_topic"]
        assert split_data["moved_post_count"] == 2
        assert split_data["source_topic"]["reply_count"] == 1
        assert new_topic["reply_count"] == 1

        source_posts = await client.get(f"/api/v1/topics/{topic['id']}/posts")
        target_posts = await client.get(f"/api/v1/topics/{new_topic['id']}/posts")
        assert [item["id"] for item in source_posts.json()["data"]] == [
            source_posts.json()["data"][0]["id"],
            first_reply["id"],
        ]
        assert [item["post_number"] for item in source_posts.json()["data"]] == [1, 2]
        assert [item["id"] for item in target_posts.json()["data"]] == [
            second_reply["id"],
            third_reply["id"],
        ]
        assert [item["post_number"] for item in target_posts.json()["data"]] == [1, 2]

        async with session_factory() as session:
            board = await session.scalar(select(Board).where(Board.slug == "support"))
            assert board is not None
            assert board.topic_count == 2
            assert board.post_count == 4

    await engine.dispose()


@pytest.mark.asyncio
async def test_merge_topic_moves_posts_and_old_topic_returns_explicit_status() -> None:
    session_factory, engine = await create_test_session()

    async def override_session():
        async with session_factory() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_session] = override_session

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        owner = await register_user(client, "owner")
        author = await register_user(client, "author")
        await create_board(client, owner["auth"], "support", "支持与排障")
        source = await create_topic(client, author["auth"], "support", "源主题合并测试", "源首楼。")
        await reply(client, author["auth"], source["id"], "源回复。")
        target = await create_topic(
            client,
            author["auth"],
            "support",
            "目标主题合并测试",
            "目标首楼。",
        )
        await reply(client, author["auth"], target["id"], "目标回复。")

        merged = await client.post(
            f"/api/v1/topics/{source['id']}/merge",
            headers={"Authorization": owner["auth"]},
            json={"target_topic_id": target["id"], "note": "合并重复讨论"},
        )
        assert merged.status_code == 200
        assert merged.json()["data"]["target_topic"]["id"] == target["id"]
        assert merged.json()["data"]["moved_post_count"] == 2

        source_read = await client.get(f"/api/v1/topics/{source['id']}")
        assert source_read.status_code == 409
        assert source_read.json()["error"]["code"] == "topic_merged"
        assert source_read.json()["error"]["details"]["target_topic_id"] == target["id"]

        target_posts = await client.get(f"/api/v1/topics/{target['id']}/posts")
        assert target_posts.status_code == 200
        target_post_data = target_posts.json()["data"]
        assert [post["post_number"] for post in target_post_data] == [1, 2, 3, 4]
        assert target_post_data[2]["raw_md"] == "源首楼。"
        assert target_post_data[3]["raw_md"] == "源回复。"

        async with session_factory() as session:
            source_topic = await session.get(Topic, source["id"])
            board = await session.scalar(select(Board).where(Board.slug == "support"))
            actions = list(
                await session.scalars(
                    select(AuditLog.action).where(
                        AuditLog.target_type == "topic",
                        AuditLog.target_id == source["id"],
                    )
                )
            )
            assert source_topic is not None
            assert source_topic.merged_into_topic_id == target["id"]
            assert board is not None
            assert board.topic_count == 1
            assert board.post_count == 4
            assert "topic_merged" in actions

    await engine.dispose()


@pytest.mark.asyncio
async def test_merged_source_only_redirects_when_target_topic_is_visible() -> None:
    session_factory, engine = await create_test_session()

    async def override_session():
        async with session_factory() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_session] = override_session

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        owner = await register_user(client, "owner-private-merge")
        author = await register_user(client, "author-private-merge")
        stranger = await register_user(client, "stranger-private-merge")
        await create_board(client, owner["auth"], "public-merge", "公开合并")
        await create_board(
            client,
            owner["auth"],
            "private-merge",
            "私密合并",
            visibility="private",
        )
        source = await create_topic(
            client,
            author["auth"],
            "public-merge",
            "公开源主题",
            "源主题内容。",
        )
        target = await create_topic(
            client,
            owner["auth"],
            "private-merge",
            "私密目标主题",
            "目标主题内容。",
        )

        merged = await client.post(
            f"/api/v1/topics/{source['id']}/merge",
            headers={"Authorization": owner["auth"]},
            json={"target_topic_id": target["id"], "note": "合并到私密目标"},
        )
        assert merged.status_code == 200

        stranger_read = await client.get(
            f"/api/v1/topics/{source['id']}",
            headers={"Authorization": stranger["auth"]},
        )
        assert stranger_read.status_code == 404
        assert stranger_read.json()["error"]["code"] == "topic_not_found"

        owner_read = await client.get(
            f"/api/v1/topics/{source['id']}",
            headers={"Authorization": owner["auth"]},
        )
        assert owner_read.status_code == 409
        assert owner_read.json()["error"]["code"] == "topic_merged"
        assert owner_read.json()["error"]["details"]["target_topic_id"] == target["id"]

    await engine.dispose()

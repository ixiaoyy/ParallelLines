from datetime import UTC, datetime, timedelta

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.v1.dependencies import get_session
from app.main import create_app
from app.models.forum import Poll, PollOption, PollVote, Post, Topic
from app.models.interaction import Vote
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


async def create_topic_with_reply(client: AsyncClient, owner_auth: str, replier_auth: str):
    board = await client.post(
        "/api/v1/boards",
        headers={"Authorization": owner_auth},
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
        headers={"Authorization": owner_auth},
        json={
            "title": "如何排查后台任务卡住？",
            "raw_md": "描述一个可以复现的后台任务问题。",
            "tags": ["worker"],
        },
    )
    assert topic.status_code == 201
    topic_data = topic.json()["data"]

    reply = await client.post(
        f"/api/v1/topics/{topic_data['id']}/posts",
        headers={"Authorization": replier_auth},
        json={"raw_md": "可以先检查 dead letter 队列和重试日志。"},
    )
    assert reply.status_code == 201
    return topic_data, reply.json()["data"]


@pytest.mark.asyncio
async def test_solution_permission_and_qa_ordering() -> None:
    session_factory, engine = await create_test_session()

    async def override_session():
        async with session_factory() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_session] = override_session

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        owner = await register_user(client, "owner")
        member = await register_user(client, "member")
        topic, reply = await create_topic_with_reply(client, owner["auth"], member["auth"])

        forbidden = await client.put(
            f"/api/v1/topics/{topic['id']}/solution",
            headers={"Authorization": member["auth"]},
            json={"post_id": reply["id"]},
        )
        assert forbidden.status_code == 403
        assert forbidden.json()["error"]["code"] == "solution_forbidden"

        first_post = (await client.get(f"/api/v1/topics/{topic['id']}/posts")).json()["data"][0]
        invalid = await client.put(
            f"/api/v1/topics/{topic['id']}/solution",
            headers={"Authorization": owner["auth"]},
            json={"post_id": first_post["id"]},
        )
        assert invalid.status_code == 422
        assert invalid.json()["error"]["code"] == "solution_must_be_reply"

        accepted = await client.put(
            f"/api/v1/topics/{topic['id']}/solution",
            headers={"Authorization": owner["auth"]},
            json={"post_id": reply["id"]},
        )
        assert accepted.status_code == 200
        accepted_data = accepted.json()["data"]
        assert accepted_data["accepted_answer_post_id"] == reply["id"]
        assert accepted_data["solved_at"] is not None

        posts = await client.get(f"/api/v1/topics/{topic['id']}/posts?sort=qa")
        assert posts.status_code == 200
        post_data = posts.json()["data"]
        assert [item["post_number"] for item in post_data] == [1, 2]
        assert post_data[1]["accepted_answer"] is True

        cleared = await client.put(
            f"/api/v1/topics/{topic['id']}/solution",
            headers={"Authorization": owner["auth"]},
            json={"post_id": None},
        )
        assert cleared.status_code == 200
        assert cleared.json()["data"]["accepted_answer_post_id"] is None

    await engine.dispose()


@pytest.mark.asyncio
async def test_topic_and_post_votes_are_idempotent_and_counted() -> None:
    session_factory, engine = await create_test_session()

    async def override_session():
        async with session_factory() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_session] = override_session

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        owner = await register_user(client, "owner")
        voter = await register_user(client, "voter")
        topic, reply = await create_topic_with_reply(client, owner["auth"], voter["auth"])
        voter_headers = {"Authorization": voter["auth"]}

        upvote = await client.put(
            f"/api/v1/posts/{reply['id']}/vote",
            headers=voter_headers,
            json={"value": 1},
        )
        repeat_upvote = await client.put(
            f"/api/v1/posts/{reply['id']}/vote",
            headers=voter_headers,
            json={"value": 1},
        )
        assert upvote.status_code == 200
        assert repeat_upvote.status_code == 200
        assert repeat_upvote.json()["data"] == {
            "target_type": "post",
            "target_id": reply["id"],
            "value": 1,
            "score": 1,
            "count": 1,
        }

        downvote = await client.put(
            f"/api/v1/posts/{reply['id']}/vote",
            headers=voter_headers,
            json={"value": -1},
        )
        assert downvote.json()["data"]["score"] == -1
        assert downvote.json()["data"]["count"] == 1

        remove = await client.put(
            f"/api/v1/posts/{reply['id']}/vote",
            headers=voter_headers,
            json={"value": 0},
        )
        assert remove.json()["data"]["score"] == 0
        assert remove.json()["data"]["count"] == 0

        topic_vote = await client.put(
            f"/api/v1/topics/{topic['id']}/vote",
            headers=voter_headers,
            json={"value": 1},
        )
        repeat_topic_vote = await client.put(
            f"/api/v1/topics/{topic['id']}/vote",
            headers=voter_headers,
            json={"value": 1},
        )
        assert topic_vote.status_code == 200
        assert repeat_topic_vote.json()["data"]["score"] == 1
        assert repeat_topic_vote.json()["data"]["count"] == 1

    async with session_factory() as session:
        vote_count = await session.scalar(select(func.count(Vote.id)))
        topic_row = await session.scalar(select(Topic).where(Topic.id == topic["id"]))
        post_row = await session.scalar(select(Post).where(Post.id == reply["id"]))
        assert vote_count == 1
        assert topic_row is not None and topic_row.vote_score == 1 and topic_row.vote_count == 1
        assert post_row is not None and post_row.vote_score == 0 and post_row.vote_count == 0

    await engine.dispose()


@pytest.mark.asyncio
async def test_poll_vote_replacement_and_closed_poll_rejection() -> None:
    session_factory, engine = await create_test_session()

    async def override_session():
        async with session_factory() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_session] = override_session

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        owner = await register_user(client, "owner")
        voter = await register_user(client, "voter")
        board = await client.post(
            "/api/v1/boards",
            headers={"Authorization": owner["auth"]},
            json={
                "slug": "polls",
                "name": "投票讨论",
                "description": "用于验证 Poll 的版块。",
                "color": "#7C3AED",
            },
        )
        assert board.status_code == 201

        closes_at = (datetime.now(UTC) + timedelta(days=1)).isoformat()
        topic = await client.post(
            "/api/v1/boards/polls/topics",
            headers={"Authorization": owner["auth"]},
            json={
                "title": "下个版本先做哪项？",
                "raw_md": "请选择一个优先方向。",
                "tags": ["roadmap"],
                "poll": {
                    "question": "最想先上线哪个能力？",
                    "options": ["投票", "徽章", "日历"],
                    "multiple_choice": False,
                    "closes_at": closes_at,
                },
            },
        )
        assert topic.status_code == 201
        poll = topic.json()["data"]["poll"]
        assert poll["closed"] is False
        option_ids = [option["id"] for option in poll["options"]]

        first_vote = await client.put(
            f"/api/v1/topics/{topic.json()['data']['id']}/poll/vote",
            headers={"Authorization": voter["auth"]},
            json={"option_ids": [option_ids[0]]},
        )
        assert first_vote.status_code == 200
        assert first_vote.json()["data"]["selected_option_ids"] == [option_ids[0]]

        replacement = await client.put(
            f"/api/v1/topics/{topic.json()['data']['id']}/poll/vote",
            headers={"Authorization": voter["auth"]},
            json={"option_ids": [option_ids[1]]},
        )
        assert replacement.status_code == 200
        replacement_data = replacement.json()["data"]
        assert replacement_data["total_votes"] == 1
        assert replacement_data["selected_option_ids"] == [option_ids[1]]
        counts = {option["id"]: option["vote_count"] for option in replacement_data["options"]}
        assert counts[option_ids[0]] == 0
        assert counts[option_ids[1]] == 1

        async with session_factory() as session:
            poll_row = await session.scalar(select(Poll))
            assert poll_row is not None
            poll_row.closes_at = datetime.now(UTC) - timedelta(minutes=1)
            await session.commit()

        closed_vote = await client.put(
            f"/api/v1/topics/{topic.json()['data']['id']}/poll/vote",
            headers={"Authorization": voter["auth"]},
            json={"option_ids": [option_ids[2]]},
        )
        assert closed_vote.status_code == 422
        assert closed_vote.json()["error"]["code"] == "poll_closed"

    async with session_factory() as session:
        option_count = await session.scalar(select(func.count(PollOption.id)))
        vote_count = await session.scalar(select(func.count(PollVote.id)))
        assert option_count == 3
        assert vote_count == 1

    await engine.dispose()

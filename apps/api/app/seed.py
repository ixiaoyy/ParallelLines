import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import configure_logging, get_logger
from app.core.security import hash_password
from app.db.session import AsyncSessionLocal
from app.models.forum import Board, BoardMember, Topic
from app.models.user import User
from app.schemas.forum import TopicCreateRequest
from app.services.forum import ForumService

DEMO_PASSWORD = "parallellines-demo-123"


async def seed_demo_data(session: AsyncSession) -> None:
    logger = get_logger("seed")
    admin = await upsert_user(
        session,
        username="demo_admin",
        email="demo_admin@example.com",
        role="admin",
    )
    moderator = await upsert_user(
        session,
        username="demo_moderator",
        email="demo_moderator@example.com",
        role="moderator",
    )
    member = await upsert_user(
        session,
        username="demo_member",
        email="demo_member@example.com",
        role="user",
    )

    support = await upsert_board(
        session,
        slug="support",
        name="支持与排障",
        description="安装、升级、错误码定位与可复现问题协作排查。",
        color="#10B981",
        owner=moderator,
    )
    engineering = await upsert_board(
        session,
        slug="engineering",
        name="工程实践",
        description="API 设计、异步任务、可观测性与工程质量经验沉淀。",
        color="#3B82F6",
        owner=admin,
    )
    await ensure_board_member(
        session, support, member, role="follower", notification_level="watching"
    )
    await session.commit()

    await create_topic_if_missing(
        session,
        board=support,
        author=member,
        title="OIDC 登录回调 state mismatch 如何排查？",
        raw_md=(
            "我们在 Edge callback 日志中看到 state mismatch，"
            "需要确认 Cookie、回调地址和时钟偏移。"
        ),
        tags=["oidc", "登录", "已解决"],
    )
    await create_topic_if_missing(
        session,
        board=engineering,
        author=moderator,
        title="如何把 CSV 导入 API 拆成后台队列？",
        raw_md="同步导入两万行会 timeout，计划改成任务表、worker 与通知中心联动。",
        tags=["csv", "queue", "api"],
    )
    await create_topic_if_missing(
        session,
        board=engineering,
        author=admin,
        title="上线前需要哪些可观测性检查？",
        raw_md="建议检查 request_id、结构化日志、/metrics、健康检查、回滚清单和 smoke test。",
        tags=["observability", "deployment"],
    )
    logger.info("seed_completed", demo_users=["demo_admin", "demo_moderator", "demo_member"])


async def upsert_user(session: AsyncSession, *, username: str, email: str, role: str) -> User:
    user = await session.scalar(select(User).where(User.username == username))
    if user:
        user.role = role
        user.status = "active"
        return user
    user = User(
        username=username,
        email=email,
        hashed_password=hash_password(DEMO_PASSWORD),
        role=role,
        status="active",
    )
    session.add(user)
    await session.flush()
    return user


async def upsert_board(
    session: AsyncSession,
    *,
    slug: str,
    name: str,
    description: str,
    color: str,
    owner: User,
) -> Board:
    board = await session.scalar(select(Board).where(Board.slug == slug))
    if board:
        board.name = name
        board.description = description
        board.color = color
        board.owner_id = owner.id
    else:
        board = Board(
            slug=slug,
            name=name,
            description=description,
            color=color,
            owner_id=owner.id,
            visibility="public",
            follower_count=0,
        )
        session.add(board)
        await session.flush()
    await ensure_board_member(session, board, owner, role="owner", notification_level="watching")
    return board


async def ensure_board_member(
    session: AsyncSession,
    board: Board,
    user: User,
    *,
    role: str,
    notification_level: str,
) -> None:
    member = await session.scalar(
        select(BoardMember).where(BoardMember.board_id == board.id, BoardMember.user_id == user.id)
    )
    if member:
        member.role = role
        member.notification_level = notification_level
        return
    board.follower_count += 1
    session.add(
        BoardMember(
            board_id=board.id,
            user_id=user.id,
            role=role,
            notification_level=notification_level,
        )
    )


async def create_topic_if_missing(
    session: AsyncSession,
    *,
    board: Board,
    author: User,
    title: str,
    raw_md: str,
    tags: list[str],
) -> None:
    existing = await session.scalar(
        select(Topic.id).where(Topic.board_id == board.id, Topic.title == title)
    )
    if existing:
        return
    await ForumService(session).create_topic(
        board.slug,
        TopicCreateRequest(title=title, raw_md=raw_md, tags=tags),
        author,
    )


async def main() -> None:
    configure_logging()
    async with AsyncSessionLocal() as session:
        await seed_demo_data(session)


if __name__ == "__main__":
    asyncio.run(main())

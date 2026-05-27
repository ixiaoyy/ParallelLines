import asyncio
from argparse import ArgumentParser
from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import configure_logging, get_logger
from app.core.security import hash_password
from app.db.base import utcnow
from app.db.session import AsyncSessionLocal
from app.models.forum import Board, BoardMember, Post, Topic
from app.models.user import User
from app.schemas.forum import PostCreateRequest, TopicCreateRequest
from app.services.forum import ForumService, render_markdown
from app.services.quality_posts import QUALITY_POST_AUTHOR_USERNAME, QUALITY_POST_SPECS
from app.services.search import SearchIndexService

DEMO_PASSWORD = "parallellines-demo-123"


@dataclass(frozen=True)
class BoardSeedSpec:
    key: str
    slug: str
    name: str
    description: str
    color: str
    owner_key: str
    purpose: str
    guidance: str


BOARD_SEED_SPECS = [
    BoardSeedSpec(
        key="announcements",
        slug="announcements",
        name="官方动态",
        description="平台公告、规则说明、活动通知与版本更新。",
        color="#409EFF",
        owner_key="admin",
        purpose="发布社区重要信息、规则变更、活动安排和版本更新，让大家知道这里正在发生什么。",
        guidance="发布时请写清背景、影响范围、时间节点和需要用户采取的动作。",
    ),
    BoardSeedSpec(
        key="resources",
        slug="resources",
        name="资源荟萃",
        description="收集值得收藏的工具、资料、网站、课程和内容。",
        color="#F97316",
        owner_key="ops",
        purpose="沉淀真正有用的资源清单，方便之后反复查找、补充和复用。",
        guidance="推荐资源时请附上链接、适合人群、使用场景，以及你为什么觉得它值得收藏。",
    ),
    BoardSeedSpec(
        key="reading",
        slug="reading",
        name="读书感悟",
        description="分享读书摘记、阅读心得、金句摘录与文字感悟。",
        color="#DB2777",
        owner_key="member",
        purpose="记录阅读带来的触动、启发和思考，让一本书、一句话或一段文字继续发酵。",
        guidance="可以写书名、摘录、你的理解，也可以只分享一段读后感或延伸思考。",
    ),
    BoardSeedSpec(
        key="health",
        slug="health",
        name="健康百科",
        description="交流饮食、运动、睡眠、心理与日常健康知识。",
        color="#10B981",
        owner_key="moderator",
        purpose="分享日常健康知识和个人实践经验，帮助大家更好地照顾身体与情绪。",
        guidance="请尽量标注信息来源；涉及疾病、用药和诊断时，应提醒大家以专业医生意见为准。",
    ),
    BoardSeedSpec(
        key="news",
        slug="news",
        name="前沿快讯",
        description="关注 AI、科技、行业变化和正在发生的新鲜事。",
        color="#6366F1",
        owner_key="frontend",
        purpose="汇集新技术、新趋势、新产品和行业变化，方便大家快速了解外部世界。",
        guidance="转发资讯时请补充来源、摘要和你的判断，避免只贴标题或制造焦虑。",
    ),
    BoardSeedSpec(
        key="experience",
        slug="experience",
        name="经验分享",
        description="记录亲身经历、实用方法、踩坑教训和复盘总结。",
        color="#EA580C",
        owner_key="admin",
        purpose="把个人经历变成可参考的经验，让后来者少走弯路，也让自己完成复盘。",
        guidance="建议写清背景、过程、结果、学到什么，以及如果重来一次你会怎么做。",
    ),
    BoardSeedSpec(
        key="qna",
        slug="qna",
        name="有问必答",
        description="有困惑就提出来，带上背景，大家一起帮你理清。",
        color="#65A30D",
        owner_key="moderator",
        purpose="承接各种求助、疑问和想不明白的问题，让社区成员一起补充线索和思路。",
        guidance="提问时请说明你想解决什么、已经尝试过什么、卡在哪里，以及希望得到哪类帮助。",
    ),
    BoardSeedSpec(
        key="feedback",
        slug="feedback",
        name="社区反馈",
        description="对网站功能、内容氛围和社区规则提出建议。",
        color="#64748B",
        owner_key="moderator",
        purpose="收集大家对产品功能、内容组织、社区氛围和规则治理的建议。",
        guidance="反馈时请尽量写清使用场景、遇到的问题、期望变化，以及可接受的替代方案。",
    ),
    BoardSeedSpec(
        key="lounge",
        slug="lounge",
        name="闲聊茶馆",
        description="轻松聊天、日常分享、兴趣交流和不那么严肃的话题。",
        color="#8B5CF6",
        owner_key="member",
        purpose="提供一个轻松的公共客厅，聊近况、兴趣、碎碎念和生活里的小发现。",
        guidance="欢迎轻松表达，但仍请保持友善、尊重他人，不刷屏、不引战。",
    ),
]


async def seed_demo_data(session: AsyncSession, *, only_if_empty: bool = False) -> None:
    logger = get_logger("seed")
    if only_if_empty and await has_existing_content(session):
        logger.info("seed_skipped_existing_content")
        return

    users = {
        "admin": await upsert_user(
            session,
            username="parallel_admin",
            email="parallel_admin@example.com",
            role="admin",
        ),
        "moderator": await upsert_user(
            session,
            username="moderator_lin",
            email="moderator_lin@example.com",
            role="moderator",
        ),
        "ops": await upsert_user(
            session,
            username="ops_writer",
            email="ops_writer@example.com",
            role="user",
        ),
        "frontend": await upsert_user(
            session,
            username="frontend_dev",
            email="frontend_dev@example.com",
            role="user",
        ),
        "plugin": await upsert_user(
            session,
            username="plugin_maker",
            email="plugin_maker@example.com",
            role="user",
        ),
        "member": await upsert_user(
            session,
            username="community_user",
            email="community_user@example.com",
            role="user",
        ),
        "quality_author": await upsert_user(
            session,
            username=QUALITY_POST_AUTHOR_USERNAME,
            email="quality_author@example.com",
            role="user",
        ),
        # Keep documented local accounts available for manual login and smoke checks.
        "demo_admin": await upsert_user(
            session,
            username="demo_admin",
            email="demo_admin@example.com",
            role="admin",
        ),
        "demo_moderator": await upsert_user(
            session,
            username="demo_moderator",
            email="demo_moderator@example.com",
            role="moderator",
        ),
        "demo_member": await upsert_user(
            session,
            username="demo_member",
            email="demo_member@example.com",
            role="user",
        ),
    }

    boards: dict[str, Board] = {}
    for board_spec in BOARD_SEED_SPECS:
        boards[board_spec.key] = await upsert_board(
            session,
            slug=board_spec.slug,
            name=board_spec.name,
            description=board_spec.description,
            color=board_spec.color,
            owner=users[board_spec.owner_key],
        )

    for board in boards.values():
        await ensure_board_member(
            session,
            board,
            users["member"],
            role="follower",
            notification_level="watching",
        )
    await session.commit()

    seeded_topics: dict[str, Topic] = {}
    for topic in starter_topics(boards, users):
        topic_payload = dict(topic)
        topic_key = str(topic_payload.pop("key"))
        seeded_topics[topic_key] = await create_topic_if_missing(session, **topic_payload)

    await create_reply_if_missing(
        session,
        topic=seeded_topics["clear-question"],
        author=users["moderator"],
        raw_md=(
            "可以先把目标、已经尝试过的方法、遇到的阻碍分成三段写。"
            "别人越容易理解上下文，就越容易给出真正有用的建议。"
        ),
    )
    await create_reply_if_missing(
        session,
        topic=seeded_topics["record-month"],
        author=users["ops"],
        raw_md=(
            "我会把门槛降到每天三句话：今天发生了什么、我有什么感受、"
            "明天想做一个什么小动作。先持续，再追求写得漂亮。"
        ),
    )
    await create_reply_if_missing(
        session,
        topic=seeded_topics["health-break"],
        author=users["frontend"],
        raw_md="番茄钟结束后站起来活动两分钟，对久坐的人比一次性高强度运动更容易坚持。",
    )
    await create_reply_if_missing(
        session,
        topic=seeded_topics["resource-toolkit"],
        author=users["plugin"],
        raw_md="推荐资源时可以补一句「我用它解决了什么问题」，比单纯贴链接更有参考价值。",
    )

    logger.info(
        "seed_completed",
        users=len(users),
        boards=len(boards),
        topics=len(seeded_topics),
    )


async def has_existing_content(session: AsyncSession) -> bool:
    board_count = await session.scalar(select(func.count()).select_from(Board))
    topic_count = await session.scalar(select(func.count()).select_from(Topic))
    return bool((board_count or 0) > 0 or (topic_count or 0) > 0)


def starter_topics(boards: dict[str, Board], users: dict[str, User]) -> list[dict[str, object]]:
    return [
        *[
            {
                "key": post.key,
                "board": boards["announcements"],
                "author": users["quality_author"],
                "title": post.title,
                "raw_md": post.raw_md,
                "tags": post.tags,
                "pinned": post.pinned,
                "featured": post.featured,
            }
            for post in QUALITY_POST_SPECS
        ],
        *board_about_topics(boards, users),
        {
            "key": "welcome-guide",
            "board": boards["announcements"],
            "author": users["admin"],
            "title": "新朋友从哪里开始了解平行线？",
            "raw_md": (
                "可以先浏览置顶的社区初衷和各版块说明，再从自己最想记录或提问的内容开始。"
                "不必追求一次写完整，清楚表达真实想法更重要。"
            ),
            "tags": ["新手指南", "社区说明"],
            "pinned": False,
            "featured": True,
        },
        {
            "key": "resource-toolkit",
            "board": boards["resources"],
            "author": users["ops"],
            "title": "你最近收藏了哪些真正用得上的工具或资料？",
            "raw_md": "欢迎分享网站、课程、书单、模板或工具，并说明它适合谁、能解决什么问题。",
            "tags": ["工具资源", "收藏"],
            "featured": True,
        },
        {
            "key": "reading-sentence",
            "board": boards["reading"],
            "author": users["member"],
            "title": "最近读到哪句话，让你停下来想了很久？",
            "raw_md": "可以贴一小段摘录，也可以只写它为什么打动你、让你想到了什么。",
            "tags": ["读书", "感悟"],
        },
        {
            "key": "health-break",
            "board": boards["health"],
            "author": users["moderator"],
            "title": "久坐之后，怎样用很小的动作照顾身体？",
            "raw_md": (
                "想收集一些低门槛、容易坚持的日常活动方式，"
                "比如拉伸、散步、喝水提醒和睡前放松。"
            ),
            "tags": ["健康习惯", "运动"],
        },
        {
            "key": "ai-tools-signal",
            "board": boards["news"],
            "author": users["frontend"],
            "title": "AI 工具更新太快，怎样判断一个新功能值不值得试？",
            "raw_md": "比起追每一条新闻，我更想知道大家如何判断信息质量、使用成本和真实价值。",
            "tags": ["AI", "科技前沿"],
            "featured": True,
        },
        {
            "key": "record-month",
            "board": boards["experience"],
            "author": users["admin"],
            "title": "如何把一个想法坚持记录一个月？",
            "raw_md": (
                "从每天几句话开始，记录触发点、行动和反馈。"
                "等积累到一定数量，再回头整理主题。"
            ),
            "tags": ["记录", "复盘"],
            "featured": True,
        },
        {
            "key": "clear-question",
            "board": boards["qna"],
            "author": users["member"],
            "title": "怎样把一个问题描述清楚，更容易得到帮助？",
            "raw_md": "我有时只知道自己卡住了，却不知道怎么问。想整理一个更容易被回复的提问格式。",
            "tags": ["提问", "求助"],
        },
        {
            "key": "feedback-tags",
            "board": boards["feedback"],
            "author": users["moderator"],
            "title": "你希望社区优先补充哪些内容标签？",
            "raw_md": (
                "比如读书、健康、AI、工具、生活经验等。"
                "欢迎说说哪些标签能帮助你更快找到内容。"
            ),
            "tags": ["功能建议", "社区共建"],
        },
        {
            "key": "lounge-daily",
            "board": boards["lounge"],
            "author": users["member"],
            "title": "今天有什么想随手分享的小事？",
            "raw_md": "可以是一张图、一句话、一个小发现，也可以只是今天过得怎么样。",
            "tags": ["闲聊", "日常"],
        },
    ]


def board_about_topics(boards: dict[str, Board], users: dict[str, User]) -> list[dict[str, object]]:
    topics: list[dict[str, object]] = []
    for spec in BOARD_SEED_SPECS:
        topics.append(
            {
                "key": f"about-{spec.slug}",
                "board": boards[spec.key],
                "author": users[spec.owner_key],
                "title": f"关于「{spec.name}」",
                "raw_md": (
                    f"# 关于「{spec.name}」\n\n"
                    f"{spec.description}\n\n"
                    f"这个版块用于{spec.purpose}\n\n"
                    "## 适合发布\n\n"
                    f"- {spec.guidance}\n"
                    "- 尽量写清背景、来源和你希望得到的讨论方向。\n"
                    "- 如果内容更适合其他版块，也可以在发布前重新选择。\n\n"
                    "希望这里能成为一个清楚、有用、友善的交流空间。"
                ),
                "tags": [],
                "pinned": True,
                "featured": False,
            }
        )
    return topics


async def upsert_user(
    session: AsyncSession,
    *,
    username: str,
    email: str,
    role: str,
    level: int = 0,
) -> User:
    user = await session.scalar(select(User).where(User.username == username))
    if user:
        user.role = role
        user.level = level
        user.status = "active"
        return user
    user = User(
        username=username,
        email=email,
        hashed_password=hash_password(DEMO_PASSWORD),
        role=role,
        level=level,
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
    pinned: bool = False,
    featured: bool = False,
) -> Topic:
    existing = await session.scalar(
        select(Topic).where(Topic.board_id == board.id, Topic.title == title)
    )
    if existing:
        existing.user_id = author.id
        existing.pinned = pinned
        existing.featured = featured
        stripped_raw_md = raw_md.strip()
        first_post = await session.scalar(
            select(Post).where(Post.topic_id == existing.id, Post.post_number == 1)
        )
        if first_post is not None:
            first_post.user_id = author.id
            if first_post.raw_md != stripped_raw_md:
                first_post.raw_md = stripped_raw_md
                first_post.cooked_html = render_markdown(stripped_raw_md)
                first_post.updated_at = utcnow()
                existing.updated_at = utcnow()
        await session.flush()
        await SearchIndexService(session).sync_topic(existing.id)
        await session.commit()
        return await ForumService(session).get_topic(existing.id)

    return await ForumService(session).create_topic(
        board.slug,
        TopicCreateRequest(
            title=title,
            raw_md=raw_md,
            tags=tags,
            pinned=pinned,
            featured=featured,
        ),
        author,
        skip_spam_checks=True,
    )


async def create_reply_if_missing(
    session: AsyncSession,
    *,
    topic: Topic,
    author: User,
    raw_md: str,
) -> None:
    existing = await session.scalar(
        select(Post.id).where(Post.topic_id == topic.id, Post.raw_md == raw_md.strip())
    )
    if existing:
        return

    await ForumService(session).reply_to_topic(
        topic.id,
        PostCreateRequest(raw_md=raw_md),
        author,
        skip_spam_checks=True,
    )


def parse_args(argv: Sequence[str] | None = None) -> bool:
    parser = ArgumentParser(description="Seed ParallelLines demo data.")
    parser.add_argument(
        "--if-empty",
        action="store_true",
        help="Only seed when no boards or topics exist.",
    )
    return parser.parse_args(argv).if_empty


async def main(argv: Sequence[str] | None = None) -> None:
    configure_logging()
    only_if_empty = parse_args(argv)
    async with AsyncSessionLocal() as session:
        await seed_demo_data(session, only_if_empty=only_if_empty)


if __name__ == "__main__":
    asyncio.run(main())

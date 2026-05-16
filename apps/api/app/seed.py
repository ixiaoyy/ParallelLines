import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import configure_logging, get_logger
from app.core.security import hash_password
from app.db.session import AsyncSessionLocal
from app.models.forum import Board, BoardMember, Post, Topic
from app.models.user import User
from app.schemas.forum import PostCreateRequest, TopicCreateRequest
from app.services.forum import ForumService

DEMO_PASSWORD = "parallellines-demo-123"


async def seed_demo_data(session: AsyncSession) -> None:
    logger = get_logger("seed")
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

    boards = {
        "announcements": await upsert_board(
            session,
            slug="announcements",
            name="公告与更新",
            description="版本发布、维护窗口、路线图和社区规则更新。",
            color="#3B82F6",
            owner=users["admin"],
        ),
        "support": await upsert_board(
            session,
            slug="support",
            name="支持与排障",
            description="安装、升级、错误码定位与可复现问题协作排查。",
            color="#10B981",
            owner=users["moderator"],
        ),
        "engineering": await upsert_board(
            session,
            slug="engineering",
            name="工程实践",
            description="接口设计、异步任务、可观测性与工程质量经验沉淀。",
            color="#3B82F6",
            owner=users["admin"],
        ),
        "frontend": await upsert_board(
            session,
            slug="frontend",
            name="前端体验",
            description="Vue、组件、移动端适配、可访问性和交互体验讨论。",
            color="#8B5CF6",
            owner=users["frontend"],
        ),
        "plugins": await upsert_board(
            session,
            slug="plugins",
            name="插件与扩展",
            description="插件安装、依赖冲突、扩展能力和集成经验。",
            color="#F59E0B",
            owner=users["plugin"],
        ),
        "community": await upsert_board(
            session,
            slug="community",
            name="社区反馈",
            description="站点建议、版务讨论、内容治理和使用反馈。",
            color="#EF4444",
            owner=users["moderator"],
        ),
    }

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
        topic=seeded_topics["oidc-state"],
        author=users["moderator"],
        raw_md=(
            "先比对浏览器里的回调域名、Cookie SameSite 设置和服务端时钟。"
            "如果 state 只在跨域跳转后丢失，优先检查代理层是否改写了协议头。"
        ),
    )
    await create_reply_if_missing(
        session,
        topic=seeded_topics["queue-import"],
        author=users["ops"],
        raw_md=(
            "我们通常会拆成上传记录、解析任务和结果通知三段。"
            "前台只展示任务状态，失败明细放到可下载报告里。"
        ),
    )
    await create_reply_if_missing(
        session,
        topic=seeded_topics["mobile-nav"],
        author=users["frontend"],
        raw_md="移动端优先保证导航、搜索和发帖入口可达，再补充动画和手势细节。",
    )
    await create_reply_if_missing(
        session,
        topic=seeded_topics["plugin-deps"],
        author=users["plugin"],
        raw_md="依赖冲突最好贴出包管理器输出、运行时版本和最小复现仓库。",
    )

    logger.info(
        "seed_completed",
        users=len(users),
        boards=len(boards),
        topics=len(seeded_topics),
    )


def starter_topics(boards: dict[str, Board], users: dict[str, User]) -> list[dict[str, object]]:
    return [
        {
            "key": "welcome-guide",
            "board": boards["announcements"],
            "author": users["admin"],
            "title": "平行线使用指南：如何发布一个清晰主题？",
            "raw_md": (
                "发布前先选择版块，再补充背景、复现步骤、日志和期望结果。"
                "这样后续讨论会留在同一条主题线里，方便检索和复用。"
            ),
            "tags": ["指南", "新手", "社区规则"],
            "pinned": True,
            "featured": True,
        },
        {
            "key": "release-checklist",
            "board": boards["announcements"],
            "author": users["admin"],
            "title": "发布前检查清单需要覆盖哪些内容？",
            "raw_md": "建议覆盖迁移、回滚、健康检查、监控指标、冒烟测试和公告窗口。",
            "tags": ["发布", "检查清单", "运维"],
            "featured": True,
        },
        {
            "key": "oidc-state",
            "board": boards["support"],
            "author": users["member"],
            "title": "OIDC 登录回调 state mismatch 如何排查？",
            "raw_md": (
                "我们在回调日志中看到 state mismatch，需要确认 Cookie、"
                "回调地址、代理头和时钟偏移。"
            ),
            "tags": ["oidc", "登录", "已解决"],
        },
        {
            "key": "migration-field",
            "board": boards["support"],
            "author": users["ops"],
            "title": "升级后迁移提示缺少 notification_cursor 字段怎么办？",
            "raw_md": "升级后启动失败，迁移日志提示字段不存在。需要确认迁移顺序和数据库版本。",
            "tags": ["升级", "迁移", "数据库"],
        },
        {
            "key": "search-miss",
            "board": boards["support"],
            "author": users["member"],
            "title": "搜索不到刚发布的主题时应该先看哪里？",
            "raw_md": "主题详情可打开，但搜索结果没有命中。想确认索引延迟和筛选条件是否有关。",
            "tags": ["搜索", "索引", "排障"],
        },
        {
            "key": "queue-import",
            "board": boards["engineering"],
            "author": users["moderator"],
            "title": "如何把 CSV 导入拆成后台队列？",
            "raw_md": "同步导入两万行会超时，计划改成任务表、worker 与通知中心联动。",
            "tags": ["csv", "queue", "接口设计"],
            "featured": True,
        },
        {
            "key": "observability",
            "board": boards["engineering"],
            "author": users["admin"],
            "title": "上线前需要哪些可观测性检查？",
            "raw_md": "建议检查 request_id、结构化日志、metrics、健康检查、回滚清单和冒烟测试。",
            "tags": ["可观测性", "deployment", "日志"],
        },
        {
            "key": "tag-design",
            "board": boards["engineering"],
            "author": users["moderator"],
            "title": "主题标签怎样设计才便于长期检索？",
            "raw_md": "标签应同时覆盖模块、症状和技术栈，避免把同义词拆成多个孤岛。",
            "tags": ["标签", "信息架构", "检索"],
        },
        {
            "key": "mobile-nav",
            "board": boards["frontend"],
            "author": users["frontend"],
            "title": "移动端导航如何兼顾搜索、版块和发帖入口？",
            "raw_md": "小屏幕下顶部空间有限，需要折叠菜单，并保证键盘和读屏器可用。",
            "tags": ["移动端", "导航", "可访问性"],
        },
        {
            "key": "markdown-copy",
            "board": boards["frontend"],
            "author": users["frontend"],
            "title": "代码块复制按钮在主题详情里放哪里更合适？",
            "raw_md": "代码块很多时，复制按钮既要容易找到，也不能遮挡代码内容。",
            "tags": ["Markdown", "代码块", "交互"],
        },
        {
            "key": "plugin-deps",
            "board": boards["plugins"],
            "author": users["plugin"],
            "title": "插件安装失败时如何定位依赖冲突？",
            "raw_md": "安装时报 peer dependency 冲突，想整理一个最小排查流程。",
            "tags": ["插件", "依赖", "排障"],
        },
        {
            "key": "theme-extension",
            "board": boards["plugins"],
            "author": users["plugin"],
            "title": "主题扩展应该开放哪些插槽？",
            "raw_md": "希望在不破坏主布局的前提下，允许扩展侧边栏卡片和主题动作区。",
            "tags": ["主题", "扩展", "组件"],
        },
        {
            "key": "duplicate-topics",
            "board": boards["community"],
            "author": users["moderator"],
            "title": "重复主题应该合并还是保留？",
            "raw_md": "同一个错误码出现多个主题时，需要制定合并、引用和保留差异信息的规则。",
            "tags": ["版务", "治理", "重复主题"],
        },
        {
            "key": "feedback-format",
            "board": boards["community"],
            "author": users["member"],
            "title": "站点反馈应该包含哪些信息？",
            "raw_md": "建议反馈里包含页面地址、操作步骤、预期结果和实际截图。",
            "tags": ["反馈", "社区规则", "体验"],
        },
    ]


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
    pinned: bool = False,
    featured: bool = False,
) -> Topic:
    existing = await session.scalar(
        select(Topic).where(Topic.board_id == board.id, Topic.title == title)
    )
    if existing:
        existing.pinned = pinned
        existing.featured = featured
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
    )


async def main() -> None:
    configure_logging()
    async with AsyncSessionLocal() as session:
        await seed_demo_data(session)


if __name__ == "__main__":
    asyncio.run(main())

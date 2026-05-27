"""cleanup board pins and rename lounge

Revision ID: 0042_cleanup_board_pins
Revises: 0041_add_benefits_board
Create Date: 2026-05-27
"""

from __future__ import annotations

import html
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import NamedTuple

import sqlalchemy as sa

from alembic import op

revision: str = "0042_cleanup_board_pins"
down_revision: str | None = "0041_add_benefits_board"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


class BoardSpec(NamedTuple):
    slug: str
    name: str
    description: str
    color: str
    purpose: str
    guidance: str


BOARD_SPECS = (
    BoardSpec(
        "announcements",
        "官方动态",
        "平台公告、规则说明、活动通知与版本更新。",
        "#409EFF",
        "发布社区重要信息、规则变更、活动安排和版本更新，让大家知道这里正在发生什么。",
        "发布时请写清背景、影响范围、时间节点和需要用户采取的动作。",
    ),
    BoardSpec(
        "resources",
        "资源荟萃",
        "收集值得收藏的工具、资料、网站、课程和内容。",
        "#F97316",
        "沉淀真正有用的资源清单，方便之后反复查找、补充和复用。",
        "推荐资源时请附上链接、适合人群、使用场景，以及你为什么觉得它值得收藏。",
    ),
    BoardSpec(
        "benefits",
        "福利羊毛",
        "优惠信息、免费资源、限时活动、实用福利与避坑提醒。",
        "#F59E0B",
        "集中分享靠谱的福利线索、优惠活动、免费资源和省钱经验，方便大家及时发现也避免踩坑。",
        "发布时请写清领取方式、有效时间、适用条件、风险提醒和是否需要付费或绑定信息。",
    ),
    BoardSpec(
        "reading",
        "读书感悟",
        "分享读书摘记、阅读心得、金句摘录与文字感悟。",
        "#DB2777",
        "记录阅读带来的触动、启发和思考，让一本书、一句话或一段文字继续发酵。",
        "可以写书名、摘录、你的理解，也可以只分享一段读后感或延伸思考。",
    ),
    BoardSpec(
        "health",
        "健康百科",
        "交流饮食、运动、睡眠、心理与日常健康知识。",
        "#10B981",
        "分享日常健康知识和个人实践经验，帮助大家更好地照顾身体与情绪。",
        "请尽量标注信息来源；涉及疾病、用药和诊断时，应提醒大家以专业医生意见为准。",
    ),
    BoardSpec(
        "news",
        "前沿快讯",
        "关注 AI、科技、行业变化和正在发生的新鲜事。",
        "#6366F1",
        "汇集新技术、新趋势、新产品和行业变化，方便大家快速了解外部世界。",
        "转发资讯时请补充来源、摘要和你的判断，避免只贴标题或制造焦虑。",
    ),
    BoardSpec(
        "experience",
        "经验分享",
        "记录亲身经历、实用方法、踩坑教训和复盘总结。",
        "#EA580C",
        "把个人经历变成可参考的经验，让后来者少走弯路，也让自己完成复盘。",
        "建议写清背景、过程、结果、学到什么，以及如果重来一次你会怎么做。",
    ),
    BoardSpec(
        "qna",
        "有问必答",
        "有困惑就提出来，带上背景，大家一起帮你理清。",
        "#65A30D",
        "承接各种求助、疑问和想不明白的问题，让社区成员一起补充线索和思路。",
        "提问时请说明你想解决什么、已经尝试过什么、卡在哪里，以及希望得到哪类帮助。",
    ),
    BoardSpec(
        "lounge",
        "闲聊八卦",
        "轻松聊天、日常分享、兴趣交流、热点八卦和不那么严肃的话题。",
        "#8B5CF6",
        "提供一个轻松的公共客厅，聊近况、兴趣、碎碎念、热点八卦和生活里的小发现。",
        "欢迎轻松表达，但仍请保持友善、尊重他人，不刷屏、不引战。",
    ),
    BoardSpec(
        "feedback",
        "社区反馈",
        "对网站功能、内容氛围和社区规则提出建议。",
        "#64748B",
        "收集大家对产品功能、内容组织、社区氛围和规则治理的建议。",
        "反馈时请尽量写清使用场景、遇到的问题、期望变化，以及可接受的替代方案。",
    ),
)

CLUTTER_TOPIC_TITLES = (
    "平行线使用指南：如何发布一个清晰主题？",
    "发布前检查清单需要覆盖哪些内容？",
    "升级后迁移提示缺少 notification_cursor 字段怎么办？",
    "OIDC 登录回调 state mismatch 如何排查？",
    "搜索不到刚发布的主题时应该先看哪里？",
    "如何把 CSV 导入拆成后台队列？",
    "主题标签怎样设计才便于长期检索？",
    "上线前需要哪些可观测性检查？",
    "移动端导航如何兼顾搜索、版块和发帖入口？",
    "代码块复制按钮在主题详情里放哪里更合适？",
    "主题扩展应该开放哪些插槽？",
    "插件安装失败时如何定位依赖冲突？",
    "重复主题应该合并还是保留？",
    "站点反馈应该包含哪些信息？",
    "论坛初衷：记录、连接与共同成长",
    "社区规范：友善交流、尊重原创与保护隐私",
    "社区规范：理性交流、尊重原创与保护隐私",
    "新朋友从哪里开始了解平行线？",
    "你最近收藏了哪些真正用得上的工具或资料？",
    "分享福利羊毛时，哪些信息必须写清楚？",
    "最近读到哪句话，让你停下来想了很久？",
    "最近有哪些低门槛的健康习惯值得坚持？",
    "久坐之后，怎样用很小的动作照顾身体？",
    "AI 工具更新太快，怎样判断一个新功能值不值得试？",
    "如何把一个想法坚持记录一个月？",
    "怎样把一个问题描述清楚，更容易得到帮助？",
    "你希望社区优先补充哪些内容标签？",
    "今天有什么想随手分享的小事？",
)

boards = sa.table(
    "boards",
    sa.column("id", sa.BigInteger()),
    sa.column("slug", sa.String()),
    sa.column("name", sa.String()),
    sa.column("name_localizations", sa.JSON()),
    sa.column("description", sa.String()),
    sa.column("color", sa.String()),
    sa.column("visibility", sa.String()),
    sa.column("owner_id", sa.BigInteger()),
    sa.column("topic_count", sa.Integer()),
    sa.column("post_count", sa.Integer()),
    sa.column("follower_count", sa.Integer()),
    sa.column("updated_at", sa.DateTime(timezone=True)),
)
users = sa.table(
    "users",
    sa.column("id", sa.BigInteger()),
    sa.column("username", sa.String()),
    sa.column("role", sa.String()),
    sa.column("status", sa.String()),
)
topics = sa.table(
    "topics",
    sa.column("id", sa.BigInteger()),
    sa.column("board_id", sa.BigInteger()),
    sa.column("user_id", sa.BigInteger()),
    sa.column("title", sa.String()),
    sa.column("title_localizations", sa.JSON()),
    sa.column("slug", sa.String()),
    sa.column("topic_type", sa.String()),
    sa.column("visibility", sa.String()),
    sa.column("status", sa.String()),
    sa.column("pinned", sa.Boolean()),
    sa.column("featured", sa.Boolean()),
    sa.column("view_count", sa.Integer()),
    sa.column("reply_count", sa.Integer()),
    sa.column("like_count", sa.Integer()),
    sa.column("hot_score", sa.Float()),
    sa.column("last_posted_at", sa.DateTime(timezone=True)),
    sa.column("deleted_at", sa.DateTime(timezone=True)),
    sa.column("created_at", sa.DateTime(timezone=True)),
    sa.column("updated_at", sa.DateTime(timezone=True)),
)
posts = sa.table(
    "posts",
    sa.column("id", sa.BigInteger()),
    sa.column("topic_id", sa.BigInteger()),
    sa.column("user_id", sa.BigInteger()),
    sa.column("post_number", sa.Integer()),
    sa.column("raw_md", sa.Text()),
    sa.column("cooked_html", sa.Text()),
    sa.column("reply_count", sa.Integer()),
    sa.column("like_count", sa.Integer()),
    sa.column("vote_score", sa.Integer()),
    sa.column("vote_count", sa.Integer()),
    sa.column("deleted_at", sa.DateTime(timezone=True)),
    sa.column("created_at", sa.DateTime(timezone=True)),
    sa.column("updated_at", sa.DateTime(timezone=True)),
)
tags = sa.table(
    "tags",
    sa.column("id", sa.BigInteger()),
    sa.column("topic_count", sa.Integer()),
    sa.column("updated_at", sa.DateTime(timezone=True)),
)
topic_tags = sa.table(
    "topic_tags",
    sa.column("topic_id", sa.BigInteger()),
    sa.column("tag_id", sa.BigInteger()),
)
board_members = sa.table(
    "board_members",
    sa.column("id", sa.BigInteger()),
    sa.column("board_id", sa.BigInteger()),
)


def upgrade() -> None:
    bind = op.get_bind()
    if not table_exists(bind, "boards") or not table_exists(bind, "topics"):
        return
    if bind.execute(sa.select(sa.func.count()).select_from(boards)).scalar_one() == 0:
        return

    author = select_migration_author(bind)
    if author is None:
        return

    now_value = now()
    for spec in BOARD_SPECS:
        board = board_by_slug(bind, spec.slug)
        if board is None:
            continue
        bind.execute(
            boards.update()
            .where(boards.c.id == board.id)
            .values(
                name=spec.name,
                name_localizations=None,
                description=spec.description,
                color=spec.color,
                visibility="public",
                updated_at=now_value,
            )
        )
        board_author_id = int(board.owner_id or author["id"])
        about_id = ensure_about_topic(bind, int(board.id), board_author_id, spec)
        normalize_board_pins(bind, int(board.id), about_id)

    hide_clutter_topics(bind)
    recompute_board_counters(bind)
    recompute_tag_counters(bind)


def downgrade() -> None:
    return


def now() -> datetime:
    return datetime.now(UTC)


def table_exists(bind: sa.Connection, table_name: str) -> bool:
    return sa.inspect(bind).has_table(table_name)


def board_by_slug(bind: sa.Connection, slug: str):
    return bind.execute(sa.select(boards).where(boards.c.slug == slug).limit(1)).first()


def select_migration_author(bind: sa.Connection) -> dict[str, object] | None:
    row = bind.execute(
        sa.select(users.c.id, users.c.username)
        .where(users.c.status == "active")
        .order_by(
            sa.case(
                (users.c.username == "多动脑子z", 0),
                (users.c.username == "大脚板", 1),
                (users.c.role == "admin", 2),
                (users.c.role == "moderator", 3),
                else_=4,
            ),
            users.c.id,
        )
        .limit(1)
    ).first()
    if row is None:
        return None
    return {"id": row.id, "username": row.username}


def ensure_about_topic(
    bind: sa.Connection,
    board_id: int,
    author_id: int,
    spec: BoardSpec,
) -> int:
    title = about_title(spec.name)
    previous_titles = (title, "关于「闲聊茶馆」") if spec.slug == "lounge" else (title,)
    row = bind.execute(
        sa.select(topics)
        .where(
            topics.c.board_id == board_id,
            sa.or_(
                topics.c.title.in_(previous_titles),
                topics.c.slug == f"about-{spec.slug}",
            ),
        )
        .order_by(
            sa.case((topics.c.deleted_at.is_(None), 0), else_=1),
            sa.case((topics.c.title == title, 0), else_=1),
            topics.c.id,
        )
        .limit(1)
    ).first()

    markdown = about_markdown(spec)
    cooked = about_html(spec)
    current_time = now()
    if row is None:
        bind.execute(
            topics.insert().values(
                board_id=board_id,
                user_id=author_id,
                title=title,
                title_localizations=None,
                slug=f"about-{spec.slug}",
                topic_type="regular",
                visibility="public",
                status="open",
                pinned=True,
                featured=False,
                view_count=0,
                reply_count=0,
                like_count=0,
                hot_score=0,
                last_posted_at=current_time,
                deleted_at=None,
                created_at=current_time,
                updated_at=current_time,
            )
        )
        topic_id = int(
            bind.execute(
                sa.select(topics.c.id).where(
                    topics.c.board_id == board_id,
                    topics.c.slug == f"about-{spec.slug}",
                )
            ).scalar_one()
        )
        bind.execute(
            posts.insert().values(
                topic_id=topic_id,
                user_id=author_id,
                post_number=1,
                raw_md=markdown,
                cooked_html=cooked,
                reply_count=0,
                like_count=0,
                vote_score=0,
                vote_count=0,
                deleted_at=None,
                created_at=current_time,
                updated_at=current_time,
            )
        )
        return topic_id

    topic_id = int(row.id)
    bind.execute(
        topics.update()
        .where(topics.c.id == topic_id)
        .values(
            user_id=author_id,
            title=title,
            title_localizations=None,
            slug=f"about-{spec.slug}",
            topic_type="regular",
            visibility="public",
            status="open",
            pinned=True,
            featured=False,
            deleted_at=None,
            updated_at=current_time,
        )
    )
    first_post = bind.execute(
        sa.select(posts.c.id).where(posts.c.topic_id == topic_id, posts.c.post_number == 1).limit(1)
    ).first()
    if first_post:
        bind.execute(
            posts.update()
            .where(posts.c.id == first_post.id)
            .values(
                user_id=author_id,
                raw_md=markdown,
                cooked_html=cooked,
                deleted_at=None,
                updated_at=current_time,
            )
        )
    else:
        bind.execute(
            posts.insert().values(
                topic_id=topic_id,
                user_id=author_id,
                post_number=1,
                raw_md=markdown,
                cooked_html=cooked,
                reply_count=0,
                like_count=0,
                vote_score=0,
                vote_count=0,
                deleted_at=None,
                created_at=current_time,
                updated_at=current_time,
            )
        )
    return topic_id


def normalize_board_pins(bind: sa.Connection, board_id: int, about_id: int) -> None:
    current_time = now()
    bind.execute(
        topics.update()
        .where(
            topics.c.board_id == board_id,
            topics.c.id != about_id,
            topics.c.deleted_at.is_(None),
        )
        .values(pinned=False, featured=False, updated_at=current_time)
    )
    bind.execute(
        topics.update()
        .where(topics.c.id == about_id)
        .values(
            pinned=True,
            featured=False,
            status="open",
            deleted_at=None,
            updated_at=current_time,
        )
    )
    duplicate_about_ids = bind.execute(
        sa.select(topics.c.id).where(
            topics.c.board_id == board_id,
            topics.c.id != about_id,
            topics.c.deleted_at.is_(None),
            topics.c.title.like("关于「%"),
        )
    ).scalars().all()
    if duplicate_about_ids:
        bind.execute(
            topics.update()
            .where(topics.c.id.in_(duplicate_about_ids))
            .values(
                pinned=False,
                featured=False,
                status="hidden",
                deleted_at=current_time,
                updated_at=current_time,
            )
        )


def hide_clutter_topics(bind: sa.Connection) -> None:
    current_time = now()
    clutter_ids = bind.execute(
        sa.select(topics.c.id).where(
            topics.c.title.in_(CLUTTER_TOPIC_TITLES),
            topics.c.deleted_at.is_(None),
        )
    ).scalars().all()
    if not clutter_ids:
        return
    bind.execute(
        topics.update()
        .where(topics.c.id.in_(clutter_ids))
        .values(
            pinned=False,
            featured=False,
            status="hidden",
            deleted_at=current_time,
            updated_at=current_time,
        )
    )


def recompute_board_counters(bind: sa.Connection) -> None:
    for board_id in bind.execute(sa.select(boards.c.id)).scalars().all():
        topic_count = bind.execute(
            sa.select(sa.func.count())
            .select_from(topics)
            .where(topics.c.board_id == board_id, topics.c.deleted_at.is_(None))
        ).scalar_one()
        post_count = bind.execute(
            sa.select(sa.func.count())
            .select_from(posts.join(topics, posts.c.topic_id == topics.c.id))
            .where(
                topics.c.board_id == board_id,
                topics.c.deleted_at.is_(None),
                posts.c.deleted_at.is_(None),
            )
        ).scalar_one()
        follower_count = bind.execute(
            sa.select(sa.func.count())
            .select_from(board_members)
            .where(board_members.c.board_id == board_id)
        ).scalar_one()
        bind.execute(
            boards.update()
            .where(boards.c.id == board_id)
            .values(
                topic_count=topic_count,
                post_count=post_count,
                follower_count=follower_count,
                updated_at=now(),
            )
        )


def recompute_tag_counters(bind: sa.Connection) -> None:
    for tag_id in bind.execute(sa.select(tags.c.id)).scalars().all():
        topic_count = bind.execute(
            sa.select(sa.func.count(sa.distinct(topic_tags.c.topic_id)))
            .select_from(topic_tags.join(topics, topic_tags.c.topic_id == topics.c.id))
            .where(topic_tags.c.tag_id == tag_id, topics.c.deleted_at.is_(None))
        ).scalar_one()
        bind.execute(
            tags.update()
            .where(tags.c.id == tag_id)
            .values(topic_count=topic_count, updated_at=now())
        )


def about_title(board_name: str) -> str:
    return f"关于「{board_name}」"


def about_markdown(spec: BoardSpec) -> str:
    return (
        f"# {about_title(spec.name)}\n\n"
        f"{spec.description}\n\n"
        f"这个板块用于{spec.purpose}\n\n"
        "## 适合发布\n\n"
        f"- {spec.guidance}\n"
        "- 尽量写清背景、来源和你希望得到的讨论方向。\n"
        "- 如果内容更适合其他板块，也可以在发布前重新选择。\n\n"
        "希望这里能成为一个清楚、有用、友善的交流空间。"
    )


def about_html(spec: BoardSpec) -> str:
    items = [
        spec.guidance,
        "尽量写清背景、来源和你希望得到的讨论方向。",
        "如果内容更适合其他板块，也可以在发布前重新选择。",
    ]
    return "".join(
        [
            f"<h1>{html.escape(about_title(spec.name))}</h1>",
            f"<p>{html.escape(spec.description)}</p>",
            f"<p>这个板块用于{html.escape(spec.purpose)}</p>",
            "<h2>适合发布</h2>",
            "<ul>",
            *(f"<li>{html.escape(item)}</li>" for item in items),
            "</ul>",
            "<p>希望这里能成为一个清楚、有用、友善的交流空间。</p>",
        ]
    )

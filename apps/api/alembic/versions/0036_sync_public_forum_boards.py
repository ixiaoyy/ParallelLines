"""sync public forum boards

Revision ID: 0036_sync_public_forum_boards
Revises: 0035_remove_subscriptions_payments
Create Date: 2026-05-27
"""

from __future__ import annotations

import html
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import NamedTuple

import sqlalchemy as sa

from alembic import op

revision: str = "0036_sync_public_forum_boards"
down_revision: str | None = "0035_remove_subscriptions_payments"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


class BoardSpec(NamedTuple):
    slug: str
    legacy_slugs: tuple[str, ...]
    legacy_names: tuple[str, ...]
    name: str
    description: str
    color: str
    purpose: str
    guidance: str


class TagMigration(NamedTuple):
    legacy_names: tuple[str, ...]
    legacy_slugs: tuple[str, ...]
    name: str
    slug: str


BOARD_SPECS = (
    BoardSpec(
        slug="announcements",
        legacy_slugs=("announcements",),
        legacy_names=("公告与更新", "官方动态"),
        name="官方动态",
        description="平台公告、规则说明、活动通知与版本更新。",
        color="#409EFF",
        purpose="发布社区重要信息、规则变更、活动安排和版本更新，让大家知道这里正在发生什么。",
        guidance="发布时请写清背景、影响范围、时间节点和需要用户采取的动作。",
    ),
    BoardSpec(
        slug="resources",
        legacy_slugs=("resources", "plugins"),
        legacy_names=("资源荟萃", "插件与扩展"),
        name="资源荟萃",
        description="收集值得收藏的工具、资料、网站、课程和内容。",
        color="#F97316",
        purpose="沉淀真正有用的资源清单，方便之后反复查找、补充和复用。",
        guidance="推荐资源时请附上链接、适合人群、使用场景，以及你为什么觉得它值得收藏。",
    ),
    BoardSpec(
        slug="reading",
        legacy_slugs=("reading",),
        legacy_names=("读书感悟", "读书成诗"),
        name="读书感悟",
        description="分享读书摘记、阅读心得、金句摘录与文字感悟。",
        color="#DB2777",
        purpose="记录阅读带来的触动、启发和思考，让一本书、一句话或一段文字继续发酵。",
        guidance="可以写书名、摘录、你的理解，也可以只分享一段读后感或延伸思考。",
    ),
    BoardSpec(
        slug="health",
        legacy_slugs=("health",),
        legacy_names=("健康百科",),
        name="健康百科",
        description="交流饮食、运动、睡眠、心理与日常健康知识。",
        color="#10B981",
        purpose="分享日常健康知识和个人实践经验，帮助大家更好地照顾身体与情绪。",
        guidance="请尽量标注信息来源；涉及疾病、用药和诊断时，应提醒大家以专业医生意见为准。",
    ),
    BoardSpec(
        slug="news",
        legacy_slugs=("news", "frontend"),
        legacy_names=("前沿快讯", "前端体验"),
        name="前沿快讯",
        description="关注 AI、科技、行业变化和正在发生的新鲜事。",
        color="#6366F1",
        purpose="汇集新技术、新趋势、新产品和行业变化，方便大家快速了解外部世界。",
        guidance="转发资讯时请补充来源、摘要和你的判断，避免只贴标题或制造焦虑。",
    ),
    BoardSpec(
        slug="experience",
        legacy_slugs=("experience", "engineering", "dev"),
        legacy_names=("经验分享", "工程实践"),
        name="经验分享",
        description="记录亲身经历、实用方法、踩坑教训和复盘总结。",
        color="#EA580C",
        purpose="把个人经历变成可参考的经验，让后来者少走弯路，也让自己完成复盘。",
        guidance="建议写清背景、过程、结果、学到什么，以及如果重来一次你会怎么做。",
    ),
    BoardSpec(
        slug="qna",
        legacy_slugs=("qna", "support"),
        legacy_names=("有问必答", "支持与排障"),
        name="有问必答",
        description="有困惑就提出来，带上背景，大家一起帮你理清。",
        color="#65A30D",
        purpose="承接各种求助、疑问和想不明白的问题，让社区成员一起补充线索和思路。",
        guidance="提问时请说明你想解决什么、已经尝试过什么、卡在哪里，以及希望得到哪类帮助。",
    ),
    BoardSpec(
        slug="feedback",
        legacy_slugs=("feedback", "community"),
        legacy_names=("社区反馈",),
        name="社区反馈",
        description="对网站功能、内容氛围和社区规则提出建议。",
        color="#64748B",
        purpose="收集大家对产品功能、内容组织、社区氛围和规则治理的建议。",
        guidance="反馈时请尽量写清使用场景、遇到的问题、期望变化，以及可接受的替代方案。",
    ),
    BoardSpec(
        slug="lounge",
        legacy_slugs=("lounge", "chat"),
        legacy_names=("闲聊茶馆", "闲聊"),
        name="闲聊茶馆",
        description="轻松聊天、日常分享、兴趣交流和不那么严肃的话题。",
        color="#8B5CF6",
        purpose="提供一个轻松的公共客厅，聊近况、兴趣、碎碎念和生活里的小发现。",
        guidance="欢迎轻松表达，但仍请保持友善、尊重他人，不刷屏、不引战。",
    ),
)

TAG_MIGRATIONS = (
    TagMigration(("e2e",), ("e2e",), "记录", "record"),
    TagMigration(("smoke",), ("smoke",), "功能体验", "feature-experience"),
    TagMigration(("deployment",), ("deployment",), "版本更新", "release-notes"),
    TagMigration(("排障",), ("排障",), "求助", "help"),
    TagMigration(("社区规则",), ("社区规则",), "社区说明", "community-guide"),
    TagMigration(("csv",), ("csv",), "资源整理", "resource-list"),
)


boards = sa.table(
    "boards",
    sa.column("id", sa.BigInteger()),
    sa.column("slug", sa.String()),
    sa.column("name", sa.String()),
    sa.column("name_localizations", sa.JSON()),
    sa.column("description", sa.Text()),
    sa.column("color", sa.String()),
    sa.column("avatar_url", sa.String()),
    sa.column("owner_id", sa.BigInteger()),
    sa.column("parent_board_id", sa.BigInteger()),
    sa.column("visibility", sa.String()),
    sa.column("required_tags", sa.JSON()),
    sa.column("allowed_tags", sa.JSON()),
    sa.column("post_template", sa.Text()),
    sa.column("default_notification_level", sa.String()),
    sa.column("default_sort", sa.String()),
    sa.column("topic_count", sa.Integer()),
    sa.column("post_count", sa.Integer()),
    sa.column("follower_count", sa.Integer()),
    sa.column("created_at", sa.DateTime(timezone=True)),
    sa.column("updated_at", sa.DateTime(timezone=True)),
)
board_members = sa.table(
    "board_members",
    sa.column("id", sa.BigInteger()),
    sa.column("board_id", sa.BigInteger()),
    sa.column("user_id", sa.BigInteger()),
    sa.column("role", sa.String()),
    sa.column("notification_level", sa.String()),
    sa.column("joined_at", sa.DateTime(timezone=True)),
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
    sa.column("merged_into_topic_id", sa.BigInteger()),
    sa.column("accepted_answer_post_id", sa.BigInteger()),
    sa.column("solved_at", sa.DateTime(timezone=True)),
    sa.column("solved_by_id", sa.BigInteger()),
    sa.column("answer_mode", sa.Boolean()),
    sa.column("vote_score", sa.Integer()),
    sa.column("vote_count", sa.Integer()),
    sa.column("created_at", sa.DateTime(timezone=True)),
    sa.column("updated_at", sa.DateTime(timezone=True)),
)
posts = sa.table(
    "posts",
    sa.column("id", sa.BigInteger()),
    sa.column("topic_id", sa.BigInteger()),
    sa.column("user_id", sa.BigInteger()),
    sa.column("parent_id", sa.BigInteger()),
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
users = sa.table(
    "users",
    sa.column("id", sa.BigInteger()),
    sa.column("username", sa.String()),
    sa.column("role", sa.String()),
    sa.column("status", sa.String()),
    sa.column("created_at", sa.DateTime(timezone=True)),
)
tags = sa.table(
    "tags",
    sa.column("id", sa.BigInteger()),
    sa.column("name", sa.String()),
    sa.column("slug", sa.String()),
    sa.column("topic_count", sa.Integer()),
    sa.column("created_at", sa.DateTime(timezone=True)),
    sa.column("updated_at", sa.DateTime(timezone=True)),
)
topic_tags = sa.table(
    "topic_tags",
    sa.column("topic_id", sa.BigInteger()),
    sa.column("tag_id", sa.BigInteger()),
)
search_documents = sa.table(
    "search_documents",
    sa.column("id", sa.BigInteger()),
    sa.column("topic_id", sa.BigInteger()),
    sa.column("board_id", sa.BigInteger()),
    sa.column("author_id", sa.BigInteger()),
    sa.column("author_username", sa.String()),
    sa.column("topic_status", sa.String()),
    sa.column("title", sa.String()),
    sa.column("body", sa.Text()),
    sa.column("tags_text", sa.Text()),
    sa.column("indexed_at", sa.DateTime(timezone=True)),
    sa.column("created_at", sa.DateTime(timezone=True)),
    sa.column("updated_at", sa.DateTime(timezone=True)),
)


def upgrade() -> None:
    bind = op.get_bind()
    if not table_exists(bind, "boards") or not table_exists(bind, "topics"):
        return
    if bind.execute(sa.select(sa.func.count()).select_from(boards)).scalar_one() == 0:
        # Fresh installs stay empty until an operator creates/imports content.
        # Do not create boards in this migration.
        return

    author = select_migration_author(bind)
    for spec in BOARD_SPECS:
        board_id = ensure_board(bind, spec, author["id"] if author else None)
        if author:
            ensure_board_member(bind, board_id, author["id"])
            ensure_about_topic(bind, board_id, spec, author)

    hide_smoke_test_boards(bind)

    for migration in TAG_MIGRATIONS:
        merge_tag(bind, migration)

    recompute_board_counters(bind)
    recompute_tag_counters(bind)


def downgrade() -> None:
    # This is an irreversible content migration. Downgrading schema should not try
    # to rename live community content back to old product copy.
    return


def now() -> datetime:
    return datetime.now(UTC)


def table_exists(bind: sa.Connection, table_name: str) -> bool:
    return sa.inspect(bind).has_table(table_name)


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


def ensure_board(bind: sa.Connection, spec: BoardSpec, owner_id: int | None) -> int:
    target = board_by_slug(bind, spec.slug)
    candidates = board_candidates(bind, spec, exclude_id=target.id if target else None)

    if target is None:
        if candidates:
            target = candidates[0]
            bind.execute(
                boards.update()
                .where(boards.c.id == target.id)
                .values(slug=spec.slug, updated_at=now())
            )
        else:
            bind.execute(
                boards.insert().values(
                    slug=spec.slug,
                    name=spec.name,
                    name_localizations=None,
                    description=spec.description,
                    color=spec.color,
                    avatar_url=None,
                    owner_id=owner_id,
                    parent_board_id=None,
                    visibility="public",
                    required_tags=None,
                    allowed_tags=None,
                    post_template=None,
                    default_notification_level="normal",
                    default_sort="latest",
                    topic_count=0,
                    post_count=0,
                    follower_count=0,
                    created_at=now(),
                    updated_at=now(),
                )
            )
            return int(board_by_slug(bind, spec.slug).id)

    update_board_metadata(bind, int(target.id), spec)

    for source in board_candidates(bind, spec, exclude_id=int(target.id)):
        merge_board(bind, int(source.id), int(target.id))

    return int(target.id)


def board_by_slug(bind: sa.Connection, slug: str):
    return bind.execute(sa.select(boards).where(boards.c.slug == slug).limit(1)).first()


def board_candidates(bind: sa.Connection, spec: BoardSpec, *, exclude_id: int | None = None):
    conditions = [boards.c.slug.in_(spec.legacy_slugs), boards.c.name.in_(spec.legacy_names)]
    statement = sa.select(boards).where(sa.or_(*conditions)).order_by(boards.c.id)
    if exclude_id is not None:
        statement = statement.where(boards.c.id != exclude_id)
    return list(bind.execute(statement).all())


def update_board_metadata(bind: sa.Connection, board_id: int, spec: BoardSpec) -> None:
    bind.execute(
        boards.update()
        .where(boards.c.id == board_id)
        .values(
            name=spec.name,
            name_localizations=None,
            description=spec.description,
            color=spec.color,
            parent_board_id=None,
            visibility="public",
            updated_at=now(),
        )
    )


def merge_board(bind: sa.Connection, source_board_id: int, target_board_id: int) -> None:
    if source_board_id == target_board_id:
        return

    move_topics_to_board(bind, source_board_id, target_board_id)
    merge_board_members(bind, source_board_id, target_board_id)

    bind.execute(
        boards.update()
        .where(boards.c.parent_board_id == source_board_id)
        .values(parent_board_id=target_board_id, updated_at=now())
    )
    for table_name in (
        "board_invitations",
        "flags",
        "audit_logs",
        "reviewables",
        "uploads",
        "search_documents",
        "chat_channels",
    ):
        update_optional_board_reference(bind, table_name, source_board_id, target_board_id)
    bind.execute(boards.delete().where(boards.c.id == source_board_id))


def move_topics_to_board(bind: sa.Connection, source_board_id: int, target_board_id: int) -> None:
    rows = bind.execute(
        sa.select(topics.c.id, topics.c.slug).where(topics.c.board_id == source_board_id)
    ).all()
    for row in rows:
        slug = unique_topic_slug(bind, target_board_id, row.slug, int(row.id))
        bind.execute(
            topics.update()
            .where(topics.c.id == row.id)
            .values(board_id=target_board_id, slug=slug, updated_at=now())
        )


def unique_topic_slug(
    bind: sa.Connection, board_id: int, desired_slug: str, topic_id: int
) -> str:
    slug = desired_slug
    suffix = 1
    while bind.execute(
        sa.select(topics.c.id)
        .where(
            topics.c.board_id == board_id,
            topics.c.slug == slug,
            topics.c.id != topic_id,
        )
        .limit(1)
    ).first():
        suffix += 1
        base = desired_slug[: max(1, 200 - len(str(topic_id)) - len(str(suffix)))]
        slug = f"{base}-{topic_id}-{suffix}"
    return slug


def merge_board_members(bind: sa.Connection, source_board_id: int, target_board_id: int) -> None:
    rows = bind.execute(
        sa.select(
            board_members.c.id,
            board_members.c.user_id,
        ).where(board_members.c.board_id == source_board_id)
    ).all()
    for row in rows:
        exists = bind.execute(
            sa.select(board_members.c.id)
            .where(
                board_members.c.board_id == target_board_id,
                board_members.c.user_id == row.user_id,
            )
            .limit(1)
        ).first()
        if exists:
            bind.execute(board_members.delete().where(board_members.c.id == row.id))
        else:
            bind.execute(
                board_members.update()
                .where(board_members.c.id == row.id)
                .values(board_id=target_board_id)
            )


def update_optional_board_reference(
    bind: sa.Connection, table_name: str, source_board_id: int, target_board_id: int
) -> None:
    if not table_exists(bind, table_name):
        return
    table = sa.table(table_name, sa.column("board_id", sa.BigInteger()))
    bind.execute(
        table.update()
        .where(table.c.board_id == source_board_id)
        .values(board_id=target_board_id)
    )


def ensure_board_member(bind: sa.Connection, board_id: int, user_id: int) -> None:
    exists = bind.execute(
        sa.select(board_members.c.id)
        .where(board_members.c.board_id == board_id, board_members.c.user_id == user_id)
        .limit(1)
    ).first()
    if exists:
        return
    bind.execute(
        board_members.insert().values(
            board_id=board_id,
            user_id=user_id,
            role="owner",
            notification_level="watching",
            joined_at=now(),
        )
    )


def ensure_about_topic(
    bind: sa.Connection,
    board_id: int,
    spec: BoardSpec,
    author: dict[str, object],
) -> None:
    title = f"关于「{spec.name}」"
    slug = f"about-{spec.slug}"
    raw_md = about_topic_markdown(spec)
    cooked_html = render_about_html(spec)
    existing = bind.execute(
        sa.select(topics.c.id)
        .where(
            topics.c.board_id == board_id,
            sa.or_(topics.c.slug == slug, topics.c.title == title),
        )
        .order_by(topics.c.id)
        .limit(1)
    ).first()
    if existing:
        topic_id = int(existing.id)
        bind.execute(
            topics.update()
            .where(topics.c.id == topic_id)
            .values(
                title=title,
                title_localizations=None,
                slug=slug,
                user_id=author["id"],
                pinned=True,
                featured=False,
                status="open",
                topic_type="regular",
                visibility="public",
                updated_at=now(),
            )
        )
        bind.execute(
            posts.update()
            .where(posts.c.topic_id == topic_id, posts.c.post_number == 1)
            .values(
                user_id=author["id"],
                raw_md=raw_md,
                cooked_html=cooked_html,
                updated_at=now(),
            )
        )
        sync_search_document(bind, topic_id, board_id, spec, author, raw_md)
        return

    bind.execute(
        topics.insert().values(
            board_id=board_id,
            user_id=author["id"],
            title=title,
            title_localizations=None,
            slug=slug,
            topic_type="regular",
            visibility="public",
            status="open",
            pinned=True,
            featured=False,
            view_count=0,
            reply_count=0,
            like_count=0,
            hot_score=0.0,
            last_posted_at=now(),
            deleted_at=None,
            merged_into_topic_id=None,
            accepted_answer_post_id=None,
            solved_at=None,
            solved_by_id=None,
            answer_mode=False,
            vote_score=0,
            vote_count=0,
            created_at=now(),
            updated_at=now(),
        )
    )
    topic_id = int(
        bind.execute(
            sa.select(topics.c.id).where(topics.c.board_id == board_id, topics.c.slug == slug)
        ).scalar_one()
    )
    bind.execute(
        posts.insert().values(
            topic_id=topic_id,
            user_id=author["id"],
            parent_id=None,
            post_number=1,
            raw_md=raw_md,
            cooked_html=cooked_html,
            reply_count=0,
            like_count=0,
            vote_score=0,
            vote_count=0,
            deleted_at=None,
            created_at=now(),
            updated_at=now(),
        )
    )
    sync_search_document(bind, topic_id, board_id, spec, author, raw_md)


def about_topic_markdown(spec: BoardSpec) -> str:
    return (
        f"# 关于「{spec.name}」\n\n"
        f"{spec.description}\n\n"
        f"这个版块用于{spec.purpose}\n\n"
        "## 适合发布\n\n"
        f"- {spec.guidance}\n"
        "- 尽量写清背景、来源和你希望得到的讨论方向。\n"
        "- 如果内容更适合其他版块，也可以在发布前重新选择。\n\n"
        "希望这里能成为一个清楚、有用、友善的交流空间。"
    )


def render_about_html(spec: BoardSpec) -> str:
    paragraphs = [
        f"<h1>关于「{html.escape(spec.name)}」</h1>",
        f"<p>{html.escape(spec.description)}</p>",
        f"<p>这个版块用于{html.escape(spec.purpose)}</p>",
        "<h2>适合发布</h2>",
        "<ul>",
        f"<li>{html.escape(spec.guidance)}</li>",
        "<li>尽量写清背景、来源和你希望得到的讨论方向。</li>",
        "<li>如果内容更适合其他版块，也可以在发布前重新选择。</li>",
        "</ul>",
        "<p>希望这里能成为一个清楚、有用、友善的交流空间。</p>",
    ]
    return "\n".join(paragraphs)


def sync_search_document(
    bind: sa.Connection,
    topic_id: int,
    board_id: int,
    spec: BoardSpec,
    author: dict[str, object],
    raw_md: str,
) -> None:
    if not table_exists(bind, "search_documents"):
        return
    values = {
        "topic_id": topic_id,
        "board_id": board_id,
        "author_id": author["id"],
        "author_username": author["username"],
        "topic_status": "open",
        "title": f"关于「{spec.name}」",
        "body": raw_md,
        "tags_text": str(author["username"]),
        "indexed_at": now(),
        "updated_at": now(),
    }
    existing = bind.execute(
        sa.select(search_documents.c.id).where(search_documents.c.topic_id == topic_id).limit(1)
    ).first()
    if existing:
        bind.execute(
            search_documents.update()
            .where(search_documents.c.id == existing.id)
            .values(**values)
        )
    else:
        bind.execute(search_documents.insert().values(**values, created_at=now()))


def hide_smoke_test_boards(bind: sa.Connection) -> None:
    bind.execute(
        boards.update()
        .where(sa.or_(boards.c.slug.like("smoke-%"), boards.c.name.like("Smoke 测试版块%")))
        .values(visibility="private", updated_at=now())
    )


def merge_tag(bind: sa.Connection, migration: TagMigration) -> None:
    target = tag_by_name_or_slug(bind, migration.name, migration.slug)
    sources = tag_candidates(bind, migration)
    if target is None and sources:
        target = sources[0]
        bind.execute(
            tags.update()
            .where(tags.c.id == target.id)
            .values(name=migration.name, slug=migration.slug, updated_at=now())
        )
    elif target is None:
        return

    for source in tag_candidates(bind, migration, exclude_id=int(target.id)):
        merge_tag_rows(bind, int(source.id), int(target.id))


def tag_by_name_or_slug(bind: sa.Connection, name: str, slug: str):
    return bind.execute(
        sa.select(tags).where(sa.or_(tags.c.name == name, tags.c.slug == slug)).limit(1)
    ).first()


def tag_candidates(bind: sa.Connection, migration: TagMigration, *, exclude_id: int | None = None):
    statement = (
        sa.select(tags)
        .where(
            sa.or_(
                tags.c.name.in_((*migration.legacy_names, migration.name)),
                tags.c.slug.in_((*migration.legacy_slugs, migration.slug)),
            )
        )
        .order_by(tags.c.id)
    )
    if exclude_id is not None:
        statement = statement.where(tags.c.id != exclude_id)
    return list(bind.execute(statement).all())


def merge_tag_rows(bind: sa.Connection, source_tag_id: int, target_tag_id: int) -> None:
    topic_ids = bind.execute(
        sa.select(topic_tags.c.topic_id).where(topic_tags.c.tag_id == source_tag_id)
    ).scalars()
    for topic_id in topic_ids:
        exists = bind.execute(
            sa.select(topic_tags.c.topic_id)
            .where(topic_tags.c.topic_id == topic_id, topic_tags.c.tag_id == target_tag_id)
            .limit(1)
        ).first()
        if not exists:
            bind.execute(topic_tags.insert().values(topic_id=topic_id, tag_id=target_tag_id))
    bind.execute(topic_tags.delete().where(topic_tags.c.tag_id == source_tag_id))
    bind.execute(tags.delete().where(tags.c.id == source_tag_id))


def recompute_board_counters(bind: sa.Connection) -> None:
    board_ids = bind.execute(sa.select(boards.c.id)).scalars().all()
    for board_id in board_ids:
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
    tag_ids = bind.execute(sa.select(tags.c.id)).scalars().all()
    for tag_id in tag_ids:
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

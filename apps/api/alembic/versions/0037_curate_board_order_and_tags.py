"""curate board order and public tags

Revision ID: 0037_curate_board_order_and_tags
Revises: 0036_sync_public_forum_boards
Create Date: 2026-05-27
"""

from __future__ import annotations

import html
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import NamedTuple

import sqlalchemy as sa

from alembic import op

revision: str = "0037_curate_board_order_and_tags"
down_revision: str | None = "0036_sync_public_forum_boards"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


class TagSpec(NamedTuple):
    name: str
    slug: str
    aliases: tuple[str, ...]
    alias_slugs: tuple[str, ...] = ()


class StarterTopicSpec(NamedTuple):
    board_slug: str
    slug: str
    title: str
    raw_md: str
    tags: tuple[str, ...]
    pinned: bool = False
    featured: bool = False


TAG_SPECS = (
    TagSpec("社区说明", "community-guide", ("社区说明", "社区规则", "社区共建", "治理", "版务")),
    TagSpec("新手指南", "getting-started", ("新手指南", "新手", "指南", "检查清单")),
    TagSpec(
        "提问求助",
        "help",
        (
            "提问求助",
            "求助",
            "提问",
            "排障",
            "升级",
            "数据库",
            "迁移",
            "已解决",
            "登录",
            "搜索",
            "索引",
        ),
        ("oidc",),
    ),
    TagSpec(
        "经验复盘",
        "experience-review",
        ("经验复盘", "记录", "复盘", "成长记录", "接口设计", "可观测性", "日志", "运维", "避坑"),
        ("queue",),
    ),
    TagSpec(
        "资源推荐",
        "resources",
        ("资源推荐", "工具资源", "收藏", "资源整理", "主题", "扩展", "组件", "插件", "依赖"),
        ("csv",),
    ),
    TagSpec("前沿观察", "frontier", ("前沿观察", "科技前沿", "移动端", "可访问性"), ("ai",)),
    TagSpec("读书感悟", "reading-notes", ("读书感悟", "读书", "感悟")),
    TagSpec("健康生活", "healthy-life", ("健康生活", "健康习惯", "运动")),
    TagSpec("日常分享", "daily-share", ("日常分享", "日常", "分享"), ("e2e", "smoke")),
    TagSpec("日常闲聊", "lounge-chat", ("日常闲聊", "闲聊")),
    TagSpec(
        "功能建议",
        "feature-feedback",
        ("功能建议", "反馈", "体验", "交互", "导航", "标签", "检索", "信息架构", "版本更新"),
        ("markdown", "deployment"),
    ),
    TagSpec("规则公告", "rules", ("规则公告", "隐私保护", "发布")),
)

STARTER_TOPICS = (
    StarterTopicSpec(
        "announcements",
        "forum-intent",
        "论坛初衷：记录、连接与共同成长",
        "这里用于说明平行线为什么存在：记录真实经验，连接相似问题，让每个人都能长期沉淀自己的思考。",
        ("社区说明", "新手指南"),
        pinned=True,
        featured=True,
    ),
    StarterTopicSpec(
        "announcements",
        "community-guidelines",
        "社区规范：友善交流、尊重原创与保护隐私",
        "欢迎认真表达，也请保持友善、注明来源、保护隐私。好的社区靠大家一起维护。",
        ("社区说明", "规则公告"),
        pinned=True,
        featured=True,
    ),
    StarterTopicSpec(
        "resources",
        "resource-toolkit",
        "你最近收藏了哪些真正用得上的工具或资料？",
        "欢迎分享网站、课程、书单、模板或工具，并说明它适合谁、能解决什么问题。",
        ("资源推荐", "日常分享"),
        featured=True,
    ),
    StarterTopicSpec(
        "reading",
        "reading-sentence",
        "最近读到哪句话，让你停下来想了很久？",
        "可以贴一小段摘录，也可以只写它为什么打动你、让你想到了什么。",
        ("读书感悟", "日常分享"),
    ),
    StarterTopicSpec(
        "health",
        "health-break",
        "最近有哪些低门槛的健康习惯值得坚持？",
        "欢迎分享饮食、运动、睡眠、情绪管理等日常经验；涉及疾病和用药请以医生意见为准。",
        ("健康生活", "日常分享"),
    ),
    StarterTopicSpec(
        "news",
        "ai-tools-signal",
        "AI 工具更新太快，怎样判断一个新功能值不值得试？",
        "比起追每一条新闻，我更想知道大家如何判断信息质量、使用成本和真实价值。",
        ("前沿观察", "资源推荐"),
        featured=True,
    ),
    StarterTopicSpec(
        "experience",
        "record-month",
        "如何把一个想法坚持记录一个月？",
        "从每天几句话开始，记录触发点、行动和反馈。等积累到一定数量，再回头整理主题。",
        ("经验复盘", "日常分享"),
        featured=True,
    ),
    StarterTopicSpec(
        "qna",
        "clear-question",
        "怎样把一个问题描述清楚，更容易得到帮助？",
        "可以先写清目标、背景、已经尝试过什么、卡在哪里，以及希望得到哪类帮助。",
        ("提问求助", "新手指南"),
    ),
    StarterTopicSpec(
        "feedback",
        "feedback-tags",
        "你希望社区优先补充哪些内容标签？",
        "比如读书、健康、AI、工具、生活经验等。欢迎说说哪些标签能帮助你更快找到内容。",
        ("功能建议", "社区说明"),
    ),
    StarterTopicSpec(
        "lounge",
        "lounge-daily",
        "今天有什么想随手分享的小事？",
        "可以是一张图、一句话、一个小发现，也可以只是今天过得怎么样。",
        ("日常闲聊", "日常分享"),
    ),
)


boards = sa.table(
    "boards",
    sa.column("id", sa.BigInteger()),
    sa.column("slug", sa.String()),
    sa.column("topic_count", sa.Integer()),
    sa.column("post_count", sa.Integer()),
    sa.column("follower_count", sa.Integer()),
    sa.column("updated_at", sa.DateTime(timezone=True)),
)
board_members = sa.table(
    "board_members",
    sa.column("id", sa.BigInteger()),
    sa.column("board_id", sa.BigInteger()),
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
    if not table_exists(bind, "boards") or not table_exists(bind, "tags"):
        return
    if bind.execute(sa.select(sa.func.count()).select_from(boards)).scalar_one() == 0:
        return

    for spec in TAG_SPECS:
        merge_tag_family(bind, spec)

    author = select_migration_author(bind)
    if author is not None:
        for spec in STARTER_TOPICS:
            ensure_starter_topic(bind, spec, author)

    recompute_board_counters(bind)
    recompute_tag_counters(bind)


def downgrade() -> None:
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
                (users.c.username == "parallel_admin", 0),
                (users.c.username == "demo_admin", 1),
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


def merge_tag_family(bind: sa.Connection, spec: TagSpec) -> None:
    names = (*spec.aliases, spec.name)
    slugs = (*spec.alias_slugs, spec.slug)
    candidates = list(
        bind.execute(
            sa.select(tags)
            .where(sa.or_(tags.c.name.in_(names), tags.c.slug.in_(slugs)))
            .order_by(
                sa.case(
                    (tags.c.name == spec.name, 0),
                    (tags.c.slug == spec.slug, 1),
                    else_=2,
                ),
                tags.c.id,
            )
        ).all()
    )
    if candidates:
        target = candidates[0]
    else:
        bind.execute(
            tags.insert().values(
                name=spec.name,
                slug=spec.slug,
                topic_count=0,
                created_at=now(),
                updated_at=now(),
            )
        )
        target = bind.execute(sa.select(tags).where(tags.c.slug == spec.slug)).first()

    target_id = int(target.id)
    for candidate in candidates:
        if int(candidate.id) != target_id:
            merge_tag_rows(bind, int(candidate.id), target_id)

    bind.execute(
        tags.update()
        .where(tags.c.id == target_id)
        .values(name=spec.name, slug=spec.slug, updated_at=now())
    )


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


def ensure_starter_topic(
    bind: sa.Connection,
    spec: StarterTopicSpec,
    author: dict[str, object],
) -> None:
    board = bind.execute(sa.select(boards).where(boards.c.slug == spec.board_slug)).first()
    if board is None:
        return

    existing = bind.execute(
        sa.select(topics.c.id)
        .where(
            topics.c.board_id == board.id,
            sa.or_(topics.c.slug == spec.slug, topics.c.title == spec.title),
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
                title=spec.title,
                slug=spec.slug,
                user_id=author["id"],
                pinned=spec.pinned,
                featured=spec.featured,
                updated_at=now(),
            )
        )
        bind.execute(
            posts.update()
            .where(posts.c.topic_id == topic_id, posts.c.post_number == 1)
            .values(
                user_id=author["id"],
                raw_md=spec.raw_md,
                cooked_html=render_html(spec.raw_md),
                updated_at=now(),
            )
        )
    else:
        topic_id = create_topic(bind, int(board.id), spec, int(author["id"]))

    replace_topic_tags(bind, topic_id, spec.tags)
    sync_search_document(bind, topic_id, int(board.id), spec, author)


def create_topic(
    bind: sa.Connection,
    board_id: int,
    spec: StarterTopicSpec,
    author_id: int,
) -> int:
    slug = unique_topic_slug(bind, board_id, spec.slug)
    bind.execute(
        topics.insert().values(
            board_id=board_id,
            user_id=author_id,
            title=spec.title,
            slug=slug,
            topic_type="regular",
            visibility="public",
            status="open",
            pinned=spec.pinned,
            featured=spec.featured,
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
            user_id=author_id,
            parent_id=None,
            post_number=1,
            raw_md=spec.raw_md,
            cooked_html=render_html(spec.raw_md),
            reply_count=0,
            like_count=0,
            vote_score=0,
            vote_count=0,
            deleted_at=None,
            created_at=now(),
            updated_at=now(),
        )
    )
    return topic_id


def unique_topic_slug(bind: sa.Connection, board_id: int, desired_slug: str) -> str:
    slug = desired_slug
    suffix = 1
    while bind.execute(
        sa.select(topics.c.id)
        .where(topics.c.board_id == board_id, topics.c.slug == slug)
        .limit(1)
    ).first():
        suffix += 1
        slug = f"{desired_slug}-{suffix}"
    return slug


def replace_topic_tags(
    bind: sa.Connection,
    topic_id: int,
    tag_names: Sequence[str],
) -> None:
    bind.execute(topic_tags.delete().where(topic_tags.c.topic_id == topic_id))
    for tag_name in tag_names:
        tag_id = tag_id_by_name(bind, tag_name)
        if tag_id is None:
            continue
        bind.execute(topic_tags.insert().values(topic_id=topic_id, tag_id=tag_id))


def tag_id_by_name(bind: sa.Connection, tag_name: str) -> int | None:
    row = bind.execute(sa.select(tags.c.id).where(tags.c.name == tag_name).limit(1)).first()
    return int(row.id) if row else None


def render_html(raw_md: str) -> str:
    return "\n".join(f"<p>{html.escape(line)}</p>" for line in raw_md.splitlines() if line.strip())


def sync_search_document(
    bind: sa.Connection,
    topic_id: int,
    board_id: int,
    spec: StarterTopicSpec,
    author: dict[str, object],
) -> None:
    if not table_exists(bind, "search_documents"):
        return
    values = {
        "topic_id": topic_id,
        "board_id": board_id,
        "author_id": author["id"],
        "author_username": author["username"],
        "topic_status": "open",
        "title": spec.title,
        "body": spec.raw_md,
        "tags_text": " ".join(spec.tags),
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

"""refine public tag taxonomy

Revision ID: 0038_refine_public_tag_taxonomy
Revises: 0037_curate_board_order_and_tags
Create Date: 2026-05-27
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import NamedTuple

import sqlalchemy as sa

from alembic import op

revision: str = "0038_refine_public_tag_taxonomy"
down_revision: str | None = "0037_curate_board_order_and_tags"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


class TagSpec(NamedTuple):
    name: str
    slug: str
    aliases: tuple[str, ...]
    alias_slugs: tuple[str, ...] = ()


class TopicTagUpdate(NamedTuple):
    board_slug: str
    slugs: tuple[str, ...]
    titles: tuple[str, ...]
    tags: tuple[str, ...]


TAG_SPECS = (
    TagSpec(
        "公告",
        "announcement",
        ("公告", "社区说明", "规则公告", "发布", "版本更新", "维护", "重要提醒"),
    ),
    TagSpec("精华神帖", "featured", ("精华神帖", "精华", "优质博文", "高质")),
    TagSpec("集中帖", "collection", ("集中帖",)),
    TagSpec("发帖模板", "template", ("发帖模板", "新手指南", "检查清单", "指南", "新手")),
    TagSpec(
        "快问快答",
        "quick-qna",
        (
            "快问快答",
            "提问求助",
            "求助",
            "提问",
            "排障",
            "已解决",
            "问题",
            "疑难杂症",
            "搜索",
            "索引",
            "登录",
            "升级",
            "数据库",
            "迁移",
        ),
        ("oidc",),
    ),
    TagSpec(
        "人工智能",
        "ai",
        (
            "人工智能",
            "AI",
            "AIGC",
            "大模型",
            "前沿观察",
            "科技前沿",
            "ChatGPT",
            "OpenAI",
            "Claude",
            "Gemini",
            "DeepSeek",
            "LLM",
            "Prompt",
        ),
        ("ai",),
    ),
    TagSpec("原创", "original", ("原创", "经验复盘", "记录", "复盘", "成长记录", "经验总结")),
    TagSpec(
        "资源分享",
        "resources",
        (
            "资源分享",
            "资源推荐",
            "工具资源",
            "收藏",
            "资源整理",
            "求资源",
            "文档",
            "开源",
            "开源项目",
        ),
        ("csv",),
    ),
    TagSpec(
        "教程",
        "tutorial",
        ("教程", "技术方案", "接口设计", "可观测性", "日志", "运维"),
        ("queue",),
    ),
    TagSpec("作品集", "portfolio", ("作品集",)),
    TagSpec("读书", "reading", ("读书", "读书感悟", "书籍", "笔记", "读后感")),
    TagSpec("健康", "health", ("健康", "健康生活", "健康习惯", "运动", "健身", "心理健康")),
    TagSpec(
        "闲聊",
        "chat",
        ("闲聊", "日常闲聊", "日常分享", "日常", "分享", "生活", "碎碎念", "树洞", "纯水"),
        ("e2e", "smoke"),
    ),
    TagSpec(
        "站务反馈",
        "site-feedback",
        (
            "站务反馈",
            "功能建议",
            "反馈",
            "反馈建议",
            "站务",
            "体验",
            "交互",
            "导航",
            "标签",
            "检索",
            "信息架构",
        ),
        ("markdown", "deployment"),
    ),
    TagSpec("活动", "event", ("活动", "投票")),
)


TOPIC_TAG_UPDATES = (
    TopicTagUpdate(
        "announcements",
        ("forum-intent",),
        ("论坛初衷：记录、连接与共同成长",),
        ("公告", "精华神帖"),
    ),
    TopicTagUpdate(
        "announcements",
        ("community-guidelines",),
        (
            "社区规范：理性交流、尊重原创与保护隐私",
            "社区规范：友善交流、尊重原创与保护隐私",
        ),
        ("公告", "发帖模板"),
    ),
    TopicTagUpdate(
        "announcements",
        ("welcome-guide",),
        ("新朋友从哪里开始了解平行线？", "平行线使用指南：如何发布一个清晰主题？"),
        ("公告", "发帖模板"),
    ),
    TopicTagUpdate(
        "resources",
        ("resource-toolkit",),
        ("你最近收藏了哪些真正用得上的工具或资料？",),
        ("资源分享", "原创"),
    ),
    TopicTagUpdate(
        "reading",
        ("reading-sentence",),
        ("最近读到哪句话，让你停下来想了很久？",),
        ("读书", "原创"),
    ),
    TopicTagUpdate(
        "health",
        ("health-break",),
        ("久坐之后，怎样用很小的动作照顾身体？", "最近有哪些低门槛的健康习惯值得坚持？"),
        ("健康", "原创"),
    ),
    TopicTagUpdate(
        "news",
        ("ai-tools-signal",),
        ("AI 工具更新太快，怎样判断一个新功能值不值得试？",),
        ("人工智能", "资源分享"),
    ),
    TopicTagUpdate(
        "experience",
        ("record-month",),
        ("如何把一个想法坚持记录一个月？",),
        ("原创", "教程"),
    ),
    TopicTagUpdate(
        "qna",
        ("clear-question",),
        ("怎样把一个问题描述清楚，更容易得到帮助？",),
        ("快问快答", "发帖模板"),
    ),
    TopicTagUpdate(
        "feedback",
        ("feedback-tags",),
        ("你希望社区优先补充哪些内容标签？",),
        ("站务反馈", "公告"),
    ),
    TopicTagUpdate(
        "lounge",
        ("lounge-daily",),
        ("今天有什么想随手分享的小事？",),
        ("闲聊",),
    ),
)


boards = sa.table("boards", sa.column("id", sa.BigInteger()), sa.column("slug", sa.String()))
tags = sa.table(
    "tags",
    sa.column("id", sa.BigInteger()),
    sa.column("name", sa.String()),
    sa.column("slug", sa.String()),
    sa.column("topic_count", sa.Integer()),
    sa.column("created_at", sa.DateTime(timezone=True)),
    sa.column("updated_at", sa.DateTime(timezone=True)),
)
topics = sa.table(
    "topics",
    sa.column("id", sa.BigInteger()),
    sa.column("board_id", sa.BigInteger()),
    sa.column("title", sa.String()),
    sa.column("slug", sa.String()),
    sa.column("deleted_at", sa.DateTime(timezone=True)),
)
topic_tags = sa.table(
    "topic_tags",
    sa.column("topic_id", sa.BigInteger()),
    sa.column("tag_id", sa.BigInteger()),
)


def upgrade() -> None:
    bind = op.get_bind()
    if not table_exists(bind, "tags") or not table_exists(bind, "topics"):
        return

    for spec in TAG_SPECS:
        merge_tag_family(bind, spec)

    for update in TOPIC_TAG_UPDATES:
        apply_topic_tag_update(bind, update)

    recompute_tag_counters(bind)


def downgrade() -> None:
    return


def now() -> datetime:
    return datetime.now(UTC)


def table_exists(bind: sa.Connection, table_name: str) -> bool:
    return sa.inspect(bind).has_table(table_name)


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


def apply_topic_tag_update(bind: sa.Connection, update: TopicTagUpdate) -> None:
    board = bind.execute(sa.select(boards.c.id).where(boards.c.slug == update.board_slug)).first()
    if board is None:
        return
    matched_topic_ids = bind.execute(
        sa.select(topics.c.id).where(
            topics.c.board_id == board.id,
            topics.c.deleted_at.is_(None),
            sa.or_(topics.c.slug.in_(update.slugs), topics.c.title.in_(update.titles)),
        )
    ).scalars()
    tag_ids = [tag_id for tag_id in (tag_id_by_name(bind, name) for name in update.tags) if tag_id]
    for topic_id in matched_topic_ids:
        bind.execute(topic_tags.delete().where(topic_tags.c.topic_id == topic_id))
        for tag_id in tag_ids:
            bind.execute(topic_tags.insert().values(topic_id=topic_id, tag_id=tag_id))


def tag_id_by_name(bind: sa.Connection, tag_name: str) -> int | None:
    row = bind.execute(sa.select(tags.c.id).where(tags.c.name == tag_name).limit(1)).first()
    return int(row.id) if row else None


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

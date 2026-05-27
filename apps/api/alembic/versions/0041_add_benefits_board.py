"""add benefits board

Revision ID: 0041_add_benefits_board
Revises: 0040_remove_giveaway_tag
Create Date: 2026-05-27
"""

from __future__ import annotations

import html
from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa

from alembic import op

revision: str = "0041_add_benefits_board"
down_revision: str | None = "0040_remove_giveaway_tag"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

BOARD_SLUG = "benefits"
BOARD_NAME = "福利羊毛"
BOARD_DESCRIPTION = "优惠信息、免费资源、限时活动、实用福利与避坑提醒。"
BOARD_COLOR = "#F59E0B"
BOARD_PURPOSE = "集中分享靠谱的福利线索、优惠活动、免费资源和省钱经验，方便大家及时发现也避免踩坑。"
BOARD_GUIDANCE = "发布时请写清领取方式、有效时间、适用条件、风险提醒和是否需要付费或绑定信息。"


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


def upgrade() -> None:
    bind = op.get_bind()
    if not table_exists(bind, "boards") or not table_exists(bind, "topics"):
        return
    if bind.execute(sa.select(sa.func.count()).select_from(boards)).scalar_one() == 0:
        return

    author = select_migration_author(bind)
    board_id = ensure_board(bind, author["id"] if author else None)
    ensure_tag(bind, "福利羊毛", "benefits")
    ensure_tag(bind, "发帖模板", "template")
    if author is not None:
        ensure_board_member(bind, board_id, int(author["id"]))
        ensure_topic(
            bind,
            board_id,
            int(author["id"]),
            "about-benefits",
            f"关于「{BOARD_NAME}」",
            about_topic_markdown(),
            ("福利羊毛",),
            pinned=True,
            featured=False,
        )
        ensure_topic(
            bind,
            board_id,
            int(author["id"]),
            "benefits-safe-deals",
            "分享福利羊毛时，哪些信息必须写清楚？",
            (
                "建议至少写清领取入口、有效时间、适用地区或账号条件、是否需要付费、"
                "是否涉及隐私授权，以及你亲自验证过的结果。"
            ),
            ("福利羊毛", "发帖模板"),
            pinned=False,
            featured=True,
        )

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


def ensure_board(bind: sa.Connection, owner_id: int | None) -> int:
    row = bind.execute(sa.select(boards).where(boards.c.slug == BOARD_SLUG).limit(1)).first()
    if row:
        bind.execute(
            boards.update()
            .where(boards.c.id == row.id)
            .values(
                name=BOARD_NAME,
                name_localizations=None,
                description=BOARD_DESCRIPTION,
                color=BOARD_COLOR,
                visibility="public",
                updated_at=now(),
            )
        )
        return int(row.id)

    bind.execute(
        boards.insert().values(
            slug=BOARD_SLUG,
            name=BOARD_NAME,
            name_localizations=None,
            description=BOARD_DESCRIPTION,
            color=BOARD_COLOR,
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
    return int(bind.execute(sa.select(boards.c.id).where(boards.c.slug == BOARD_SLUG)).scalar_one())


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


def ensure_tag(bind: sa.Connection, name: str, slug: str) -> int:
    row = bind.execute(
        sa.select(tags.c.id).where(sa.or_(tags.c.name == name, tags.c.slug == slug)).limit(1)
    ).first()
    if row:
        bind.execute(
            tags.update()
            .where(tags.c.id == row.id)
            .values(name=name, slug=slug, updated_at=now())
        )
        return int(row.id)
    bind.execute(
        tags.insert().values(
            name=name,
            slug=slug,
            topic_count=0,
            created_at=now(),
            updated_at=now(),
        )
    )
    return int(bind.execute(sa.select(tags.c.id).where(tags.c.slug == slug)).scalar_one())


def ensure_topic(
    bind: sa.Connection,
    board_id: int,
    author_id: int,
    slug: str,
    title: str,
    raw_md: str,
    tag_names: Sequence[str],
    *,
    pinned: bool,
    featured: bool,
) -> None:
    row = bind.execute(
        sa.select(topics.c.id)
        .where(
            topics.c.board_id == board_id,
            sa.or_(topics.c.slug == slug, topics.c.title == title),
        )
        .limit(1)
    ).first()
    if row:
        topic_id = int(row.id)
        bind.execute(
            topics.update()
            .where(topics.c.id == topic_id)
            .values(
                user_id=author_id,
                title=title,
                slug=slug,
                pinned=pinned,
                featured=featured,
                updated_at=now(),
            )
        )
        bind.execute(
            posts.update()
            .where(posts.c.topic_id == topic_id, posts.c.post_number == 1)
            .values(
                user_id=author_id,
                raw_md=raw_md,
                cooked_html=render_html(raw_md),
                updated_at=now(),
            )
        )
    else:
        bind.execute(
            topics.insert().values(
                board_id=board_id,
                user_id=author_id,
                title=title,
                title_localizations=None,
                slug=slug,
                topic_type="regular",
                visibility="public",
                status="open",
                pinned=pinned,
                featured=featured,
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
                raw_md=raw_md,
                cooked_html=render_html(raw_md),
                reply_count=0,
                like_count=0,
                vote_score=0,
                vote_count=0,
                deleted_at=None,
                created_at=now(),
                updated_at=now(),
            )
        )

    bind.execute(topic_tags.delete().where(topic_tags.c.topic_id == topic_id))
    for tag_name in tag_names:
        tag_id = bind.execute(sa.select(tags.c.id).where(tags.c.name == tag_name).limit(1)).first()
        if tag_id:
            bind.execute(topic_tags.insert().values(topic_id=topic_id, tag_id=int(tag_id.id)))


def about_topic_markdown() -> str:
    return (
        f"# 关于「{BOARD_NAME}」\n\n"
        f"{BOARD_DESCRIPTION}\n\n"
        f"这个版块用于{BOARD_PURPOSE}\n\n"
        "## 适合发布\n\n"
        f"- {BOARD_GUIDANCE}\n"
        "- 尽量说明来源是否可靠、是否亲测、是否存在时效或地区限制。\n"
        "- 不发布欺诈、诱导充值、灰黑产或侵犯他人权益的内容。\n\n"
        "希望这里的福利信息清楚、真实、可验证。"
    )


def render_html(raw_md: str) -> str:
    return "\n".join(f"<p>{html.escape(line)}</p>" for line in raw_md.splitlines() if line.strip())


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

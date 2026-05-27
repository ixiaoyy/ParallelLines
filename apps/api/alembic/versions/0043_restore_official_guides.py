"""restore official guide topics

Revision ID: 0043_restore_official_guides
Revises: 0042_cleanup_board_pins
Create Date: 2026-05-27
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import NamedTuple

import sqlalchemy as sa

from alembic import op

revision: str = "0043_restore_official_guides"
down_revision: str | None = "0042_cleanup_board_pins"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


class OfficialTopicSpec(NamedTuple):
    slug: str
    title: str
    raw_md: str
    tags: tuple[str, ...]


OFFICIAL_TOPICS = (
    OfficialTopicSpec(
        "forum-intent",
        "论坛初衷：记录、连接与共同成长",
        (
            "# 论坛初衷：记录、连接与共同成长\n\n"
            "这个论坛建立的初衷，是希望为每个人提供一个能够长期记录与连接的空间。\n\n"
            "你可以在这里保存灵感、整理知识、记录生活，也可以与他人交流观点，"
            "在讨论中不断完善自己的认知体系。\n\n"
            "**记录，本身就是一种力量。**\n\n"
            "它不仅帮助我们保存信息，更帮助我们理解自己。\n\n"
            "而成长，也很少是孤立完成的。一个人的坚持或许有限，但一群人的交流与陪伴，"
            "往往能够让改变发生得更快。\n\n"
            "## 你可以从这里开始\n\n"
            "- 保存一个突然出现的灵感，让它以后还能被找回。\n"
            "- 整理一段新学到的知识，把零散信息变成自己的理解。\n"
            "- 记录一次生活里的变化，给未来的自己留下线索。\n"
            "- 发起一个问题或观点，在交流中获得新的角度。\n\n"
            "希望这里能真正帮助到每一个愿意思考、表达与成长的人。"
        ),
        ("公告", "精华神帖"),
    ),
    OfficialTopicSpec(
        "community-guidelines",
        "社区规范：友善交流、尊重原创与保护隐私",
        (
            "# 社区规范：友善交流、尊重原创与保护隐私\n\n"
            "平行线希望长期保存有价值的记录，也希望每一次讨论都能让人更清晰、更安全、"
            "更愿意继续表达。\n\n"
            "## 我们鼓励什么\n\n"
            "- **真实表达**：欢迎原创经验、生活记录、读书感悟、工具分享和问题求助。\n"
            "- **建设性讨论**：指出问题时，请聚焦事实，给出可参考的方案或资料。\n"
            "- **完整上下文**：提问时尽量补充背景、已经尝试过什么、卡在哪里。\n"
            "- **对事不对人**：讨论观点和做法，不攻击表达者本身。\n\n"
            "## 我们不接受什么\n\n"
            "- 人身攻击、地域歧视、恶意引战、侮辱性言论或挂人。\n"
            "- 纯广告、无意义刷屏、重复灌水，以及明显跑题内容。\n"
            "- 抄袭、洗稿，或把他人文章、代码、开源成果据为己有；转载请注明作者和出处。\n\n"
            "## 一起维护这个空间\n\n"
            "好的社区不是靠规则压出来的，而是靠每个人在发帖、回复、引用和质疑时多做一步确认。"
            "希望大家在这里既能大胆表达，也能被认真对待。"
        ),
        ("公告", "发帖模板"),
    ),
)

boards = sa.table(
    "boards",
    sa.column("id", sa.BigInteger()),
    sa.column("slug", sa.String()),
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
board_members = sa.table(
    "board_members",
    sa.column("id", sa.BigInteger()),
    sa.column("board_id", sa.BigInteger()),
)


def upgrade() -> None:
    bind = op.get_bind()
    if not table_exists(bind, "boards") or not table_exists(bind, "topics"):
        return

    board = bind.execute(sa.select(boards).where(boards.c.slug == "announcements")).first()
    if board is None:
        return

    author_id = select_admin_author_id(bind, int(board.owner_id) if board.owner_id else None)
    if author_id is None:
        return

    for spec in OFFICIAL_TOPICS:
        topic_id = ensure_official_topic(bind, int(board.id), author_id, spec)
        sync_topic_tags(bind, topic_id, spec.tags)

    recompute_board_counters(bind)
    recompute_tag_counters(bind)


def downgrade() -> None:
    return


def now() -> datetime:
    return datetime.now(UTC)


def table_exists(bind: sa.Connection, table_name: str) -> bool:
    return sa.inspect(bind).has_table(table_name)


def select_admin_author_id(bind: sa.Connection, owner_id: int | None) -> int | None:
    preferred = bind.execute(
        sa.select(users.c.id)
        .where(
            users.c.status == "active",
            users.c.username.in_(("多动脑子z", "大脚板")),
        )
        .order_by(
            sa.case(
                (users.c.username == "多动脑子z", 0),
                (users.c.username == "大脚板", 1),
                else_=2,
            ),
            users.c.id,
        )
        .limit(1)
    ).first()
    if preferred:
        return int(preferred.id)

    if owner_id is not None:
        owner = bind.execute(
            sa.select(users.c.id).where(users.c.id == owner_id, users.c.status == "active")
        ).first()
        if owner:
            return int(owner.id)
    row = bind.execute(
        sa.select(users.c.id)
        .where(users.c.status == "active", users.c.role == "admin")
        .order_by(users.c.id)
        .limit(1)
    ).first()
    return int(row.id) if row else None


def ensure_official_topic(
    bind: sa.Connection,
    board_id: int,
    author_id: int,
    spec: OfficialTopicSpec,
) -> int:
    row = bind.execute(
        sa.select(topics)
        .where(
            topics.c.board_id == board_id,
            sa.or_(topics.c.slug == spec.slug, topics.c.title == spec.title),
        )
        .order_by(sa.case((topics.c.deleted_at.is_(None), 0), else_=1), topics.c.id)
        .limit(1)
    ).first()
    current_time = now()
    cooked_html = render_basic_markdown(spec.raw_md)
    if row is None:
        bind.execute(
            topics.insert().values(
                board_id=board_id,
                user_id=author_id,
                title=spec.title,
                slug=spec.slug,
                topic_type="regular",
                visibility="public",
                status="open",
                pinned=False,
                featured=True,
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
                    topics.c.slug == spec.slug,
                )
            ).scalar_one()
        )
        bind.execute(
            posts.insert().values(
                topic_id=topic_id,
                user_id=author_id,
                post_number=1,
                raw_md=spec.raw_md,
                cooked_html=cooked_html,
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
            title=spec.title,
            slug=spec.slug,
            topic_type="regular",
            visibility="public",
            status="open",
            pinned=False,
            featured=True,
            deleted_at=None,
            updated_at=current_time,
        )
    )
    first_post = bind.execute(
        sa.select(posts.c.id).where(posts.c.topic_id == topic_id, posts.c.post_number == 1)
    ).first()
    if first_post:
        bind.execute(
            posts.update()
            .where(posts.c.id == first_post.id)
            .values(
                user_id=author_id,
                raw_md=spec.raw_md,
                cooked_html=cooked_html,
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
                raw_md=spec.raw_md,
                cooked_html=cooked_html,
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


def sync_topic_tags(bind: sa.Connection, topic_id: int, tag_names: tuple[str, ...]) -> None:
    bind.execute(topic_tags.delete().where(topic_tags.c.topic_id == topic_id))
    for name in tag_names:
        tag_id = ensure_tag(bind, name, slugify_tag(name))
        bind.execute(topic_tags.insert().values(topic_id=topic_id, tag_id=tag_id))


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


def slugify_tag(name: str) -> str:
    mapping = {
        "公告": "announcement",
        "精华神帖": "featured",
        "发帖模板": "template",
    }
    return mapping.get(name, name.lower())


def recompute_board_counters(bind: sa.Connection) -> None:
    for board_id in bind.execute(sa.select(boards.c.id)).scalars().all():
        topic_count = bind.execute(
            sa.select(sa.func.count()).where(
                topics.c.board_id == board_id,
                topics.c.deleted_at.is_(None),
            )
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
            sa.select(sa.func.count()).where(board_members.c.board_id == board_id)
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


def render_basic_markdown(markdown: str) -> str:
    lines = markdown.splitlines()
    output: list[str] = []
    in_list = False
    for line in lines:
        stripped = line.strip()
        if not stripped:
            if in_list:
                output.append("</ul>")
                in_list = False
            continue
        if stripped.startswith("# "):
            if in_list:
                output.append("</ul>")
                in_list = False
            output.append(f"<h1>{stripped[2:]}</h1>")
        elif stripped.startswith("## "):
            if in_list:
                output.append("</ul>")
                in_list = False
            output.append(f"<h2>{stripped[3:]}</h2>")
        elif stripped.startswith("- "):
            if not in_list:
                output.append("<ul>")
                in_list = True
            output.append(f"<li>{stripped[2:]}</li>")
        else:
            if in_list:
                output.append("</ul>")
                in_list = False
            output.append(f"<p>{stripped}</p>")
    if in_list:
        output.append("</ul>")
    return "".join(output)

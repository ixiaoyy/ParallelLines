"""refine memory notes template

Revision ID: 0048_refine_memory_notes_template
Revises: 0047_add_memory_notes_board
Create Date: 2026-06-01
"""

from __future__ import annotations

import html
from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa

from alembic import op

revision: str = "0048_refine_memory_notes_template"
down_revision: str | None = "0047_add_memory_notes_board"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

BOARD_SLUG = "memory-notes"
BOARD_NAME = "微光手记"
POST_TEMPLATE = """## 想留下来的片段

## 当时为什么触动我

## 现在回头看
"""
ABOUT_TOPIC_SLUG = "about-memory-notes"
ABOUT_TOPIC_TITLE = "关于「微光手记」"
ABOUT_TOPIC_MARKDOWN = """# 关于「微光手记」

这里适合存放旧日文字、每日金句、网络记忆、生活片段和短篇感想。

## 发帖模板说明

- **想留下来的片段**：贴正文、金句、截图文字或记忆片段。
- **当时为什么触动我**：写一两句背景，说明什么时候看到或写下。
- **现在回头看**：补充现在的想法、变化，或想和大家聊的方向。
"""

boards = sa.table(
    "boards",
    sa.column("id", sa.BigInteger()),
    sa.column("slug", sa.String()),
    sa.column("name", sa.String()),
    sa.column("post_template", sa.Text()),
    sa.column("topic_count", sa.Integer()),
    sa.column("post_count", sa.Integer()),
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


# upgrade 用途：移除微光手记发帖模板中的解释文案，并把说明沉淀到置顶说明帖；
# 无返回值，副作用是写入业务数据。
def upgrade() -> None:
    """Refine the memory-notes post template and ensure its pinned guide topic."""
    bind = op.get_bind()
    if not table_exists(bind, "boards"):
        return
    board = bind.execute(
        sa.select(boards.c.id, boards.c.name).where(boards.c.slug == BOARD_SLUG).limit(1)
    ).first()
    if board is None:
        return

    bind.execute(
        boards.update()
        .where(boards.c.id == board.id)
        .values(post_template=POST_TEMPLATE, updated_at=now())
    )
    author = select_migration_author(bind)
    if author is not None and table_exists(bind, "topics") and table_exists(bind, "posts"):
        ensure_about_topic(bind, int(board.id), author)
        recompute_board_counters(bind, int(board.id))


# downgrade 用途：内容优化迁移不可逆；不恢复编辑器解释文案，避免覆盖运营已调整内容。
def downgrade() -> None:
    """Keep refined content in place when downgrading."""
    return


# now 用途：统一生成迁移写入时间；无参数，返回当前 UTC 时间。
def now() -> datetime:
    """Return the current UTC timestamp for inserted/updated rows."""
    return datetime.now(UTC)


# table_exists 用途：检查目标表是否存在；table_name 为表名，返回布尔值避免空库迁移失败。
def table_exists(bind: sa.Connection, table_name: str) -> bool:
    """Check whether a table exists before running data-migration statements."""
    return sa.inspect(bind).has_table(table_name)


# select_migration_author 用途：选择可作为置顶说明帖作者的活跃用户；
# 无用户表或无活跃用户时返回 None。
def select_migration_author(bind: sa.Connection) -> dict[str, object] | None:
    """Select the preferred active user to author the memory-notes guide topic."""
    if not table_exists(bind, "users"):
        return None
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


# ensure_about_topic 用途：幂等创建/更新微光手记置顶说明帖；
# board_id 为板块 ID，author 为作者信息，无返回值。
def ensure_about_topic(
    bind: sa.Connection,
    board_id: int,
    author: dict[str, object],
) -> None:
    """Create or refresh the pinned guide topic for the memory-notes board."""
    existing = bind.execute(
        sa.select(topics.c.id)
        .where(
            topics.c.board_id == board_id,
            sa.or_(topics.c.slug == ABOUT_TOPIC_SLUG, topics.c.title == ABOUT_TOPIC_TITLE),
        )
        .order_by(topics.c.id)
        .limit(1)
    ).first()
    cooked_html = render_html(ABOUT_TOPIC_MARKDOWN)
    if existing:
        topic_id = int(existing.id)
        bind.execute(
            topics.update()
            .where(topics.c.id == topic_id)
            .values(
                title=ABOUT_TOPIC_TITLE,
                title_localizations=None,
                slug=ABOUT_TOPIC_SLUG,
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
                raw_md=ABOUT_TOPIC_MARKDOWN,
                cooked_html=cooked_html,
                updated_at=now(),
            )
        )
        sync_search_document(bind, topic_id, board_id, author)
        return

    bind.execute(
        topics.insert().values(
            board_id=board_id,
            user_id=author["id"],
            title=ABOUT_TOPIC_TITLE,
            title_localizations=None,
            slug=ABOUT_TOPIC_SLUG,
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
            sa.select(topics.c.id)
            .where(topics.c.board_id == board_id, topics.c.slug == ABOUT_TOPIC_SLUG)
            .limit(1)
        ).scalar_one()
    )
    bind.execute(
        posts.insert().values(
            topic_id=topic_id,
            user_id=author["id"],
            parent_id=None,
            post_number=1,
            raw_md=ABOUT_TOPIC_MARKDOWN,
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
    sync_search_document(bind, topic_id, board_id, author)


# render_html 用途：把置顶说明帖 Markdown 转为简单安全 HTML；raw_md 为 Markdown，返回 HTML 字符串。
def render_html(raw_md: str) -> str:
    """Render the migration guide markdown into minimal escaped HTML."""
    paragraphs = []
    for line in raw_md.splitlines():
        if not line.strip():
            continue
        if line.startswith("# "):
            paragraphs.append(f"<h1>{html.escape(line[2:])}</h1>")
        elif line.startswith("## "):
            paragraphs.append(f"<h2>{html.escape(line[3:])}</h2>")
        elif line.startswith("- "):
            paragraphs.append(f"<p>{html.escape(line)}</p>")
        else:
            paragraphs.append(f"<p>{html.escape(line)}</p>")
    return "\n".join(paragraphs)


# sync_search_document 用途：同步置顶说明帖搜索索引行；
# topic_id/board_id 为数据库 ID，author 为作者信息。
def sync_search_document(
    bind: sa.Connection,
    topic_id: int,
    board_id: int,
    author: dict[str, object],
) -> None:
    """Upsert the search document for the memory-notes guide topic when available."""
    if not table_exists(bind, "search_documents"):
        return
    values = {
        "topic_id": topic_id,
        "board_id": board_id,
        "author_id": author["id"],
        "author_username": author["username"],
        "topic_status": "open",
        "title": ABOUT_TOPIC_TITLE,
        "body": ABOUT_TOPIC_MARKDOWN,
        "tags_text": str(author["username"]),
        "indexed_at": now(),
        "updated_at": now(),
    }
    existing = bind.execute(
        sa.select(search_documents.c.id)
        .where(search_documents.c.topic_id == topic_id)
        .limit(1)
    ).first()
    if existing:
        bind.execute(
            search_documents.update()
            .where(search_documents.c.id == existing.id)
            .values(**values)
        )
    else:
        bind.execute(search_documents.insert().values(**values, created_at=now()))


# recompute_board_counters 用途：重算目标板块主题/帖子计数；board_id 为板块 ID，无返回值。
def recompute_board_counters(bind: sa.Connection, board_id: int) -> None:
    """Recompute topic and post counters for the changed board."""
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
    bind.execute(
        boards.update()
        .where(boards.c.id == board_id)
        .values(topic_count=topic_count, post_count=post_count, updated_at=now())
    )

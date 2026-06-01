"""add memory notes board

Revision ID: 0047_add_memory_notes_board
Revises: 0046_add_comics_board
Create Date: 2026-06-01
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa

from alembic import op

revision: str = "0047_add_memory_notes_board"
down_revision: str | None = "0046_add_comics_board"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

BOARD_SLUG = "memory-notes"
BOARD_NAME = "微光手记"
BOARD_DESCRIPTION = "存放旧日文字、每日金句、网络记忆、生活片段和短篇感想。"
BOARD_COLOR = "#F59E0B"
POST_TEMPLATE = """## 想留下来的片段

（贴上这次想保存的旧日文字、金句、截图文字或记忆片段。）

## 当时为什么触动我

（写一两句背景：什么时候看到/写下，为什么觉得值得留下。）

## 现在回头看

（补充现在的想法、变化，或想和大家聊的方向。）
"""

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


# upgrade 用途：幂等创建/更新公共「微光手记」板块、默认 owner 关系和新主题模板；
# 无返回值，副作用是写入业务数据。
def upgrade() -> None:
    """Create or refresh the public memory-notes board and its post template."""
    bind = op.get_bind()
    if not table_exists(bind, "boards") or not table_exists(bind, "board_members"):
        return
    if bind.execute(sa.select(sa.func.count()).select_from(boards)).scalar_one() == 0:
        return

    author = select_migration_author(bind)
    board_id = ensure_board(bind, int(author["id"]) if author else None)
    if author is not None:
        ensure_board_owner_membership(bind, board_id, int(author["id"]))


# downgrade 用途：数据迁移不删除用户可能已使用的「微光手记」板块；无参数无返回值，无副作用。
def downgrade() -> None:
    """Keep created content in place when downgrading to avoid deleting user data."""
    return


# now 用途：统一生成迁移写入时间；无参数，返回当前 UTC 时间。
def now() -> datetime:
    """Return the current UTC timestamp for inserted/updated rows."""
    return datetime.now(UTC)


# table_exists 用途：检查目标表是否存在；table_name 为表名，返回布尔值避免空库迁移失败。
def table_exists(bind: sa.Connection, table_name: str) -> bool:
    """Check whether a table exists before running data-migration statements."""
    return sa.inspect(bind).has_table(table_name)


# select_migration_author 用途：选择可作为板块 owner 的活跃用户；无用户表或无活跃用户时返回 None。
def select_migration_author(bind: sa.Connection) -> dict[str, object] | None:
    """Select the preferred active user to own the seeded memory-notes board."""
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


# ensure_board 用途：按 slug 幂等创建或更新「微光手记」板块；owner_id 可为空，返回板块 ID。
def ensure_board(bind: sa.Connection, owner_id: int | None) -> int:
    """Create or update the public memory-notes board and return its database id."""
    row = bind.execute(sa.select(boards).where(boards.c.slug == BOARD_SLUG).limit(1)).first()
    if row:
        values: dict[str, object] = {
            "name": BOARD_NAME,
            "name_localizations": None,
            "description": BOARD_DESCRIPTION,
            "color": BOARD_COLOR,
            "visibility": "public",
            "required_tags": None,
            "allowed_tags": None,
            "post_template": POST_TEMPLATE,
            "default_notification_level": "normal",
            "default_sort": "latest",
            "updated_at": now(),
        }
        if owner_id is not None and row.owner_id is None:
            values["owner_id"] = owner_id
        bind.execute(boards.update().where(boards.c.id == row.id).values(**values))
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
            post_template=POST_TEMPLATE,
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


# ensure_board_owner_membership 用途：保证迁移作者关注/管理该板块；
# board_id/user_id 为数据库 ID，无返回值。
def ensure_board_owner_membership(bind: sa.Connection, board_id: int, user_id: int) -> None:
    """Ensure the selected migration author is an owner member of the memory-notes board."""
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
    bind.execute(
        boards.update()
        .where(boards.c.id == board_id)
        .values(follower_count=boards.c.follower_count + 1, updated_at=now())
    )

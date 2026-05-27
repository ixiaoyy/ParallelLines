"""cleanup demo users and promote real admins

Revision ID: 0044_cleanup_demo_users
Revises: 0043_restore_official_guides
Create Date: 2026-05-27
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa

from alembic import op

revision: str = "0044_cleanup_demo_users"
down_revision: str | None = "0043_restore_official_guides"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PRIMARY_ADMIN_USERNAME = "多动脑子z"
PRIMARY_ADMIN_EMAIL = "364437340@qq.com"
SECONDARY_ADMIN_USERNAME = "大脚板"
SECONDARY_ADMIN_EMAIL = "phpxiaoyz@gmail.com"
MAX_LEVEL = 10
MAX_LEVEL_EXPERIENCE = 6000
MAX_TRUST_LEVEL = 4


users = sa.table(
    "users",
    sa.column("id", sa.BigInteger()),
    sa.column("username", sa.String()),
    sa.column("email", sa.String()),
    sa.column("role", sa.String()),
    sa.column("level", sa.Integer()),
    sa.column("points_balance", sa.Integer()),
    sa.column("experience_total", sa.Integer()),
    sa.column("trust_level", sa.Integer()),
    sa.column("trust_level_changed_at", sa.DateTime(timezone=True)),
    sa.column("status", sa.String()),
    sa.column("updated_at", sa.DateTime(timezone=True)),
)
boards = sa.table(
    "boards",
    sa.column("id", sa.BigInteger()),
    sa.column("owner_id", sa.BigInteger()),
    sa.column("topic_count", sa.Integer()),
    sa.column("post_count", sa.Integer()),
    sa.column("follower_count", sa.Integer()),
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
    sa.column("deleted_at", sa.DateTime(timezone=True)),
    sa.column("updated_at", sa.DateTime(timezone=True)),
)
posts = sa.table(
    "posts",
    sa.column("id", sa.BigInteger()),
    sa.column("topic_id", sa.BigInteger()),
    sa.column("user_id", sa.BigInteger()),
    sa.column("deleted_at", sa.DateTime(timezone=True)),
    sa.column("updated_at", sa.DateTime(timezone=True)),
)
search_documents = sa.table(
    "search_documents",
    sa.column("id", sa.BigInteger()),
    sa.column("author_id", sa.BigInteger()),
    sa.column("author_username", sa.String()),
    sa.column("updated_at", sa.DateTime(timezone=True)),
)


def upgrade() -> None:
    bind = op.get_bind()
    required_tables = ("users", "topics", "posts", "boards", "board_members")
    if any(not table_exists(bind, table_name) for table_name in required_tables):
        return

    primary_id = find_user_id(bind, PRIMARY_ADMIN_USERNAME, PRIMARY_ADMIN_EMAIL)
    secondary_id = find_user_id(bind, SECONDARY_ADMIN_USERNAME, SECONDARY_ADMIN_EMAIL)
    if primary_id is None or secondary_id is None or primary_id == secondary_id:
        return

    real_user_ids = (primary_id, secondary_id)
    promote_real_admins(bind, primary_id, secondary_id)
    reassign_content(bind, primary_id, real_user_ids)
    ensure_real_admin_board_memberships(bind, real_user_ids)
    delete_non_real_users(bind, real_user_ids)
    recompute_board_counters(bind)


def downgrade() -> None:
    return


def now() -> datetime:
    return datetime.now(UTC)


def table_exists(bind: sa.Connection, table_name: str) -> bool:
    return sa.inspect(bind).has_table(table_name)


def find_user_id(bind: sa.Connection, username: str, email: str) -> int | None:
    row = bind.execute(
        sa.select(users.c.id)
        .where(sa.or_(users.c.username == username, users.c.email == email))
        .order_by(
            sa.case(
                (users.c.email == email, 0),
                (users.c.username == username, 1),
                else_=2,
            ),
            users.c.id,
        )
        .limit(1)
    ).first()
    return int(row.id) if row else None


def promote_real_admins(bind: sa.Connection, primary_id: int, secondary_id: int) -> None:
    current_time = now()
    bind.execute(
        users.update()
        .where(users.c.id == primary_id)
        .values(
            username=PRIMARY_ADMIN_USERNAME,
            email=PRIMARY_ADMIN_EMAIL,
            role="admin",
            level=MAX_LEVEL,
            points_balance=sa.func.greatest(users.c.points_balance, MAX_LEVEL_EXPERIENCE),
            experience_total=sa.func.greatest(users.c.experience_total, MAX_LEVEL_EXPERIENCE),
            trust_level=MAX_TRUST_LEVEL,
            trust_level_changed_at=current_time,
            status="active",
            updated_at=current_time,
        )
    )
    bind.execute(
        users.update()
        .where(users.c.id == secondary_id)
        .values(
            username=SECONDARY_ADMIN_USERNAME,
            email=SECONDARY_ADMIN_EMAIL,
            role="admin",
            level=MAX_LEVEL,
            points_balance=sa.func.greatest(users.c.points_balance, MAX_LEVEL_EXPERIENCE),
            experience_total=sa.func.greatest(users.c.experience_total, MAX_LEVEL_EXPERIENCE),
            trust_level=MAX_TRUST_LEVEL,
            trust_level_changed_at=current_time,
            status="active",
            updated_at=current_time,
        )
    )


def reassign_content(bind: sa.Connection, primary_id: int, real_user_ids: tuple[int, int]) -> None:
    current_time = now()
    bind.execute(
        topics.update()
        .where(topics.c.user_id.not_in(real_user_ids))
        .values(user_id=primary_id, updated_at=current_time)
    )
    bind.execute(
        posts.update()
        .where(posts.c.user_id.not_in(real_user_ids))
        .values(user_id=primary_id, updated_at=current_time)
    )
    bind.execute(boards.update().values(owner_id=primary_id, updated_at=current_time))
    if table_exists(bind, "search_documents"):
        bind.execute(
            search_documents.update().values(
                author_id=primary_id,
                author_username=PRIMARY_ADMIN_USERNAME,
                updated_at=current_time,
            )
        )


def ensure_real_admin_board_memberships(
    bind: sa.Connection,
    real_user_ids: tuple[int, int],
) -> None:
    for board_id in bind.execute(sa.select(boards.c.id)).scalars().all():
        for user_id in real_user_ids:
            existing = bind.execute(
                sa.select(board_members.c.id)
                .where(board_members.c.board_id == board_id, board_members.c.user_id == user_id)
                .limit(1)
            ).first()
            if existing:
                bind.execute(
                    board_members.update()
                    .where(board_members.c.id == existing.id)
                    .values(role="owner", notification_level="watching")
                )
            else:
                bind.execute(
                    board_members.insert().values(
                        board_id=board_id,
                        user_id=user_id,
                        role="owner",
                        notification_level="watching",
                        joined_at=now(),
                    )
                )


def delete_non_real_users(bind: sa.Connection, real_user_ids: tuple[int, int]) -> None:
    bind.execute(users.delete().where(users.c.id.not_in(real_user_ids)))


def recompute_board_counters(bind: sa.Connection) -> None:
    current_time = now()
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
                updated_at=current_time,
            )
        )

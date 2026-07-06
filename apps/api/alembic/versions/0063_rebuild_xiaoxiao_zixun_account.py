"""rebuild xiaoxiao zixun account

Revision ID: 0063_rebuild_xiaoxiao_zixun_account
Revises: 0062_soft_delete_frontier_sources
Create Date: 2026-07-06
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa

from alembic import op

revision: str = "0063_rebuild_xiaoxiao_zixun_account"
down_revision: str | None = "0062_soft_delete_frontier_sources"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NEWS_USERNAME = "小小资讯"
LEGACY_NEWS_EMAIL = "frontier-news-bot@parallellines.local"
NEWS_EMAIL = "xiaoxiao-zixun@pingxingxian.space"
NEWS_AVATAR_URL = "/avatars/xiaoxiao-zixun.png"
NEWS_PASSWORD_HASH = (
    "$argon2id$v=19$m=65536,t=3,p=4$MayotJlSrXQ+5vEo6hhv9g"
    "$1sbvN4pn2shulw8Vg1BJhx4lTUeUzHleM7MUHJ7dcuo"
)
NEWS_BIO = "小小资讯，专注 AI 前沿与热点整理。"

users = sa.table(
    "users",
    sa.column("id", sa.BigInteger()),
    sa.column("username", sa.String()),
    sa.column("email", sa.String()),
    sa.column("hashed_password", sa.String()),
    sa.column("avatar_url", sa.String()),
    sa.column("display_name", sa.String()),
    sa.column("bio", sa.Text()),
    sa.column("website_url", sa.String()),
    sa.column("location", sa.String()),
    sa.column("role", sa.String()),
    sa.column("level", sa.Integer()),
    sa.column("trust_level", sa.Integer()),
    sa.column("trust_level_changed_at", sa.DateTime(timezone=True)),
    sa.column("points_balance", sa.Integer()),
    sa.column("experience_total", sa.Integer()),
    sa.column("status", sa.String()),
    sa.column("last_seen_at", sa.DateTime(timezone=True)),
    sa.column("two_factor_enabled", sa.Boolean()),
    sa.column("two_factor_secret", sa.String()),
    sa.column("profile_visibility", sa.String()),
    sa.column("show_activity", sa.Boolean()),
    sa.column("interface_theme", sa.String()),
    sa.column("locale", sa.String()),
    sa.column("created_at", sa.DateTime(timezone=True)),
    sa.column("updated_at", sa.DateTime(timezone=True)),
)

email_verification_codes = sa.table(
    "email_verification_codes",
    sa.column("user_id", sa.BigInteger()),
)

user_security_tokens = sa.table(
    "user_security_tokens",
    sa.column("user_id", sa.BigInteger()),
)

user_sessions = sa.table(
    "user_sessions",
    sa.column("user_id", sa.BigInteger()),
)

user_recovery_codes = sa.table(
    "user_recovery_codes",
    sa.column("user_id", sa.BigInteger()),
)


def upgrade() -> None:
    """Rebuild the Xiaoxiao News persona as a login-capable public account.

    Key parameters: none. Return value: none. Side effect: inserts or updates
    the `小小资讯` row to a response-schema-valid email, resets login/security
    material, and preserves authored content by keeping the same user id.
    """

    bind = op.get_bind()
    if not table_exists(bind, "users"):
        return
    now = current_utc()
    existing = resolve_news_user(bind)
    if existing is None:
        bind.execute(
            users.insert().values(
                username=NEWS_USERNAME,
                email=NEWS_EMAIL,
                hashed_password=NEWS_PASSWORD_HASH,
                avatar_url=NEWS_AVATAR_URL,
                display_name=NEWS_USERNAME,
                bio=NEWS_BIO,
                website_url=None,
                location=None,
                role="user",
                level=0,
                trust_level=0,
                trust_level_changed_at=None,
                points_balance=0,
                experience_total=0,
                status="active",
                last_seen_at=None,
                two_factor_enabled=False,
                two_factor_secret=None,
                profile_visibility="public",
                show_activity=True,
                interface_theme="system",
                locale="zh-CN",
                created_at=now,
                updated_at=now,
            )
        )
        return

    bind.execute(
        users.update()
        .where(users.c.id == existing.id)
        .values(
            username=NEWS_USERNAME,
            email=NEWS_EMAIL,
            hashed_password=NEWS_PASSWORD_HASH,
            avatar_url=NEWS_AVATAR_URL,
            display_name=NEWS_USERNAME,
            bio=NEWS_BIO,
            website_url=None,
            location=None,
            role="user",
            status="active",
            last_seen_at=None,
            two_factor_enabled=False,
            two_factor_secret=None,
            profile_visibility="public",
            show_activity=True,
            interface_theme="system",
            locale="zh-CN",
            updated_at=now,
        )
    )
    delete_login_artifacts(bind, int(existing.id))


def downgrade() -> None:
    """Restore the previous local-only email while keeping authored content.

    Key parameters: none. Return value: none. Side effect: reverts only the
    Xiaoxiao News account email when no conflicting legacy row exists.
    """

    bind = op.get_bind()
    if not table_exists(bind, "users"):
        return
    existing = bind.execute(
        sa.select(users.c.id).where(users.c.username == NEWS_USERNAME)
    ).first()
    if existing is None:
        return
    conflict = bind.execute(
        sa.select(users.c.id).where(users.c.email == LEGACY_NEWS_EMAIL)
    ).first()
    if conflict is not None and int(conflict.id) != int(existing.id):
        raise RuntimeError("Legacy Xiaoxiao News email already belongs to another user")
    bind.execute(
        users.update()
        .where(users.c.id == existing.id)
        .values(email=LEGACY_NEWS_EMAIL, updated_at=current_utc())
    )


def resolve_news_user(bind: sa.Connection):
    """Resolve the one canonical Xiaoxiao News user row or raise on conflicts.

    Key parameter `bind` is the migration connection. Return value: one row or
    `None`. Side effect: reads existing user rows and aborts on ambiguous ids.
    """

    rows = bind.execute(
        sa.select(users.c.id, users.c.username, users.c.email).where(
            sa.or_(
                users.c.username == NEWS_USERNAME,
                users.c.email == LEGACY_NEWS_EMAIL,
                users.c.email == NEWS_EMAIL,
            )
        )
    ).fetchall()
    if not rows:
        return None
    ids = {int(row.id) for row in rows}
    if len(ids) != 1:
        raise RuntimeError(
            "Xiaoxiao News identity conflicts with multiple users: "
            + ", ".join(f"id={row.id},username={row.username},email={row.email}" for row in rows)
        )
    row = rows[0]
    if row.username != NEWS_USERNAME and row.email not in {LEGACY_NEWS_EMAIL, NEWS_EMAIL}:
        raise RuntimeError(
            "Xiaoxiao News target row does not match expected username/email: "
            f"id={row.id}, username={row.username}, email={row.email}"
        )
    conflict = bind.execute(
        sa.select(users.c.id).where(
            sa.and_(users.c.email == NEWS_EMAIL, users.c.id != row.id)
        )
    ).first()
    if conflict is not None:
        raise RuntimeError("Xiaoxiao News target email already belongs to another user")
    return row


def delete_login_artifacts(bind: sa.Connection, user_id: int) -> None:
    """Delete short-lived auth artifacts so the rebuilt account starts clean.

    Key parameters are the migration connection and `user_id`. Return value:
    none. Side effect: removes pending verifications, sessions, recovery codes,
    and security tokens for this one user when the tables exist.
    """

    delete_rows_if_table_exists(bind, "email_verification_codes", email_verification_codes, user_id)
    delete_rows_if_table_exists(bind, "user_security_tokens", user_security_tokens, user_id)
    delete_rows_if_table_exists(bind, "user_sessions", user_sessions, user_id)
    delete_rows_if_table_exists(bind, "user_recovery_codes", user_recovery_codes, user_id)


def delete_rows_if_table_exists(
    bind: sa.Connection,
    table_name: str,
    table: sa.Table,
    user_id: int,
) -> None:
    """Delete one user's rows from an optional auth-related table.

    Key parameters are the migration connection, physical table name, SQLAlchemy
    lightweight table object, and `user_id`. Return value: none. Side effect:
    issues one delete statement when the table exists.
    """

    if not table_exists(bind, table_name):
        return
    bind.execute(table.delete().where(table.c.user_id == user_id))


def table_exists(bind: sa.Connection, table_name: str) -> bool:
    """Check table presence before running data-migration statements.

    Key parameters: `bind` is the migration connection and `table_name` is the
    table name. Return value: true when the table exists. Side effect: reads
    database metadata only.
    """

    return sa.inspect(bind).has_table(table_name)


def current_utc() -> datetime:
    """Return a timezone-aware UTC timestamp for migration writes.

    Key parameters: none. Return value: current UTC datetime. Side effect:
    none.
    """

    return datetime.now(UTC)

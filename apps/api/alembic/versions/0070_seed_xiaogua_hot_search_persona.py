"""seed xiaogua hot search persona and tag

Revision ID: 0070_seed_xiaogua_hot_search_persona
Revises: 0069_daily_report_assistant
Create Date: 2026-07-27
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa

from alembic import op

revision: str = "0070_seed_xiaogua_hot_search_persona"
down_revision: str | None = "0069_daily_report_assistant"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

USERNAME = "小瓜同学"
EMAIL = "xiaogua@pingxingxian.space"
AVATAR_URL = "/avatars/xiaogua.png"
BIO = "每天逛一圈热搜，只捡有意思又能聊的。"
PASSWORD_HASH = (
    "$argon2id$v=19$m=65536,t=3,p=4$5aCoItTwPRL0PuHLIhy0VA"
    "$x6YNtM+YCwnu8Sub6fQHFQ7EQ6wqAHj4mu5xVZHGiPk"
)
TAG_NAME = "热搜闲聊"
TAG_SLUG = "hot-search-chat"

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
    sa.column("is_persona", sa.Boolean()),
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

tags = sa.table(
    "tags",
    sa.column("id", sa.BigInteger()),
    sa.column("name", sa.String()),
    sa.column("slug", sa.String()),
    sa.column("topic_count", sa.Integer()),
    sa.column("created_at", sa.DateTime(timezone=True)),
    sa.column("updated_at", sa.DateTime(timezone=True)),
)


def upgrade() -> None:
    """Upsert the dedicated hot-search persona and its forum tag.

    Key parameters: none. Return value: none. Side effect: writes one ordinary
    persona user and one tag when their backing tables exist.
    """

    bind = op.get_bind()
    current_time = current_utc()
    if table_exists(bind, "users"):
        upsert_persona(bind, current_time)
    if table_exists(bind, "tags"):
        upsert_tag(bind, current_time)


def downgrade() -> None:
    """Leave the persona and tag in place to preserve authored content.

    Key parameters: none. Return value: none. Side effect: intentionally none.
    """


def upsert_persona(bind: sa.Connection, current_time: datetime) -> None:
    """Create or refresh the dedicated hot-search persona.

    Key parameters are the Alembic connection and timestamp. Return value:
    none. Side effect: inserts or updates only the exact username/email pair.
    """

    existing = resolve_persona_user(bind)
    if existing is None:
        bind.execute(
            users.insert().values(
                username=USERNAME,
                email=EMAIL,
                hashed_password=PASSWORD_HASH,
                avatar_url=AVATAR_URL,
                display_name=USERNAME,
                bio=BIO,
                website_url=None,
                location=None,
                role="user",
                level=0,
                trust_level=0,
                trust_level_changed_at=None,
                points_balance=0,
                experience_total=0,
                status="active",
                is_persona=True,
                last_seen_at=None,
                two_factor_enabled=False,
                two_factor_secret=None,
                profile_visibility="public",
                show_activity=True,
                interface_theme="system",
                locale="zh-CN",
                created_at=current_time,
                updated_at=current_time,
            )
        )
        return

    if existing.role == "admin":
        raise RuntimeError(f"Refusing to rewrite admin account as persona: {USERNAME}")
    bind.execute(
        users.update()
        .where(users.c.id == existing.id)
        .values(
            hashed_password=PASSWORD_HASH,
            avatar_url=AVATAR_URL,
            display_name=USERNAME,
            bio=BIO,
            role="user",
            status="active",
            is_persona=True,
            last_seen_at=None,
            two_factor_enabled=False,
            two_factor_secret=None,
            profile_visibility="public",
            show_activity=True,
            interface_theme="system",
            locale="zh-CN",
            updated_at=current_time,
        )
    )


def resolve_persona_user(bind: sa.Connection):
    """Resolve the exact persona row or fail on username/email conflicts.

    Key parameter is the Alembic connection. Return value is one matching row
    or `None`. Side effect: reads users only.
    """

    rows = bind.execute(
        sa.select(users.c.id, users.c.username, users.c.email, users.c.role).where(
            sa.or_(users.c.username == USERNAME, users.c.email == EMAIL)
        )
    ).fetchall()
    if not rows:
        return None
    ids = {int(row.id) for row in rows}
    if len(ids) != 1:
        raise RuntimeError(
            f"Persona identity conflict for {USERNAME}: "
            + ", ".join(f"id={row.id},username={row.username},email={row.email}" for row in rows)
        )
    row = rows[0]
    if row.username != USERNAME or row.email != EMAIL:
        raise RuntimeError(
            "Persona username/email must belong to the same exact row: "
            f"id={row.id},username={row.username},email={row.email}"
        )
    return row


def upsert_tag(bind: sa.Connection, current_time: datetime) -> None:
    """Create the dedicated hot-search tag or validate its existing identity.

    Key parameters are the Alembic connection and timestamp. Return value:
    none. Side effect: inserts the tag when absent.
    """

    rows = bind.execute(
        sa.select(tags.c.id, tags.c.name, tags.c.slug).where(
            sa.or_(tags.c.name == TAG_NAME, tags.c.slug == TAG_SLUG)
        )
    ).fetchall()
    if not rows:
        bind.execute(
            tags.insert().values(
                name=TAG_NAME,
                slug=TAG_SLUG,
                topic_count=0,
                created_at=current_time,
                updated_at=current_time,
            )
        )
        return
    ids = {int(row.id) for row in rows}
    row = rows[0]
    if len(ids) != 1 or row.name != TAG_NAME or row.slug != TAG_SLUG:
        raise RuntimeError(
            f"Tag identity conflict for {TAG_NAME}/{TAG_SLUG}: "
            + ", ".join(f"id={item.id},name={item.name},slug={item.slug}" for item in rows)
        )


def table_exists(bind: sa.Connection, table_name: str) -> bool:
    """Return whether one table exists before optional data statements run."""

    return sa.inspect(bind).has_table(table_name)


def current_utc() -> datetime:
    """Return a timezone-aware UTC timestamp for migration writes."""

    return datetime.now(UTC)

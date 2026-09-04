"""seed page margin light daily reading persona

Revision ID: 0071_seed_page_margin_light_persona
Revises: 0070_seed_xiaogua_hot_search_persona
Create Date: 2026-08-12
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa

from alembic import op

revision: str = "0071_seed_page_margin_light_persona"
down_revision: str | None = "0070_seed_xiaogua_hot_search_persona"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

USERNAME = "页边有光"
EMAIL = "page-margin-light@pingxingxian.space"
AVATAR_URL = "/avatars/page-margin-light.png"
BIO = "动画游戏都玩一点，偶尔记下读完几页后的想法。"
PASSWORD_HASH = (
    "$argon2id$v=19$m=65536,t=3,p=4$Siah7iYvx47OTQwcWB6fNA"
    "$CCYpHyqXc+R2G2uVXAjrVpLmO5bg+WINOcB+n9JkDUg"
)

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


def upgrade() -> None:
    """Upsert the login-capable daily-reading persona when users exist.

    Key parameters: none. Return value: none. Side effect: inserts or refreshes
    exactly one ordinary persona account without changing database structure.
    """

    bind = op.get_bind()
    if table_exists(bind, "users"):
        upsert_persona(bind, datetime.now(UTC))


def downgrade() -> None:
    """Leave the persona in place so authored forum content keeps its owner.

    Key parameters: none. Return value: none. Side effect: intentionally none.
    """


def upsert_persona(bind: sa.Connection, current_time: datetime) -> None:
    """Create or refresh the dedicated daily-reading persona.

    Key parameters are the Alembic connection and write timestamp. Return value:
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
    or ``None``. Side effect: reads only the users identity columns.
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
            + ", ".join(
                f"id={row.id},username={row.username},email={row.email}" for row in rows
            )
        )
    row = rows[0]
    if row.username != USERNAME or row.email != EMAIL:
        raise RuntimeError(
            "Persona username/email must belong to the same exact row: "
            f"id={row.id},username={row.username},email={row.email}"
        )
    return row


def table_exists(bind: sa.Connection, table_name: str) -> bool:
    """Return whether a named table exists without changing schema or data."""

    return sa.inspect(bind).has_table(table_name)

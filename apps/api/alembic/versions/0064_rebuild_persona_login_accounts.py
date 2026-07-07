"""rebuild persona login accounts

Revision ID: 0064_rebuild_persona_login_accounts
Revises: 0063_rebuild_xiaoxiao_zixun_account
Create Date: 2026-07-07
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import NamedTuple

import sqlalchemy as sa

from alembic import op

revision: str = "0064_rebuild_persona_login_accounts"
down_revision: str | None = "0063_rebuild_xiaoxiao_zixun_account"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PERSONA_PASSWORD_HASH = (
    "$argon2id$v=19$m=65536,t=3,p=4$er4+3q+8wZXh23w1LVFBRQ"
    "$t8lGosc0QpE/Rhq/Hjj6YY71D/xG7EM4Sm99Tuh5Bv8"
)


class PersonaLoginSpec(NamedTuple):
    """Describe one seeded persona account that should be login-capable."""

    username: str
    email: str
    legacy_emails: tuple[str, ...]
    bio: str
    avatar_url: str | None = None


PERSONA_SPECS: tuple[PersonaLoginSpec, ...] = (
    PersonaLoginSpec(
        "不吃香菜的猫",
        "no-coriander-cat@pingxingxian.space",
        ("no_coriander_cat@parallellines.local",),
        "不太会写长篇，想到什么说什么。",
    ),
    PersonaLoginSpec(
        "一杯冰美式续命",
        "iced-americano@pingxingxian.space",
        ("iced_americano@parallellines.local",),
        "靠咖啡和一点点好心情撑住工作日。",
    ),
    PersonaLoginSpec(
        "外卖备注写错了",
        "waimai-note@pingxingxian.space",
        ("waimai_note@parallellines.local",),
        "经常在小事上翻车，也经常被小事治好。",
    ),
    PersonaLoginSpec(
        "冰箱里还有半瓶可乐",
        "half-cola@pingxingxian.space",
        ("half_cola@parallellines.local",),
        "普通生活记录员。",
    ),
    PersonaLoginSpec(
        "刚下班别催",
        "offwork-no-push@pingxingxian.space",
        ("offwork_no_push@parallellines.local",),
        "下班后慢半拍回复。",
    ),
    PersonaLoginSpec(
        "雾里看山",
        "fog-mountain@pingxingxian.space",
        ("fog_mountain@parallellines.local",),
        "喜欢慢慢读、慢慢走。",
    ),
    PersonaLoginSpec(
        "远山便利店",
        "yuanshan-shop@pingxingxian.space",
        ("yuanshan_shop@parallellines.local",),
        "收藏一些顺手的小工具。",
    ),
    PersonaLoginSpec(
        "老槐",
        "old-huai-tree@pingxingxian.space",
        ("old_huai_tree@parallellines.local",),
        "偶尔认真，偶尔摆烂。",
    ),
    PersonaLoginSpec(
        "oldhuai",
        "oldhuai@pingxingxian.space",
        ("oldhuai@parallellines.local",),
        "路过看看，也会留两句。",
    ),
    PersonaLoginSpec(
        "huai_07",
        "huai-07@pingxingxian.space",
        ("huai_07@parallellines.local",),
        "对产品细节有点挑。",
    ),
    PersonaLoginSpec(
        "Aki_慢慢来",
        "aki-slow@pingxingxian.space",
        ("aki_slow@parallellines.local",),
        "慢慢做也算做。",
    ),
    PersonaLoginSpec(
        "momo-离线",
        "momo-offline@pingxingxian.space",
        ("momo_offline@parallellines.local",),
        "不在线的时候比较像自己。",
    ),
    PersonaLoginSpec(
        "kk不在线",
        "kk-offline@pingxingxian.space",
        ("kk_offline@parallellines.local",),
        "收藏夹总是爆满。",
    ),
    PersonaLoginSpec(
        "Nate_路过",
        "nate-passby@pingxingxian.space",
        ("nate_passby@parallellines.local",),
        "路过补充一点点。",
    ),
    PersonaLoginSpec(
        "小K_再看看",
        "xiaok-look@pingxingxian.space",
        ("xiaok_look@parallellines.local",),
        "先看看，再决定。",
    ),
    PersonaLoginSpec(
        "rain_404",
        "rain404@pingxingxian.space",
        ("rain404@parallellines.local",),
        "不太会坚持，但还在试。",
    ),
    PersonaLoginSpec(
        "zzZ_醒了",
        "zzz-awake@pingxingxian.space",
        ("zzz_awake@parallellines.local",),
        "每天都在和闹钟协商。",
    ),
    PersonaLoginSpec(
        "beta路人",
        "beta-passer@pingxingxian.space",
        ("beta_passer@parallellines.local",),
        "偶尔捡到一些省钱小提醒。",
    ),
    PersonaLoginSpec(
        "loop_一下",
        "loop-once@pingxingxian.space",
        ("loop_once@parallellines.local",),
        "喜欢把问题绕回来再看一遍。",
    ),
    PersonaLoginSpec(
        "穿猫的靴子",
        "cat-boots@pingxingxian.space",
        ("cat_boots@parallellines.local",),
        "写点看到的变化和小趋势。",
    ),
    PersonaLoginSpec(
        "小漫家",
        "xiaomanjia@pingxingxian.space",
        ("xiaomanjia@parallellines.cn",),
        "每天翻几页漫画，看到好玩的分镜就想分享。",
    ),
    PersonaLoginSpec(
        "小小资讯",
        "xiaoxiao-zixun@pingxingxian.space",
        ("frontier-news-bot@parallellines.local",),
        "小小资讯，专注 AI 前沿与热点整理。",
        "/avatars/xiaoxiao-zixun.png",
    ),
    PersonaLoginSpec(
        "小小鸡仔",
        "xiaoxiao-jizai@pingxingxian.space",
        (),
        "小小鸡仔，偶尔啄两句。",
        "/avatars/xiaoxiao-jizai.png",
    ),
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
    """Rebuild all seeded persona accounts as login-capable ordinary users.

    Key parameters: none. Return value: none. Side effect: inserts or updates
    only the configured persona rows, refuses admin-role collisions, and clears
    stale login artifacts after password/email changes.
    """

    bind = op.get_bind()
    if not table_exists(bind, "users"):
        return
    current_time = current_utc()
    for spec in PERSONA_SPECS:
        upsert_persona(bind, spec, current_time)


def downgrade() -> None:
    """Leave persona accounts in place when downgrading.

    Key parameters: none. Return value: none. Side effect: intentionally none
    so authored topics/posts keep valid user references.
    """


def upsert_persona(bind: sa.Connection, spec: PersonaLoginSpec, current_time: datetime) -> None:
    """Insert or update one configured persona login account.

    Key parameters are the Alembic connection, persona spec, and timestamp.
    Return value: none. Side effect: writes the user row and clears stale auth
    artifacts for updated rows.
    """

    existing = resolve_persona_user(bind, spec)
    if existing is None:
        bind.execute(
            users.insert().values(
                username=spec.username,
                email=spec.email,
                hashed_password=PERSONA_PASSWORD_HASH,
                avatar_url=spec.avatar_url,
                display_name=spec.username,
                bio=spec.bio,
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
                created_at=current_time,
                updated_at=current_time,
            )
        )
        return

    if existing.role == "admin":
        raise RuntimeError(f"Refusing to rewrite admin account as persona: {spec.username}")
    update_values: dict[str, object] = {
        "username": spec.username,
        "email": spec.email,
        "hashed_password": PERSONA_PASSWORD_HASH,
        "display_name": spec.username,
        "bio": spec.bio,
        "role": "user",
        "status": "active",
        "last_seen_at": None,
        "two_factor_enabled": False,
        "two_factor_secret": None,
        "profile_visibility": "public",
        "show_activity": True,
        "interface_theme": "system",
        "locale": "zh-CN",
        "updated_at": current_time,
    }
    if spec.avatar_url is not None:
        update_values["avatar_url"] = spec.avatar_url
    bind.execute(users.update().where(users.c.id == existing.id).values(**update_values))
    delete_login_artifacts(bind, int(existing.id))


def resolve_persona_user(bind: sa.Connection, spec: PersonaLoginSpec):
    """Resolve the existing row for one persona or fail on ambiguous matches.

    Key parameters are the Alembic connection and persona spec. Return value is
    an existing user row or `None`. Side effect: reads user rows only.
    """

    emails = (spec.email, *spec.legacy_emails)
    rows = bind.execute(
        sa.select(users.c.id, users.c.username, users.c.email, users.c.role).where(
            sa.or_(users.c.username == spec.username, users.c.email.in_(emails))
        )
    ).fetchall()
    if not rows:
        return None
    ids = {int(row.id) for row in rows}
    if len(ids) != 1:
        raise RuntimeError(
            f"Persona identity conflict for {spec.username}: "
            + ", ".join(f"id={row.id},username={row.username},email={row.email}" for row in rows)
        )
    row = rows[0]
    if row.username != spec.username and row.email == spec.email:
        raise RuntimeError(
            f"Persona target email already belongs to another username: "
            f"id={row.id},username={row.username},email={row.email}"
        )
    return row


def delete_login_artifacts(bind: sa.Connection, user_id: int) -> None:
    """Delete short-lived auth artifacts for one rebuilt persona account.

    Key parameters are the Alembic connection and `user_id`. Return value: none.
    Side effect: deletes sessions, tokens, verification codes, and recovery
    codes from optional auth-related tables when present.
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

    Key parameters are the Alembic connection, physical table name, lightweight
    table object, and `user_id`. Return value: none. Side effect: issues one
    delete statement when the table exists.
    """

    if not table_exists(bind, table_name):
        return
    bind.execute(table.delete().where(table.c.user_id == user_id))


def table_exists(bind: sa.Connection, table_name: str) -> bool:
    """Return whether a table exists before optional data statements run."""

    return sa.inspect(bind).has_table(table_name)


def current_utc() -> datetime:
    """Return a timezone-aware UTC timestamp for migration writes."""

    return datetime.now(UTC)

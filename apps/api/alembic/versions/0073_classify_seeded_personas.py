"""Classify project-owned seeded persona accounts.

Revision ID: 0073_classify_seeded_personas
Revises: 0072_add_user_persona_kind
Create Date: 2026-09-04
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import NamedTuple

import sqlalchemy as sa

from alembic import op

revision: str = "0073_classify_seeded_personas"
down_revision: str | None = "0072_add_user_persona_kind"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


class PersonaClassification(NamedTuple):
    """Describe one exact seeded identity and its approved public subtype."""

    username: str
    email: str
    kind: str


PERSONA_CLASSIFICATIONS: tuple[PersonaClassification, ...] = (
    PersonaClassification(
        "不吃香菜的猫", "no-coriander-cat@pingxingxian.space", "fictional"
    ),
    PersonaClassification(
        "一杯冰美式续命", "iced-americano@pingxingxian.space", "fictional"
    ),
    PersonaClassification("外卖备注写错了", "waimai-note@pingxingxian.space", "fictional"),
    PersonaClassification(
        "冰箱里还有半瓶可乐", "half-cola@pingxingxian.space", "fictional"
    ),
    PersonaClassification("刚下班别催", "offwork-no-push@pingxingxian.space", "fictional"),
    PersonaClassification("雾里看山", "fog-mountain@pingxingxian.space", "fictional"),
    PersonaClassification("远山便利店", "yuanshan-shop@pingxingxian.space", "fictional"),
    PersonaClassification("老槐", "old-huai-tree@pingxingxian.space", "fictional"),
    PersonaClassification("oldhuai", "oldhuai@pingxingxian.space", "fictional"),
    PersonaClassification("huai_07", "huai-07@pingxingxian.space", "fictional"),
    PersonaClassification("Aki_慢慢来", "aki-slow@pingxingxian.space", "fictional"),
    PersonaClassification("momo-离线", "momo-offline@pingxingxian.space", "fictional"),
    PersonaClassification("kk不在线", "kk-offline@pingxingxian.space", "fictional"),
    PersonaClassification("Nate_路过", "nate-passby@pingxingxian.space", "fictional"),
    PersonaClassification("小K_再看看", "xiaok-look@pingxingxian.space", "fictional"),
    PersonaClassification("rain_404", "rain404@pingxingxian.space", "fictional"),
    PersonaClassification("zzZ_醒了", "zzz-awake@pingxingxian.space", "fictional"),
    PersonaClassification("beta路人", "beta-passer@pingxingxian.space", "fictional"),
    PersonaClassification("loop_一下", "loop-once@pingxingxian.space", "fictional"),
    PersonaClassification("穿猫的靴子", "cat-boots@pingxingxian.space", "fictional"),
    PersonaClassification("小漫家", "xiaomanjia@pingxingxian.space", "fictional"),
    PersonaClassification(
        "小小资讯", "xiaoxiao-zixun@pingxingxian.space", "automation"
    ),
    PersonaClassification(
        "小小鸡仔", "xiaoxiao-jizai@pingxingxian.space", "editorial"
    ),
    PersonaClassification("小瓜同学", "xiaogua@pingxingxian.space", "editorial"),
    PersonaClassification(
        "页边有光", "page-margin-light@pingxingxian.space", "editorial"
    ),
    PersonaClassification(
        "今天也想早睡", "sleepy_today@parallellines.local", "fictional"
    ),
)

users = sa.table(
    "users",
    sa.column("username", sa.String()),
    sa.column("email", sa.String()),
    sa.column("is_persona", sa.Boolean()),
    sa.column("persona_kind", sa.String()),
)


def classification_updates() -> tuple[sa.Update, ...]:
    """Build the three bounded updates without opening a database connection.

    There are no parameters. The return value contains one statement per kind;
    each statement only fills null kinds for exact, still-managed seed identities.
    """

    statements: list[sa.Update] = []
    for kind in ("automation", "editorial", "fictional"):
        identities = tuple(
            sa.and_(
                users.c.username == classification.username,
                users.c.email == classification.email,
            )
            for classification in PERSONA_CLASSIFICATIONS
            if classification.kind == kind
        )
        statements.append(
            users.update()
            .where(
                users.c.is_persona.is_(True),
                users.c.persona_kind.is_(None),
                sa.or_(*identities),
            )
            .values(persona_kind=kind)
        )
    return tuple(statements)


def upgrade() -> None:
    """Fill approved seed subtypes while preserving manual and non-operator state.

    There are no parameters or return value. The side effect is three bounded
    UPDATE statements against exact seeded username/email pairs.
    """

    bind = op.get_bind()
    for statement in classification_updates():
        bind.execute(statement)


def downgrade() -> None:
    """Keep classifications because their origin cannot later be distinguished.

    There are no parameters or return value. This downgrade intentionally has
    no side effects so administrator choices are never erased.
    """

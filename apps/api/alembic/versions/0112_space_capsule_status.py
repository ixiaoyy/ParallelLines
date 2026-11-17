"""为私密圈补充时间胶囊、此刻状态与情绪共鸣字段。

Revision ID: 0112_space_capsule_status
Revises: 0111_add_personal_space_tables
Create Date: 2026-11-17
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0112_space_capsule_status"
down_revision: str | None = "0111_add_personal_space_tables"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "space_settings",
        sa.Column(
            "current_status",
            sa.String(48),
            nullable=False,
            server_default="",
            comment="当前此刻状态胶囊文案，如 🎧 听歌中、🎮 开黑中。",
        ),
    )
    op.add_column(
        "space_journal_entries",
        sa.Column(
            "unlock_at",
            sa.String(10),
            nullable=True,
            comment="时间胶囊拆封日期（YYYY-MM-DD）；为空表示普通即时可见手账。",
        ),
    )
    op.add_column(
        "space_journal_entries",
        sa.Column(
            "reactions",
            sa.JSON(),
            nullable=True,
            comment="情绪共鸣贴纸计数字典，如 hug、spark、toast、party。",
        ),
    )


def downgrade() -> None:
    op.drop_column("space_journal_entries", "reactions")
    op.drop_column("space_journal_entries", "unlock_at")
    op.drop_column("space_settings", "current_status")

"""add calendar event status

Revision ID: 0051_calendar_event_status
Revises: 0050_frontier_news_curation
Create Date: 2026-06-08
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0051_calendar_event_status"
down_revision: str | None = "0050_frontier_news_curation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add persisted lifecycle state for community calendar events.

    Key parameters: none. Return value: none. Side effect: adds a non-null
    `status` column with `scheduled` as the default for existing rows.
    """

    op.add_column(
        "calendar_events",
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            server_default="scheduled",
            comment="活动状态：scheduled 或 canceled。",
        ),
    )


def downgrade() -> None:
    """Remove persisted lifecycle state from community calendar events.

    Key parameters: none. Return value: none. Side effect: drops the `status`
    column from `calendar_events`.
    """

    op.drop_column("calendar_events", "status")

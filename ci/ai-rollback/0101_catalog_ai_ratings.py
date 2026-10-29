"""Store versioned AI assessments without changing player ratings.

Revision ID: 0101_catalog_ai_ratings
Revises: 0100_add_yiji_pochao
Create Date: 2026-10-29
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0101_catalog_ai_ratings"
down_revision: str | None = "0100_add_yiji_pochao"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create empty AI-only tables; no historical/player data is written."""

    op.create_table(
        "catalog_ai_rating_rules",
        sa.Column("version", sa.String(80), primary_key=True),
        sa.Column("definition_digest", sa.CHAR(64), nullable=False),
        sa.Column("dimensions", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "catalog_ai_rating_weight_schemes",
        sa.Column("version", sa.String(80), primary_key=True),
        sa.Column(
            "rule_version", sa.String(80),
            sa.ForeignKey("catalog_ai_rating_rules.version", ondelete="RESTRICT"), nullable=False,
        ),
        sa.Column("weights", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "catalog_ai_rating_batches",
        sa.Column("id", sa.String(120), primary_key=True),
        sa.Column("evaluator_kind", sa.String(8), nullable=False, server_default="ai"),
        sa.Column("evaluator_identity", sa.JSON(), nullable=False),
        sa.Column("source_kind", sa.String(32), nullable=False, server_default="independent_ai"),
        sa.Column("source_reference", sa.Text()),
        sa.Column("source_metadata", sa.JSON(), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload_digest", sa.CHAR(64), nullable=False),
        sa.CheckConstraint("evaluator_kind = 'ai'", name="ck_catalog_ai_batch_evaluator"),
        sa.CheckConstraint(
            "source_kind IN ('independent_ai', 'user_accepted_external_ai')",
            name="ck_catalog_ai_batch_source",
        ),
        sa.CheckConstraint(
            "source_kind <> 'user_accepted_external_ai' OR "
            "(source_reference IS NOT NULL AND length(trim(source_reference)) > 0)",
            name="ck_catalog_ai_batch_source_reference",
        ),
    )
    op.create_table(
        "catalog_ai_game_assessments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "batch_id", sa.String(120),
            sa.ForeignKey("catalog_ai_rating_batches.id", ondelete="RESTRICT"), nullable=False,
        ),
        sa.Column(
            "game_id", sa.BigInteger(),
            sa.ForeignKey("catalog_projects.id", ondelete="RESTRICT"), nullable=False,
        ),
        sa.Column(
            "rule_version", sa.String(80),
            sa.ForeignKey("catalog_ai_rating_rules.version", ondelete="RESTRICT"), nullable=False,
        ),
        sa.Column("identity_key", sa.CHAR(64), nullable=False),
        sa.Column("game_version", sa.String(200)),
        sa.Column("snapshot_key", sa.String(200)),
        sa.Column("evaluated_at", sa.DateTime(timezone=True)),
        sa.Column("reported_review_date", sa.Date()),
        sa.Column("reported_timezone", sa.String(100)),
        sa.Column("environment", sa.JSON(), nullable=False),
        sa.Column("play_scope", sa.JSON(), nullable=False),
        sa.Column("evidence", sa.JSON(), nullable=False),
        sa.Column("limitations", sa.JSON(), nullable=False),
        sa.Column("payload_digest", sa.CHAR(64), nullable=False),
        sa.Column(
            "supersedes_id", sa.String(36),
            sa.ForeignKey("catalog_ai_game_assessments.id", ondelete="RESTRICT"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "game_version IS NOT NULL OR snapshot_key IS NOT NULL",
            name="ck_catalog_ai_assessment_version_scope",
        ),
        sa.CheckConstraint(
            "supersedes_id IS NULL OR supersedes_id <> id",
            name="ck_catalog_ai_assessment_supersedes",
        ),
        sa.UniqueConstraint(
            "batch_id", "game_id", "rule_version", "identity_key",
            name="uq_catalog_ai_assessment_batch_identity",
        ),
    )
    op.create_index(
        "ix_catalog_ai_assessment_game_rule_date", "catalog_ai_game_assessments",
        ["game_id", "rule_version", "evaluated_at"],
    )
    op.create_index(
        "ix_catalog_ai_assessment_identity", "catalog_ai_game_assessments", ["identity_key"]
    )
    op.create_table(
        "catalog_ai_assessment_dimensions",
        sa.Column(
            "assessment_id", sa.String(36),
            sa.ForeignKey("catalog_ai_game_assessments.id", ondelete="RESTRICT"),
            primary_key=True,
        ),
        sa.Column("dimension_key", sa.String(80), primary_key=True),
        sa.Column("score", sa.Numeric(4, 2)),
        sa.Column("evidence", sa.JSON(), nullable=False),
        sa.CheckConstraint(
            "score IS NULL OR score BETWEEN 0 AND 10", name="ck_catalog_ai_dimension_score"
        ),
    )
    op.create_table(
        "catalog_ai_assessment_human_reviews",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "assessment_id", sa.String(36),
            sa.ForeignKey("catalog_ai_game_assessments.id", ondelete="RESTRICT"), nullable=False,
        ),
        sa.Column("reviewer_identity", sa.String(200), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("verdict", sa.String(32), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False),
        sa.Column("evidence", sa.JSON(), nullable=False),
        sa.CheckConstraint(
            "verdict IN ('confirmed', 'needs_reassessment', 'rejected')",
            name="ck_catalog_ai_human_review_verdict",
        ),
    )
    op.create_index(
        "ix_catalog_ai_human_review_assessment", "catalog_ai_assessment_human_reviews",
        ["assessment_id", "reviewed_at"],
    )


def downgrade() -> None:
    """Destructive: export all AI tables first; player rating tables are untouched."""

    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        # The project production database is MySQL. Handle SQLite's self-FK
        # DROP limitation only for explicitly approved in-memory test databases.
        options = op.get_context().opts
        if not options.get("catalog_ai_isolated_sqlite") or bind.engine.url.database not in (
            None, "", ":memory:",
        ):
            raise RuntimeError("SQLite downgrade requires an explicit isolated in-memory test DB")

    op.drop_index(
        "ix_catalog_ai_human_review_assessment", table_name="catalog_ai_assessment_human_reviews"
    )
    op.drop_table("catalog_ai_assessment_human_reviews")
    op.drop_table("catalog_ai_assessment_dimensions")
    op.drop_index("ix_catalog_ai_assessment_identity", table_name="catalog_ai_game_assessments")
    op.drop_index(
        "ix_catalog_ai_assessment_game_rule_date", table_name="catalog_ai_game_assessments"
    )
    if bind.dialect.name == "sqlite":
        op.execute(sa.text("UPDATE catalog_ai_game_assessments SET supersedes_id = NULL"))
    op.drop_table("catalog_ai_game_assessments")
    op.drop_table("catalog_ai_rating_batches")
    op.drop_table("catalog_ai_rating_weight_schemes")
    op.drop_table("catalog_ai_rating_rules")

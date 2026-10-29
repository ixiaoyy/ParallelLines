"""Append-only AI assessments, separate from catalog player ratings.

The importing service validates dimension membership and immutable rule/weight
versions. Database constraints additionally protect scores, provenance links and
per-batch identity. No aggregate score is persisted: each calculation names its
weight scheme explicitly.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    CHAR,
    JSON,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, id_column_type, utcnow


class AiRatingRule(Base):
    __tablename__ = "catalog_ai_rating_rules"

    version: Mapped[str] = mapped_column(String(80), primary_key=True)
    definition_digest: Mapped[str] = mapped_column(CHAR(64), nullable=False)
    dimensions: Mapped[list[dict[str, object]]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AiRatingWeightScheme(Base):
    __tablename__ = "catalog_ai_rating_weight_schemes"

    version: Mapped[str] = mapped_column(String(80), primary_key=True)
    rule_version: Mapped[str] = mapped_column(
        String(80), ForeignKey("catalog_ai_rating_rules.version", ondelete="RESTRICT"),
        nullable=False,
    )
    weights: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AiRatingBatch(Base):
    __tablename__ = "catalog_ai_rating_batches"
    __table_args__ = (
        CheckConstraint("evaluator_kind = 'ai'", name="ck_catalog_ai_batch_evaluator"),
        CheckConstraint(
            "source_kind IN ('independent_ai', 'user_accepted_external_ai')",
            name="ck_catalog_ai_batch_source",
        ),
        CheckConstraint(
            "source_kind <> 'user_accepted_external_ai' OR "
            "(source_reference IS NOT NULL AND length(trim(source_reference)) > 0)",
            name="ck_catalog_ai_batch_source_reference",
        ),
    )

    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    evaluator_kind: Mapped[str] = mapped_column(
        String(8), nullable=False, default="ai", server_default="ai"
    )
    evaluator_identity: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    source_kind: Mapped[str] = mapped_column(
        String(32), nullable=False, default="independent_ai", server_default="independent_ai"
    )
    source_reference: Mapped[str | None] = mapped_column(Text)
    source_metadata: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    payload_digest: Mapped[str] = mapped_column(CHAR(64), nullable=False)


class AiGameAssessment(Base):
    __tablename__ = "catalog_ai_game_assessments"
    __table_args__ = (
        CheckConstraint(
            "game_version IS NOT NULL OR snapshot_key IS NOT NULL",
            name="ck_catalog_ai_assessment_version_scope",
        ),
        CheckConstraint(
            "supersedes_id IS NULL OR supersedes_id <> id",
            name="ck_catalog_ai_assessment_supersedes",
        ),
        UniqueConstraint(
            "batch_id", "game_id", "rule_version", "identity_key",
            name="uq_catalog_ai_assessment_batch_identity",
        ),
        Index(
            "ix_catalog_ai_assessment_game_rule_date", "game_id", "rule_version", "evaluated_at"
        ),
        Index("ix_catalog_ai_assessment_identity", "identity_key"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    batch_id: Mapped[str] = mapped_column(
        String(120), ForeignKey("catalog_ai_rating_batches.id", ondelete="RESTRICT"),
        nullable=False,
    )
    game_id: Mapped[str] = mapped_column(
        id_column_type(), ForeignKey("catalog_projects.id", ondelete="RESTRICT"), nullable=False
    )
    rule_version: Mapped[str] = mapped_column(
        String(80), ForeignKey("catalog_ai_rating_rules.version", ondelete="RESTRICT"),
        nullable=False,
    )
    identity_key: Mapped[str] = mapped_column(CHAR(64), nullable=False)
    game_version: Mapped[str | None] = mapped_column(String(200))
    snapshot_key: Mapped[str | None] = mapped_column(String(200))
    evaluated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reported_review_date: Mapped[date | None] = mapped_column(Date)
    reported_timezone: Mapped[str | None] = mapped_column(String(100))
    environment: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    play_scope: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    evidence: Mapped[list[object]] = mapped_column(JSON, nullable=False)
    limitations: Mapped[list[object]] = mapped_column(JSON, nullable=False)
    payload_digest: Mapped[str] = mapped_column(CHAR(64), nullable=False)
    supersedes_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("catalog_ai_game_assessments.id", ondelete="RESTRICT")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AiAssessmentDimension(Base):
    __tablename__ = "catalog_ai_assessment_dimensions"
    __table_args__ = (
        CheckConstraint(
            "score IS NULL OR score BETWEEN 0 AND 10", name="ck_catalog_ai_dimension_score"
        ),
    )

    assessment_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("catalog_ai_game_assessments.id", ondelete="RESTRICT"),
        primary_key=True,
    )
    dimension_key: Mapped[str] = mapped_column(String(80), primary_key=True)
    score: Mapped[Decimal | None] = mapped_column(Numeric(4, 2))
    evidence: Mapped[list[object]] = mapped_column(JSON, nullable=False)


class AiAssessmentHumanReview(Base):
    __tablename__ = "catalog_ai_assessment_human_reviews"
    __table_args__ = (
        CheckConstraint(
            "verdict IN ('confirmed', 'needs_reassessment', 'rejected')",
            name="ck_catalog_ai_human_review_verdict",
        ),
        Index("ix_catalog_ai_human_review_assessment", "assessment_id", "reviewed_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    assessment_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("catalog_ai_game_assessments.id", ondelete="RESTRICT"),
        nullable=False,
    )
    reviewer_identity: Mapped[str] = mapped_column(String(200), nullable=False)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    verdict: Mapped[str] = mapped_column(String(32), nullable=False)
    notes: Mapped[str] = mapped_column(Text, nullable=False)
    evidence: Mapped[list[object]] = mapped_column(JSON, nullable=False)

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, IntegerPrimaryKeyMixin, TimestampMixin


class AiTopicSummary(IntegerPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "ai_topic_summaries"
    __table_args__ = (
        UniqueConstraint("topic_id", name="uq_ai_topic_summaries_topic"),
        Index("ix_ai_topic_summaries_generated", "generated_at"),
    )

    topic_id: Mapped[str] = mapped_column(
        ForeignKey("topics.id", ondelete="CASCADE"), nullable=False
    )
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    key_points: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    key_post_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    model_name: Mapped[str] = mapped_column(
        String(80), nullable=False, default="local-deterministic"
    )
    cost_units: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    refreshed_by_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    topic = relationship("Topic", lazy="selectin")
    refreshed_by = relationship("User", lazy="selectin")

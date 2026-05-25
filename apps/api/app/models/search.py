from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, IntegerPrimaryKeyMixin, TimestampMixin, utcnow


class SearchDocument(IntegerPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "search_documents"
    __table_args__ = (
        Index("ix_search_documents_topic", "topic_id", unique=True),
        Index("ix_search_documents_board_updated", "board_id", "updated_at"),
        Index("ix_search_documents_author_updated", "author_id", "updated_at"),
        Index("ix_search_documents_status_updated", "topic_status", "updated_at"),
    )

    topic_id: Mapped[str] = mapped_column(
        ForeignKey("topics.id", ondelete="CASCADE"), nullable=False
    )
    board_id: Mapped[str] = mapped_column(
        ForeignKey("boards.id", ondelete="CASCADE"), nullable=False
    )
    author_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    author_username: Mapped[str] = mapped_column(String(64), nullable=False)
    topic_status: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(180), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False, default="")
    tags_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    indexed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    topic = relationship("Topic", lazy="selectin")


class SearchLog(IntegerPrimaryKeyMixin, Base):
    __tablename__ = "search_logs"
    __table_args__ = (
        Index("ix_search_logs_query_created", "normalized_query", "created_at"),
        Index("ix_search_logs_user_created", "user_id", "created_at"),
        Index("ix_search_logs_has_results_created", "has_results", "created_at"),
    )

    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    query: Mapped[str] = mapped_column(String(120), nullable=False)
    normalized_query: Mapped[str] = mapped_column(String(120), nullable=False)
    filters: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    result_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    has_results: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

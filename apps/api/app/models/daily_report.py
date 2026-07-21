from __future__ import annotations

from datetime import date

from sqlalchemy import JSON, Date, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IntegerPrimaryKeyMixin, TimestampMixin, id_column_type


class DailyReportProfile(IntegerPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "daily_report_profiles"
    __table_args__ = (UniqueConstraint("user_id", name="uq_daily_report_profiles_user"),)

    user_id: Mapped[str] = mapped_column(
        id_column_type(),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    custom_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    preferences: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    prompt_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class DailyReportPromptVersion(IntegerPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "daily_report_prompt_versions"
    __table_args__ = (
        UniqueConstraint(
            "profile_id",
            "version",
            name="uq_daily_report_prompt_versions_profile_version",
        ),
        Index("ix_daily_report_prompt_versions_user_created", "user_id", "created_at"),
    )

    profile_id: Mapped[str] = mapped_column(
        id_column_type(),
        ForeignKey("daily_report_profiles.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[str] = mapped_column(
        id_column_type(),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    custom_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    preferences: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    change_summary: Mapped[str] = mapped_column(String(500), nullable=False)


class DailyReportSession(IntegerPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "daily_report_sessions"
    __table_args__ = (
        Index("ix_daily_report_sessions_user_created", "user_id", "created_at"),
        Index("ix_daily_report_sessions_user_status", "user_id", "status"),
    )

    user_id: Mapped[str] = mapped_column(
        id_column_type(),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    work_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="active")
    input_data: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    current_draft: Mapped[str] = mapped_column(Text, nullable=False)
    prompt_version: Mapped[int] = mapped_column(Integer, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    model_name: Mapped[str] = mapped_column(String(120), nullable=False)
    provider_mode: Mapped[str] = mapped_column(String(32), nullable=False)


class DailyReportMessage(IntegerPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "daily_report_messages"
    __table_args__ = (
        UniqueConstraint(
            "session_id",
            "sequence",
            name="uq_daily_report_messages_session_sequence",
        ),
        Index("ix_daily_report_messages_user_created", "user_id", "created_at"),
    )

    session_id: Mapped[str] = mapped_column(
        id_column_type(),
        ForeignKey("daily_report_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[str] = mapped_column(
        id_column_type(),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    message_metadata: Mapped[dict[str, object]] = mapped_column(
        "metadata",
        JSON,
        nullable=False,
        default=dict,
    )


class DailyReport(IntegerPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "daily_reports"
    __table_args__ = (
        UniqueConstraint("session_id", name="uq_daily_reports_session"),
        Index("ix_daily_reports_user_work_date", "user_id", "work_date"),
        Index("ix_daily_reports_user_created", "user_id", "created_at"),
    )

    user_id: Mapped[str] = mapped_column(
        id_column_type(),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    session_id: Mapped[str] = mapped_column(
        id_column_type(),
        ForeignKey("daily_report_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    work_date: Mapped[date] = mapped_column(Date, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    source_input: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    prompt_version: Mapped[int] = mapped_column(Integer, nullable=False)
    model_name: Mapped[str] = mapped_column(String(120), nullable=False)

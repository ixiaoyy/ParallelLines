from __future__ import annotations

from datetime import datetime
from typing import Literal

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

BackgroundJobStatus = Literal["queued", "running", "succeeded", "dead"]


class BackgroundJob(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "background_jobs"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_background_jobs_idempotency_key"),
        Index("ix_background_jobs_status_run", "status", "run_at", "priority", "created_at"),
        Index("ix_background_jobs_task_status", "task_name", "status"),
    )

    queue: Mapped[str] = mapped_column(String(64), default="default", nullable=False)
    task_name: Mapped[str] = mapped_column(String(128), nullable=False)
    payload: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(32), default="queued", nullable=False)
    idempotency_key: Mapped[str | None] = mapped_column(String(255))
    priority: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    locked_by: Mapped[str | None] = mapped_column(String(128))
    last_error: Mapped[str | None] = mapped_column(Text)
    result: Mapped[dict[str, object] | None] = mapped_column(JSON)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class BackgroundJobLog(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "background_job_logs"
    __table_args__ = (Index("ix_background_job_logs_job_created", "job_id", "created_at"),)

    job_id: Mapped[str] = mapped_column(
        ForeignKey("background_jobs.id", ondelete="CASCADE"), nullable=False
    )
    event: Mapped[str] = mapped_column(String(64), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    data: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    job: Mapped[BackgroundJob] = relationship("BackgroundJob", lazy="selectin")

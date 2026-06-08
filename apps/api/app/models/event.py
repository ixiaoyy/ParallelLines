from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Literal

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, IntegerPrimaryKeyMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.forum import Topic
    from app.models.user import User

EventStatus = Literal["scheduled", "canceled"]
EventRsvpStatus = Literal["going", "canceled"]


class CalendarEvent(IntegerPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "calendar_events"
    __table_args__ = (
        Index("ix_calendar_events_start_end", "start_at", "end_at"),
        Index("ix_calendar_events_creator", "created_by_id", "created_at"),
        {"comment": "社区日历活动，支持 RSVP、时区和 iCal 订阅。"},
    )

    title: Mapped[str] = mapped_column(String(180), nullable=False, comment="活动标题。")
    description: Mapped[str | None] = mapped_column(Text, comment="活动说明；为空表示无说明。")
    topic_id: Mapped[str | None] = mapped_column(
        ForeignKey("topics.id", ondelete="SET NULL"), comment="关联活动主题 ID；为空表示独立活动。"
    )
    created_by_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, comment="活动创建者 ID。"
    )
    start_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, comment="活动开始时间（UTC）。"
    )
    end_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, comment="活动结束时间（UTC）。"
    )
    timezone: Mapped[str] = mapped_column(
        String(64), nullable=False, default="UTC", comment="活动默认展示时区 IANA 名称。"
    )
    location: Mapped[str | None] = mapped_column(String(200), comment="活动地点或线上链接。")
    capacity: Mapped[int | None] = mapped_column(Integer, comment="报名人数上限；为空表示不限。")
    rsvp_deadline: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), comment="报名截止时间；为空表示开始前均可报名。"
    )
    reminder_minutes_before: Mapped[int] = mapped_column(
        Integer, nullable=False, default=60, comment="提醒提前分钟数。"
    )
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="scheduled", comment="活动状态：scheduled 或 canceled。"
    )

    topic: Mapped[Topic | None] = relationship("Topic", lazy="selectin")
    creator: Mapped[User] = relationship("User", lazy="selectin")


class EventRsvp(IntegerPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "event_rsvps"
    __table_args__ = (
        UniqueConstraint("event_id", "user_id", name="uq_event_rsvps_event_user"),
        Index("ix_event_rsvps_user_status", "user_id", "status"),
        {"comment": "活动 RSVP/报名记录和提醒发送状态。"},
    )

    event_id: Mapped[str] = mapped_column(
        ForeignKey("calendar_events.id", ondelete="CASCADE"), nullable=False, comment="活动 ID。"
    )
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, comment="报名用户 ID。"
    )
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="going", comment="报名状态：going 或 canceled。"
    )
    reminder_sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), comment="提醒发送时间；为空表示尚未提醒。"
    )

    event: Mapped[CalendarEvent] = relationship("CalendarEvent", lazy="selectin")
    user: Mapped[User] = relationship("User", lazy="selectin")

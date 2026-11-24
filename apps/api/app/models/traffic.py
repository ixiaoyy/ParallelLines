from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import BigInteger, Date, DateTime, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class TrafficEvent(Base):
    """仅存隐私化统计事件；UUID 主键确保队列提交后重放不会重复累计。"""

    __tablename__ = "traffic_events"
    __table_args__ = (
        Index("ix_traffic_events_site_occurred", "site_key", "occurred_at"),
        Index("ix_traffic_events_visitor_occurred", "visitor_key", "occurred_at"),
        Index("ix_traffic_events_occurred", "occurred_at"),
        Index("ix_traffic_events_received", "received_at"),
        Index("ix_traffic_events_site_received", "site_key", "received_at"),
    )

    event_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    site_key: Mapped[str] = mapped_column(String(16), nullable=False)
    visitor_key: Mapped[str] = mapped_column(String(96), nullable=False)
    identity_scope: Mapped[str] = mapped_column(String(16), nullable=False)
    event_name: Mapped[str] = mapped_column(String(24), nullable=False)
    path: Mapped[str] = mapped_column(String(256), nullable=False)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    source_name: Mapped[str] = mapped_column(String(128), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class TrafficVisitor(Base):
    """采集以来每站/全局浏览器首次与末次访问；临时身份不用于回访指标。"""

    __tablename__ = "traffic_visitors"
    __table_args__ = (Index("ix_traffic_visitors_first_seen", "site_key", "first_seen_at"),)

    site_key: Mapped[str] = mapped_column(String(16), primary_key=True)
    visitor_key: Mapped[str] = mapped_column(String(96), primary_key=True)
    identity_scope: Mapped[str] = mapped_column(String(16), nullable=False)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class TrafficDailyVisitor(Base):
    """上海日界下的每站/全局浏览器计数；报表总览不扫描原始访问事件。"""

    __tablename__ = "traffic_daily_visitors"
    __table_args__ = (
        Index("ix_traffic_daily_site_day", "site_key", "day"),
        Index("ix_traffic_daily_visitor_day", "site_key", "visitor_key", "day"),
    )

    day: Mapped[date] = mapped_column(Date, primary_key=True)
    site_key: Mapped[str] = mapped_column(String(16), primary_key=True)
    visitor_key: Mapped[str] = mapped_column(String(96), primary_key=True)
    identity_scope: Mapped[str] = mapped_column(String(16), nullable=False)
    page_views: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0, server_default="0"
    )
    actions: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, server_default="0")
    shared_page_views: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0, server_default="0"
    )
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

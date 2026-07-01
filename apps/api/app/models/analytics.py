from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IntegerPrimaryKeyMixin, id_column_type, utcnow


class SiteVisit(IntegerPrimaryKeyMixin, Base):
    __tablename__ = "site_visits"
    __table_args__ = (
        Index("ix_site_visits_created", "created_at"),
        Index("ix_site_visits_visitor_created", "visitor_key", "created_at"),
        Index("ix_site_visits_source_created", "source_type", "source_name", "created_at"),
        Index("ix_site_visits_path_created", "path", "created_at"),
        Index("ix_site_visits_user_created", "user_id", "created_at"),
    )

    visitor_key: Mapped[str] = mapped_column(
        String(96),
        nullable=False,
        comment="访问者去重键；保存登录用户或匿名访客标识的哈希，不保存原始访客 ID。",
    )
    user_id: Mapped[str | None] = mapped_column(
        id_column_type(),
        ForeignKey("users.id", ondelete="SET NULL"),
        comment="登录访问者用户 ID；匿名访问为空。",
    )
    path: Mapped[str] = mapped_column(
        String(512),
        nullable=False,
        comment="访问的站内路径，包含查询字符串但不包含域名。",
    )
    title: Mapped[str | None] = mapped_column(
        String(180),
        comment="访问时浏览器页面标题；为空表示前端未提供。",
    )
    referrer_host: Mapped[str | None] = mapped_column(
        String(255),
        comment="来源 URL 的主机名；直接访问或无法解析时为空。",
    )
    source_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        comment="访问来源类型：direct、internal、search、social、referral 或 campaign。",
    )
    source_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="归一化来源名称，如 Direct、Internal、baidu.com 或 utm_source。",
    )
    utm_source: Mapped[str | None] = mapped_column(
        String(128),
        comment="URL 查询参数 utm_source；为空表示未带广告/活动来源。",
    )
    utm_medium: Mapped[str | None] = mapped_column(
        String(128),
        comment="URL 查询参数 utm_medium；为空表示未带媒介。",
    )
    utm_campaign: Mapped[str | None] = mapped_column(
        String(180),
        comment="URL 查询参数 utm_campaign；为空表示未带活动名称。",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        nullable=False,
        comment="访问事件记录时间（UTC）。",
    )

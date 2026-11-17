from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import BigInteger, Boolean, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, IntegerPrimaryKeyMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User


class SpaceSetting(IntegerPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "space_settings"
    __table_args__ = (
        UniqueConstraint("user_id", name="uq_space_settings_user_id"),
        Index("ix_space_settings_user_id", "user_id"),
    )

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        comment="所属用户 ID。",
    )
    space_title: Mapped[str] = mapped_column(
        String(80),
        default="",
        nullable=False,
        comment="个人空间自定义标题；为空时前端使用昵称默认名称。",
    )
    space_subtitle: Mapped[str] = mapped_column(
        String(200),
        default="",
        nullable=False,
        comment="个人空间顶栏签名或心情寄语。",
    )
    cover_preset: Mapped[str] = mapped_column(
        String(32),
        default="aurora",
        nullable=False,
        comment="个人空间封面主题预设标识，如 aurora、sunset、meadow、paper、starlight。",
    )
    monthly_budget_cents: Mapped[int] = mapped_column(
        BigInteger,
        default=300000,
        nullable=False,
        comment="个人账本月度预算金额（单位：分），仅用户本人可见。",
    )
    current_status: Mapped[str] = mapped_column(
        String(48),
        default="",
        nullable=False,
        comment="当前此刻状态胶囊文案，如 🎧 听歌中、🎮 开黑中。",
    )

    user: Mapped[User] = relationship("User", lazy="selectin")


class SpaceJournalEntry(IntegerPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "space_journal_entries"
    __table_args__ = (
        Index("ix_space_journal_entries_user_date", "user_id", "entry_date"),
        Index("ix_space_journal_entries_user_vis_created", "user_id", "visibility", "created_at"),
        Index("ix_space_journal_entries_vis_created", "visibility", "created_at"),
    )

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        comment="手账作者用户 ID。",
    )
    entry_date: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        comment="手账归属日期（YYYY-MM-DD），用于心情日历与按日检索。",
    )
    title: Mapped[str] = mapped_column(
        String(160),
        default="",
        nullable=False,
        comment="手账可选短标题；为空表示纯闪念/碎碎念卡片。",
    )
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="手账正文内容，支持轻量文本与标签记录。",
    )
    mood: Mapped[str] = mapped_column(
        String(32),
        default="happy",
        nullable=False,
        comment="当日心情贴纸标识，如 happy、focused、calm、cozy、inspired、tired、rainy、celebrate。",
    )
    weather: Mapped[str] = mapped_column(
        String(32),
        default="sunny",
        nullable=False,
        comment="当日天气或状态图标标识，如 sunny、cloudy、breezy、rainy、snowy、night。",
    )
    location: Mapped[str] = mapped_column(
        String(80),
        default="",
        nullable=False,
        comment="手账可选地点或场景小标，如 书桌前、咖啡馆、通勤路上。",
    )
    visibility: Mapped[str] = mapped_column(
        String(16),
        default="public",
        nullable=False,
        comment="可见性范围：public 表示公开到个人空间与圈子，private 表示仅自己可见。",
    )
    is_pinned: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="是否在个人空间置顶展示。",
    )
    card_theme: Mapped[str] = mapped_column(
        String(32),
        default="paper",
        nullable=False,
        comment="手账信纸视觉主题：paper、sky、mint、sunset、lavender、grid。",
    )
    tags: Mapped[list[str]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
        comment="手账关联的标签字符串数组。",
    )
    media_urls: Mapped[list[str]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
        comment="手账配图 URL 列表（最多 9 张）。",
    )
    checklist: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
        comment="手账内嵌打卡/待办清单项列表，每项包含 id、text、done。",
    )
    ledger_snapshot: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True,
        comment="可选关联的记账摘要或月度账单快照卡片数据；为空表示普通手账。",
    )
    likes_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="手账收到的暖心点赞互动次数。",
    )
    unlock_at: Mapped[str | None] = mapped_column(
        String(10),
        nullable=True,
        comment="时间胶囊拆封日期（YYYY-MM-DD）；为空表示普通即时可见手账。",
    )
    reactions: Mapped[dict[str, int] | None] = mapped_column(
        JSON,
        nullable=True,
        comment="情绪共鸣贴纸计数字典，如 hug、spark、toast、party。",
    )

    user: Mapped[User] = relationship("User", lazy="selectin")


class SpaceLedgerEntry(IntegerPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "space_ledger_entries"
    __table_args__ = (
        Index("ix_space_ledger_entries_user_date", "user_id", "entry_date"),
        Index("ix_space_ledger_entries_user_kind_date", "user_id", "kind", "entry_date"),
    )

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        comment="记账所属用户 ID；账本明细严格仅本人可见。",
    )
    entry_date: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        comment="记账发生日期（YYYY-MM-DD）。",
    )
    kind: Mapped[str] = mapped_column(
        String(16),
        default="expense",
        nullable=False,
        comment="收支类型：expense（支出）或 income（收入）。",
    )
    amount_cents: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        comment="记账金额（单位：分，正整数）。",
    )
    category: Mapped[str] = mapped_column(
        String(32),
        default="dining",
        nullable=False,
        comment="收支分类标识，如 dining、coffee、gaming、shopping、transit、entertainment、housing、salary、other。",
    )
    note: Mapped[str] = mapped_column(
        String(200),
        default="",
        nullable=False,
        comment="记账一句话备注。",
    )
    payment_method: Mapped[str] = mapped_column(
        String(32),
        default="wechat",
        nullable=False,
        comment="支付或入账方式标识，如 wechat、alipay、card、cash。",
    )

    user: Mapped[User] = relationship("User", lazy="selectin")

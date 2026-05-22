from __future__ import annotations

from typing import Any

from sqlalchemy import JSON, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Draft(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "drafts"
    __table_args__ = (
        Index("ix_drafts_user_id", "user_id"),
        UniqueConstraint("user_id", "target_type", "target_id", name="uq_drafts_user_target"),
    )

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        comment="草稿所属用户 ID。",
    )
    target_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        comment="草稿目标类型：new_topic 表示新主题，topic 表示某主题回复。",
    )
    target_id: Mapped[str] = mapped_column(
        String(36),
        nullable=False,
        default="",
        comment="草稿目标 ID；新主题草稿为空字符串，回复草稿为主题 ID。",
    )
    draft_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        comment="草稿内容类型：topic 表示主题草稿，reply 表示回复草稿。",
    )
    data: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        comment="草稿结构化数据，保存标题、正文、标签等客户端状态。",
    )
    version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        comment="草稿版本号，用于客户端-服务端冲突检测。",
    )

    user = relationship("User", lazy="selectin")

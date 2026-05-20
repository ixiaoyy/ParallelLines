from __future__ import annotations

from datetime import datetime
from typing import Literal

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

UploadKind = Literal["post_attachment", "avatar"]
UploadStatus = Literal["temporary", "attached", "avatar", "deleted"]


class Upload(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "uploads"
    __table_args__ = (
        Index("ix_uploads_user_status", "user_id", "status"),
        Index("ix_uploads_post_status", "post_id", "status"),
        Index("ix_uploads_board_status", "board_id", "status"),
    )

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    board_id: Mapped[str | None] = mapped_column(ForeignKey("boards.id", ondelete="SET NULL"))
    topic_id: Mapped[str | None] = mapped_column(ForeignKey("topics.id", ondelete="SET NULL"))
    post_id: Mapped[str | None] = mapped_column(ForeignKey("posts.id", ondelete="SET NULL"))
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_backend: Mapped[str] = mapped_column(String(32), nullable=False, default="local")
    storage_key: Mapped[str] = mapped_column(String(512), nullable=False, unique=True)
    media_type: Mapped[str] = mapped_column(String(128), nullable=False)
    byte_size: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False, default="post_attachment")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="temporary")
    is_image: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    owner = relationship("User", lazy="selectin")
    board = relationship("Board", lazy="selectin")
    topic = relationship("Topic", lazy="selectin")
    post = relationship("Post", lazy="selectin")

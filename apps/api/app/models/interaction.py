from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Literal

from sqlalchemy import JSON, DateTime, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.forum import Post, Topic
    from app.models.user import User

ReactionTargetType = Literal["post", "topic"]
BookmarkTargetType = Literal["post", "topic"]
ReactionType = Literal["like"]
NotificationType = Literal[
    "replied",
    "mentioned",
    "liked",
    "topic_new_post",
    "board_new_topic",
    "user_new_topic",
    "private_message",
    "moderation",
]


class Reaction(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "reactions"
    __table_args__ = (
        UniqueConstraint(
            "target_type",
            "target_id",
            "user_id",
            "type",
            name="uq_reactions_target_user_type",
        ),
        Index("ix_reactions_target", "target_type", "target_id"),
    )

    target_type: Mapped[str] = mapped_column(String(32), nullable=False)
    target_id: Mapped[str] = mapped_column(String(36), nullable=False)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    type: Mapped[str] = mapped_column(String(32), nullable=False, default="like")

    user: Mapped[User] = relationship("User", lazy="selectin")


class Bookmark(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "bookmarks"
    __table_args__ = (
        UniqueConstraint("target_type", "target_id", "user_id", name="uq_bookmarks_target_user"),
        Index("ix_bookmarks_target", "target_type", "target_id"),
        Index("ix_bookmarks_user_created", "user_id", "created_at"),
    )

    target_type: Mapped[str] = mapped_column(String(32), nullable=False)
    target_id: Mapped[str] = mapped_column(String(36), nullable=False)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    user: Mapped[User] = relationship("User", lazy="selectin")


class Notification(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "notifications"
    __table_args__ = (
        Index("ix_notifications_user_read_created", "user_id", "read_at", "created_at"),
        Index("ix_notifications_topic_created", "topic_id", "created_at"),
    )

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    type: Mapped[str] = mapped_column(String(64), nullable=False)
    topic_id: Mapped[str | None] = mapped_column(ForeignKey("topics.id", ondelete="SET NULL"))
    post_id: Mapped[str | None] = mapped_column(ForeignKey("posts.id", ondelete="SET NULL"))
    actor_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    data: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped[User] = relationship("User", foreign_keys=[user_id], lazy="selectin")
    actor: Mapped[User | None] = relationship("User", foreign_keys=[actor_id], lazy="selectin")
    topic: Mapped[Topic | None] = relationship("Topic", lazy="selectin")
    post: Mapped[Post | None] = relationship("Post", lazy="selectin")

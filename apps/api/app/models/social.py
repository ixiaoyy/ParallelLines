from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Literal

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, utcnow

if TYPE_CHECKING:
    from app.models.forum import Topic
    from app.models.user import User

UserRelationshipType = Literal["follow", "ignore", "block"]
PrivateMessageParticipantRole = Literal["owner", "participant"]


class UserRelationship(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "user_relationships"
    __table_args__ = (
        UniqueConstraint(
            "actor_user_id",
            "target_user_id",
            "relationship_type",
            name="uq_user_relationships_actor_target_type",
        ),
        Index("ix_user_relationships_actor_type", "actor_user_id", "relationship_type"),
        Index("ix_user_relationships_target_type", "target_user_id", "relationship_type"),
    )

    actor_user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        comment="发起关系的用户 ID。",
    )
    target_user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        comment="被关注、忽略或屏蔽的目标用户 ID。",
    )
    relationship_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        comment="用户关系类型：follow、ignore 或 block。",
    )
    note: Mapped[str | None] = mapped_column(
        String(255),
        comment="用户关系备注；为空表示未填写备注。",
    )

    actor: Mapped[User] = relationship("User", foreign_keys=[actor_user_id], lazy="selectin")
    target: Mapped[User] = relationship("User", foreign_keys=[target_user_id], lazy="selectin")


class PrivateMessageParticipant(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "private_message_participants"
    __table_args__ = (
        UniqueConstraint("topic_id", "user_id", name="uq_private_message_participants_topic_user"),
        Index("ix_private_message_participants_user_created", "user_id", "created_at"),
        Index("ix_private_message_participants_topic_role", "topic_id", "role"),
    )

    topic_id: Mapped[str] = mapped_column(
        ForeignKey("topics.id", ondelete="CASCADE"),
        nullable=False,
        comment="私信主题 ID。",
    )
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        comment="参与私信的用户 ID。",
    )
    role: Mapped[str] = mapped_column(
        String(32),
        default="participant",
        nullable=False,
        comment="私信参与者角色：owner 或 participant。",
    )
    last_read_post_number: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="该参与者在私信主题中已读到的最高楼层编号。",
    )
    muted: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="该参与者是否静音此私信主题。",
    )
    last_read_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        comment="该参与者最后阅读私信的时间；为空表示尚未阅读。",
    )
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        nullable=False,
        comment="用户加入私信主题的时间。",
    )

    topic: Mapped[Topic] = relationship("Topic", lazy="selectin")
    user: Mapped[User] = relationship("User", lazy="selectin")

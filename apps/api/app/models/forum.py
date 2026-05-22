from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Literal

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, utcnow

if TYPE_CHECKING:
    from app.models.user import User

BoardVisibility = Literal["public", "private", "unlisted"]
BoardMemberRole = Literal["follower", "moderator", "owner"]
NotificationLevel = Literal["muted", "normal", "tracking", "watching"]
TopicStatus = Literal["open", "closed", "archived", "hidden"]
BoardInvitationStatus = Literal["pending", "accepted", "declined", "revoked", "expired"]


topic_tags = Table(
    "topic_tags",
    Base.metadata,
    Column("topic_id", ForeignKey("topics.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
)


class Board(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "boards"
    __table_args__ = (UniqueConstraint("slug", name="uq_boards_slug"),)

    slug: Mapped[str] = mapped_column(String(96), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    color: Mapped[str] = mapped_column(String(32), nullable=False, default="#3B82F6")
    avatar_url: Mapped[str | None] = mapped_column(String(512))
    owner_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    visibility: Mapped[str] = mapped_column(String(32), nullable=False, default="public")
    topic_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    post_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    follower_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    topics: Mapped[list[Topic]] = relationship(back_populates="board", lazy="selectin")
    owner: Mapped[User | None] = relationship("User", lazy="selectin")


class BoardMember(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "board_members"
    __table_args__ = (UniqueConstraint("board_id", "user_id", name="uq_board_members_board_user"),)

    board_id: Mapped[str] = mapped_column(
        ForeignKey("boards.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False, default="follower")
    notification_level: Mapped[str] = mapped_column(String(32), nullable=False, default="normal")
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )


class BoardInvitation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "board_invitations"
    __table_args__ = (
        Index("ix_board_invitations_invitee_status", "invitee_id", "status"),
        Index("ix_board_invitations_board_status", "board_id", "status"),
    )

    board_id: Mapped[str] = mapped_column(
        ForeignKey("boards.id", ondelete="CASCADE"), nullable=False
    )
    inviter_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    invitee_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_by_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))

    board: Mapped[Board] = relationship("Board", lazy="selectin")
    inviter: Mapped[User] = relationship("User", foreign_keys=[inviter_id], lazy="selectin")
    invitee: Mapped[User] = relationship("User", foreign_keys=[invitee_id], lazy="selectin")
    revoked_by: Mapped[User | None] = relationship(
        "User", foreign_keys=[revoked_by_id], lazy="selectin"
    )


class Tag(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "tags"
    __table_args__ = (
        UniqueConstraint("name", name="uq_tags_name"),
        UniqueConstraint("slug", name="uq_tags_slug"),
    )

    name: Mapped[str] = mapped_column(String(48), nullable=False)
    slug: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    topic_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    topics: Mapped[list[Topic]] = relationship(
        secondary=topic_tags,
        back_populates="tags",
        lazy="selectin",
    )


class Topic(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "topics"
    __table_args__ = (
        UniqueConstraint("board_id", "slug", name="uq_topics_board_slug"),
        Index("ix_topics_board_last_posted", "board_id", "last_posted_at"),
        Index("ix_topics_board_hot_score", "board_id", "hot_score"),
    )

    board_id: Mapped[str] = mapped_column(
        ForeignKey("boards.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(String(180), nullable=False)
    slug: Mapped[str] = mapped_column(String(220), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="open")
    pinned: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    featured: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    view_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    reply_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    like_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    hot_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    last_posted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    merged_into_topic_id: Mapped[str | None] = mapped_column(
        ForeignKey("topics.id", ondelete="SET NULL")
    )

    board: Mapped[Board] = relationship(back_populates="topics", lazy="selectin")
    author: Mapped[User] = relationship("User", lazy="selectin")
    merged_into: Mapped[Topic | None] = relationship(
        "Topic",
        remote_side="Topic.id",
        lazy="selectin",
    )
    posts: Mapped[list[Post]] = relationship(back_populates="topic", lazy="selectin")
    tags: Mapped[list[Tag]] = relationship(
        secondary=topic_tags,
        back_populates="topics",
        lazy="selectin",
    )


class Post(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "posts"
    __table_args__ = (UniqueConstraint("topic_id", "post_number", name="uq_posts_topic_number"),)

    topic_id: Mapped[str] = mapped_column(
        ForeignKey("topics.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    parent_id: Mapped[str | None] = mapped_column(ForeignKey("posts.id", ondelete="SET NULL"))
    post_number: Mapped[int] = mapped_column(Integer, nullable=False)
    raw_md: Mapped[str] = mapped_column(Text, nullable=False)
    cooked_html: Mapped[str] = mapped_column(Text, nullable=False)
    reply_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    like_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    topic: Mapped[Topic] = relationship(back_populates="posts", lazy="selectin")
    author: Mapped[User] = relationship("User", lazy="selectin")


class PostRevision(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "post_revisions"
    __table_args__ = (
        UniqueConstraint("post_id", "version_number", name="uq_post_revisions_post_version"),
        Index("ix_post_revisions_post_created", "post_id", "created_at"),
        Index("ix_post_revisions_editor_created", "editor_id", "created_at"),
    )

    post_id: Mapped[str] = mapped_column(ForeignKey("posts.id", ondelete="CASCADE"), nullable=False)
    topic_id: Mapped[str] = mapped_column(
        ForeignKey("topics.id", ondelete="CASCADE"), nullable=False
    )
    editor_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    raw_md: Mapped[str] = mapped_column(Text, nullable=False)
    cooked_html: Mapped[str] = mapped_column(Text, nullable=False)
    edit_reason: Mapped[str | None] = mapped_column(String(500))
    summary: Mapped[str] = mapped_column(String(500), nullable=False)
    restored_from_revision_id: Mapped[str | None] = mapped_column(
        ForeignKey("post_revisions.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    post: Mapped[Post] = relationship("Post", lazy="selectin")
    topic: Mapped[Topic] = relationship("Topic", lazy="selectin")
    editor: Mapped[User | None] = relationship("User", lazy="selectin")
    restored_from_revision: Mapped[PostRevision | None] = relationship(
        "PostRevision",
        remote_side="PostRevision.id",
        lazy="selectin",
    )


class TopicRead(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "topic_reads"
    __table_args__ = (UniqueConstraint("user_id", "topic_id", name="uq_topic_reads_user_topic"),)

    topic_id: Mapped[str] = mapped_column(
        ForeignKey("topics.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    last_read_post_number: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    notification_level: Mapped[str] = mapped_column(String(32), nullable=False, default="normal")

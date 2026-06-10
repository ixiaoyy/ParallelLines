from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Literal

from sqlalchemy import (
    JSON,
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

from app.db.base import Base, IntegerPrimaryKeyMixin, TimestampMixin, id_column_type, utcnow

if TYPE_CHECKING:
    from app.models.user import User

BoardVisibility = Literal["public", "private", "unlisted"]
BoardMemberRole = Literal["follower", "moderator", "owner"]
NotificationLevel = Literal["muted", "normal", "tracking", "watching"]
BoardDefaultSort = Literal["latest", "hot", "top"]
TopicType = Literal["regular", "private_message"]
TopicVisibility = Literal["public", "private_message"]
TopicStatus = Literal["open", "closed", "archived", "hidden"]
BoardInvitationStatus = Literal["pending", "accepted", "declined", "revoked", "expired"]


topic_tags = Table(
    "topic_tags",
    Base.metadata,
    Column("topic_id", ForeignKey("topics.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
)


class Board(IntegerPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "boards"
    __table_args__ = (
        UniqueConstraint("slug", name="uq_boards_slug"),
        Index("ix_boards_parent", "parent_board_id"),
    )

    slug: Mapped[str] = mapped_column(String(96), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    name_localizations: Mapped[dict[str, str] | None] = mapped_column(
        JSON,
        comment="版块名称本地化映射，键为 BCP47 locale；为空表示使用 name。",
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)
    color: Mapped[str] = mapped_column(String(32), nullable=False, default="#409EFF")
    avatar_url: Mapped[str | None] = mapped_column(String(512))
    owner_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    parent_board_id: Mapped[str | None] = mapped_column(
        ForeignKey("boards.id", ondelete="SET NULL"),
        comment="父版块 ID；为空表示顶层版块。",
    )
    visibility: Mapped[str] = mapped_column(String(32), nullable=False, default="public")
    required_tags: Mapped[list[str] | None] = mapped_column(
        JSON,
        comment="发帖必须包含的规范化标签名列表；为空或空数组表示不强制。",
    )
    allowed_tags: Mapped[list[str] | None] = mapped_column(
        JSON,
        comment="允许使用的规范化标签名列表；为空或空数组表示不限制。",
    )
    post_template: Mapped[str | None] = mapped_column(
        Text,
        comment="该版块新主题默认 Markdown 模板；为空表示不预填。",
    )
    default_notification_level: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="normal",
        comment="新关注者或受邀成员默认版块通知级别。",
    )
    default_sort: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="latest",
        comment="版块主题默认排序：latest、hot 或 top。",
    )
    topic_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    post_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    follower_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    topics: Mapped[list[Topic]] = relationship(back_populates="board", lazy="selectin")
    owner: Mapped[User | None] = relationship("User", lazy="selectin")
    parent_board: Mapped[Board | None] = relationship(
        "Board",
        remote_side="Board.id",
        back_populates="child_boards",
        lazy="selectin",
    )
    child_boards: Mapped[list[Board]] = relationship(
        "Board",
        back_populates="parent_board",
        lazy="selectin",
    )


class BoardMember(IntegerPrimaryKeyMixin, Base):
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

    board: Mapped[Board] = relationship("Board", lazy="selectin")
    user: Mapped[User] = relationship("User", lazy="selectin")


class BoardInvitation(IntegerPrimaryKeyMixin, TimestampMixin, Base):
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


class Tag(IntegerPrimaryKeyMixin, TimestampMixin, Base):
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


class Topic(IntegerPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "topics"
    __table_args__ = (
        UniqueConstraint("board_id", "slug", name="uq_topics_board_slug"),
        Index("ix_topics_board_last_posted", "board_id", "last_posted_at"),
        Index("ix_topics_board_hot_score", "board_id", "hot_score"),
        Index(
            "ix_topics_public_latest_feed",
            "visibility",
            "deleted_at",
            "pinned",
            "last_posted_at",
            "id",
        ),
        Index(
            "ix_topics_public_hot_feed",
            "visibility",
            "deleted_at",
            "hot_score",
            "last_posted_at",
            "id",
        ),
        Index(
            "ix_topics_public_top_feed",
            "visibility",
            "deleted_at",
            "like_count",
            "reply_count",
            "id",
        ),
        Index(
            "ix_topics_public_votes_feed",
            "visibility",
            "deleted_at",
            "vote_score",
            "vote_count",
            "last_posted_at",
            "id",
        ),
    )

    board_id: Mapped[str] = mapped_column(
        ForeignKey("boards.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(String(180), nullable=False)
    title_localizations: Mapped[dict[str, str] | None] = mapped_column(
        JSON,
        comment="主题标题本地化映射，键为 BCP47 locale；为空表示使用 title。",
    )
    slug: Mapped[str] = mapped_column(String(220), nullable=False)
    topic_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="regular",
        comment="主题类型：regular 表示公开/版块主题，private_message 表示私信主题。",
    )
    visibility: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="public",
        comment="主题可见性：public 表示沿用版块可见性，private_message 表示仅私信参与者可见。",
    )
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
    accepted_answer_post_id: Mapped[str | None] = mapped_column(
        id_column_type(),
        comment="被采纳为解决方案的回复帖子 ID；为空表示未解决。",
    )
    solved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        comment="主题被标记为已解决的时间；为空表示未解决。",
    )
    solved_by_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        comment="执行采纳或最后标记解决的用户 ID；为空表示未解决或用户已删除。",
    )
    answer_mode: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="是否启用问答排序提示；有采纳答案时通常为 true。",
    )
    vote_score: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="主题赞成票减反对票的缓存分数。",
    )
    vote_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="主题有效投票数量缓存。",
    )

    board: Mapped[Board] = relationship(back_populates="topics", lazy="selectin")
    author: Mapped[User] = relationship("User", foreign_keys=[user_id], lazy="selectin")
    merged_into: Mapped[Topic | None] = relationship(
        "Topic",
        remote_side="Topic.id",
        lazy="selectin",
    )
    solved_by: Mapped[User | None] = relationship(
        "User",
        foreign_keys=[solved_by_id],
        lazy="selectin",
    )
    posts: Mapped[list[Post]] = relationship(back_populates="topic", lazy="selectin")
    poll: Mapped[Poll | None] = relationship(
        "Poll",
        back_populates="topic",
        uselist=False,
        lazy="selectin",
        cascade="all, delete-orphan",
    )
    tags: Mapped[list[Tag]] = relationship(
        secondary=topic_tags,
        back_populates="topics",
        lazy="selectin",
    )


class Post(IntegerPrimaryKeyMixin, TimestampMixin, Base):
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
    vote_score: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="帖子赞成票减反对票的缓存分数。",
    )
    vote_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="帖子有效投票数量缓存。",
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    topic: Mapped[Topic] = relationship(back_populates="posts", lazy="selectin")
    author: Mapped[User] = relationship("User", lazy="selectin")


class PostRevision(IntegerPrimaryKeyMixin, Base):
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


class TopicRead(IntegerPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "topic_reads"
    __table_args__ = (UniqueConstraint("user_id", "topic_id", name="uq_topic_reads_user_topic"),)

    topic_id: Mapped[str] = mapped_column(
        ForeignKey("topics.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    last_read_post_number: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    notification_level: Mapped[str] = mapped_column(String(32), nullable=False, default="normal")


class TopicView(IntegerPrimaryKeyMixin, TimestampMixin, Base):
    """Persist one counted view identity per topic for deduplicated view counts."""

    __tablename__ = "topic_views"
    __table_args__ = (
        UniqueConstraint("topic_id", "viewer_key", name="uq_topic_views_topic_viewer"),
        Index("ix_topic_views_viewer_key", "viewer_key"),
    )

    topic_id: Mapped[str] = mapped_column(
        ForeignKey("topics.id", ondelete="CASCADE"),
        nullable=False,
        comment="被浏览主题 ID。",
    )
    viewer_key: Mapped[str] = mapped_column(
        String(96),
        nullable=False,
        comment="浏览者去重键；保存登录用户或匿名访客标识的哈希，不保存原始访客 ID。",
    )
    first_viewed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        nullable=False,
        comment="该浏览者首次计入主题浏览数的时间（UTC）。",
    )


class Poll(IntegerPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "polls"
    __table_args__ = (Index("ix_polls_topic", "topic_id"),)

    topic_id: Mapped[str] = mapped_column(
        ForeignKey("topics.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        comment="关联主题 ID；首版每个主题最多一个 Poll。",
    )
    question: Mapped[str] = mapped_column(
        String(240),
        nullable=False,
        comment="Poll 问题文本。",
    )
    multiple_choice: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="是否允许多选。",
    )
    closes_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        comment="Poll 截止时间；为空表示不自动截止。",
    )
    total_votes: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="参与投票的去重用户数量缓存。",
    )

    topic: Mapped[Topic] = relationship("Topic", back_populates="poll", lazy="selectin")
    options: Mapped[list[PollOption]] = relationship(
        "PollOption",
        back_populates="poll",
        lazy="selectin",
        cascade="all, delete-orphan",
        order_by="PollOption.position",
    )


class PollOption(IntegerPrimaryKeyMixin, Base):
    __tablename__ = "poll_options"
    __table_args__ = (
        UniqueConstraint("poll_id", "position", name="uq_poll_options_poll_position"),
        Index("ix_poll_options_poll", "poll_id"),
    )

    poll_id: Mapped[str] = mapped_column(
        ForeignKey("polls.id", ondelete="CASCADE"),
        nullable=False,
        comment="所属 Poll ID。",
    )
    label: Mapped[str] = mapped_column(
        String(160),
        nullable=False,
        comment="选项展示文本。",
    )
    position: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="选项排序，从 1 开始。",
    )
    vote_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="选择该选项的投票数量缓存。",
    )

    poll: Mapped[Poll] = relationship("Poll", back_populates="options", lazy="selectin")
    votes: Mapped[list[PollVote]] = relationship(
        "PollVote",
        back_populates="option",
        lazy="selectin",
        cascade="all, delete-orphan",
    )


class PollVote(IntegerPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "poll_votes"
    __table_args__ = (
        UniqueConstraint("option_id", "user_id", name="uq_poll_votes_option_user"),
        Index("ix_poll_votes_poll_user", "poll_id", "user_id"),
    )

    poll_id: Mapped[str] = mapped_column(
        ForeignKey("polls.id", ondelete="CASCADE"),
        nullable=False,
        comment="所属 Poll ID。",
    )
    option_id: Mapped[str] = mapped_column(
        ForeignKey("poll_options.id", ondelete="CASCADE"),
        nullable=False,
        comment="被选择的 Poll 选项 ID。",
    )
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        comment="投票用户 ID。",
    )

    poll: Mapped[Poll] = relationship("Poll", lazy="selectin")
    option: Mapped[PollOption] = relationship("PollOption", back_populates="votes", lazy="selectin")
    user: Mapped[User] = relationship("User", lazy="selectin")

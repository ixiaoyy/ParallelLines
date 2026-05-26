from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.db.base import utcnow
from app.models.forum import (
    Board,
    BoardDefaultSort,
    BoardInvitation,
    BoardMember,
    NotificationLevel,
    Poll,
    PollOption,
    Post,
    PostRevision,
    Topic,
)
from app.schemas.common import ORMModel

TopicSort = Literal["latest", "hot", "top", "votes", "relevance"]
PostSort = Literal["chronological", "qa"]


class BoardCreateRequest(BaseModel):
    slug: str = Field(min_length=2, max_length=96, pattern=r"^[a-z0-9][a-z0-9-]*$")
    name: str = Field(min_length=2, max_length=80)
    description: str = Field(min_length=2, max_length=2000)
    color: str = Field(default="#409EFF", max_length=32)
    visibility: Literal["public", "private", "unlisted"] = "public"
    parent_board_id: str | None = Field(default=None, max_length=36)
    parent_board_slug: str | None = Field(default=None, max_length=96)
    required_tags: list[str] = Field(default_factory=list, max_length=12)
    allowed_tags: list[str] = Field(default_factory=list, max_length=40)
    post_template: str | None = Field(default=None, max_length=10_000)
    default_notification_level: NotificationLevel = "normal"
    default_sort: BoardDefaultSort = "latest"


class BoardResponse(ORMModel):
    id: str
    slug: str
    name: str
    name_localizations: dict[str, str] = Field(default_factory=dict)
    description: str
    color: str
    avatar_url: str | None = None
    owner_id: str | None = None
    parent_board_id: str | None = None
    parent_board_slug: str | None = None
    parent_board_name: str | None = None
    visibility: str
    required_tags: list[str] = Field(default_factory=list)
    allowed_tags: list[str] = Field(default_factory=list)
    post_template: str | None = None
    default_notification_level: NotificationLevel
    default_sort: BoardDefaultSort
    topic_count: int
    post_count: int
    follower_count: int
    is_following: bool = False
    notification_level: NotificationLevel | None = None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_board(cls, board: Board, member: BoardMember | None = None) -> BoardResponse:
        return cls(
            id=board.id,
            slug=board.slug,
            name=board.name,
            name_localizations=dict(board.name_localizations or {}),
            description=board.description,
            color=board.color,
            avatar_url=board.avatar_url,
            owner_id=board.owner_id,
            parent_board_id=board.parent_board_id,
            parent_board_slug=board.parent_board.slug if board.parent_board else None,
            parent_board_name=board.parent_board.name if board.parent_board else None,
            visibility=board.visibility,
            required_tags=list(board.required_tags or []),
            allowed_tags=list(board.allowed_tags or []),
            post_template=board.post_template,
            default_notification_level=board.default_notification_level,
            default_sort=board.default_sort,
            topic_count=board.topic_count,
            post_count=board.post_count,
            follower_count=board.follower_count,
            is_following=member is not None,
            notification_level=member.notification_level if member else None,
            created_at=board.created_at,
            updated_at=board.updated_at,
        )


class TagResponse(ORMModel):
    id: str
    name: str
    slug: str
    topic_count: int


class PollCreateRequest(BaseModel):
    question: str = Field(min_length=4, max_length=240)
    options: list[str] = Field(min_length=2, max_length=10)
    multiple_choice: bool = False
    closes_at: datetime | None = None


class PollOptionResponse(BaseModel):
    id: str
    label: str
    position: int
    vote_count: int

    @classmethod
    def from_model(cls, option: PollOption) -> PollOptionResponse:
        return cls(
            id=option.id,
            label=option.label,
            position=option.position,
            vote_count=option.vote_count,
        )


class PollResponse(BaseModel):
    id: str
    topic_id: str
    question: str
    multiple_choice: bool
    closes_at: datetime | None = None
    closed: bool
    total_votes: int
    selected_option_ids: list[str] = Field(default_factory=list)
    options: list[PollOptionResponse]
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_model(cls, poll: Poll) -> PollResponse:
        selected_option_ids = list(getattr(poll, "selected_option_ids", []))
        closes_at = poll.closes_at
        if closes_at is not None and closes_at.tzinfo is None:
            closes_at = closes_at.replace(tzinfo=utcnow().tzinfo)
        closed = closes_at is not None and closes_at <= utcnow()
        return cls(
            id=poll.id,
            topic_id=poll.topic_id,
            question=poll.question,
            multiple_choice=poll.multiple_choice,
            closes_at=closes_at,
            closed=closed,
            total_votes=poll.total_votes,
            selected_option_ids=selected_option_ids,
            options=[
                PollOptionResponse.from_model(option)
                for option in sorted(poll.options, key=lambda item: item.position)
            ],
            created_at=poll.created_at,
            updated_at=poll.updated_at,
        )


class TopicSolutionRequest(BaseModel):
    post_id: str | None = Field(default=None, max_length=36)


class PollVoteRequest(BaseModel):
    option_ids: list[str] = Field(default_factory=list, max_length=10)


class TopicCreateRequest(BaseModel):
    title: str = Field(min_length=4, max_length=180)
    raw_md: str = Field(min_length=1, max_length=20_000)
    tags: list[str] = Field(default_factory=list, max_length=8)
    pinned: bool = False
    featured: bool = False
    poll: PollCreateRequest | None = None


class BoardSettingsUpdateRequest(BaseModel):
    parent_board_id: str | None = Field(default=None, max_length=36)
    parent_board_slug: str | None = Field(default=None, max_length=96)
    required_tags: list[str] = Field(default_factory=list, max_length=12)
    allowed_tags: list[str] = Field(default_factory=list, max_length=40)
    post_template: str | None = Field(default=None, max_length=10_000)
    default_notification_level: NotificationLevel = "normal"
    default_sort: BoardDefaultSort = "latest"


class BoardMemberUpdateRequest(BaseModel):
    role: Literal["follower", "moderator"]
    notification_level: NotificationLevel | None = None


class PostCreateRequest(BaseModel):
    raw_md: str = Field(min_length=1, max_length=20_000)
    parent_post_id: str | None = None


class PostUpdateRequest(BaseModel):
    raw_md: str = Field(min_length=1, max_length=20_000)
    edit_reason: str | None = Field(default=None, max_length=500)


class PostRevisionRestoreRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=500)


class TopicLifecycleRequest(BaseModel):
    status: Literal["open", "closed", "archived"] | None = None
    pinned: bool | None = None
    note: str | None = Field(default=None, max_length=500)


class TopicMoveRequest(BaseModel):
    board_id: str | None = Field(default=None, max_length=36)
    board_slug: str | None = Field(default=None, max_length=96)
    note: str | None = Field(default=None, max_length=500)


class TopicSplitRequest(BaseModel):
    title: str = Field(min_length=4, max_length=180)
    post_ids: list[str] = Field(min_length=1, max_length=100)
    board_id: str | None = Field(default=None, max_length=36)
    board_slug: str | None = Field(default=None, max_length=96)
    note: str | None = Field(default=None, max_length=500)


class TopicMergeRequest(BaseModel):
    target_topic_id: str = Field(min_length=1, max_length=36)
    note: str | None = Field(default=None, max_length=500)


class TopicResponse(BaseModel):
    id: str
    slug: str
    title: str
    title_localizations: dict[str, str] = Field(default_factory=dict)
    board_id: str
    board_slug: str
    board_name: str
    board_color: str
    author_id: str
    author_name: str
    author_avatar_url: str | None = None
    author_role: str
    author_level: int
    author_trust_level: int
    author_trust_level_label: str
    tags: list[str]
    accepted_answer_post_id: str | None = None
    solved_at: datetime | None = None
    solved_by_id: str | None = None
    answer_mode: bool = False
    vote_score: int = 0
    vote_count: int = 0
    my_vote: int = 0
    poll: PollResponse | None = None
    topic_type: str
    visibility: str
    status: str
    pinned: bool
    featured: bool
    view_count: int
    reply_count: int
    like_count: int
    liked_by_me: bool = False
    bookmark_count: int = 0
    bookmarked_by_me: bool = False
    hot_score: float
    last_posted_at: datetime
    created_at: datetime
    updated_at: datetime
    merged_into_topic_id: str | None = None
    share_url: str
    excerpt: str

    @classmethod
    def from_model(cls, topic: Topic) -> TopicResponse:
        first_post = next((p for p in topic.posts if p.post_number == 1), None)
        if not first_post and topic.posts:
            first_post = sorted(topic.posts, key=lambda p: p.post_number)[0]

        excerpt = ""
        if first_post:
            cleaned = " ".join(first_post.raw_md.split())
            excerpt = cleaned[:140] + "..." if len(cleaned) > 140 else cleaned

        return cls(
            id=topic.id,
            slug=topic.slug,
            title=topic.title,
            title_localizations=dict(topic.title_localizations or {}),
            board_id=topic.board_id,
            board_slug=topic.board.slug,
            board_name=topic.board.name,
            board_color=topic.board.color,
            author_id=topic.user_id,
            author_name=topic.author.username,
            author_avatar_url=topic.author.avatar_url,
            author_role=topic.author.role,
            author_level=topic.author.level,
            author_trust_level=topic.author.trust_level,
            author_trust_level_label=topic.author.trust_level_label,
            tags=[tag.name for tag in topic.tags],
            accepted_answer_post_id=topic.accepted_answer_post_id,
            solved_at=topic.solved_at,
            solved_by_id=topic.solved_by_id,
            answer_mode=topic.answer_mode,
            vote_score=topic.vote_score,
            vote_count=topic.vote_count,
            my_vote=int(getattr(topic, "my_vote", 0) or 0),
            poll=(
                PollResponse.from_model(topic.__dict__["poll"])
                if topic.__dict__.get("poll")
                else None
            ),
            topic_type=topic.topic_type,
            visibility=topic.visibility,
            status=topic.status,
            pinned=topic.pinned,
            featured=topic.featured,
            view_count=topic.view_count,
            reply_count=topic.reply_count,
            like_count=topic.like_count,
            liked_by_me=bool(getattr(topic, "liked_by_me", False)),
            bookmark_count=int(getattr(topic, "bookmark_count", 0) or 0),
            bookmarked_by_me=bool(getattr(topic, "bookmarked_by_me", False)),
            hot_score=topic.hot_score,
            last_posted_at=topic.last_posted_at,
            created_at=topic.created_at,
            updated_at=topic.updated_at,
            merged_into_topic_id=topic.merged_into_topic_id,
            share_url=f"/topics/{topic.id}/{topic.slug}",
            excerpt=excerpt,
        )


class PostResponse(BaseModel):
    id: str
    topic_id: str
    user_id: str
    author_name: str
    author_role: str
    author_level: int
    author_trust_level: int
    author_trust_level_label: str
    parent_id: str | None = None
    post_number: int
    raw_md: str
    cooked_html: str
    reply_count: int
    like_count: int
    liked_by_me: bool = False
    accepted_answer: bool = False
    vote_score: int = 0
    vote_count: int = 0
    my_vote: int = 0
    share_url: str
    deleted_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_model(cls, post: Post) -> PostResponse:
        hidden = post.deleted_at is not None
        topic = getattr(post, "topic", None)
        accepted_answer = bool(
            getattr(post, "accepted_answer", False)
            or (topic is not None and topic.accepted_answer_post_id == post.id)
        )
        return cls(
            id=post.id,
            topic_id=post.topic_id,
            user_id=post.user_id,
            author_name=post.author.username,
            author_role=post.author.role,
            author_level=post.author.level,
            author_trust_level=post.author.trust_level,
            author_trust_level_label=post.author.trust_level_label,
            parent_id=post.parent_id,
            post_number=post.post_number,
            raw_md="" if hidden else post.raw_md,
            cooked_html="" if hidden else post.cooked_html,
            reply_count=post.reply_count,
            like_count=post.like_count,
            liked_by_me=bool(getattr(post, "liked_by_me", False)),
            accepted_answer=accepted_answer,
            vote_score=post.vote_score,
            vote_count=post.vote_count,
            my_vote=int(getattr(post, "my_vote", 0) or 0),
            share_url=f"/topics/{post.topic_id}/{topic.slug}#post-{post.post_number}"
            if topic is not None
            else f"/topics/{post.topic_id}#post-{post.post_number}",
            deleted_at=post.deleted_at,
            created_at=post.created_at,
            updated_at=post.updated_at,
        )


class PostRevisionResponse(BaseModel):
    id: str
    post_id: str
    topic_id: str
    version_number: int
    editor_id: str | None = None
    editor_name: str | None = None
    raw_md: str
    cooked_html: str
    edit_reason: str | None = None
    summary: str
    restored_from_revision_id: str | None = None
    created_at: datetime

    @classmethod
    def from_model(cls, revision: PostRevision) -> PostRevisionResponse:
        return cls(
            id=revision.id,
            post_id=revision.post_id,
            topic_id=revision.topic_id,
            version_number=revision.version_number,
            editor_id=revision.editor_id,
            editor_name=revision.editor.username if revision.editor else None,
            raw_md=revision.raw_md,
            cooked_html=revision.cooked_html,
            edit_reason=revision.edit_reason,
            summary=revision.summary,
            restored_from_revision_id=revision.restored_from_revision_id,
            created_at=revision.created_at,
        )


class TopicDetailResponse(TopicResponse):
    posts: list[PostResponse]

    @classmethod
    def from_topic_and_posts(cls, topic: Topic, posts: list[Post]) -> TopicDetailResponse:
        topic_data = TopicResponse.from_model(topic).model_dump()
        return cls(**topic_data, posts=[PostResponse.from_model(post) for post in posts])


class TopicLifecycleResponse(BaseModel):
    source_topic: TopicResponse | None = None
    target_topic: TopicResponse
    moved_post_count: int = 0
    audit_action: str


class BoardMemberResponse(BaseModel):
    user_id: str
    username: str
    role: str
    notification_level: NotificationLevel
    joined_at: datetime

    @classmethod
    def from_member(cls, member: BoardMember) -> BoardMemberResponse:
        return cls(
            user_id=member.user_id,
            username=member.user.username,
            role=member.role,
            notification_level=member.notification_level,
            joined_at=member.joined_at,
        )


class BoardMemberRemoveResponse(BaseModel):
    board_id: str
    username: str
    removed: bool


class BoardDetailResponse(BoardResponse):
    latest_topics: list[TopicResponse]
    child_boards: list[BoardResponse] = Field(default_factory=list)

    @classmethod
    def from_board_and_topics(
        cls,
        board: Board,
        topics: list[Topic],
        member: BoardMember | None = None,
        child_boards: list[Board] | None = None,
        child_memberships: dict[str, BoardMember] | None = None,
    ) -> BoardDetailResponse:
        board_data = BoardResponse.from_board(board, member).model_dump()
        return cls(
            **board_data,
            latest_topics=[TopicResponse.from_model(topic) for topic in topics],
            child_boards=[
                BoardResponse.from_board(
                    child_board,
                    (child_memberships or {}).get(child_board.id),
                )
                for child_board in (child_boards or [])
            ],
        )


class BoardSettingsResponse(BaseModel):
    board: BoardResponse
    members: list[BoardMemberResponse]


class BoardInviteCreateRequest(BaseModel):
    board_id: str = Field(min_length=1, max_length=36)
    username: str = Field(min_length=3, max_length=32)


class BoardInviteResponse(BaseModel):
    id: str
    board_id: str
    board_slug: str
    board_name: str
    board_description: str
    board_color: str
    inviter_id: str
    inviter_name: str
    invitee_id: str
    invitee_name: str
    status: str
    expires_at: datetime | None = None
    responded_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_model(cls, invitation: BoardInvitation) -> BoardInviteResponse:
        return cls(
            id=invitation.id,
            board_id=invitation.board_id,
            board_slug=invitation.board.slug,
            board_name=invitation.board.name,
            board_description=invitation.board.description,
            board_color=invitation.board.color,
            inviter_id=invitation.inviter_id,
            inviter_name=invitation.inviter.username,
            invitee_id=invitation.invitee_id,
            invitee_name=invitation.invitee.username,
            status=invitation.status,
            expires_at=invitation.expires_at,
            responded_at=invitation.responded_at,
            created_at=invitation.created_at,
            updated_at=invitation.updated_at,
        )


class MyBoardInvitesResponse(BaseModel):
    received: list[BoardInviteResponse]
    managed: list[BoardInviteResponse]
    owned_boards: list[BoardResponse]


class TagListResponse(BaseModel):
    tags: list[TagResponse]

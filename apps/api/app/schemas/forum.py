from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.models.forum import Board, BoardInvitation, Post, PostRevision, Topic
from app.schemas.common import ORMModel

TopicSort = Literal["latest", "hot", "top"]


class BoardCreateRequest(BaseModel):
    slug: str = Field(min_length=2, max_length=96, pattern=r"^[a-z0-9][a-z0-9-]*$")
    name: str = Field(min_length=2, max_length=80)
    description: str = Field(min_length=2, max_length=2000)
    color: str = Field(default="#3B82F6", max_length=32)
    visibility: Literal["public", "private", "unlisted"] = "public"


class BoardResponse(ORMModel):
    id: str
    slug: str
    name: str
    description: str
    color: str
    avatar_url: str | None = None
    owner_id: str | None = None
    visibility: str
    topic_count: int
    post_count: int
    follower_count: int
    created_at: datetime
    updated_at: datetime


class TagResponse(ORMModel):
    id: str
    name: str
    slug: str
    topic_count: int


class TopicCreateRequest(BaseModel):
    title: str = Field(min_length=4, max_length=180)
    raw_md: str = Field(min_length=1, max_length=20_000)
    tags: list[str] = Field(default_factory=list, max_length=8)
    pinned: bool = False
    featured: bool = False


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
    board_id: str
    board_slug: str
    board_name: str
    board_color: str
    author_id: str
    author_name: str
    tags: list[str]
    status: str
    pinned: bool
    featured: bool
    view_count: int
    reply_count: int
    like_count: int
    hot_score: float
    last_posted_at: datetime
    created_at: datetime
    updated_at: datetime
    merged_into_topic_id: str | None = None
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
            board_id=topic.board_id,
            board_slug=topic.board.slug,
            board_name=topic.board.name,
            board_color=topic.board.color,
            author_id=topic.user_id,
            author_name=topic.author.username,
            tags=[tag.name for tag in topic.tags],
            status=topic.status,
            pinned=topic.pinned,
            featured=topic.featured,
            view_count=topic.view_count,
            reply_count=topic.reply_count,
            like_count=topic.like_count,
            hot_score=topic.hot_score,
            last_posted_at=topic.last_posted_at,
            created_at=topic.created_at,
            updated_at=topic.updated_at,
            merged_into_topic_id=topic.merged_into_topic_id,
            excerpt=excerpt,
        )


class PostResponse(BaseModel):
    id: str
    topic_id: str
    user_id: str
    author_name: str
    parent_id: str | None = None
    post_number: int
    raw_md: str
    cooked_html: str
    reply_count: int
    like_count: int
    deleted_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_model(cls, post: Post) -> PostResponse:
        hidden = post.deleted_at is not None
        return cls(
            id=post.id,
            topic_id=post.topic_id,
            user_id=post.user_id,
            author_name=post.author.username,
            parent_id=post.parent_id,
            post_number=post.post_number,
            raw_md="" if hidden else post.raw_md,
            cooked_html="" if hidden else post.cooked_html,
            reply_count=post.reply_count,
            like_count=post.like_count,
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


class BoardDetailResponse(BoardResponse):
    latest_topics: list[TopicResponse]

    @classmethod
    def from_board_and_topics(cls, board: Board, topics: list[Topic]) -> BoardDetailResponse:
        board_data = BoardResponse.model_validate(board).model_dump()
        return cls(
            **board_data, latest_topics=[TopicResponse.from_model(topic) for topic in topics]
        )


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

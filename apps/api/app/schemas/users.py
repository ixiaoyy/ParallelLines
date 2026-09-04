from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field

from app.core.personas import PersonaKind
from app.models.forum import Topic
from app.models.social import PrivateMessageParticipant
from app.schemas.badges import UserBadgeResponse
from app.schemas.common import ORMModel
from app.schemas.forum import TopicResponse


class UserPublic(ORMModel):
    id: str
    username: str
    email: EmailStr
    avatar_url: str | None = None
    display_name: str | None = None
    bio: str | None = None
    website_url: str | None = None
    location: str | None = None
    role: str
    level: int
    trust_level: int
    trust_level_label: str
    points_balance: int
    experience_total: int
    experience_to_next_level: int
    level_progress_percent: int
    status: str
    two_factor_enabled: bool
    profile_visibility: str
    show_activity: bool
    interface_theme: str
    locale: str
    created_at: datetime


class UserProfileResponse(ORMModel):
    is_persona: bool
    persona_kind: PersonaKind | None
    id: str
    username: str
    avatar_url: str | None = None
    display_name: str | None = None
    bio: str | None = None
    website_url: str | None = None
    location: str | None = None
    role: str
    level: int
    trust_level: int
    trust_level_label: str
    points_balance: int
    experience_total: int
    experience_to_next_level: int
    level_progress_percent: int
    status: str
    profile_visibility: str
    show_activity: bool
    can_edit: bool = False
    created_at: datetime
    topic_count: int
    post_count: int
    following_count: int
    follower_count: int
    badges: list[UserBadgeResponse] = Field(default_factory=list)


class UserProfileUpdateRequest(BaseModel):
    display_name: str | None = Field(default=None, max_length=80)
    bio: str | None = Field(default=None, max_length=1000)
    website_url: str | None = Field(default=None, max_length=512)
    location: str | None = Field(default=None, max_length=120)
    profile_visibility: Literal["public", "members", "private"] | None = None
    show_activity: bool | None = None
    interface_theme: Literal["system", "light", "colorful"] | None = None
    locale: Literal["zh-CN", "en-US"] | None = None


class UserDirectoryResponse(BaseModel):
    is_persona: bool
    persona_kind: PersonaKind | None
    id: str
    username: str
    display_name: str | None = None
    avatar_url: str | None = None
    role: str
    level: int
    trust_level: int
    trust_level_label: str
    points_balance: int
    topic_count: int
    post_count: int
    last_seen_at: datetime | None = None
    created_at: datetime


class UserRelationshipUserResponse(BaseModel):
    is_persona: bool
    persona_kind: PersonaKind | None
    id: str
    username: str
    display_name: str | None = None
    avatar_url: str | None = None
    role: str
    level: int
    trust_level: int
    trust_level_label: str
    topic_count: int
    post_count: int
    followed_at: datetime


class UserActivityItemResponse(BaseModel):
    id: str
    type: Literal["post", "liked_topic", "liked_post", "bookmarked_topic", "bookmarked_post"]
    created_at: datetime
    topic_id: str
    topic_title: str
    topic_slug: str
    post_number: int | None = None
    excerpt: str


class UserRelationshipStateResponse(BaseModel):
    target_user_id: str
    target_username: str
    following: bool
    ignored: bool
    blocked: bool
    followed_by: bool


class PrivateMessageCreateRequest(BaseModel):
    participant_usernames: list[str] = Field(min_length=1, max_length=20)
    title: str = Field(min_length=2, max_length=180)
    raw_md: str = Field(min_length=1, max_length=20_000)


class PrivateMessageParticipantResponse(BaseModel):
    user_id: str
    username: str
    role: str
    last_read_post_number: int
    muted: bool

    @classmethod
    def from_model(
        cls,
        participant: PrivateMessageParticipant,
    ) -> "PrivateMessageParticipantResponse":
        return cls(
            user_id=participant.user_id,
            username=participant.user.username,
            role=participant.role,
            last_read_post_number=participant.last_read_post_number,
            muted=participant.muted,
        )


class PrivateMessageTopicResponse(BaseModel):
    topic: TopicResponse
    participants: list[PrivateMessageParticipantResponse]
    unread: bool

    @classmethod
    def from_topic(
        cls,
        topic: Topic,
        participants: list[PrivateMessageParticipant],
        *,
        current_user_id: str,
    ) -> "PrivateMessageTopicResponse":
        own_participant = next(
            (participant for participant in participants if participant.user_id == current_user_id),
            None,
        )
        last_read_post_number = own_participant.last_read_post_number if own_participant else 0
        return cls(
            topic=TopicResponse.from_model(topic),
            participants=[
                PrivateMessageParticipantResponse.from_model(participant)
                for participant in participants
            ],
            unread=topic.reply_count + 1 > last_read_post_number,
        )

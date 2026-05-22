from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from app.models.forum import Topic
from app.models.social import PrivateMessageParticipant
from app.schemas.common import ORMModel
from app.schemas.forum import TopicResponse


class UserPublic(ORMModel):
    id: str
    username: str
    email: EmailStr
    avatar_url: str | None = None
    role: str
    level: int
    status: str
    two_factor_enabled: bool
    created_at: datetime


class UserProfileResponse(ORMModel):
    id: str
    username: str
    avatar_url: str | None = None
    role: str
    level: int
    status: str
    created_at: datetime
    topic_count: int
    post_count: int


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

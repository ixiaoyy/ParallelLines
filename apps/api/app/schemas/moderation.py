from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.models.moderation import AuditLog, Flag
from app.schemas.common import ORMModel

FlagTargetType = Literal["topic", "post"]
FlagReason = Literal["spam", "harassment", "off_topic", "private_info", "other"]
FlagStatus = Literal["pending", "resolved", "rejected"]
UserModerationStatus = Literal["active", "silenced", "suspended"]


class FlagCreateRequest(BaseModel):
    target_type: FlagTargetType
    target_id: str = Field(min_length=1, max_length=36)
    reason: FlagReason = "other"
    detail: str | None = Field(default=None, max_length=2_000)


class FlagStatusUpdateRequest(BaseModel):
    status: FlagStatus
    resolution_note: str | None = Field(default=None, max_length=2_000)


class HideContentRequest(BaseModel):
    note: str | None = Field(default=None, max_length=2_000)


class UserStatusUpdateRequest(BaseModel):
    status: UserModerationStatus
    note: str | None = Field(default=None, max_length=2_000)


class ModerationTargetResponse(BaseModel):
    target_type: str
    target_id: str
    topic_id: str | None = None
    topic_slug: str | None = None
    post_number: int | None = None
    board_id: str
    board_slug: str
    board_name: str
    author_id: str
    author_name: str
    title: str
    excerpt: str
    hidden: bool


class FlagResponse(ORMModel):
    id: str
    target_type: str
    target_id: str
    board_id: str
    reporter_id: str
    reporter_name: str
    reason: str
    detail: str | None = None
    status: str
    resolution_note: str | None = None
    resolved_by_id: str | None = None
    resolved_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    target: ModerationTargetResponse

    @classmethod
    def from_model(cls, flag: Flag, target: ModerationTargetResponse) -> "FlagResponse":
        return cls(
            id=flag.id,
            target_type=flag.target_type,
            target_id=flag.target_id,
            board_id=flag.board_id,
            reporter_id=flag.reporter_id,
            reporter_name=flag.reporter.username,
            reason=flag.reason,
            detail=flag.detail,
            status=flag.status,
            resolution_note=flag.resolution_note,
            resolved_by_id=flag.resolved_by_id,
            resolved_at=flag.resolved_at,
            created_at=flag.created_at,
            updated_at=flag.updated_at,
            target=target,
        )


class ModerationActionResponse(BaseModel):
    target_type: str
    target_id: str
    hidden: bool
    status: str | None = None


class UserStatusResponse(BaseModel):
    user_id: str
    username: str
    status: str


class AuditLogResponse(BaseModel):
    id: str
    actor_id: str | None = None
    actor_name: str | None = None
    action: str
    target_type: str
    target_id: str
    board_id: str | None = None
    data: dict[str, object]
    created_at: datetime

    @classmethod
    def from_model(cls, log: AuditLog) -> "AuditLogResponse":
        return cls(
            id=log.id,
            actor_id=log.actor_id,
            actor_name=log.actor.username if log.actor else None,
            action=log.action,
            target_type=log.target_type,
            target_id=log.target_id,
            board_id=log.board_id,
            data=log.data,
            created_at=log.created_at,
        )

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.models.moderation import (
    AuditLog,
    Flag,
    Reviewable,
    ReviewableEvent,
    ScreenedRule,
    SpamAction,
)
from app.schemas.common import ORMModel

FlagTargetType = Literal["topic", "post"]
FlagReason = Literal["spam", "harassment", "off_topic", "private_info", "other"]
FlagStatus = Literal["pending", "resolved", "rejected"]
ReviewableStatus = Literal[
    "pending",
    "claimed",
    "approved",
    "rejected",
    "hidden",
    "deleted",
    "silenced",
    "escalated",
    "appealed",
]
ReviewableType = Literal["flag", "queued_topic", "queued_post", "queued_edit", "appeal", "system"]
ReviewableDecisionAction = Literal["approve", "reject", "hide", "delete", "silence", "escalate"]
UserModerationStatus = Literal["active", "silenced", "suspended"]
ScreenedRuleKind = Literal["email", "ip", "url"]
ScreenedRuleAction = Literal["block", "silence"]


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


class ReviewableDecisionRequest(BaseModel):
    action: ReviewableDecisionAction
    note: str | None = Field(default=None, max_length=2_000)


class ReviewableAppealRequest(BaseModel):
    reason: str = Field(min_length=4, max_length=2_000)


class ScreenedRuleCreateRequest(BaseModel):
    kind: ScreenedRuleKind
    value: str = Field(min_length=1, max_length=255)
    action: ScreenedRuleAction = "block"
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


class ReviewableEventResponse(BaseModel):
    id: str
    actor_id: str | None = None
    actor_name: str | None = None
    event: str
    from_status: str | None = None
    to_status: str | None = None
    note: str | None = None
    data: dict[str, object]
    created_at: datetime

    @classmethod
    def from_model(cls, event: ReviewableEvent) -> "ReviewableEventResponse":
        return cls(
            id=event.id,
            actor_id=event.actor_id,
            actor_name=event.actor.username if event.actor else None,
            event=event.event,
            from_status=event.from_status,
            to_status=event.to_status,
            note=event.note,
            data=event.data,
            created_at=event.created_at,
        )


class ReviewableResponse(BaseModel):
    id: str
    type: str
    status: str
    priority: int
    source: str
    source_summary: str
    target_type: str | None = None
    target_id: str | None = None
    board_id: str | None = None
    board_name: str | None = None
    topic_id: str | None = None
    post_id: str | None = None
    flag_id: str | None = None
    created_by_id: str | None = None
    created_by_name: str | None = None
    target_user_id: str | None = None
    target_user_name: str | None = None
    assigned_to_id: str | None = None
    assigned_to_name: str | None = None
    assigned_at: datetime | None = None
    resolved_by_id: str | None = None
    resolved_by_name: str | None = None
    resolved_at: datetime | None = None
    appeal_available: bool = False
    data: dict[str, object]
    events: list[ReviewableEventResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_model(
        cls,
        reviewable: Reviewable,
        *,
        include_private_data: bool = True,
        current_user_id: str | None = None,
    ) -> "ReviewableResponse":
        data = reviewable.data if include_private_data else public_reviewable_data(reviewable.data)
        return cls(
            id=reviewable.id,
            type=reviewable.type,
            status=reviewable.status,
            priority=reviewable.priority,
            source=reviewable.source,
            source_summary=reviewable.source_summary,
            target_type=reviewable.target_type,
            target_id=reviewable.target_id,
            board_id=reviewable.board_id,
            board_name=reviewable.board.name if reviewable.board else None,
            topic_id=reviewable.topic_id,
            post_id=reviewable.post_id,
            flag_id=reviewable.flag_id,
            created_by_id=reviewable.created_by_id,
            created_by_name=reviewable.created_by.username if reviewable.created_by else None,
            target_user_id=reviewable.target_user_id,
            target_user_name=reviewable.target_user.username if reviewable.target_user else None,
            assigned_to_id=reviewable.assigned_to_id,
            assigned_to_name=reviewable.assigned_to.username if reviewable.assigned_to else None,
            assigned_at=reviewable.assigned_at,
            resolved_by_id=reviewable.resolved_by_id,
            resolved_by_name=reviewable.resolved_by.username if reviewable.resolved_by else None,
            resolved_at=reviewable.resolved_at,
            appeal_available=can_user_appeal(reviewable, current_user_id),
            data=data,
            events=[
                ReviewableEventResponse.from_model(event)
                for event in sorted(reviewable.events, key=lambda item: item.created_at)
            ],
            created_at=reviewable.created_at,
            updated_at=reviewable.updated_at,
        )


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


class ScreenedRuleResponse(BaseModel):
    id: str
    kind: str
    value: str
    action: str
    note: str | None = None
    active: bool
    created_by_id: str | None = None
    created_by_name: str | None = None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_model(cls, rule: ScreenedRule) -> "ScreenedRuleResponse":
        return cls(
            id=rule.id,
            kind=rule.kind,
            value=rule.value,
            action=rule.action,
            note=rule.note,
            active=rule.active,
            created_by_id=rule.created_by_id,
            created_by_name=rule.created_by.username if rule.created_by else None,
            created_at=rule.created_at,
            updated_at=rule.updated_at,
        )


class SpamActionResponse(BaseModel):
    id: str
    kind: str
    action: str
    reason: str
    user_id: str | None = None
    username: str | None = None
    ip_address: str | None = None
    email: str | None = None
    url: str | None = None
    screened_rule_id: str | None = None
    data: dict[str, object]
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_model(cls, action: SpamAction) -> "SpamActionResponse":
        return cls(
            id=action.id,
            kind=action.kind,
            action=action.action,
            reason=action.reason,
            user_id=action.user_id,
            username=action.user.username if action.user else None,
            ip_address=action.ip_address,
            email=action.email,
            url=action.url,
            screened_rule_id=action.screened_rule_id,
            data=action.data,
            created_at=action.created_at,
            updated_at=action.updated_at,
        )


def can_user_appeal(reviewable: Reviewable, current_user_id: str | None) -> bool:
    if current_user_id is None:
        return False
    if current_user_id not in {reviewable.created_by_id, reviewable.target_user_id}:
        return False
    return reviewable.status in {"rejected", "hidden", "deleted", "silenced", "escalated"}


def public_reviewable_data(data: dict[str, object]) -> dict[str, object]:
    public_keys = {
        "title",
        "excerpt",
        "fields",
        "matched_fields",
        "decision_action",
        "appeal_count",
    }
    return {key: value for key, value in data.items() if key in public_keys}

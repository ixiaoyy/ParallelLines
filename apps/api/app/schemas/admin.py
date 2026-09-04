from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.core.personas import PersonaKind, normalize_persona_kind
from app.models.admin import SiteSetting
from app.models.background_job import BackgroundJob, BackgroundJobLog
from app.models.user import User
from app.schemas.badges import UserBadgeResponse
from app.schemas.common import ORMModel
from app.schemas.moderation import AuditLogResponse


class SiteSettingUpdateRequest(BaseModel):
    value: object


class SiteSettingResponse(ORMModel):
    id: str
    key: str
    value: object
    data_type: str
    category: str
    description: str
    public: bool
    updated_by_id: str | None = None
    updated_by_name: str | None = None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_model(cls, setting: SiteSetting) -> "SiteSettingResponse":
        return cls(
            id=setting.id,
            key=setting.key,
            value=setting.value,
            data_type=setting.data_type,
            category=setting.category,
            description=setting.description,
            public=setting.public,
            updated_by_id=setting.updated_by_id,
            updated_by_name=setting.updated_by.username if setting.updated_by else None,
            created_at=setting.created_at,
            updated_at=setting.updated_at,
        )


class PublicSiteSettingsResponse(BaseModel):
    settings: dict[str, object]
    updated_at: datetime | None = None


class AdminUserUpdateRequest(BaseModel):
    role: Literal["user", "moderator", "admin"] | None = None
    status: Literal[
        "pending_verification", "active", "silenced", "suspended", "deleted"
    ] | None = None
    is_persona: bool | None = None
    persona_kind: PersonaKind | None = None
    level: int | None = Field(default=None, ge=0, le=5)
    points_delta: int | None = Field(default=None, ge=-100_000, le=100_000)
    experience_delta: int | None = Field(default=None, ge=-100_000, le=100_000)
    adjustment_reason: str | None = Field(default=None, max_length=500)


class AdminUserResponse(ORMModel):
    id: str
    username: str
    email: str
    avatar_url: str | None = None
    role: str
    level: int
    trust_level: int
    trust_level_label: str
    points_balance: int
    experience_total: int
    experience_to_next_level: int
    level_progress_percent: int
    status: str
    is_persona: bool
    persona_kind: PersonaKind | None
    two_factor_enabled: bool
    created_at: datetime
    updated_at: datetime
    last_seen_at: datetime | None = None
    topic_count: int
    post_count: int
    badges: list[UserBadgeResponse] = Field(default_factory=list)

    @classmethod
    def from_model(
        cls,
        user: User,
        *,
        topic_count: int = 0,
        post_count: int = 0,
        badges: list[UserBadgeResponse] | None = None,
    ) -> "AdminUserResponse":
        return cls(
            id=user.id,
            username=user.username,
            email=user.email,
            avatar_url=user.avatar_url,
            role=user.role,
            level=user.level,
            trust_level=user.trust_level,
            trust_level_label=user.trust_level_label,
            points_balance=user.points_balance,
            experience_total=user.experience_total,
            experience_to_next_level=user.experience_to_next_level,
            level_progress_percent=user.level_progress_percent,
            status=user.status,
            is_persona=user.is_persona,
            persona_kind=normalize_persona_kind(user.is_persona, user.persona_kind),
            two_factor_enabled=user.two_factor_enabled,
            created_at=user.created_at,
            updated_at=user.updated_at,
            last_seen_at=user.last_seen_at,
            topic_count=topic_count,
            post_count=post_count,
            badges=badges or [],
        )


class AdminServiceStatusResponse(BaseModel):
    name: str
    status: Literal["ok", "degraded", "unknown"]
    detail: str


class AdminStatsResponse(BaseModel):
    users: int
    boards: int
    topics: int
    posts: int
    pending_flags: int
    audit_logs: int
    spam_actions: int


class AdminEmailLogResponse(BaseModel):
    to_email: str
    subject: str
    kind: str
    sent_at: datetime


class AdminBackgroundJobResponse(ORMModel):
    id: str
    queue: str
    task_name: str
    status: str
    idempotency_key: str | None = None
    priority: int
    run_at: datetime
    attempts: int
    max_attempts: int
    locked_at: datetime | None = None
    locked_by: str | None = None
    last_error: str | None = None
    result: dict[str, object] | None = None
    finished_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_model(cls, job: BackgroundJob) -> "AdminBackgroundJobResponse":
        return cls(
            id=job.id,
            queue=job.queue,
            task_name=job.task_name,
            status=job.status,
            idempotency_key=job.idempotency_key,
            priority=job.priority,
            run_at=job.run_at,
            attempts=job.attempts,
            max_attempts=job.max_attempts,
            locked_at=job.locked_at,
            locked_by=job.locked_by,
            last_error=job.last_error,
            result=job.result,
            finished_at=job.finished_at,
            created_at=job.created_at,
            updated_at=job.updated_at,
        )


class AdminBackgroundJobLogResponse(ORMModel):
    id: str
    job_id: str
    event: str
    message: str
    data: dict[str, object]
    created_at: datetime

    @classmethod
    def from_model(cls, log: BackgroundJobLog) -> "AdminBackgroundJobLogResponse":
        return cls(
            id=log.id,
            job_id=log.job_id,
            event=log.event,
            message=log.message,
            data=log.data,
            created_at=log.created_at,
        )


class AdminSystemOverviewResponse(BaseModel):
    version: str
    environment: str
    services: list[AdminServiceStatusResponse]
    stats: AdminStatsResponse
    queue: dict[str, object]
    recent_audit_logs: list[AuditLogResponse]
    recent_email_logs: list[AdminEmailLogResponse]
    recent_errors: list[dict[str, object]]

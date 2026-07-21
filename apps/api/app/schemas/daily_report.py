from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Literal, cast

from pydantic import BaseModel, Field

from app.models.daily_report import (
    DailyReport,
    DailyReportMessage,
    DailyReportProfile,
    DailyReportSession,
)

WorkText = Annotated[str, Field(min_length=1, max_length=500)]
DailyReportStyle = Literal["concise", "detailed", "result", "process"]


class DailyReportInput(BaseModel):
    work_date: date
    recurring_work: list[WorkText] = Field(default_factory=list, max_length=30)
    extra_work: list[WorkText] = Field(default_factory=list, max_length=30)
    risks: list[WorkText] = Field(default_factory=list, max_length=20)
    tomorrow_plan: list[WorkText] = Field(default_factory=list, max_length=30)
    style: DailyReportStyle = "detailed"


class DailyReportProfileUpdateRequest(BaseModel):
    custom_prompt: str = Field(min_length=1, max_length=6000)
    expected_version: int = Field(ge=1)


class DailyReportPreferenceAcceptRequest(BaseModel):
    requirement: str = Field(min_length=1, max_length=500)
    expected_version: int = Field(ge=1)


class DailyReportProfileResponse(BaseModel):
    custom_prompt: str
    preferences: dict[str, object]
    prompt_version: int
    ai_enabled: bool
    provider_mode: Literal["ai", "local_fallback"]
    model_name: str
    privacy_notice: str
    updated_at: datetime

    @classmethod
    def from_model(
        cls,
        profile: DailyReportProfile,
        *,
        ai_enabled: bool,
        provider_mode: Literal["ai", "local_fallback"],
        model_name: str,
    ) -> DailyReportProfileResponse:
        return cls(
            custom_prompt=profile.custom_prompt,
            preferences=dict(profile.preferences or {}),
            prompt_version=profile.prompt_version,
            ai_enabled=ai_enabled,
            provider_mode=provider_mode,
            model_name=model_name,
            privacy_notice=(
                "AI 模式会把本次工作内容、个人 Prompt 和少量相似历史日报发送到站点配置的模型服务；"
                "请勿填写密码、密钥或无需处理的敏感信息。"
                if ai_enabled
                else "当前未配置站点模型密钥，正在使用本地降级模式；内容不会发送到外部模型。"
            ),
            updated_at=profile.updated_at,
        )


class DailyReportSessionStartRequest(DailyReportInput):
    pass


class DailyReportSessionFollowupRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    current_content: str | None = Field(default=None, min_length=1, max_length=12000)
    expected_version: int = Field(ge=1)


class DailyReportSessionConfirmRequest(BaseModel):
    content: str = Field(min_length=1, max_length=12000)
    expected_version: int = Field(ge=1)


class DailyReportMessageResponse(BaseModel):
    id: str
    sequence: int
    role: Literal["user", "assistant"]
    content: str
    preference_suggestion: str | None = None
    created_at: datetime

    @classmethod
    def from_model(cls, message: DailyReportMessage) -> DailyReportMessageResponse:
        suggestion = (message.message_metadata or {}).get("preference_suggestion")
        return cls(
            id=message.id,
            sequence=message.sequence,
            role=cast(Literal["user", "assistant"], message.role),
            content=message.content,
            preference_suggestion=(
                str(suggestion).strip()[:500]
                if isinstance(suggestion, str) and suggestion
                else None
            ),
            created_at=message.created_at,
        )


class DailyReportSessionResponse(BaseModel):
    id: str
    work_date: date
    status: Literal["active", "confirmed"]
    input: DailyReportInput
    current_draft: str
    prompt_version: int
    version: int
    model_name: str
    provider_mode: Literal["ai", "local_fallback"]
    messages: list[DailyReportMessageResponse]
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_model(
        cls,
        session: DailyReportSession,
        messages: list[DailyReportMessage],
    ) -> DailyReportSessionResponse:
        return cls(
            id=session.id,
            work_date=session.work_date,
            status=cast(Literal["active", "confirmed"], session.status),
            input=DailyReportInput.model_validate(session.input_data),
            current_draft=session.current_draft,
            prompt_version=session.prompt_version,
            version=session.version,
            model_name=session.model_name,
            provider_mode=cast(Literal["ai", "local_fallback"], session.provider_mode),
            messages=[DailyReportMessageResponse.from_model(message) for message in messages],
            created_at=session.created_at,
            updated_at=session.updated_at,
        )


class DailyReportResponse(BaseModel):
    id: str
    session_id: str
    work_date: date
    content: str
    input: DailyReportInput
    prompt_version: int
    model_name: str
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_model(cls, report: DailyReport) -> DailyReportResponse:
        return cls(
            id=report.id,
            session_id=report.session_id,
            work_date=report.work_date,
            content=report.content,
            input=DailyReportInput.model_validate(report.source_input),
            prompt_version=report.prompt_version,
            model_name=report.model_name,
            created_at=report.created_at,
            updated_at=report.updated_at,
        )

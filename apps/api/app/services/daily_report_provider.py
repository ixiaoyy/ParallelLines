from __future__ import annotations

import asyncio
from dataclasses import dataclass

from app.core.config import Settings
from app.core.exceptions import AppError
from app.services.openai_chat import (
    extract_chat_content,
    extract_json_object,
    request_openai_chat,
)


@dataclass(frozen=True)
class DailyReportProviderResult:
    report: str
    reply: str
    preference_suggestion: str | None
    model_name: str
    provider_mode: str


class DailyReportProvider:
    async def generate(
        self,
        messages: list[dict[str, str]],
        *,
        fallback_report: str,
    ) -> DailyReportProviderResult:
        raise NotImplementedError


class OpenAICompatibleDailyReportProvider(DailyReportProvider):
    def __init__(self, settings: Settings, api_key: str) -> None:
        self.settings = settings
        self.api_key = api_key

    async def generate(
        self,
        messages: list[dict[str, str]],
        *,
        fallback_report: str,
    ) -> DailyReportProviderResult:
        del fallback_report
        payload = await asyncio.to_thread(
            request_openai_chat,
            base_url=self.settings.daily_report_ai_base_url,
            api_key=self.api_key,
            model=self.settings.daily_report_ai_model,
            messages=messages,
            temperature=self.settings.daily_report_ai_temperature,
            max_tokens=self.settings.daily_report_ai_max_tokens,
            timeout_seconds=self.settings.daily_report_ai_timeout_seconds,
            error_prefix="daily_report_provider",
            service_label="日报模型服务",
        )
        return parse_provider_result(payload, self.settings.daily_report_ai_model)


class LocalDailyReportProvider(DailyReportProvider):
    def __init__(self, model_name: str = "local-daily-report-v1") -> None:
        self.model_name = model_name

    async def generate(
        self,
        messages: list[dict[str, str]],
        *,
        fallback_report: str,
    ) -> DailyReportProviderResult:
        suggestion = local_preference_suggestion(messages[-1]["content"] if messages else "")
        return DailyReportProviderResult(
            report=fallback_report,
            reply=(
                "站点模型当前未配置或暂时不可用，已使用本地规则生成草稿。"
                "你仍可直接编辑并确认；本轮要求已保留在会话中。"
            ),
            preference_suggestion=suggestion,
            model_name=self.model_name,
            provider_mode="local_fallback",
        )


def configured_provider(settings: Settings) -> tuple[DailyReportProvider, bool]:
    api_key = (settings.daily_report_ai_api_key or settings.opencode_api_key).strip()
    if settings.daily_report_ai_provider != "local" and api_key:
        return OpenAICompatibleDailyReportProvider(settings, api_key), True
    return LocalDailyReportProvider(), False


def parse_provider_result(
    response: dict[str, object],
    fallback_model: str,
) -> DailyReportProviderResult:
    content = extract_chat_content(
        response,
        error_prefix="daily_report_provider",
        service_label="日报模型服务",
    )
    payload = extract_json_object(
        content,
        error_prefix="daily_report_provider",
        service_label="日报模型服务",
    )
    report = payload.get("report")
    reply = payload.get("reply")
    suggestion = payload.get("preference_suggestion")
    if not isinstance(report, str) or not report.strip():
        raise AppError(
            "daily_report_provider_invalid_response",
            "日报模型服务没有返回有效草稿",
            status_code=503,
        )
    return DailyReportProviderResult(
        report=report.strip()[:12000],
        reply=(
            reply.strip()[:1000] if isinstance(reply, str) and reply.strip() else "已更新日报草稿。"
        ),
        preference_suggestion=(
            suggestion.strip()[:500] if isinstance(suggestion, str) and suggestion.strip() else None
        ),
        model_name=str(response.get("model") or fallback_model)[:120],
        provider_mode="ai",
    )


def local_preference_suggestion(message: str) -> str | None:
    normalized = " ".join(message.split())
    durable_markers = ("以后", "每次", "固定", "一直", "不要", "避免", "都要")
    if normalized and any(marker in normalized for marker in durable_markers):
        return normalized[:500]
    return None

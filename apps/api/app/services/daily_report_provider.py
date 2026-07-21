from __future__ import annotations

import asyncio
import json
import re
import urllib.error
import urllib.request
from dataclasses import dataclass

from app.core.config import Settings
from app.core.exceptions import AppError


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
        payload = await asyncio.to_thread(self._request, messages)
        return parse_provider_result(payload, self.settings.daily_report_ai_model)

    def _request(self, messages: list[dict[str, str]]) -> dict[str, object]:
        base_url = self.settings.daily_report_ai_base_url.rstrip("/")
        url = base_url if base_url.endswith("/chat/completions") else f"{base_url}/chat/completions"
        body = {
            "model": self.settings.daily_report_ai_model,
            "messages": messages,
            "temperature": self.settings.daily_report_ai_temperature,
            "max_tokens": self.settings.daily_report_ai_max_tokens,
            "stream": False,
        }
        request = urllib.request.Request(
            url,
            data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
                "User-Agent": "ParallelLines/1.0",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(
                request,
                timeout=self.settings.daily_report_ai_timeout_seconds,
            ) as response:
                decoded = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise AppError(
                "daily_report_provider_error",
                f"日报模型服务返回 HTTP {exc.code}",
                status_code=503,
            ) from exc
        except (OSError, TimeoutError, json.JSONDecodeError) as exc:
            raise AppError(
                "daily_report_provider_unavailable",
                "日报模型服务暂时不可用",
                status_code=503,
            ) from exc
        if not isinstance(decoded, dict):
            raise AppError(
                "daily_report_provider_invalid_response",
                "日报模型服务返回了无法识别的内容",
                status_code=503,
            )
        return decoded


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
    choices = response.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        raise AppError(
            "daily_report_provider_invalid_response",
            "日报模型服务没有返回候选内容",
            status_code=503,
        )
    message = choices[0].get("message")
    if not isinstance(message, dict) or not isinstance(message.get("content"), str):
        raise AppError(
            "daily_report_provider_invalid_response",
            "日报模型服务没有返回文本内容",
            status_code=503,
        )
    payload = extract_json_object(message["content"])
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


def extract_json_object(content: str) -> dict[str, object]:
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", content.strip(), flags=re.IGNORECASE)
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start < 0 or end <= start:
        raise AppError(
            "daily_report_provider_invalid_response",
            "日报模型服务没有按约定返回 JSON",
            status_code=503,
        )
    try:
        payload = json.loads(cleaned[start : end + 1])
    except json.JSONDecodeError as exc:
        raise AppError(
            "daily_report_provider_invalid_response",
            "日报模型服务返回的 JSON 无法解析",
            status_code=503,
        ) from exc
    if not isinstance(payload, dict):
        raise AppError(
            "daily_report_provider_invalid_response",
            "日报模型服务返回的 JSON 类型错误",
            status_code=503,
        )
    return payload


def local_preference_suggestion(message: str) -> str | None:
    normalized = " ".join(message.split())
    durable_markers = ("以后", "每次", "固定", "一直", "不要", "避免", "都要")
    if normalized and any(marker in normalized for marker in durable_markers):
        return normalized[:500]
    return None

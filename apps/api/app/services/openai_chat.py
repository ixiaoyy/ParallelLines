from __future__ import annotations

import json
import re
import urllib.error
import urllib.request

from app.core.exceptions import AppError


def request_openai_chat(
    *,
    base_url: str,
    api_key: str,
    model: str,
    messages: list[dict[str, str]],
    temperature: float,
    max_tokens: int,
    timeout_seconds: float,
    error_prefix: str,
    service_label: str,
) -> dict[str, object]:
    """Send one OpenAI-compatible chat request and return its decoded object payload.

    Key parameters define the provider request and feature-specific safe error labels.
    The return value is the decoded top-level JSON object. Side effect: performs one
    outbound HTTPS request without logging credentials or provider content.
    """
    normalized_base_url = base_url.rstrip("/")
    url = (
        normalized_base_url
        if normalized_base_url.endswith("/chat/completions")
        else f"{normalized_base_url}/chat/completions"
    )
    body = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,
    }
    request = urllib.request.Request(
        url,
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
            "User-Agent": "ParallelLines/1.0",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            decoded = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise AppError(
            f"{error_prefix}_error",
            f"{service_label}返回 HTTP {exc.code}",
            status_code=503,
        ) from exc
    except (OSError, TimeoutError, json.JSONDecodeError) as exc:
        raise AppError(
            f"{error_prefix}_unavailable",
            f"{service_label}暂时不可用",
            status_code=503,
        ) from exc
    if not isinstance(decoded, dict):
        raise AppError(
            f"{error_prefix}_invalid_response",
            f"{service_label}返回了无法识别的内容",
            status_code=503,
        )
    return decoded


def extract_chat_content(
    response: dict[str, object],
    *,
    error_prefix: str,
    service_label: str,
) -> str:
    """Extract the first assistant text from an OpenAI-compatible response.

    Key parameters are the decoded provider response and feature-specific error labels.
    The return value is non-empty assistant content. Side effect: raises a safe 503
    application error when the provider contract is malformed.
    """
    choices = response.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        raise AppError(
            f"{error_prefix}_invalid_response",
            f"{service_label}没有返回候选内容",
            status_code=503,
        )
    message = choices[0].get("message")
    if not isinstance(message, dict) or not isinstance(message.get("content"), str):
        raise AppError(
            f"{error_prefix}_invalid_response",
            f"{service_label}没有返回文本内容",
            status_code=503,
        )
    content = message["content"].strip()
    if not content:
        raise AppError(
            f"{error_prefix}_invalid_response",
            f"{service_label}返回了空文本",
            status_code=503,
        )
    return content


def extract_json_object(
    content: str,
    *,
    error_prefix: str,
    service_label: str,
) -> dict[str, object]:
    """Parse the outermost JSON object from assistant content.

    Key parameters are raw assistant text and feature-specific error labels. The return
    value is a JSON object. Side effect: raises a safe 503 error for invalid model output.
    """
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", content.strip(), flags=re.IGNORECASE)
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start < 0 or end <= start:
        raise AppError(
            f"{error_prefix}_invalid_response",
            f"{service_label}没有按约定返回 JSON",
            status_code=503,
        )
    try:
        payload = json.loads(cleaned[start : end + 1])
    except json.JSONDecodeError as exc:
        raise AppError(
            f"{error_prefix}_invalid_response",
            f"{service_label}返回的 JSON 无法解析",
            status_code=503,
        ) from exc
    if not isinstance(payload, dict):
        raise AppError(
            f"{error_prefix}_invalid_response",
            f"{service_label}返回的 JSON 类型错误",
            status_code=503,
        )
    return payload

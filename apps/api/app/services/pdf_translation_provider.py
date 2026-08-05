from __future__ import annotations

import asyncio
import json
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass
from typing import Protocol

from app.core.config import Settings
from app.core.exceptions import AppError
from app.services.openai_chat import (
    extract_chat_content,
    extract_json_object,
    request_openai_chat,
)

CJK_PATTERN = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")
ALPHANUMERIC_IDENTIFIER_PATTERN = re.compile(
    r"(?<![A-Za-z0-9])([A-Za-z0-9][A-Za-z0-9./()_-]{3,})(?![A-Za-z0-9])"
)
NUMBER_PATTERN = re.compile(r"\d+(?:[.,]\d+)*")

TRANSLATION_SYSTEM_PROMPT = (
    "You translate Chinese professional PDFs into English.\n"
    "Return JSON only. Every translation must contain ASCII English, digits, and ASCII "
    "punctuation only.\n\n"
    "Mandatory rules:\n"
    "1. Remove every Chinese character. Translate headings, body text, headers, footers, "
    "watermarks, labels, and table cells.\n"
    "2. Transliterate the distinctive part of Chinese company and institution names with "
    "pinyin, then use a standard English legal suffix. Example: "
    "测试科技（惠州）有限公司 -> Shi Ce Technology (Huizhou) Co., Ltd.\n"
    "3. Render Chinese personal names in pinyin. Example: 张某某 -> Zhang Moumou.\n"
    "4. Preserve registration numbers, Unified Social Credit Codes, patent numbers, "
    "certificate numbers, dates, monetary values, percentages, model numbers, and other "
    "identifiers exactly. Keep every numeric date component and prefer YYYY-MM-DD.\n"
    "5. Format addresses in natural English order without losing province, city, district, "
    "street, building, room, or postal-code facts.\n"
    "6. Use concise professional report language that fits the source layout. Do not add "
    "explanations, facts, labels, or translator notes.\n"
    "7. Apply the supplied glossary exactly and consistently.\n"
)

GLOSSARY_SYSTEM_PROMPT = (
    "Identify Chinese proper names that need consistent English rendering in a professional "
    "document.\n"
    'Return JSON only as {"terms":[{"source":"...","english":"..."}]}.\n'
    "Use pinyin for Chinese personal names and for the distinctive part of company or "
    "institution names. Use ASCII English only in each english value. Do not include "
    "ordinary descriptive phrases, dates, addresses, identifiers, or amounts.\n"
)


@dataclass(frozen=True)
class PdfTranslationSource:
    id: str
    text: str


class PdfTranslationProvider(Protocol):
    async def build_glossary(self, sources: list[PdfTranslationSource]) -> dict[str, str]:
        """Return a consistent source-to-English proper-name glossary for the document."""

    async def translate(
        self,
        sources: list[PdfTranslationSource],
        glossary: dict[str, str],
    ) -> dict[str, str]:
        """Return one verified pure-English translation for every source identifier."""


class OpenAICompatiblePdfTranslationProvider:
    def __init__(self, settings: Settings, api_key: str) -> None:
        """Create a PDF translator bound to server-only provider settings and credentials."""
        self.settings = settings
        self.api_key = api_key

    async def build_glossary(self, sources: list[PdfTranslationSource]) -> dict[str, str]:
        """Ask the model for a bounded document-level proper-name glossary.

        Key parameter `sources` contains extracted Chinese layout segments. The return
        value maps exact Chinese names to ASCII English renderings. Side effect: performs
        one model call when source text is available.
        """
        excerpts = bounded_unique_excerpts(sources, max_chars=16_000)
        if not excerpts:
            return {}
        payload = await self._request_json(
            [
                {"role": "system", "content": GLOSSARY_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": json.dumps({"document_text": excerpts}, ensure_ascii=False),
                },
            ]
        )
        return parse_glossary_payload(payload)

    async def translate(
        self,
        sources: list[PdfTranslationSource],
        glossary: dict[str, str],
    ) -> dict[str, str]:
        """Translate one bounded segment batch and enforce English/identifier contracts.

        Key parameters are source segments and the shared document glossary. The return
        value contains every source ID exactly once. Side effect: performs a model call
        and at most one repair call when the first response violates the contract.
        """
        if not sources:
            return {}
        request_payload = translation_request_payload(sources, glossary)
        payload = await self._request_json(
            [
                {"role": "system", "content": TRANSLATION_SYSTEM_PROMPT},
                {"role": "user", "content": request_payload},
            ]
        )
        translations, problems = parse_translation_payload(payload, sources)
        if not problems:
            return translations

        repair_payload = json.dumps(
            {
                "instruction": (
                    "Repair the translations. Return every requested id exactly once, use ASCII "
                    "English only, and preserve all listed identifiers and numeric components."
                ),
                "problems": problems,
                "glossary": glossary,
                "segments": [
                    {
                        "id": source.id,
                        "source": source.text,
                        "required_values": protected_values(source.text),
                    }
                    for source in sources
                ],
            },
            ensure_ascii=False,
        )
        repaired = await self._request_json(
            [
                {"role": "system", "content": TRANSLATION_SYSTEM_PROMPT},
                {"role": "user", "content": repair_payload},
            ]
        )
        translations, problems = parse_translation_payload(repaired, sources)
        if problems:
            raise AppError(
                "pdf_translation_contract_failed",
                "模型译文未通过纯英文或关键编号校验，请更换文档或稍后重试",
                status_code=503,
                details={"problems": problems[:12]},
            )
        return translations

    async def _request_json(self, messages: list[dict[str, str]]) -> dict[str, object]:
        """Call the configured model and parse its assistant content as one JSON object.

        Key parameter is a bounded chat message list. The return value is the parsed JSON
        object. Side effect: performs one outbound model request on a worker thread.
        """
        response = await asyncio.to_thread(
            request_openai_chat,
            base_url=self.settings.pdf_translation_ai_base_url,
            api_key=self.api_key,
            model=self.settings.pdf_translation_ai_model,
            messages=messages,
            temperature=self.settings.pdf_translation_ai_temperature,
            max_tokens=self.settings.pdf_translation_ai_max_tokens,
            timeout_seconds=self.settings.pdf_translation_ai_timeout_seconds,
            error_prefix="pdf_translation_provider",
            service_label="PDF 翻译模型服务",
        )
        content = extract_chat_content(
            response,
            error_prefix="pdf_translation_provider",
            service_label="PDF 翻译模型服务",
        )
        return extract_json_object(
            content,
            error_prefix="pdf_translation_provider",
            service_label="PDF 翻译模型服务",
        )


def configured_pdf_translation_provider(settings: Settings) -> PdfTranslationProvider:
    """Return the configured PDF translation provider or fail instead of degrading.

    Key parameter is runtime settings. The return value owns a server-only credential.
    Side effect: raises a safe 503 error when no translation credential is configured.
    """
    api_key = (
        settings.pdf_translation_ai_api_key
        or settings.daily_report_ai_api_key
        or settings.opencode_api_key
    ).strip()
    if not api_key:
        raise AppError(
            "pdf_translation_provider_not_configured",
            "站点尚未配置 PDF 翻译模型，暂时无法生成可靠的纯英文 PDF",
            status_code=503,
        )
    return OpenAICompatiblePdfTranslationProvider(settings, api_key)


def pdf_translation_provider_configured(settings: Settings) -> bool:
    """Return whether any server-only credential can power strict PDF translation.

    Key parameter is runtime settings. The boolean return value is safe to expose as a
    capability flag; credentials themselves remain private. Side effect: none.
    """
    return bool(
        (
            settings.pdf_translation_ai_api_key
            or settings.daily_report_ai_api_key
            or settings.opencode_api_key
        ).strip()
    )


def bounded_unique_excerpts(
    sources: list[PdfTranslationSource],
    *,
    max_chars: int,
) -> list[str]:
    """Return unique Chinese excerpts within the glossary prompt character budget.

    Key parameters are source segments and the maximum source-character budget. The
    return value preserves first-seen document order. Side effect: none.
    """
    excerpts: list[str] = []
    seen: set[str] = set()
    used_chars = 0
    for source in sources:
        normalized = " ".join(source.text.split())
        if not normalized or normalized in seen or not contains_cjk(normalized):
            continue
        if used_chars + len(normalized) > max_chars:
            break
        seen.add(normalized)
        excerpts.append(normalized)
        used_chars += len(normalized)
    return excerpts


def parse_glossary_payload(payload: dict[str, object]) -> dict[str, str]:
    """Validate a model glossary payload and return safe exact term mappings.

    Key parameter is parsed provider JSON. The return value is capped at 200 entries and
    contains only Chinese source keys with non-empty ASCII English values. Side effect: none.
    """
    raw_terms = payload.get("terms")
    if not isinstance(raw_terms, list):
        raise AppError(
            "pdf_translation_provider_invalid_response",
            "PDF 翻译模型没有返回有效术语表",
            status_code=503,
        )
    glossary: dict[str, str] = {}
    for item in raw_terms[:200]:
        if not isinstance(item, dict):
            continue
        source = item.get("source")
        english = item.get("english")
        if not isinstance(source, str) or not isinstance(english, str):
            continue
        source = " ".join(source.split())[:200]
        normalized = normalize_ascii_english(english)
        if source and contains_cjk(source) and normalized:
            glossary[source] = normalized[:300]
    return glossary


def translation_request_payload(
    sources: list[PdfTranslationSource],
    glossary: dict[str, str],
) -> str:
    """Serialize a bounded translation request with protected values made explicit.

    Key parameters are source segments and the document glossary. The return value is a
    JSON string for the model user message. Side effect: none.
    """
    return json.dumps(
        {
            "response_schema": {
                "translations": [{"id": "same id as input", "text": "ASCII English"}]
            },
            "glossary": glossary,
            "segments": [
                {
                    "id": source.id,
                    "source": source.text,
                    "required_values": protected_values(source.text),
                }
                for source in sources
            ],
        },
        ensure_ascii=False,
    )


def parse_translation_payload(
    payload: dict[str, object],
    sources: list[PdfTranslationSource],
) -> tuple[dict[str, str], list[str]]:
    """Decode translations and report every missing, Chinese, or identifier violation.

    Key parameters are parsed provider JSON and the exact requested source batch. Return
    values are safe normalized translations and concise problem strings. Side effect: none.
    """
    raw_translations = payload.get("translations")
    if not isinstance(raw_translations, list):
        return {}, ["translations must be an array"]
    expected = {source.id: source for source in sources}
    translations: dict[str, str] = {}
    problems: list[str] = []
    for item in raw_translations:
        if not isinstance(item, dict):
            problems.append("translation item must be an object")
            continue
        item_id = item.get("id")
        text = item.get("text")
        if not isinstance(item_id, str) or item_id not in expected:
            problems.append(f"unexpected id: {item_id!r}")
            continue
        if item_id in translations:
            problems.append(f"duplicate id: {item_id}")
            continue
        if not isinstance(text, str):
            problems.append(f"{item_id}: text must be a string")
            continue
        normalized = normalize_ascii_english(text)
        if not normalized:
            problems.append(f"{item_id}: text is empty, non-English, or contains Chinese")
            continue
        missing = missing_protected_values(expected[item_id].text, normalized)
        if missing:
            problems.append(f"{item_id}: missing protected values {missing}")
            continue
        translations[item_id] = normalized
    for item_id in expected.keys() - translations.keys():
        if not any(problem.startswith(f"{item_id}:") for problem in problems):
            problems.append(f"{item_id}: missing translation")
    return translations, problems


def normalize_ascii_english(value: str) -> str | None:
    """Normalize provider English to printable ASCII without hiding Chinese residue.

    Key parameter is one translated string. The return value is compact printable ASCII,
    or none when Chinese characters remain or the result is empty. Side effect: none.
    """
    normalized = unicodedata.normalize("NFKC", value).strip()
    replacements = {
        "“": '"',
        "”": '"',
        "‘": "'",
        "’": "'",
        "–": "-",
        "—": "-",
        "―": "-",
        "…": "...",
        "，": ", ",
        "。": ". ",
        "；": "; ",
        "：": ": ",
        "！": "! ",
        "？": "? ",
        "（": "(",
        "）": ")",
        "【": "[",
        "】": "]",
        "《": '"',
        "》": '"',
        "、": ", ",
        "￥": "CNY ",
        "¥": "CNY ",
        "€": "EUR ",
        "£": "GBP ",
    }
    for source, replacement in replacements.items():
        normalized = normalized.replace(source, replacement)
    if contains_cjk(normalized):
        return None
    ascii_text = unicodedata.normalize("NFKD", normalized).encode("ascii", "ignore").decode()
    ascii_text = re.sub(r"[\x00-\x1f\x7f]", " ", ascii_text)
    ascii_text = re.sub(r"\s+", " ", ascii_text).strip()
    return ascii_text or None


def contains_cjk(value: str) -> bool:
    """Return whether a string contains any CJK Unified Ideograph.

    Key parameter is arbitrary text. The boolean return value is used at every provider
    and final-PDF trust boundary. Side effect: none.
    """
    return CJK_PATTERN.search(value) is not None


def protected_values(source: str) -> list[str]:
    """Return stable identifiers and numeric components that translation must preserve.

    Key parameter is source text. The return value is deterministic, deduplicated, and
    ordered by first appearance. Side effect: none.
    """
    values: list[str] = []
    for candidate in ALPHANUMERIC_IDENTIFIER_PATTERN.findall(source):
        if any(char.isalpha() for char in candidate) and any(char.isdigit() for char in candidate):
            values.append(candidate)
    values.extend(NUMBER_PATTERN.findall(source))
    return list(dict.fromkeys(values))


def missing_protected_values(source: str, translation: str) -> list[str]:
    """Return source identifiers or numeric components absent from a translation.

    Key parameters are one source segment and its English translation. The return value
    lists exact identifiers or normalized numbers that were lost. Side effect: none.
    """
    missing: list[str] = []
    translation_upper = translation.upper()
    for identifier in ALPHANUMERIC_IDENTIFIER_PATTERN.findall(source):
        if (
            any(char.isalpha() for char in identifier)
            and any(char.isdigit() for char in identifier)
            and identifier.upper() not in translation_upper
        ):
            missing.append(identifier)
    source_numbers = Counter(normalize_number(value) for value in NUMBER_PATTERN.findall(source))
    translated_numbers = Counter(
        normalize_number(value) for value in NUMBER_PATTERN.findall(translation)
    )
    for number, count in source_numbers.items():
        if translated_numbers[number] < count:
            missing.extend([number] * (count - translated_numbers[number]))
    return missing


def normalize_number(value: str) -> str:
    """Normalize one numeric token for preservation comparison across punctuation changes.

    Key parameter is a token matched by `NUMBER_PATTERN`. The return value removes
    grouping commas and insignificant integer leading zeroes. Side effect: none.
    """
    compact = value.replace(",", "")
    if "." in compact:
        integer, fraction = compact.split(".", 1)
        return f"{integer.lstrip('0') or '0'}.{fraction}"
    return compact.lstrip("0") or "0"

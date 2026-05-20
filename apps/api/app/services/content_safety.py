from __future__ import annotations

import unicodedata
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

from app.core.exceptions import ValidationError

ContentSafetyAction = Literal["block", "mask"]

# Public placeholder tokens for tests and seed-like local verification only. Real policy
# terms should be supplied through a private deployment channel before production use.
BLOCK_POLICY_TEST_TOKEN = "blocked-demo-term"
MASK_POLICY_TEST_TOKEN = "mask-demo-term"


@dataclass(frozen=True)
class ContentSafetyRule:
    token: str
    action: ContentSafetyAction


@dataclass(frozen=True)
class NormalizedChar:
    value: str
    start: int
    end: int


@dataclass(frozen=True)
class ContentModerationResult:
    sanitized_fields: dict[str, str]
    blocked_fields: tuple[str, ...]
    masked_fields: tuple[str, ...]


CONTENT_SAFETY_RULES: tuple[ContentSafetyRule, ...] = (
    ContentSafetyRule(token=BLOCK_POLICY_TEST_TOKEN, action="block"),
    ContentSafetyRule(token=MASK_POLICY_TEST_TOKEN, action="mask"),
)


def enforce_content_policy(fields: Mapping[str, str]) -> dict[str, str]:
    """Apply content safety rules and raise a non-leaky validation error on block."""

    result = moderate_text_fields(fields)
    if result.blocked_fields:
        raise ValidationError(
            "content_policy_violation",
            "Content violates community safety rules; please edit and retry",
            {
                "action": "blocked",
                "fields": list(result.blocked_fields),
            },
        )
    return result.sanitized_fields


def moderate_text_fields(fields: Mapping[str, str]) -> ContentModerationResult:
    sanitized_fields = dict(fields)
    blocked_fields: set[str] = set()
    masked_fields: set[str] = set()

    for field_name, value in fields.items():
        mask_spans: list[tuple[int, int]] = []
        for rule in CONTENT_SAFETY_RULES:
            spans = _find_rule_spans(value, rule.token)
            if not spans:
                continue

            if rule.action == "block":
                blocked_fields.add(field_name)
            elif rule.action == "mask":
                masked_fields.add(field_name)
                mask_spans.extend(spans)

        if mask_spans:
            sanitized_fields[field_name] = _replace_spans(value, _merge_spans(mask_spans))

    return ContentModerationResult(
        sanitized_fields=sanitized_fields,
        blocked_fields=tuple(sorted(blocked_fields)),
        masked_fields=tuple(sorted(masked_fields)),
    )


def _find_rule_spans(value: str, token: str) -> list[tuple[int, int]]:
    normalized_token = _normalize_policy_text(token)
    if not normalized_token:
        return []

    char_map = _normalized_char_map(value)
    normalized_value = "".join(item.value for item in char_map)
    spans: list[tuple[int, int]] = []
    start = 0
    while True:
        index = normalized_value.find(normalized_token, start)
        if index < 0:
            break
        end_index = index + len(normalized_token) - 1
        spans.append((char_map[index].start, char_map[end_index].end))
        start = index + 1
    return spans


def _normalized_char_map(value: str) -> list[NormalizedChar]:
    characters: list[NormalizedChar] = []
    for index, character in enumerate(value):
        normalized = _normalize_policy_text(character)
        for normalized_character in normalized:
            characters.append(NormalizedChar(normalized_character, index, index + 1))
    return characters


def _normalize_policy_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    return "".join(character for character in normalized if _keeps_policy_character(character))


def _keeps_policy_character(character: str) -> bool:
    category = unicodedata.category(character)
    return category[0] not in {"C", "P", "S", "Z"}


def _merge_spans(spans: list[tuple[int, int]]) -> list[tuple[int, int]]:
    if not spans:
        return []

    merged: list[tuple[int, int]] = []
    for start, end in sorted(spans):
        if not merged or start > merged[-1][1]:
            merged.append((start, end))
            continue
        previous_start, previous_end = merged[-1]
        merged[-1] = (previous_start, max(previous_end, end))
    return merged


def _replace_spans(value: str, spans: list[tuple[int, int]]) -> str:
    result = value
    for start, end in reversed(spans):
        result = f"{result[:start]}***{result[end:]}"
    return result

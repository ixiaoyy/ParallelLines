from __future__ import annotations

TRUST_LEVEL_MIN = 0
TRUST_LEVEL_MAX = 4
AUTO_TRUST_LEVEL_MAX = 3

TRUST_LEVEL_LABELS: dict[int, str] = {
    0: "新成员",
    1: "基础成员",
    2: "常驻成员",
    3: "可信成员",
    4: "核心成员",
}


def clamp_trust_level(level: int | None) -> int:
    """Clamp persisted trust levels into the supported range."""
    return max(TRUST_LEVEL_MIN, min(TRUST_LEVEL_MAX, int(level or 0)))


def trust_level_label(level: int | None) -> str:
    """Return the localized display label for a trust level."""
    safe_level = clamp_trust_level(level)
    return TRUST_LEVEL_LABELS.get(safe_level, TRUST_LEVEL_LABELS[0])


def trust_adjusted_limit(base_limit: int, trust_level: int | None) -> int:
    """Return a write-rate limit adjusted by trust level.

    Level 0 users stay under stricter risk controls. Level 1 keeps default limits,
    while levels 2+ get progressively more room without granting admin authority.
    """
    safe_limit = max(1, int(base_limit))
    safe_level = clamp_trust_level(trust_level)
    if safe_level <= 0:
        return max(1, min(safe_limit, (safe_limit + 1) // 2))
    if safe_level == 1:
        return safe_limit
    if safe_level == 2:
        return safe_limit + max(1, safe_limit // 2)
    return safe_limit * 2


def review_priority_for_trust(base_priority: int, trust_level: int | None) -> int:
    """Lower review priority number means reviewers see it sooner."""
    safe_priority = max(1, min(100, int(base_priority)))
    safe_level = clamp_trust_level(trust_level)
    if safe_level <= 0:
        return max(1, safe_priority - 30)
    if safe_level >= 3:
        return min(100, safe_priority + 10)
    return safe_priority

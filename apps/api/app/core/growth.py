from __future__ import annotations

from bisect import bisect_right

LEVEL_THRESHOLDS: tuple[int, ...] = (0, 50, 150, 300, 600, 1000, 1600, 2400, 3400, 4600, 6000)
MAX_LEVEL = len(LEVEL_THRESHOLDS) - 1


def level_for_experience(experience_total: int) -> int:
    """Return the stored display level for total experience."""
    safe_experience = max(0, int(experience_total))
    return max(0, min(MAX_LEVEL, bisect_right(LEVEL_THRESHOLDS, safe_experience) - 1))


def experience_to_next_level(experience_total: int) -> int:
    """Return remaining experience before the next configured level."""
    safe_experience = max(0, int(experience_total))
    current_level = level_for_experience(safe_experience)
    if current_level >= MAX_LEVEL:
        return 0
    return max(0, LEVEL_THRESHOLDS[current_level + 1] - safe_experience)


def level_progress_percent(experience_total: int) -> int:
    """Return current-level progress as an integer percentage."""
    safe_experience = max(0, int(experience_total))
    current_level = level_for_experience(safe_experience)
    if current_level >= MAX_LEVEL:
        return 100
    current_floor = LEVEL_THRESHOLDS[current_level]
    next_floor = LEVEL_THRESHOLDS[current_level + 1]
    level_span = max(1, next_floor - current_floor)
    progress = (safe_experience - current_floor) / level_span
    return max(0, min(100, round(progress * 100)))

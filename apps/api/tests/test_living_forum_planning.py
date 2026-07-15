from datetime import date, timedelta

from app.services.living_forum import LivingForumService


def test_ai_observation_rotates_across_consecutive_days() -> None:
    """Consecutive observation slots must change while each date stays deterministic."""

    service = LivingForumService(None)
    start = date(2026, 7, 15)
    plans = [service._ai_observation_topic(start + timedelta(days=offset)) for offset in range(14)]

    assert len({plan.title for plan in plans}) == len(plans)
    assert len({plan.raw_md for plan in plans}) == len(plans)
    assert service._ai_observation_topic(start) == plans[0]
    assert all(plan.seed_key.startswith("living:") for plan in plans)

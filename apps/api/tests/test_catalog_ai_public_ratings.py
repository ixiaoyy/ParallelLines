"""Public AI projection tests use private in-memory SQLite only."""

from datetime import date, timedelta
from types import SimpleNamespace

import pytest
import sqlalchemy as sa
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.models.catalog_ai_rating import AiGameAssessment
from app.schemas.catalog_ai_ratings import AiImportBundle, AiRuleInput, AiWeightSchemeInput
from app.services.catalog import CatalogService
from app.services.catalog_ai_rating_defaults import (
    CURRENT_AI_RULE,
    CURRENT_AI_WEIGHT_SCHEME,
    PUBLIC_AI_WEIGHT_VERSION,
)
from app.services.catalog_ai_ratings import CatalogAiRatingService
from tests.test_catalog_ai_ratings import OBSERVED, SQLiteSession, observation, run
from tests.test_catalog_ai_ratings import store as store


def display_bundle(batch_id, assessments=None, *, rule=None, scheme=None, external=False):
    rule = rule or CURRENT_AI_RULE
    scheme = scheme or CURRENT_AI_WEIGHT_SCHEME
    assessments = assessments or [observation(rule_version=rule.version)]
    return AiImportBundle.model_validate({
        "schema_version": 1,
        "rule": rule.model_dump(mode="json"),
        "weight_scheme": scheme.model_dump(mode="json"),
        "batch": {
            "id": batch_id,
            "evaluator_kind": "ai",
            "evaluator_identity": {
                "provider": "fixture-provider", "model": "fixture-model",
                "agent": "fixture-agent", "run_id": "private-fixture-run",
            },
            "source_kind": "user_accepted_external_ai" if external else "independent_ai",
            "source_reference": r"C:\synthetic\private-source.json" if external else None,
            "source_metadata": {"private_note": "not for public response"},
            "recorded_at": OBSERVED + timedelta(days=3),
            "assessments": assessments,
        },
    })


def test_no_registered_scheme_keeps_public_ai_rating_null(store):
    session, ai_service = store
    assert run(ai_service.public_summaries(["1"])) == {}
    response = run(CatalogService(SQLiteSession(session), SimpleNamespace()).public_catalog())
    assert all(
        project.ai_rating is None
        for category in response.categories for project in category.projects
    )


def test_public_summary_retains_player_rating_heat_and_only_display_provenance(store, monkeypatch):
    session, ai_service = store
    observed = observation(
        rule_version=CURRENT_AI_RULE.version,
        play_scope={
            "minutes": 8, "completed": "tutorial only",
            "device_checks": {"desktop": {"tested": True, "compatible": True}},
            "source_reference": r"C:\synthetic\private-source.json",
            "nested": {"run_id": "private-fixture-run", "artifact_path": "/tmp/private.json"},
            "notes": ["tutorial checked", r"C:\synthetic\private-note.txt"],
        },
        limitations=["Mobile untested", r"C:\synthetic\private-limit.txt"],
    )
    imported = run(ai_service.import_bundle(display_bundle("public-complete", [observed])))
    service = CatalogService(SQLiteSession(session), SimpleNamespace())
    monkeypatch.setattr(service, "_ip_digest", lambda _request, required: "a" * 64)
    response = run(service.public_catalog(request=object()))
    projects = {
        project.id: project
        for category in response.categories for project in category.projects
    }
    project = projects["1"]
    assert (project.average_score, project.rating_count, project.my_score, project.view_count) == (
        5.0, 1, 5, 123,
    )
    summary = project.ai_rating
    assert summary.score == 6.9
    assert summary.label == "AI评分"
    assert summary.assessment_id in imported["assessment_ids"]
    assert summary.weight_version == CURRENT_AI_WEIGHT_SCHEME.version
    assert summary.evaluated_at == OBSERVED
    assert [item.weight for item in summary.dimensions] == [0.4, 0.3, 0.15, 0.1, 0.05]
    assert [item.score for item in summary.dimensions] == [8, 7, 6, 5, 4]
    assert summary.play_scope["device_checks"]["desktop"] == {"tested": True, "compatible": True}
    assert summary.play_scope["notes"] == ["tutorial checked"]
    assert summary.limitations == ["Mobile untested"]
    public_json = summary.model_dump_json()
    for private in ("private-source", "private-fixture-run", "evaluator_identity", "evidence"):
        assert private not in public_json
    assert projects["2"].ai_rating is None
    assert "5" not in projects and "6" not in projects


@pytest.mark.parametrize("missing", ["absent", "null"])
def test_latest_incomplete_assessment_stays_null_and_preserves_history(store, missing):
    session, ai_service = store
    old = observation(rule_version=CURRENT_AI_RULE.version)
    run(ai_service.import_bundle(display_bundle("public-old", [old])))
    latest = observation(
        rule_version=CURRENT_AI_RULE.version, evaluated_at=OBSERVED + timedelta(days=1),
        game_version=None, snapshot_key="fresh-observation-public-latest",
    )
    if missing == "absent":
        latest["dimensions"] = latest["dimensions"][:-1]
    else:
        latest["dimensions"][-1]["score"] = None
    imported = run(ai_service.import_bundle(display_bundle("public-latest", [latest])))
    summary = run(ai_service.public_summaries(["1"]))["1"]
    assert summary.assessment_id in imported["assessment_ids"]
    assert summary.score is None
    assert summary.dimensions[-1].score is None
    assert summary.game_version is None
    assert session.scalar(sa.select(sa.func.count()).select_from(AiGameAssessment)) == 2


def test_active_visual_rule_takes_precedence_without_mixing_definitions_and_keeps_date_only(store):
    _, ai_service = store
    run(ai_service.import_bundle(display_bundle("public-fallback", [
        observation(game_id="1", rule_version=CURRENT_AI_RULE.version),
        observation(game_id="2", rule_version=CURRENT_AI_RULE.version),
    ])))
    source_rule = AiRuleInput.model_validate({
        "version": "synthetic-visual-definitions-v1",
        "dimensions": [
            {**item.model_dump(), "key": "visual", "label": "视觉表现"}
            if item.key == "audiovisual" else item.model_dump()
            for item in CURRENT_AI_RULE.dimensions
        ],
    })
    source_scheme = AiWeightSchemeInput(
        version=PUBLIC_AI_WEIGHT_VERSION, rule_version=source_rule.version,
        weights={
            "visual" if key == "audiovisual" else key: value
            for key, value in CURRENT_AI_WEIGHT_SCHEME.weights.items()
        },
    )
    source_observation = observation(
        rule_version=source_rule.version, evaluated_at=None,
        reported_review_date=date(2026, 10, 29), reported_timezone="Asia/Shanghai",
    )
    source_observation["dimensions"][-1]["dimension_key"] = "visual"
    run(ai_service.import_bundle(display_bundle(
        "accepted-visual-source", [source_observation],
        rule=source_rule, scheme=source_scheme, external=True,
    )))
    summaries = run(ai_service.public_summaries(["1", "2"]))
    assert "2" not in summaries  # A response never mixes visual and audiovisual definitions.
    summary = summaries["1"]
    assert summary.source_kind == "user_accepted_external_ai"
    assert summary.weight_version == PUBLIC_AI_WEIGHT_VERSION
    assert summary.rule_version == source_rule.version
    assert summary.dimensions[-1].key == "visual"
    assert summary.dimensions[-1].label == "视觉表现"
    assert summary.evaluated_at is None
    assert summary.reported_review_date == date(2026, 10, 29)
    assert summary.reported_timezone == "Asia/Shanghai"
    assert summary.model_dump(mode="json")["evaluated_at"] is None
    assert summary.model_dump(mode="json")["reported_review_date"] == "2026-10-29"


def test_date_only_newer_observation_wins_over_older_actual_timestamp(store):
    _, ai_service = store
    run(ai_service.import_bundle(display_bundle("public-timestamp-old")))
    imported = run(ai_service.import_bundle(display_bundle(
        "public-date-new", [observation(
            scores=(4, 4, 4, 4, 4), rule_version=CURRENT_AI_RULE.version,
            evaluated_at=None, reported_review_date=date(2026, 10, 29), reported_timezone=None,
        )], external=True,
    )))
    summary = run(ai_service.public_summaries(["1"]))["1"]
    assert summary.assessment_id in imported["assessment_ids"]
    assert summary.score == 4.0
    assert summary.evaluated_at is None


def test_summary_query_count_does_not_grow_per_game(store):
    session, ai_service = store
    run(ai_service.import_bundle(display_bundle("public-batch", [
        observation(game_id=str(number), rule_version=CURRENT_AI_RULE.version)
        for number in range(1, 5)
    ])))

    class CountingSession(SQLiteSession):
        calls = 0

        async def get(self, entity, key):
            self.calls += 1
            return await super().get(entity, key)

        async def execute(self, statement):
            self.calls += 1
            return await super().execute(statement)

    bridge = CountingSession(session)
    service = CatalogAiRatingService(bridge)
    assert len(run(service.public_summaries(["1"]))) == 1
    one_game_calls = bridge.calls
    bridge.calls = 0
    assert len(run(service.public_summaries(["1", "2", "3", "4"]))) == 4
    assert bridge.calls == one_game_calls == 5


def test_missing_ai_tables_is_a_deployment_error_not_an_empty_summary():
    engine = sa.create_engine("sqlite://")
    try:
        with Session(engine) as session:
            service = CatalogAiRatingService(SQLiteSession(session))
            with pytest.raises(OperationalError, match="no such table"):
                run(service.public_summaries(["1"]))
    finally:
        engine.dispose()

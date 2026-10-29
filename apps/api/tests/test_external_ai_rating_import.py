"""Offline accepted-report conversion and private in-memory import checks."""

from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from decimal import Decimal

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models.catalog import CatalogCategory, CatalogProject, CatalogRating
from app.models.catalog_ai_rating import AiAssessmentDimension, AiGameAssessment, AiRatingBatch
from app.services.catalog_ai_ratings import CatalogAiRatingService
from scripts.prepare_external_ai_ratings import DIMENSIONS, prepare_bundles
from tests.test_catalog_ai_ratings import AI_TABLES, SQLiteSession, run


def source_package():
    weights = dict(zip((key for key, _label in DIMENSIONS), [0.4, 0.3, 0.15, 0.1, 0.05],
                       strict=True))
    scores = dict(zip(weights, [8, 7, 6, 5, 4], strict=True))
    version = "source-definitions-test-v1"
    return {
        "status": "approved_for_import", "review_count": 1, "unique_game_count": 1,
        "created_at_utc": "2026-10-29T08:00:00Z", "rubric_version": "source-rubric-test-v1",
        "dimension_definition_version": version,
        "weight_scheme": {"version": "source-weights-test-v1", "weights": weights},
        "source_files": [{
            "source_id": "source-test", "normalized_source_file": "report-test.json",
            "sha256": "a" * 64, "source_message_id": "message-test",
        }],
        "reviews": [{
            "status": "approved_for_import", "import_key": "external-test-1",
            "game_id": "1", "catalog_project_id": "1", "catalog_name": "Fixture game",
            "catalog_slug": "fixture-game", "catalog_url": "https://example.invalid/game",
            "dimension_definition_version": version,
            "rubric_version": "source-rubric-test-v1",
            "weight_scheme_version": "source-weights-test-v1",
            "source_id": "source-test", "reported_reviewer_id": "Reported AI identity",
            "reported_review_date": "2026-10-29", "reported_timezone": None,
            "reviewed_at_utc": None, "raw_scores": scores,
            "dimension_scores": [{
                "dimension_key": key, "dimension_definition_version": version,
                "raw_score": score, "weight": weights[key],
                "reported_reason": {"reported_reason": "Synthetic claimed observation",
                                    "independently_verified": False},
            } for key, score in scores.items()],
            "unrounded_total": "6.9", "total_score": 6.9, "reported_total": 6.8,
            "reported_environment": {"reported_description": "Claimed desktop browser"},
            "reported_played_scope": {"reported_description": "Claimed tutorial only"},
            "reported_limitations": "Audio not assessed",
            "reported_evidence": [{"kind": "reported_screenshot", "file_received": False}],
            "source_lineage": [{"source_record": "earlier report, retained"}],
            "adopted_at_utc": "2026-10-29T08:00:00Z",
        }],
    }


def test_accepted_external_conversion_preserves_source_date_and_visual_scope():
    document = source_package()
    bundle = prepare_bundles(document)[0]
    assessment = bundle.batch.assessments[0]
    assert bundle.batch.source_kind == "user_accepted_external_ai"
    assert bundle.batch.id == "external-test-1"
    assert bundle.batch.evaluator_identity.model == "unknown"
    assert bundle.batch.evaluator_identity.provider == "unknown"
    assert bundle.batch.evaluator_identity.agent == "Reported AI identity"
    assert bundle.batch.evaluator_identity.run_id == "unknown"
    assert assessment.evaluated_at is None
    assert assessment.reported_review_date.isoformat() == "2026-10-29"
    assert assessment.reported_timezone is None
    assert assessment.game_version is None
    assert assessment.snapshot_key == "external-report:external-test-1"
    assert bundle.rule.dimensions[-1].key == "visual"
    assert "仅视觉" in bundle.rule.dimensions[-1].label
    assert all(dimension.key != "audiovisual" for dimension in bundle.rule.dimensions)
    assert bundle.batch.source_metadata["source_record"] == document["reviews"][0]
    assert bundle.batch.source_metadata["source_file"]["sha256"] == "a" * 64
    assert bundle.batch.source_metadata["recomputed_total"] == "6.9"
    assert assessment.evidence[1].note.find('"file_received": false') >= 0


def test_extending_source_package_keeps_existing_batch_payload_stable():
    initial = source_package()
    expanded = deepcopy(initial)
    other = deepcopy(expanded["reviews"][0])
    other.update(import_key="external-test-2", game_id="2", catalog_project_id="2")
    expanded["reviews"].append(other)
    expanded.update(review_count=2, unique_game_count=2)
    expanded["import_bundle_version"] = "changed-package-version-not-an-assessment"
    assert prepare_bundles(initial)[0] == prepare_bundles(expanded)[0]


def test_equivalent_reason_text_metadata_wrapper_keeps_existing_batch_payload_stable():
    initial = source_package()
    repackaged = deepcopy(initial)
    for row in repackaged["reviews"][0]["dimension_scores"]:
        reason = row["reported_reason"]
        row["source_reason_metadata"] = reason
        row["reported_reason"] = reason["reported_reason"]
    assert prepare_bundles(initial)[0] == prepare_bundles(repackaged)[0]


def test_conflicting_reason_wrapper_is_not_silently_reused():
    data = source_package()
    row = data["reviews"][0]["dimension_scores"][0]
    row["source_reason_metadata"] = {"reported_reason": "Different claim"}
    with pytest.raises(ValueError, match="reason text conflicts"):
        prepare_bundles(data)


def test_score_only_source_keeps_missing_metadata_null_and_identity_unknown():
    data = source_package()
    review = data["reviews"][0]
    review.update(
        reported_reviewer_id=None, assigned_reviewer="planned-agent-not-verified",
        reported_review_date=None, reported_timezone=None, reviewed_at_utc=None,
        reported_environment=None, reported_played_scope=None, reported_limitations=None,
        reported_evidence=None,
    )
    for row in review["dimension_scores"]:
        row.update(reported_reason=None, reason_origin=None)
    prepared = prepare_bundles(data)[0]
    assessment = prepared.batch.assessments[0]
    assert assessment.evaluated_at is None and assessment.reported_review_date is None
    assert assessment.reported_timezone is None
    assert assessment.environment == assessment.play_scope == {"reported_description": None}
    assert assessment.limitations == []
    assert prepared.batch.evaluator_identity.agent == "unknown"
    assert prepared.batch.source_metadata["source_record"]["reported_evidence"] is None
    assert prepared.batch.source_metadata["source_record"]["reported_environment"] is None
    assert prepared.batch.source_metadata["source_record"]["reported_played_scope"] is None
    assert len(assessment.evidence) == 1
    assert assessment.evidence[0].kind == "user_accepted_external_ai_report"
    assert all(item.evidence[0].kind == "external_ai_score_provenance"
               for item in assessment.dimensions)
    assert all(row["reported_reason"] is None
               for row in prepared.batch.source_metadata["source_record"]["dimension_scores"])


@pytest.mark.parametrize("change", [
    "duplicate_game", "duplicate_import_key", "id_mismatch", "score_mismatch",
    "total_mismatch", "unrounded_mismatch", "weight_mismatch", "undefined_dimension",
    "out_of_range", "wrong_dimension_version",
])
def test_source_id_duplicate_score_and_arithmetic_errors_are_rejected(change):
    data = source_package()
    review = data["reviews"][0]
    if change in {"duplicate_game", "duplicate_import_key"}:
        duplicate = deepcopy(review)
        duplicate.update(import_key="external-test-2")
        if change == "duplicate_import_key":
            duplicate.update(game_id="2", catalog_project_id="2", import_key=review["import_key"])
        data["reviews"].append(duplicate)
        data.update(review_count=2, unique_game_count=2)
    elif change == "id_mismatch":
        review["catalog_project_id"] = "2"
    elif change == "score_mismatch":
        review["dimension_scores"][0]["raw_score"] = 7
    elif change == "total_mismatch":
        review["total_score"] = 7
    elif change == "unrounded_mismatch":
        review["unrounded_total"] = "6.85"
    elif change == "weight_mismatch":
        review["dimension_scores"][0]["weight"] = 0.3
    elif change == "undefined_dimension":
        data["weight_scheme"]["weights"]["audiovisual"] = (
            data["weight_scheme"]["weights"].pop("visual")
        )
    elif change == "out_of_range":
        review["raw_scores"]["gameplay"] = 10.01
        review["dimension_scores"][2]["raw_score"] = 10.01
    elif change == "wrong_dimension_version":
        review["dimension_scores"][0]["dimension_definition_version"] = "another-definition"
    with pytest.raises(ValueError):
        prepare_bundles(data)


def test_accepted_bundle_import_is_idempotent_and_does_not_change_player_scores():
    bundle = prepare_bundles(source_package())[0]
    engine = sa.create_engine("sqlite://")

    @sa.event.listens_for(engine, "connect")
    def foreign_keys_on(connection, _record):
        connection.execute("PRAGMA foreign_keys=ON")

    with engine.begin() as connection:
        connection.exec_driver_sql("CREATE TABLE uploads (id BIGINT PRIMARY KEY)")
    Base.metadata.create_all(
        engine, tables=[
            CatalogCategory.__table__, CatalogProject.__table__, CatalogRating.__table__
        ] + AI_TABLES,
    )
    with Session(engine, expire_on_commit=False) as session:
        session.add(CatalogCategory(id="1", slug="games", name="Fixture", is_visible=True))
        session.flush()
        now = datetime(2026, 10, 29, tzinfo=UTC)
        session.add(CatalogProject(
            id="1", category_id="1", slug="fixture-game", name="Fixture game",
            destination_url="https://example.invalid/game", destination_kind="external",
            view_count=123, created_at=now, updated_at=now,
        ))
        session.flush()
        session.add(CatalogRating(id="1", project_id="1", ip_digest="a" * 64, score=5))
        session.commit()
        service = CatalogAiRatingService(SQLiteSession(session))
        first = run(service.import_bundle(bundle))
        replay = run(service.import_bundle(bundle))
        assessment_id = first["assessment_ids"][0]
        assert replay["assessment_ids"] == [assessment_id]
        assert replay["inserted"] is False
        assert run(service.total_for_assessment(assessment_id, bundle.weight_scheme.version)) == (
            Decimal("6.9")
        )
        assert session.scalar(sa.select(sa.func.count()).select_from(AiRatingBatch)) == 1
        assert session.scalar(sa.select(sa.func.count()).select_from(AiGameAssessment)) == 1
        assert session.scalar(sa.select(sa.func.count()).select_from(AiAssessmentDimension)) == 5
        assert session.get(AiGameAssessment, assessment_id).evaluated_at is None
        assert session.get(CatalogProject, "1").view_count == 123
        assert session.scalar(sa.select(CatalogRating.score)) == 5
    engine.dispose()

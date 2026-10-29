"""AI assessment storage tests: only private in-memory SQLite databases are used."""

from __future__ import annotations

import importlib.util
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from io import StringIO
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from pydantic import ValidationError
from sqlalchemy.dialects import mysql
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models.catalog import CatalogCategory, CatalogProject, CatalogRating
from app.models.catalog_ai_rating import (
    AiAssessmentDimension,
    AiAssessmentHumanReview,
    AiGameAssessment,
    AiRatingBatch,
    AiRatingRule,
    AiRatingWeightScheme,
)
from app.repositories.catalog_ai_ratings import ai_ranking_statement
from app.schemas.catalog_ai_ratings import (
    AiAssessmentInput,
    AiHumanReviewInput,
    AiImportBundle,
    AiRuleInput,
    AiWeightSchemeInput,
)
from app.services.catalog_ai_ratings import CatalogAiRatingService, calculate_total

ROOT = Path(__file__).resolve().parents[1]
OBSERVED = datetime(2026, 10, 28, 12, 0, tzinfo=UTC)
KEYS = (
    "visible_system_complexity",
    "content_depth_scope",
    "gameplay",
    "controls_completion",
    "audiovisual",
)
WEIGHTS = ("0.4", "0.3", "0.15", "0.1", "0.05")
AI_TABLES = [
    AiRatingRule.__table__,
    AiRatingWeightScheme.__table__,
    AiRatingBatch.__table__,
    AiGameAssessment.__table__,
    AiAssessmentDimension.__table__,
    AiAssessmentHumanReview.__table__,
]


class SQLiteSession:
    """AsyncSession-shaped adapter over a private synchronous SQLite session."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, instance):
        self.session.add(instance)

    def add_all(self, instances):
        self.session.add_all(instances)

    async def get(self, entity, key):
        return self.session.get(entity, key)

    async def execute(self, statement):
        return self.session.execute(statement)

    async def scalar(self, statement):
        return self.session.scalar(statement)

    async def scalars(self, statement):
        return self.session.scalars(statement)

    async def flush(self):
        self.session.flush()

    @asynccontextmanager
    async def begin_nested(self):
        with self.session.begin_nested():
            yield


def run(coroutine):
    # Every SQLite adapter await completes synchronously. Driving the coroutine
    # directly also guarantees these tests cannot create a socket/event loop.
    try:
        coroutine.send(None)
    except StopIteration as complete:
        return complete.value
    else:
        coroutine.close()
        raise AssertionError("SQLite test adapter unexpectedly yielded asynchronous I/O")


def rule_input(version="dimensions-v1"):
    return AiRuleInput(
        version=version,
        dimensions=[
            {"key": key, "label": key, "definition": f"Observed evidence for {key}"} for key in KEYS
        ],
    )


def scheme_input(version="weights-v1", weights=WEIGHTS, rule_version="dimensions-v1"):
    return AiWeightSchemeInput(
        version=version,
        rule_version=rule_version,
        weights=dict(zip(KEYS, weights, strict=True)),
    )


def observation(game_id="1", scores=(8, 7, 6, 5, 4), **changes):
    data = {
        "game_id": game_id,
        "rule_version": "dimensions-v1",
        "game_version": "release-1",
        "snapshot_key": "sha256:fixture-snapshot-1",
        "evaluated_at": OBSERVED,
        "environment": {"os": "Windows", "browser": "Chrome", "audio": "not tested"},
        "play_scope": {"minutes": 8, "completed": "tutorial only"},
        "evidence": [{"kind": "observation", "note": "Synthetic fixture; no actual game rating"}],
        "limitations": ["Synthetic fixture", "Mobile and sound untested"],
        "dimensions": [
            {
                "dimension_key": key,
                "score": score,
                "evidence": [{"kind": "observation", "note": f"Synthetic evidence: {key}"}],
            }
            for key, score in zip(KEYS, scores, strict=True)
        ],
    }
    data.update(changes)
    return data


def bundle(batch_id="synthetic-batch-1", assessments=None, **changes):
    data = {
        "schema_version": 1,
        "rule": rule_input().model_dump(mode="json"),
        "weight_scheme": scheme_input().model_dump(mode="json"),
        "batch": {
            "id": batch_id,
            "evaluator_kind": "ai",
            "evaluator_identity": {
                "provider": "synthetic-fixture",
                "model": "fixture-model",
                "agent": "test-suite",
                "run_id": batch_id,
            },
            "recorded_at": OBSERVED + timedelta(days=1),
            "assessments": assessments or [observation()],
        },
    }
    data.update(changes)
    return AiImportBundle.model_validate(data)


@pytest.fixture
def store():
    engine = sa.create_engine("sqlite://")

    @sa.event.listens_for(engine, "connect")
    def foreign_keys_on(connection, _record):
        connection.execute("PRAGMA foreign_keys=ON")

    with engine.begin() as connection:
        # Catalog tables reference uploads, which is irrelevant to this isolated feature.
        connection.exec_driver_sql("CREATE TABLE uploads (id BIGINT PRIMARY KEY)")
    Base.metadata.create_all(
        engine,
        tables=[CatalogCategory.__table__, CatalogProject.__table__, CatalogRating.__table__]
        + AI_TABLES,
    )
    with Session(engine, expire_on_commit=False) as session:
        session.add_all(
            [
                CatalogCategory(id="1", slug="games", name="Games", is_visible=True),
                CatalogCategory(id="2", slug="private", name="Private", is_visible=False),
            ]
        )
        session.flush()
        session.add_all(
            [
                CatalogProject(
                    id=str(number),
                    category_id="2" if number == 6 else "1",
                    slug=f"synthetic-game-{number}",
                    name=f"Synthetic game {number}",
                    destination_url=f"https://example.invalid/game-{number}",
                    destination_kind="external",
                    is_visible=number != 5,
                    sort_order=number,
                    view_count=123,
                    created_at=OBSERVED,
                    updated_at=OBSERVED,
                )
                for number in range(1, 7)
            ]
        )
        session.flush()
        session.add(CatalogRating(id="1", project_id="1", ip_digest="a" * 64, score=5))
        session.commit()
        yield session, CatalogAiRatingService(SQLiteSession(session))
    engine.dispose()


def count(session, model):
    return session.scalar(sa.select(sa.func.count()).select_from(model))


def test_total_uses_explicit_weights_and_decimal_half_up_rounding():
    rule, scheme = rule_input(), scheme_input()
    assert calculate_total(rule, scheme, dict.fromkeys(KEYS, Decimal("6.05"))) == Decimal("6.1")
    assert calculate_total(rule, scheme, dict.fromkeys(KEYS, Decimal(0))) == Decimal("0.0")
    assert calculate_total(rule, scheme, dict.fromkeys(KEYS, Decimal(10))) == Decimal("10.0")
    assert calculate_total(
        rule, scheme, dict(zip(KEYS, map(Decimal, [8, 7, 6, 5, 4]), strict=True))
    ) == (Decimal("6.9"))


@pytest.mark.parametrize("missing", [None, "absent"])
def test_missing_required_dimension_never_becomes_zero_or_renormalizes(missing):
    scores = dict.fromkeys(KEYS, Decimal(10))
    if missing is None:
        scores[KEYS[-1]] = None
    else:
        del scores[KEYS[-1]]
    assert calculate_total(rule_input(), scheme_input(), scores) is None


def test_required_dimension_is_still_required_when_its_weight_is_zero():
    scores = dict.fromkeys(KEYS, Decimal(10))
    scores[KEYS[-1]] = None
    scheme = scheme_input(weights=("0.4", "0.3", "0.2", "0.1", "0"))
    assert calculate_total(rule_input(), scheme, scores) is None


def test_import_and_reweight_keep_raw_scores_evidence_and_player_data(store):
    session, service = store
    result = run(service.import_bundle(bundle()))
    assert result["inserted"] is True
    assessment_id = result["assessment_ids"][0]
    assert run(service.total_for_assessment(assessment_id, "weights-v1")) == Decimal("6.9")
    run(
        service.register_weight_scheme(
            scheme_input("weights-v2", ("0.05", "0.1", "0.15", "0.3", "0.4"))
        )
    )
    assert run(service.total_for_assessment(assessment_id, "weights-v2")) == Decimal("5.1")
    assert run(service.total_for_assessment(assessment_id, "weights-v1")) == Decimal("6.9")
    assert count(session, AiGameAssessment) == 1
    assert count(session, AiAssessmentDimension) == 5
    assessment = session.get(AiGameAssessment, assessment_id)
    assert assessment.game_id == "1"
    assert assessment.environment["audio"] == "not tested"
    assert assessment.play_scope["completed"] == "tutorial only"
    assert assessment.limitations == ["Synthetic fixture", "Mobile and sound untested"]
    assert session.get(AiRatingBatch, result["batch_id"]).evaluator_kind == "ai"
    assert (
        session.get(AiRatingBatch, result["batch_id"]).evaluator_identity["model"]
        == "fixture-model"
    )
    assert session.execute(sa.select(CatalogRating.project_id, CatalogRating.score)).all() == [
        ("1", 5)
    ]
    assert session.get(CatalogProject, "1").view_count == 123
    assert session.get(CatalogProject, "1").updated_at.replace(tzinfo=UTC) == OBSERVED


def test_batch_import_is_idempotent_and_conflicting_content_is_not_overwritten(store):
    session, service = store
    first = run(service.import_bundle(bundle()))
    replay = run(service.import_bundle(bundle()))
    assert replay["inserted"] is False
    assert replay["assessment_ids"] == first["assessment_ids"]
    changed = bundle(assessments=[observation(scores=(1, 1, 1, 1, 1))])
    with pytest.raises(ValueError):
        run(service.import_bundle(changed))
    assert count(session, AiRatingBatch) == count(session, AiGameAssessment) == 1
    assert run(service.total_for_assessment(first["assessment_ids"][0], "weights-v1")) == Decimal(
        "6.9"
    )


def test_new_batches_preserve_history_and_explicit_reassessment_relation(store):
    session, service = store
    first = run(service.import_bundle(bundle()))["assessment_ids"][0]
    second = run(
        service.import_bundle(
            bundle(
                "synthetic-batch-2",
                [observation(scores=(9, 9, 9, 9, 9), supersedes_id=first)],
            )
        )
    )["assessment_ids"][0]
    assert second != first
    assert count(session, AiGameAssessment) == 2
    assert session.get(AiGameAssessment, second).supersedes_id == first
    assert (
        session.get(AiGameAssessment, second).identity_key
        == session.get(AiGameAssessment, first).identity_key
    )
    assert run(service.total_for_assessment(first, "weights-v1")) == Decimal("6.9")
    assert run(service.total_for_assessment(second, "weights-v1")) == Decimal("9.0")
    previous = run(
        service.find_assessments_for_identity(
            "1", "dimensions-v1", "release-1", "sha256:fixture-snapshot-1"
        )
    )
    assert {item.id for item in previous} == {first, second}


@pytest.mark.parametrize("missing_row", [False, True])
def test_import_preserves_unknown_dimension_as_null_total(store, missing_row):
    session, service = store
    data = observation(scores=(10, 10, 10, 10, None))
    if missing_row:
        data["dimensions"].pop()
    assessment_id = run(service.import_bundle(bundle(assessments=[data])))["assessment_ids"][0]
    assert run(service.total_for_assessment(assessment_id, "weights-v1")) is None
    assert count(session, AiAssessmentDimension) == (4 if missing_row else 5)
    assert (
        next(row for row in run(service.list_ranking("weights-v1")) if row["game_id"] == "1")[
            "ai_score"
        ]
        is None
    )


def test_rule_and_weight_versions_are_immutable_and_definition_change_needs_new_rule(store):
    session, service = store
    run(service.import_bundle(bundle()))
    changed_rule = rule_input().model_dump(mode="python")
    changed_rule["dimensions"][0]["definition"] = "Different semantic dimension"
    with pytest.raises(ValueError):
        run(service.register_rule(AiRuleInput.model_validate(changed_rule)))
    with pytest.raises(ValueError):
        run(service.register_weight_scheme(scheme_input(weights=("0.2",) * 5)))
    run(service.register_rule(rule_input("dimensions-v2")))
    run(service.register_weight_scheme(scheme_input("weights-v2", rule_version="dimensions-v2")))
    assessment_id = session.scalar(sa.select(AiGameAssessment.id))
    with pytest.raises(ValueError):
        run(service.total_for_assessment(assessment_id, "weights-v2"))
    assert count(session, AiGameAssessment) == 1


def test_import_failure_rolls_back_new_rule_weight_and_batch_as_one_unit(store):
    session, service = store
    data = bundle(assessments=[observation(game_id="999")])
    with pytest.raises((ValueError, IntegrityError)):
        run(service.import_bundle(data))
    assert count(session, AiRatingRule) == 0
    assert count(session, AiRatingWeightScheme) == 0
    assert count(session, AiRatingBatch) == 0
    assert count(session, AiGameAssessment) == 0


def test_ranking_desc_null_last_uses_latest_assessment_and_filters_hidden_catalog(store):
    session, service = store
    initial = run(
        service.import_bundle(
            bundle(
                assessments=[
                    observation("1", (10, 10, 10, 10, 10)),
                    observation("2", (7, 7, 7, 7, 7)),
                    observation("3", (9, 9, 9, 9, 9)),
                    observation("5", (10, 10, 10, 10, 10)),
                    observation("6", (10, 10, 10, 10, 10)),
                ]
            )
        )
    )
    latest = run(
        service.import_bundle(
            bundle(
                "synthetic-batch-2",
                [
                    observation(
                        "1", (10, 10, 10, 10, None), evaluated_at=OBSERVED + timedelta(hours=1)
                    )
                ],
            )
        )
    )["assessment_ids"][0]
    rows = run(service.list_ranking("weights-v1"))
    assert [row["game_id"] for row in rows[:2]] == ["3", "2"]
    assert {row["game_id"] for row in rows[2:]} == {"1", "4"}
    assert [row["ai_score"] for row in rows] == [Decimal("9.0"), Decimal("7.0"), None, None]
    assert next(row for row in rows if row["game_id"] == "1")["assessment_id"] == latest
    assert next(row for row in rows if row["game_id"] == "4")["assessment_id"] is None
    assert all(row["label"] == "AI评分" and row["weight_version"] == "weights-v1" for row in rows)
    assert run(service.list_ranking("weights-v1", limit=1, offset=1)) == rows[1:2]
    assert len(initial["assessment_ids"]) == 5
    assert count(session, AiGameAssessment) == 6


def test_human_reviews_are_independent_append_only_records(store):
    session, service = store
    assessment_id = run(service.import_bundle(bundle()))["assessment_ids"][0]
    review = AiHumanReviewInput(
        id="review-1",
        assessment_id=assessment_id,
        reviewer_identity="operator:synthetic-reviewer",
        reviewed_at=OBSERVED + timedelta(hours=2),
        verdict="needs_reassessment",
        notes="Synthetic review; original assessment remains untouched",
        evidence=[{"kind": "review", "note": "Please check sound in a later assessment"}],
    )
    first = run(service.add_human_review(review))
    assert run(service.add_human_review(review)).id == first.id
    with pytest.raises(ValueError):
        run(service.add_human_review(review.model_copy(update={"verdict": "confirmed"})))
    assert count(session, AiAssessmentHumanReview) == 1
    assert count(session, AiGameAssessment) == 1
    assert run(service.total_for_assessment(assessment_id, "weights-v1")) == Decimal("6.9")


def test_supersedes_relation_cannot_cross_games_or_point_to_missing_history(store):
    session, service = store
    original = run(service.import_bundle(bundle()))["assessment_ids"][0]
    for previous in [original, "missing-assessment"]:
        with pytest.raises(ValueError):
            run(
                service.import_bundle(
                    bundle("synthetic-batch-2", [observation("2", supersedes_id=previous)])
                )
            )
    assert count(session, AiGameAssessment) == count(session, AiRatingBatch) == 1


def test_weight_total_and_batch_date_are_validated_before_import():
    with pytest.raises(ValidationError):
        scheme_input(weights=("0.1",) * 5)
    with pytest.raises(ValidationError):
        bundle(assessments=[observation(evaluated_at=OBSERVED + timedelta(days=2))])
    data = observation()
    data["dimensions"].append(data["dimensions"][0])
    with pytest.raises(ValidationError):
        AiAssessmentInput.model_validate(data)


@pytest.mark.parametrize(
    "changes",
    [
        {"game_version": None, "snapshot_key": None},
        {"game_version": None, "snapshot_key": "unknown"},
        {"game_version": "unknown"},
        {"evaluated_at": "2026-10-28T12:00:00"},
        {"environment": {}},
        {"play_scope": {}},
        {"evidence": []},
    ],
)
def test_assessment_schema_requires_explicit_unknown_scope_and_provenance(changes):
    with pytest.raises(ValidationError):
        AiAssessmentInput.model_validate(observation(**changes))


def test_unknown_versions_use_fresh_snapshot_identity_and_duplicate_batch_scope_is_rejected(store):
    session, service = store
    first = run(
        service.import_bundle(
            bundle(assessments=[observation(game_version=None, snapshot_key="observation:run-a")])
        )
    )["assessment_ids"][0]
    second = run(
        service.import_bundle(
            bundle(
                "synthetic-batch-2",
                [observation(game_version=None, snapshot_key="observation:run-b")],
            )
        )
    )["assessment_ids"][0]
    assert (
        session.get(AiGameAssessment, first).identity_key
        != session.get(AiGameAssessment, second).identity_key
    )
    with pytest.raises((ValueError, IntegrityError)):
        run(service.import_bundle(bundle("synthetic-batch-3", [observation(), observation()])))
    assert count(session, AiRatingBatch) == 2


@pytest.mark.parametrize("bad_score", [Decimal("-0.01"), Decimal("10.01")])
def test_database_rejects_out_of_range_scores_even_without_schema(store, bad_score):
    session, service = store
    assessment_id = run(service.import_bundle(bundle()))["assessment_ids"][0]
    with pytest.raises(IntegrityError), session.begin_nested():
        session.execute(
            sa.update(AiAssessmentDimension)
            .where(AiAssessmentDimension.assessment_id == assessment_id)
            .values(score=bad_score)
        )


def test_database_protects_unique_dimensions_and_referenced_history(store):
    session, service = store
    assessment_id = run(service.import_bundle(bundle()))["assessment_ids"][0]
    with pytest.raises(IntegrityError), session.begin_nested():
        session.add(
            AiAssessmentDimension(
                assessment_id=assessment_id, dimension_key=KEYS[0], score=3, evidence=[]
            )
        )
        session.flush()
    with pytest.raises(IntegrityError), session.begin_nested():
        session.execute(sa.delete(CatalogProject).where(CatalogProject.id == "1"))
    assert count(session, AiAssessmentDimension) == 5
    assert session.get(CatalogProject, "1") is not None


def migration_module():
    spec = importlib.util.spec_from_file_location(
        "catalog_ai_rating_migration", ROOT / "alembic/versions/0101_catalog_ai_ratings.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_migration_upgrade_downgrade_only_touches_ai_tables(monkeypatch):
    migration = migration_module()
    engine = sa.create_engine("sqlite://")
    with engine.begin() as connection:
        connection.exec_driver_sql("PRAGMA foreign_keys=ON")
        connection.exec_driver_sql(
            "CREATE TABLE catalog_projects (id BIGINT PRIMARY KEY, view_count BIGINT)"
        )
        connection.exec_driver_sql(
            "CREATE TABLE catalog_ratings (project_id BIGINT, score INTEGER)"
        )
        connection.exec_driver_sql("INSERT INTO catalog_projects VALUES (1, 123)")
        connection.exec_driver_sql("INSERT INTO catalog_ratings VALUES (1, 5)")
        monkeypatch.setattr(
            migration,
            "op",
            Operations(
                MigrationContext.configure(connection, opts={"catalog_ai_isolated_sqlite": True})
            ),
        )
        migration.upgrade()
        assert {table.name for table in AI_TABLES}.issubset(
            sa.inspect(connection).get_table_names()
        )
        for table in AI_TABLES:
            assert connection.scalar(sa.text(f"SELECT COUNT(*) FROM {table.name}")) == 0
        migration.downgrade()
        assert sa.inspect(connection).get_table_names() == ["catalog_projects", "catalog_ratings"]
        assert connection.exec_driver_sql("SELECT * FROM catalog_projects").all() == [(1, 123)]
        assert connection.exec_driver_sql("SELECT * FROM catalog_ratings").all() == [(1, 5)]
    engine.dispose()


def test_migration_compiles_mysql_ddl_offline_without_database_access(monkeypatch):
    migration = migration_module()
    output = StringIO()
    context = MigrationContext.configure(
        dialect_name="mysql", opts={"as_sql": True, "output_buffer": output}
    )
    monkeypatch.setattr(migration, "op", Operations(context))
    migration.upgrade()
    upgrade = output.getvalue()
    assert upgrade.count("CREATE TABLE catalog_ai_") == 6
    assert "CHECK (score IS NULL OR score BETWEEN 0 AND 10)" in upgrade
    assert "ON DELETE RESTRICT" in upgrade
    assert "CREATE TABLE catalog_ratings" not in upgrade
    assert migration.down_revision == "0100_add_yiji_pochao"
    migration.downgrade()
    assert output.getvalue().count("DROP TABLE catalog_ai_") == 6
    assert "UPDATE CATALOG_AI_GAME_ASSESSMENTS" not in output.getvalue().upper()


@pytest.mark.parametrize(
    ("raw_score", "expected"),
    [("0.05", "0.1"), ("6.85", "6.9"), ("6.95", "7.0"), ("9.95", "10.0")],
)
def test_sql_ranking_and_decimal_total_agree_at_half_up_boundaries(store, raw_score, expected):
    _session, service = store
    assessment_id = run(
        service.import_bundle(bundle(assessments=[observation(scores=(Decimal(raw_score),) * 5)]))
    )["assessment_ids"][0]
    decimal_total = run(service.total_for_assessment(assessment_id, "weights-v1"))
    sql_total = next(
        row for row in run(service.list_ranking("weights-v1")) if row["game_id"] == "1"
    )["ai_score"]
    assert decimal_total == sql_total == Decimal(expected)


def test_new_weight_scheme_changes_ranking_and_matches_decimal_totals(store):
    _session, service = store
    run(
        service.import_bundle(
            bundle(
                assessments=[
                    observation("1", (10, 10, 0, 0, 0)),
                    observation("2", (0, 0, 10, 10, 10)),
                ]
            )
        )
    )
    original = run(service.list_ranking("weights-v1"))
    assert [(row["game_id"], row["ai_score"]) for row in original[:2]] == [
        ("1", Decimal("7.0")),
        ("2", Decimal("3.0")),
    ]
    run(
        service.register_weight_scheme(
            scheme_input("weights-v2", ("0.05", "0.1", "0.15", "0.3", "0.4"))
        )
    )
    reweighted = run(service.list_ranking("weights-v2"))
    assert [(row["game_id"], row["ai_score"]) for row in reweighted[:2]] == [
        ("2", Decimal("8.5")),
        ("1", Decimal("1.5")),
    ]
    for version, rows in [("weights-v1", original), ("weights-v2", reweighted)]:
        for row in rows[:2]:
            assert row["ai_score"] == run(
                service.total_for_assessment(row["assessment_id"], version)
            )


def test_ranking_query_compiles_window_and_weighted_aggregate_for_mysql_offline():
    statement = ai_ranking_statement(rule_input(), scheme_input(), limit=20, offset=10)
    sql = str(statement.compile(dialect=mysql.dialect(), compile_kwargs={"literal_binds": True}))
    assert "row_number() OVER (PARTITION BY" in sql
    assert "max(CASE WHEN" in sql
    assert "GROUP BY catalog_ai_assessment_dimensions.assessment_id" in sql
    assert "ai_totals.ai_score IS NULL, ai_totals.ai_score DESC" in sql
    assert "LIMIT 10, 20" in sql


def test_weight_version_retry_accepts_numerically_equivalent_decimal_representations(store):
    session, service = store
    assessment_id = run(service.import_bundle(bundle()))["assessment_ids"][0]
    retry = scheme_input(weights=("0.4000", "0.3000", "0.1500", "0.1000", "0.0500"))
    assert run(service.register_weight_scheme(retry)).version == "weights-v1"
    assert count(session, AiRatingWeightScheme) == 1
    assert count(session, AiGameAssessment) == 1
    assert run(service.total_for_assessment(assessment_id, "weights-v1")) == Decimal("6.9")


def test_four_decimal_weights_and_two_decimal_scores_agree_between_sql_and_decimal(store):
    _session, service = store
    scheme = scheme_input(
        "weights-four-decimals-v1", ("0.1234", "0.2345", "0.3456", "0.1234", "0.1731")
    )
    run(
        service.import_bundle(
            bundle(
                assessments=[
                    observation("1", tuple(map(Decimal, ("9.95", "6.85", "0.05", "2.37", "8.91")))),
                    observation("2", (Decimal("6.85"),) * 5),
                ],
                weight_scheme=scheme.model_dump(mode="json"),
            )
        )
    )
    rows = run(service.list_ranking(scheme.version))
    assert [(row["game_id"], row["ai_score"]) for row in rows[:2]] == [
        ("2", Decimal("6.9")),
        ("1", Decimal("4.7")),
    ]
    for row in rows[:2]:
        assert row["ai_score"] == run(
            service.total_for_assessment(row["assessment_id"], scheme.version)
        )


def test_populated_migration_downgrade_with_reassessment_and_human_review(monkeypatch):
    migration = migration_module()
    engine = sa.create_engine("sqlite://")
    with engine.begin() as connection:
        connection.exec_driver_sql("PRAGMA foreign_keys=ON")
        connection.exec_driver_sql(
            "CREATE TABLE catalog_projects (id BIGINT PRIMARY KEY, view_count BIGINT)"
        )
        connection.exec_driver_sql(
            "CREATE TABLE catalog_ratings (project_id BIGINT, score INTEGER)"
        )
        connection.exec_driver_sql("INSERT INTO catalog_projects VALUES (1, 123)")
        connection.exec_driver_sql("INSERT INTO catalog_ratings VALUES (1, 5)")
        monkeypatch.setattr(
            migration,
            "op",
            Operations(
                MigrationContext.configure(connection, opts={"catalog_ai_isolated_sqlite": True})
            ),
        )
        migration.upgrade()
        connection.execute(
            AiRatingRule.__table__.insert(),
            {"version": "dimensions-v1", "definition_digest": "d" * 64, "dimensions": []},
        )
        connection.execute(
            AiRatingWeightScheme.__table__.insert(),
            {"version": "weights-v1", "rule_version": "dimensions-v1", "weights": {}},
        )
        connection.execute(
            AiRatingBatch.__table__.insert(),
            {
                "id": "synthetic-batch-1",
                "evaluator_identity": {"model": "synthetic-fixture"},
                "payload_digest": "b" * 64,
                "recorded_at": OBSERVED,
            },
        )
        for assessment_id, supersedes_id in [("original", None), ("reassessment", "original")]:
            connection.execute(
                AiGameAssessment.__table__.insert(),
                {
                    "id": assessment_id,
                    "batch_id": "synthetic-batch-1",
                    "game_id": "1",
                    "rule_version": "dimensions-v1",
                    "identity_key": assessment_id.ljust(64, "x"),
                    "game_version": "release-1",
                    "snapshot_key": assessment_id,
                    "evaluated_at": OBSERVED,
                    "environment": {"os": "fixture"},
                    "play_scope": {"scope": "fixture"},
                    "evidence": [],
                    "limitations": [],
                    "payload_digest": "a" * 64,
                    "supersedes_id": supersedes_id,
                },
            )
            connection.execute(
                AiAssessmentDimension.__table__.insert(),
                {
                    "assessment_id": assessment_id,
                    "dimension_key": KEYS[0],
                    "score": Decimal(7),
                    "evidence": [],
                },
            )
        connection.execute(
            AiAssessmentHumanReview.__table__.insert(),
            {
                "id": "review-1",
                "assessment_id": "reassessment",
                "reviewer_identity": "synthetic-fixture",
                "reviewed_at": OBSERVED,
                "verdict": "confirmed",
                "notes": "synthetic-fixture",
                "evidence": [],
            },
        )
        migration.downgrade()
        assert sa.inspect(connection).get_table_names() == ["catalog_projects", "catalog_ratings"]
        assert connection.exec_driver_sql("SELECT * FROM catalog_projects").all() == [(1, 123)]
        assert connection.exec_driver_sql("SELECT * FROM catalog_ratings").all() == [(1, 5)]
    engine.dispose()


def test_sqlite_downgrade_requires_explicit_isolated_flag_before_touching_any_table(monkeypatch):
    migration = migration_module()
    engine = sa.create_engine("sqlite://")
    with engine.begin() as connection:
        connection.exec_driver_sql("PRAGMA foreign_keys=ON")
        connection.exec_driver_sql("CREATE TABLE catalog_projects (id BIGINT PRIMARY KEY)")
        monkeypatch.setattr(migration, "op", Operations(MigrationContext.configure(connection)))
        migration.upgrade()
        tables_before = sa.inspect(connection).get_table_names()
        with pytest.raises(RuntimeError):
            migration.downgrade()
        assert sa.inspect(connection).get_table_names() == tables_before
        assert {table.name for table in AI_TABLES}.issubset(tables_before)
    engine.dispose()


def test_user_accepted_external_ai_keeps_source_and_history_and_participates_in_ranking(store):
    session, service = store
    independent_id = run(service.import_bundle(bundle()))["assessment_ids"][0]
    external = bundle(
        "external-batch-1",
        [
            observation("1", (10,) * 5, evaluated_at=OBSERVED + timedelta(hours=1)),
            observation("2", (10,) * 5, evaluated_at=OBSERVED + timedelta(hours=1)),
        ],
    ).model_dump(mode="python")
    external["batch"].update(
        source_kind="user_accepted_external_ai",
        source_reference="submission:synthetic-reference-1",
        source_metadata={"submitted_by": "synthetic-author", "original_scale": 10},
    )
    imported = run(service.import_bundle(AiImportBundle.model_validate(external)))
    stored = session.get(AiRatingBatch, imported["batch_id"])
    assert stored.source_kind == "user_accepted_external_ai"
    assert stored.source_reference == "submission:synthetic-reference-1"
    assert stored.source_metadata == {"submitted_by": "synthetic-author", "original_scale": 10}
    assert session.get(AiRatingBatch, "synthetic-batch-1").source_kind == "independent_ai"
    for assessment_id in imported["assessment_ids"]:
        assert run(service.total_for_assessment(assessment_id, "weights-v1")) == Decimal("10.0")
    rows = {row["game_id"]: row for row in run(service.list_ranking("weights-v1"))}
    assert rows["1"]["assessment_id"] in imported["assessment_ids"]
    assert rows["1"]["ai_score"] == rows["2"]["ai_score"] == Decimal("10.0")
    assert rows["1"]["source_kind"] == "user_accepted_external_ai"
    assert rows["1"]["source_reference"] == "submission:synthetic-reference-1"
    assert rows["1"]["source_metadata"] == stored.source_metadata
    assert session.get(AiGameAssessment, independent_id) is not None
    assert run(service.total_for_assessment(independent_id, "weights-v1")) == Decimal("6.9")
    assert count(session, AiGameAssessment) == 3


@pytest.mark.parametrize(
    "source_changes",
    [
        {"source_kind": "user_accepted_external_ai"},
        {"source_kind": "user_accepted_external_ai", "source_reference": ""},
        {"source_kind": "user_accepted_external_ai", "source_reference": None},
    ],
)
def test_batch_source_contract_requires_external_reference(source_changes):
    data = bundle().model_dump(mode="python")
    data["batch"].update(source_changes)
    with pytest.raises(ValidationError):
        AiImportBundle.model_validate(data)

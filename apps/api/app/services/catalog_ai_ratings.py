"""AI-only assessment import and derivation. Caller owns the transaction.

There is no public route or implicit database configuration in this module. Use
an explicitly supplied AsyncSession. Imports use a savepoint and flush, never
commit; the caller must commit only after reviewing a validated batch.
"""

from __future__ import annotations

import hashlib
import json
import re
from decimal import ROUND_HALF_UP, Decimal
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import as_utc_datetime
from app.models.catalog import CatalogProject
from app.models.catalog_ai_rating import (
    AiAssessmentDimension,
    AiAssessmentHumanReview,
    AiGameAssessment,
    AiRatingBatch,
    AiRatingRule,
    AiRatingWeightScheme,
)
from app.repositories.catalog_ai_public import latest_public_assessments_statement
from app.repositories.catalog_ai_ratings import ai_ranking_statement
from app.schemas.catalog import CatalogAiDimensionResponse, CatalogAiRatingResponse
from app.schemas.catalog_ai_ratings import (
    TOTAL_DECIMAL_PLACES,
    AiHumanReviewInput,
    AiImportBundle,
    AiRuleInput,
    AiWeightSchemeInput,
)
from app.services.catalog_ai_rating_defaults import (
    CURRENT_AI_WEIGHT_SCHEME,
    PUBLIC_AI_WEIGHT_VERSION,
)

AI_RATING_LABEL = "AI评分"

_PRIVATE_SCOPE_KEYS = frozenset({
    "source_reference", "source_metadata", "evaluator_identity", "run_id",
    "evidence", "environment", "snapshot_key", "batch_id",
})
_LOCAL_REFERENCE = re.compile(
    r"[a-z]:[\\/]|\\\\[^\\]+\\|file://|"
    r"(?:^|\s)/(?:users|home|tmp|var|private|mnt|work|workspace)/",
    re.IGNORECASE,
)
_PRIVATE_VALUE = object()


def _public_scope_value(value):
    """Retain scope/device facts while excluding internal keys and local paths."""

    if isinstance(value, str):
        return _PRIVATE_VALUE if _LOCAL_REFERENCE.search(value) else value
    if isinstance(value, dict):
        public = {}
        for key, item in value.items():
            normalized = key.casefold().replace("-", "_")
            if (
                normalized in _PRIVATE_SCOPE_KEYS or normalized.startswith("_")
                or normalized.endswith(("_path", "_file", "_reference", "_run_id"))
            ):
                continue
            clean = _public_scope_value(item)
            if clean is not _PRIVATE_VALUE:
                public[key] = clean
        return public
    if isinstance(value, list):
        return [
            clean for item in value
            if (clean := _public_scope_value(item)) is not _PRIVATE_VALUE
        ]
    return value


def _digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def assessment_identity(
    game_id: str, rule_version: str, game_version: str | None, snapshot_key: str | None
) -> str:
    """A planning/deduplication key, not a permanent ban on reassessment.

    For unknown versions the caller must supply a fresh observation token or a
    concrete artifact hash, scoped to this observation rather than the game URL.
    """

    placeholders = {"unknown", "latest", "current", "未知", "不详", ""}
    if game_version is not None and game_version.strip().casefold() in placeholders:
        raise ValueError("unknown game version must be null")
    if game_version is None and (
        snapshot_key is None or snapshot_key.strip().casefold() in placeholders
    ):
        raise ValueError("unknown version requires an artifact hash or fresh observation token")
    return _digest({
        "game_id": game_id, "rule_version": rule_version,
        "game_version": game_version, "snapshot_key": snapshot_key,
    })


def _compatible(rule: AiRuleInput, scheme: AiWeightSchemeInput) -> None:
    if scheme.rule_version != rule.version or set(scheme.weights) != {
        dimension.key for dimension in rule.dimensions
    }:
        raise ValueError("weight scheme is incompatible with dimension definitions")


def calculate_total(
    rule: AiRuleInput, scheme: AiWeightSchemeInput, scores: dict[str, Decimal | None]
) -> Decimal | None:
    """Derive 0..10 with Decimal HALF_UP to one place; never fill or normalize gaps."""

    _compatible(rule, scheme)
    if set(scores) - set(scheme.weights):
        raise ValueError("scores contain undefined dimensions")
    total = Decimal(0)
    for dimension in rule.dimensions:
        value = scores.get(dimension.key)
        weight = scheme.weights[dimension.key]
        if value is None:
            if dimension.required or weight > 0:
                return None
            continue
        if not value.is_finite() or not Decimal(0) <= value <= Decimal(10):
            raise ValueError("dimension score must be finite and between 0 and 10")
        total += value * weight
    return total.quantize(Decimal(1).scaleb(-TOTAL_DECIMAL_PLACES), rounding=ROUND_HALF_UP)


class CatalogAiRatingService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def public_summaries(self, game_ids: list[str]) -> dict[str, CatalogAiRatingResponse]:
        """Batch the current public summaries without changing observations or ratings.

        An unregistered display scheme means no AI summaries yet. A missing
        table or invalid persisted rule is an actual deployment/data error and
        is deliberately allowed to propagate. External AI assessments already
        accepted by the user follow the same read path as independent AI work.
        """

        if not game_ids:
            return {}
        stored_scheme = await self.session.get(AiRatingWeightScheme, PUBLIC_AI_WEIGHT_VERSION)
        if stored_scheme is None:
            stored_scheme = await self.session.get(
                AiRatingWeightScheme, CURRENT_AI_WEIGHT_SCHEME.version,
            )
        if stored_scheme is None:
            return {}
        stored_rule = await self.session.get(AiRatingRule, stored_scheme.rule_version)
        if stored_rule is None:
            raise ValueError("public AI weight scheme references a missing rule")
        rule = AiRuleInput(version=stored_rule.version, dimensions=stored_rule.dimensions)
        scheme = AiWeightSchemeInput(
            version=stored_scheme.version,
            rule_version=stored_scheme.rule_version,
            weights=stored_scheme.weights,
        )
        _compatible(rule, scheme)
        rows = list(await self.session.execute(latest_public_assessments_statement(
            list(dict.fromkeys(game_ids)), rule.version,
        )))
        if not rows:
            return {}
        scores = {row.assessment_id: {} for row in rows}
        dimension_rows = await self.session.execute(select(
            AiAssessmentDimension.assessment_id,
            AiAssessmentDimension.dimension_key,
            AiAssessmentDimension.score,
        ).where(AiAssessmentDimension.assessment_id.in_(scores)))
        for item in dimension_rows:
            scores[item.assessment_id][item.dimension_key] = item.score

        summaries = {}
        for row in rows:
            raw_scores = scores[row.assessment_id]
            total = calculate_total(rule, scheme, raw_scores)
            summaries[row.game_id] = CatalogAiRatingResponse(
                score=float(total) if total is not None else None,
                label=AI_RATING_LABEL,
                assessment_id=row.assessment_id,
                rule_version=rule.version,
                weight_version=scheme.version,
                source_kind=row.source_kind,
                evaluated_at=as_utc_datetime(row.evaluated_at) if row.evaluated_at else None,
                reported_review_date=row.reported_review_date,
                reported_timezone=row.reported_timezone,
                game_version=row.game_version,
                dimensions=[CatalogAiDimensionResponse(
                    key=definition.key, label=definition.label,
                    score=(
                        float(value)
                        if (value := raw_scores.get(definition.key)) is not None else None
                    ),
                    weight=float(scheme.weights[definition.key]),
                ) for definition in rule.dimensions],
                play_scope=_public_scope_value(row.play_scope),
                limitations=[item for item in row.limitations if not _LOCAL_REFERENCE.search(item)],
            )
        return summaries

    async def register_rule(self, rule: AiRuleInput) -> AiRatingRule:
        """Append a definition version, rejecting in-place changes even after reweighting."""

        data = rule.model_dump(mode="json")
        digest = _digest(data["dimensions"])
        existing = await self.session.get(AiRatingRule, rule.version)
        if existing is not None:
            if existing.definition_digest != digest:
                raise ValueError("rule version already exists with different definitions")
            return existing
        row = AiRatingRule(
            version=rule.version, definition_digest=digest, dimensions=data["dimensions"]
        )
        self.session.add(row)
        await self.session.flush()
        return row

    async def register_weight_scheme(self, scheme: AiWeightSchemeInput) -> AiRatingWeightScheme:
        rule = await self.session.get(AiRatingRule, scheme.rule_version)
        if rule is None:
            raise ValueError("unknown dimension rule version")
        _compatible(AiRuleInput(version=rule.version, dimensions=rule.dimensions), scheme)
        data = scheme.model_dump(mode="json")
        existing = await self.session.get(AiRatingWeightScheme, scheme.version)
        if existing is not None:
            persisted_weights = {
                key: Decimal(str(value)) for key, value in existing.weights.items()
            }
            if existing.rule_version != scheme.rule_version or persisted_weights != scheme.weights:
                raise ValueError("weight version already exists with different content")
            return existing
        row = AiRatingWeightScheme(
            version=scheme.version, rule_version=scheme.rule_version, weights=data["weights"]
        )
        self.session.add(row)
        await self.session.flush()
        return row

    async def import_bundle(self, bundle: AiImportBundle) -> dict[str, object]:
        """Atomically append a batch; exact batch retries are idempotent.

        A changed batch ID is a new historical observation, even for an identical
        game snapshot. Call find_assessments_for_identity before assigning work
        to evaluators. Concurrent identical batch inserts are protected by the
        primary key: retry the entire transaction on an IntegrityError.
        """

        batch_data = bundle.batch.model_dump(mode="json")
        batch_digest = _digest(batch_data)
        async with self.session.begin_nested():
            await self.register_rule(bundle.rule)
            await self.register_weight_scheme(bundle.weight_scheme)
            existing = await self.session.get(AiRatingBatch, bundle.batch.id)
            if existing is not None:
                if existing.payload_digest != batch_digest:
                    raise ValueError("batch ID already exists with different content")
                ids = list(await self.session.scalars(
                    select(AiGameAssessment.id)
                    .where(AiGameAssessment.batch_id == bundle.batch.id)
                    .order_by(AiGameAssessment.id)
                ))
                return {"batch_id": existing.id, "assessment_ids": ids, "inserted": False}

            # Check every relation before appending any batch data. A savepoint
            # also rolls back newly registered rule/weight versions on failure.
            identities = set()
            for assessment in bundle.batch.assessments:
                if await self.session.get(CatalogProject, assessment.game_id) is None:
                    raise ValueError(f"unknown catalog game ID: {assessment.game_id}")
                identity = assessment_identity(
                    assessment.game_id, assessment.rule_version,
                    assessment.game_version, assessment.snapshot_key,
                )
                if identity in identities:
                    raise ValueError("duplicate game/rule/snapshot in batch")
                identities.add(identity)
                if assessment.supersedes_id is not None:
                    previous = await self.session.get(AiGameAssessment, assessment.supersedes_id)
                    if previous is None or previous.game_id != assessment.game_id:
                        raise ValueError("superseded assessment must exist and belong to this game")
                    if (
                        previous.evaluated_at is not None and assessment.evaluated_at is not None
                        and as_utc_datetime(previous.evaluated_at) > assessment.evaluated_at
                    ):
                        raise ValueError("reassessment cannot predate its source assessment")

            self.session.add(AiRatingBatch(
                id=bundle.batch.id, evaluator_kind="ai",
                evaluator_identity=batch_data["evaluator_identity"],
                source_kind=bundle.batch.source_kind,
                source_reference=bundle.batch.source_reference,
                source_metadata=batch_data["source_metadata"],
                recorded_at=as_utc_datetime(bundle.batch.recorded_at), payload_digest=batch_digest,
            ))
            await self.session.flush()
            assessment_ids = []
            for assessment in bundle.batch.assessments:
                assessment_id = str(uuid4())
                assessment_ids.append(assessment_id)
                data = assessment.model_dump(mode="json")
                self.session.add(AiGameAssessment(
                    id=assessment_id, batch_id=bundle.batch.id,
                    game_id=assessment.game_id, rule_version=assessment.rule_version,
                    identity_key=assessment_identity(
                        assessment.game_id, assessment.rule_version,
                        assessment.game_version, assessment.snapshot_key,
                    ),
                    game_version=assessment.game_version, snapshot_key=assessment.snapshot_key,
                    evaluated_at=(
                        as_utc_datetime(assessment.evaluated_at)
                        if assessment.evaluated_at is not None else None
                    ),
                    reported_review_date=assessment.reported_review_date,
                    reported_timezone=assessment.reported_timezone,
                    environment=data["environment"], play_scope=data["play_scope"],
                    evidence=data["evidence"], limitations=data["limitations"],
                    payload_digest=_digest(data), supersedes_id=assessment.supersedes_id,
                ))
                await self.session.flush()
                self.session.add_all([
                    AiAssessmentDimension(
                        assessment_id=assessment_id, dimension_key=dimension.dimension_key,
                        score=dimension.score,
                        evidence=dimension.model_dump(mode="json")["evidence"],
                    )
                    for dimension in assessment.dimensions
                ])
            await self.session.flush()
            return {
                "batch_id": bundle.batch.id, "assessment_ids": sorted(assessment_ids),
                "inserted": True,
            }

    async def find_assessments_for_identity(
        self, game_id: str, rule_version: str, game_version: str | None,
        snapshot_key: str | None,
    ) -> list[AiGameAssessment]:
        """Read prior observations for work assignment; preserve every historical batch."""

        identity = assessment_identity(game_id, rule_version, game_version, snapshot_key)
        return list(await self.session.scalars(select(AiGameAssessment).where(
            AiGameAssessment.game_id == game_id, AiGameAssessment.rule_version == rule_version,
            AiGameAssessment.identity_key == identity,
        ).order_by(AiGameAssessment.evaluated_at.desc(), AiGameAssessment.id.desc())))

    async def _load_scheme(self, weight_version: str) -> tuple[AiRuleInput, AiWeightSchemeInput]:
        scheme = await self.session.get(AiRatingWeightScheme, weight_version)
        if scheme is None:
            raise ValueError("unknown weight version")
        rule = await self.session.get(AiRatingRule, scheme.rule_version)
        if rule is None:
            raise ValueError("unknown dimension rule version")
        return (
            AiRuleInput(version=rule.version, dimensions=rule.dimensions),
            AiWeightSchemeInput(
                version=scheme.version, rule_version=scheme.rule_version, weights=scheme.weights
            ),
        )

    async def total_for_assessment(self, assessment_id: str, weight_version: str) -> Decimal | None:
        rule, scheme = await self._load_scheme(weight_version)
        assessment = await self.session.get(AiGameAssessment, assessment_id)
        if assessment is None or assessment.rule_version != rule.version:
            raise ValueError("assessment is missing or uses different dimension definitions")
        rows = list(await self.session.scalars(select(AiAssessmentDimension).where(
            AiAssessmentDimension.assessment_id == assessment_id
        )))
        return calculate_total(rule, scheme, {row.dimension_key: row.score for row in rows})

    async def list_ranking(
        self, weight_version: str, *, limit: int = 50, offset: int = 0
    ) -> list[dict[str, object]]:
        """Future backend entry only. Nothing is added to public UI/API/recommendations."""

        if not 1 <= limit <= 500 or offset < 0:
            raise ValueError("invalid ranking pagination")
        rule, scheme = await self._load_scheme(weight_version)
        result = await self.session.execute(ai_ranking_statement(
            rule, scheme, limit=limit, offset=offset
        ))
        return [{
            "game_id": row.game_id, "assessment_id": row.assessment_id,
            "ai_score": row.ai_score, "rule_version": rule.version,
            "weight_version": weight_version, "label": AI_RATING_LABEL,
            "source_kind": row.source_kind, "source_reference": row.source_reference,
            "source_metadata": row.source_metadata,
        } for row in result]

    async def add_human_review(self, review: AiHumanReviewInput) -> AiAssessmentHumanReview:
        """Append an attributable review without rewriting the AI score or identity."""

        assessment = await self.session.get(AiGameAssessment, review.assessment_id)
        if assessment is None:
            raise ValueError("unknown assessment")
        if (
            assessment.evaluated_at is not None
            and review.reviewed_at < as_utc_datetime(assessment.evaluated_at)
        ):
            raise ValueError("human review cannot predate the assessment")
        existing = await self.session.get(AiAssessmentHumanReview, review.id)
        if existing is not None:
            persisted = AiHumanReviewInput(
                id=existing.id, assessment_id=existing.assessment_id,
                reviewer_identity=existing.reviewer_identity,
                reviewed_at=as_utc_datetime(existing.reviewed_at), verdict=existing.verdict,
                notes=existing.notes, evidence=existing.evidence,
            )
            if persisted != review:
                raise ValueError("review ID already exists with different content")
            return existing
        row = AiAssessmentHumanReview(
            **review.model_dump(exclude={"evidence", "reviewed_at"}),
            reviewed_at=as_utc_datetime(review.reviewed_at),
            evidence=review.model_dump(mode="json")["evidence"],
        )
        self.session.add(row)
        await self.session.flush()
        return row

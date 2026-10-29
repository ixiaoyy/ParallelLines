"""Internal AI ranking query, deliberately not connected to the public catalog."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import BigInteger, Numeric, and_, case, cast, func, literal, select

from app.models.catalog import CatalogCategory, CatalogProject
from app.models.catalog_ai_rating import AiAssessmentDimension, AiGameAssessment, AiRatingBatch
from app.schemas.catalog_ai_ratings import (
    SCORE_DECIMAL_PLACES,
    TOTAL_DECIMAL_PLACES,
    WEIGHT_DECIMAL_PLACES,
    WEIGHT_TOTAL,
    AiRuleInput,
    AiWeightSchemeInput,
)


def ai_ranking_statement(
    rule: AiRuleInput, scheme: AiWeightSchemeInput, *, limit: int = 50, offset: int = 0
):
    """Rank visible games by latest assessment, AI score descending, null last.

    The caller must load a compatible immutable rule/scheme. An incomplete latest
    assessment stays null instead of falling back to a better historical score.
    Ranking is provisional: the selected assessment's snapshot must be reviewed
    before any future public exposure. No player score or view count is used.
    """

    if (
        scheme.rule_version != rule.version
        or set(scheme.weights) != {dimension.key for dimension in rule.dimensions}
        or sum(scheme.weights.values(), Decimal(0)) != WEIGHT_TOTAL
    ):
        raise ValueError("ranking requires a compatible complete weight scheme summing to 1")

    latest = select(
        AiGameAssessment.id.label("assessment_id"),
        AiGameAssessment.game_id,
        AiRatingBatch.source_kind,
        AiRatingBatch.source_reference,
        AiRatingBatch.source_metadata,
        func.row_number().over(
            partition_by=AiGameAssessment.game_id,
            order_by=(
                func.coalesce(
                    func.date(AiGameAssessment.evaluated_at), AiGameAssessment.reported_review_date
                ).desc(),
                AiGameAssessment.evaluated_at.desc(),
                AiGameAssessment.created_at.desc(),
                AiGameAssessment.id.desc(),
            ),
        ).label("position"),
    ).join(AiRatingBatch, AiRatingBatch.id == AiGameAssessment.batch_id).where(
        AiGameAssessment.rule_version == rule.version
    ).subquery("latest_ai_assessments")

    present = []
    # Scale from the import contract, not from the default 40/30/15/10/5 scheme.
    # SQLite NUMERIC affinity otherwise makes a 9.95 HALF_UP tie become 9.9.
    score_factor = 10 ** SCORE_DECIMAL_PLACES
    weight_factor = 10 ** WEIGHT_DECIMAL_PLACES
    rounding_divisor = score_factor * weight_factor // (10 ** TOTAL_DECIMAL_PLACES)
    weighted_units = literal(0, type_=BigInteger)
    for definition in rule.dimensions:
        value = func.max(case(
            (AiAssessmentDimension.dimension_key == definition.key, AiAssessmentDimension.score),
            else_=None,
        ))
        weight = scheme.weights[definition.key]
        if definition.required or weight > 0:
            present.append(value.is_not(None))
        if weight > 0:
            score_units = cast(func.round(value * score_factor, 0), BigInteger)
            weighted_units = weighted_units + score_units * int(weight * weight_factor)

    rounded_units = func.floor((weighted_units + rounding_divisor // 2) / rounding_divisor)
    rounded_total = cast(
        rounded_units * Decimal(1).scaleb(-TOTAL_DECIMAL_PLACES),
        Numeric(TOTAL_DECIMAL_PLACES + 2, TOTAL_DECIMAL_PLACES),
    )

    totals = select(
        AiAssessmentDimension.assessment_id,
        case(
            (and_(*present), rounded_total),
            else_=None,
        ).label("ai_score"),
    ).group_by(AiAssessmentDimension.assessment_id).subquery("ai_totals")

    return (
        select(
            CatalogProject.id.label("game_id"), latest.c.assessment_id, totals.c.ai_score,
            latest.c.source_kind, latest.c.source_reference, latest.c.source_metadata,
        )
        .join(CatalogCategory, CatalogCategory.id == CatalogProject.category_id)
        .outerjoin(latest, and_(latest.c.game_id == CatalogProject.id, latest.c.position == 1))
        .outerjoin(totals, totals.c.assessment_id == latest.c.assessment_id)
        .where(CatalogProject.is_visible.is_(True), CatalogCategory.is_visible.is_(True))
        .order_by(totals.c.ai_score.is_(None), totals.c.ai_score.desc(), CatalogProject.id.asc())
        .limit(limit)
        .offset(offset)
    )

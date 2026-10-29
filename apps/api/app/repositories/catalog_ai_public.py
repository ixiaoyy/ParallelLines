"""Batched read projection for public AI rating summaries."""

from sqlalchemy import func, select

from app.models.catalog_ai_rating import AiGameAssessment, AiRatingBatch


def latest_public_assessments_statement(game_ids: list[str], rule_version: str):
    """Select each requested game's newest observation under one definition rule.

    Select only display fields: source references, evaluator identities and raw
    evidence never enter the public projection. An incomplete newest assessment
    remains selected instead of falling back to an older, higher score.
    """

    latest = select(
        AiGameAssessment.id,
        func.row_number().over(
            partition_by=AiGameAssessment.game_id,
            order_by=(
                func.coalesce(
                    func.date(AiGameAssessment.evaluated_at), AiGameAssessment.reported_review_date,
                ).desc(),
                AiGameAssessment.evaluated_at.desc(),
                AiGameAssessment.created_at.desc(),
                AiGameAssessment.id.desc(),
            ),
        ).label("position"),
    ).where(
        AiGameAssessment.game_id.in_(game_ids),
        AiGameAssessment.rule_version == rule_version,
    ).subquery("latest_public_ai_assessments")

    return select(
        AiGameAssessment.id.label("assessment_id"),
        AiGameAssessment.game_id,
        AiGameAssessment.evaluated_at,
        AiGameAssessment.reported_review_date,
        AiGameAssessment.reported_timezone,
        AiGameAssessment.game_version,
        AiGameAssessment.play_scope,
        AiGameAssessment.limitations,
        AiRatingBatch.source_kind,
    ).join(
        latest, latest.c.id == AiGameAssessment.id,
    ).join(
        AiRatingBatch, AiRatingBatch.id == AiGameAssessment.batch_id,
    ).where(latest.c.position == 1)

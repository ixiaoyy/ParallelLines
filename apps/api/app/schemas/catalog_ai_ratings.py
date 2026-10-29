"""Internal AI assessment import contract. No public catalog response is changed."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    StringConstraints,
    model_validator,
)

SCORE_DECIMAL_PLACES = 2
WEIGHT_DECIMAL_PLACES = 4
TOTAL_DECIMAL_PLACES = 1
WEIGHT_TOTAL = Decimal(1)

Key = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]
Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
Score = Annotated[Decimal, Field(
    ge=0, le=10, max_digits=SCORE_DECIMAL_PLACES + 2, decimal_places=SCORE_DECIMAL_PLACES,
)]
Weight = Annotated[Decimal, Field(
    ge=0, le=1, max_digits=WEIGHT_DECIMAL_PLACES + 1, decimal_places=WEIGHT_DECIMAL_PLACES,
)]


class ImportModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class DimensionDefinition(ImportModel):
    key: Key
    label: Text
    definition: Text
    required: bool = True


class AiRuleInput(ImportModel):
    version: Key
    dimensions: list[DimensionDefinition] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_dimensions(self) -> AiRuleInput:
        keys = [dimension.key for dimension in self.dimensions]
        if len(set(keys)) != len(keys):
            raise ValueError("duplicate dimension definition")
        return self


class AiWeightSchemeInput(ImportModel):
    version: Key
    rule_version: Key
    weights: dict[Key, Weight] = Field(min_length=1)

    @model_validator(mode="after")
    def complete_weights(self) -> AiWeightSchemeInput:
        if sum(self.weights.values(), Decimal(0)) != WEIGHT_TOTAL:
            raise ValueError("weights must sum to exactly 1; missing items are never normalized")
        return self


class AiEvaluatorIdentity(ImportModel):
    provider: Text
    model: Text
    agent: Text
    run_id: Text


class AiEvidence(ImportModel):
    kind: Text
    note: Text
    reference: str | None = None


class AiDimensionInput(ImportModel):
    dimension_key: Key
    score: Score | None
    evidence: list[AiEvidence] = Field(min_length=1)


class AiAssessmentInput(ImportModel):
    game_id: Annotated[str, StringConstraints(pattern=r"^[1-9][0-9]*$")]
    rule_version: Key
    # null is the only representation of an unknown version. The snapshot is
    # an artifact hash or a fresh observation token, never the constant 'unknown'.
    game_version: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1,
                                                  max_length=200)] | None
    snapshot_key: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1,
                                                  max_length=200)] | None
    evaluated_at: AwareDatetime | None
    reported_review_date: date | None = None
    reported_timezone: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)
    ] | None = None
    environment: dict[str, JsonValue] = Field(min_length=1)
    play_scope: dict[str, JsonValue] = Field(min_length=1)
    evidence: list[AiEvidence] = Field(min_length=1)
    limitations: list[Text]
    dimensions: list[AiDimensionInput]
    supersedes_id: str | None = None

    @model_validator(mode="after")
    def explicit_snapshot_and_unique_dimensions(self) -> AiAssessmentInput:
        placeholders = {"unknown", "latest", "current", "未知", "不详"}
        if self.game_version and self.game_version.casefold() in placeholders:
            raise ValueError("unknown game version must be null")
        if self.game_version is None and (
            self.snapshot_key is None or self.snapshot_key.casefold() in placeholders
        ):
            raise ValueError("unknown version requires an artifact hash or fresh observation token")
        keys = [item.dimension_key for item in self.dimensions]
        if len(keys) != len(set(keys)):
            raise ValueError("duplicate dimension score")
        return self


class AiBatchInput(ImportModel):
    id: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
    evaluator_kind: Literal["ai"] = "ai"
    evaluator_identity: AiEvaluatorIdentity
    source_kind: Literal["independent_ai", "user_accepted_external_ai"] = "independent_ai"
    source_reference: Text | None = None
    source_metadata: dict[str, JsonValue] = Field(default_factory=dict)
    recorded_at: AwareDatetime
    assessments: list[AiAssessmentInput] = Field(min_length=1)

    @model_validator(mode="after")
    def actual_evaluation_dates(self) -> AiBatchInput:
        if self.source_kind == "user_accepted_external_ai" and self.source_reference is None:
            raise ValueError("accepted external AI ratings require a source reference")
        if any(
            item.evaluated_at is not None and item.evaluated_at > self.recorded_at
            for item in self.assessments
        ):
            raise ValueError("evaluation date cannot be after batch recording date")
        for item in self.assessments:
            if item.evaluated_at is None:
                if self.source_kind == "independent_ai":
                    raise ValueError(
                        "independent assessment requires an actual evaluation timestamp"
                    )
                # Accepted external reports may omit both date and timestamp.
                # Keep that absence explicit instead of fabricating review time.
        return self


class AiImportBundle(ImportModel):
    schema_version: Literal[1] = 1
    rule: AiRuleInput
    weight_scheme: AiWeightSchemeInput
    batch: AiBatchInput

    @model_validator(mode="after")
    def compatible_definition_versions(self) -> AiImportBundle:
        if self.weight_scheme.rule_version != self.rule.version or any(
            item.rule_version != self.rule.version for item in self.batch.assessments
        ):
            raise ValueError("bundle must use one explicit dimension definition version")
        keys = {dimension.key for dimension in self.rule.dimensions}
        if set(self.weight_scheme.weights) != keys:
            raise ValueError("weight scheme must explicitly cover every defined dimension")
        if any(
            item.dimension_key not in keys
            for assessment in self.batch.assessments
            for item in assessment.dimensions
        ):
            raise ValueError("score dimension does not belong to this rule version")
        return self


class AiHumanReviewInput(ImportModel):
    id: Annotated[str, StringConstraints(min_length=1, max_length=36)]
    assessment_id: Annotated[str, StringConstraints(min_length=1, max_length=36)]
    reviewer_identity: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1,
                                                       max_length=200)]
    reviewed_at: AwareDatetime
    verdict: Literal["confirmed", "needs_reassessment", "rejected"]
    notes: Text
    evidence: list[AiEvidence] = Field(min_length=1)

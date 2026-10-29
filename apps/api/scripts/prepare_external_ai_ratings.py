"""Convert an accepted external AI report package to immutable storage bundles.

This command is offline: it never loads settings, opens a database, or replays a
game. Each source import_key becomes a stable batch so extending a package does
not create duplicate historical assessments for its unchanged existing records.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from decimal import Decimal
from pathlib import Path, PureWindowsPath

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.schemas.catalog_ai_ratings import (  # noqa: E402
    AiImportBundle,
    AiRuleInput,
    AiWeightSchemeInput,
)
from app.services.catalog_ai_ratings import calculate_total  # noqa: E402

DIMENSIONS = (
    ("visible_system_complexity", "可见制作/系统复杂度"),
    ("content_depth_scope", "内容深度体量"),
    ("gameplay", "玩法体验"),
    ("controls_completion", "操作与完成度"),
    ("visual", "视听表现（本次仅视觉）"),
)


def _object(value: object, name: str) -> dict:
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be an object")
    return value


def _text(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a nonempty string")
    return value.strip()


def _reported_object(value: object, missing: str) -> dict:
    if value is None:
        return {"reported_description": None}
    if isinstance(value, dict) and value:
        return value
    return {"reported_description": value if isinstance(value, str) and value else missing}


def _canonical_review(review: dict) -> dict:
    """Normalize an equivalent reason wrapper without changing assessment meaning.

    Some package revisions move the same reason object to source_reason_metadata
    while exposing its text as reported_reason. Restore that object so a growing
    package does not create a conflicting batch for an unchanged observation.
    The exact outer package bytes are retained by the manifest's SHA256 reference.
    """

    canonical = dict(review)
    dimension_rows = review.get("dimension_scores")
    if not isinstance(dimension_rows, list):
        raise ValueError("dimension_scores must be a list")
    canonical_rows = []
    for value in dimension_rows:
        row = dict(_object(value, "dimension score"))
        metadata = row.get("source_reason_metadata")
        if metadata is not None:
            if not isinstance(metadata, dict) or metadata.get("reported_reason") != row.get(
                "reported_reason"
            ):
                raise ValueError("source reason text conflicts with its retained metadata")
            row["reported_reason"] = metadata
            del row["source_reason_metadata"]
        canonical_rows.append(row)
    canonical["dimension_scores"] = canonical_rows
    return canonical


def prepare_bundles(document: dict) -> list[AiImportBundle]:
    """Validate IDs/duplicates/arithmetic and preserve source claims without upgrading them."""

    if document.get("status") != "approved_for_import":
        raise ValueError("source package must record user-accepted external AI ratings")
    version = _text(document.get("dimension_definition_version"), "dimension_definition_version")
    weights = _object(document.get("weight_scheme"), "weight_scheme")
    raw_weights = _object(weights.get("weights"), "weight_scheme.weights")
    if set(raw_weights) != {key for key, _label in DIMENSIONS}:
        raise ValueError("unsupported source dimensions; visual is never mapped to audiovisual")
    rule = AiRuleInput(version=version, dimensions=[
        {
            "key": key, "label": label, "required": True,
            "definition": (
                f"用户采纳的外部规则 {version} 中的 {key}；"
                "适用范围保留原报告分项理由和限制，未声称独立验证。"
                + ("此分项仅视觉，音频未评。" if key == "visual" else "")
            ),
        }
        for key, label in DIMENSIONS
    ])
    scheme = AiWeightSchemeInput(
        version=_text(weights.get("version"), "weight_scheme.version"),
        rule_version=version, weights=raw_weights,
    )
    reviews = document.get("reviews")
    if not isinstance(reviews, list) or not reviews:
        raise ValueError("reviews must be a nonempty list")
    if document.get("review_count") != len(reviews):
        raise ValueError("review_count does not match source records")
    source_files = document.get("source_files")
    if not isinstance(source_files, list):
        raise ValueError("source_files must be a list")
    sources = {}
    for value in source_files:
        source = _object(value, "source file")
        source_id = _text(source.get("source_id"), "source_id")
        if source_id in sources:
            raise ValueError("duplicate source_id")
        sources[source_id] = source

    bundles = []
    game_ids = set()
    import_keys = set()
    for value in reviews:
        review = _canonical_review(_object(value, "review"))
        game_id = _text(review.get("game_id"), "game_id")
        if not re.fullmatch(r"[1-9][0-9]*", game_id):
            raise ValueError("invalid catalog game ID")
        if review.get("catalog_project_id") != game_id:
            raise ValueError("game_id must exactly match catalog_project_id")
        import_key = _text(review.get("import_key"), "import_key")
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", import_key):
            raise ValueError("invalid import_key")
        if game_id in game_ids or import_key in import_keys:
            raise ValueError("duplicate game ID or import_key in source package")
        game_ids.add(game_id)
        import_keys.add(import_key)
        if review.get("status") != "approved_for_import":
            raise ValueError("record is not accepted for import")
        if (
            review.get("dimension_definition_version") != rule.version
            or review.get("weight_scheme_version") != scheme.version
            or review.get("rubric_version") != document.get("rubric_version")
        ):
            raise ValueError("record rule/weight versions differ from its package")
        raw_scores = _object(review.get("raw_scores"), "raw_scores")
        if set(raw_scores) != set(raw_weights):
            raise ValueError("raw scores must explicitly contain the source dimensions")
        dimension_rows = review.get("dimension_scores")
        if not isinstance(dimension_rows, list):
            raise ValueError("dimension_scores must be a list")
        rows = {}
        for raw_row in dimension_rows:
            row = _object(raw_row, "dimension score")
            key = _text(row.get("dimension_key"), "dimension_key")
            if key in rows or key not in raw_scores:
                raise ValueError("duplicate or undefined dimension")
            if row.get("dimension_definition_version") != rule.version:
                raise ValueError("dimension definition version differs from source rule")
            if Decimal(str(row.get("weight"))) != scheme.weights[key]:
                raise ValueError("dimension weight differs from source scheme")
            if row.get("raw_score") != raw_scores[key]:
                raise ValueError("dimension score differs from raw_scores")
            rows[key] = row
        if set(rows) != set(raw_scores):
            raise ValueError("dimension rows do not cover raw_scores")
        scores = {key: None if value is None else Decimal(str(value))
                  for key, value in raw_scores.items()}
        total = calculate_total(rule, scheme, scores)
        declared_total = review.get("total_score")
        if (None if declared_total is None else Decimal(str(declared_total))) != total:
            raise ValueError(f"game {game_id}: total_score does not match raw scores and weights")
        unrounded = review.get("unrounded_total")
        if unrounded is not None and all(score is not None for score in scores.values()):
            exact = sum((scores[key] * scheme.weights[key] for key in scores), Decimal(0))
            if Decimal(str(unrounded)) != exact:
                raise ValueError(f"game {game_id}: unrounded_total does not match raw scores")

        source_id = _text(review.get("source_id"), "source_id")
        if source_id not in sources:
            raise ValueError("record refers to an unknown source_id")
        source = sources[source_id]
        source_file_name = PureWindowsPath(
            str(source.get("normalized_source_file", source_id))
        ).name
        reference = f"{source_file_name}#{import_key}"
        reviewer = review.get("reported_reviewer_id") or "unknown"
        limitations = review.get("reported_limitations")
        if limitations is None:
            limitations = []
        if isinstance(limitations, str):
            limitations = [limitations] if limitations.strip() else []
        if not isinstance(limitations, list) or any(
            not isinstance(item, str) for item in limitations
        ):
            raise ValueError("reported_limitations must be a string or a list of strings")
        limitations = list(limitations)
        if review.get("reviewed_at_utc") is None and review.get("reported_review_date") is not None:
            limitations.append("原报告仅提供评测日期，未提供可核验的 UTC 试玩时刻。")
        evidence = [{
            "kind": "user_accepted_external_ai_report",
            "note": "用户已采纳的外部 AI 报告；本次只校验 ID、去重和算术，未重复试玩。",
            "reference": reference,
        }]
        for item in review.get("reported_evidence") or []:
            evidence.append({
                "kind": str(item.get("kind", "reported_evidence")) if isinstance(item, dict)
                else "reported_evidence",
                "note": json.dumps(item, ensure_ascii=False, sort_keys=True),
                "reference": reference,
            })
        assessment = {
            "game_id": game_id, "rule_version": rule.version,
            "game_version": review.get("reported_game_version"),
            "snapshot_key": f"external-report:{import_key}",
            "evaluated_at": review.get("reviewed_at_utc"),
            "reported_review_date": review.get("reported_review_date"),
            "reported_timezone": review.get("reported_timezone"),
            "environment": _reported_object(review.get("reported_environment"), "原报告未说明环境"),
            "play_scope": _reported_object(
                review.get("reported_played_scope"), "原报告未说明试玩范围"
            ),
            "evidence": evidence, "limitations": limitations,
            "dimensions": [{
                "dimension_key": key, "score": raw_scores[key],
                "evidence": [{
                    "kind": (
                        "external_ai_score_provenance" if rows[key].get("reported_reason") is None
                        else "external_ai_dimension_reason"
                    ),
                    "note": (
                        "原报告仅提供该维度分值，未提供评分依据。"
                        if rows[key].get("reported_reason") is None
                        else json.dumps(rows[key]["reported_reason"], ensure_ascii=False,
                                        sort_keys=True)
                    ),
                    "reference": f"{reference}:{key}",
                }],
            } for key, _label in DIMENSIONS],
        }
        bundles.append(AiImportBundle.model_validate({
            "schema_version": 1,
            "rule": rule.model_dump(mode="json"),
            "weight_scheme": scheme.model_dump(mode="json"),
            "batch": {
                "id": import_key, "evaluator_kind": "ai",
                "evaluator_identity": {
                    "provider": review.get("reported_provider") or "unknown",
                    "model": review.get("reported_model") or "unknown",
                    "agent": reviewer, "run_id": review.get("reported_run_id") or "unknown",
                },
                "source_kind": "user_accepted_external_ai", "source_reference": reference,
                "source_metadata": {
                    "source_file": source, "source_record": review,
                    "rubric_version": document.get("rubric_version"),
                    "source_definition_text_available": False,
                    "recomputed_total": str(total) if total is not None else None,
                },
                "recorded_at": review.get("adopted_at_utc") or document.get("created_at_utc"),
                "assessments": [assessment],
            },
        }))
    if document.get("unique_game_count") != len(game_ids):
        raise ValueError("unique_game_count does not match source records")
    return bundles


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    raw = args.input.read_bytes()
    document = _object(json.loads(raw.decode("utf-8")), "source package")
    bundles = prepare_bundles(document)
    pending = {f"{bundle.batch.id}.json": bundle.model_dump_json(indent=2) + "\n"
               for bundle in bundles}
    manifest = {
        "source_package": args.input.name,
        "source_package_sha256": hashlib.sha256(raw).hexdigest(),
        "rule_version": bundles[0].rule.version,
        "weight_version": bundles[0].weight_scheme.version,
        "count": len(bundles), "source_kind": "user_accepted_external_ai",
        "database_write_performed": False, "independent_gameplay_performed": False,
        "bundles": [{"file": name, "batch_id": bundle.batch.id,
                     "game_id": bundle.batch.assessments[0].game_id}
                    for name, bundle in zip(pending, bundles, strict=True)],
    }
    pending["manifest.json"] = json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
    for name, content in pending.items():
        target = args.output_dir / name
        if target.exists() and target.read_text(encoding="utf-8") != content:
            raise FileExistsError(f"refusing to overwrite changed prepared output: {target}")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for name, content in pending.items():
        (args.output_dir / name).write_text(content, encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

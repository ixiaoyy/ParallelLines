"""Validate a review JSON bundle locally; never load settings or connect to a DB."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.schemas.catalog_ai_ratings import AiImportBundle  # noqa: E402
from app.services.catalog_ai_ratings import calculate_total  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path)
    args = parser.parse_args()
    bundle = AiImportBundle.model_validate_json(args.bundle.read_text(encoding="utf-8"))
    print(json.dumps({
        "valid": True,
        "batch_id": bundle.batch.id,
        "rule_version": bundle.rule.version,
        "weight_version": bundle.weight_scheme.version,
        "label": "AI评分",
        "assessments": [{
            "game_id": assessment.game_id,
            "ai_score": (
                str(score) if (score := calculate_total(
                    bundle.rule, bundle.weight_scheme,
                    {item.dimension_key: item.score for item in assessment.dimensions},
                )) is not None else None
            ),
        } for assessment in bundle.batch.assessments],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

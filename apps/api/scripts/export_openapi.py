from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.main import create_app

DEFAULT_OUTPUT = Path(__file__).resolve().parents[1] / "openapi" / "openapi.json"


def stable_openapi_document() -> dict[str, Any]:
    schema = create_app().openapi()
    schema.setdefault("info", {})["x-schema-source"] = "apps/api/scripts/export_openapi.py"
    return json.loads(json.dumps(schema, ensure_ascii=False, sort_keys=True))


def render_schema(schema: dict[str, Any]) -> str:
    return json.dumps(schema, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Export the stable public OpenAPI schema.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check", action="store_true", help="Fail if output is stale.")
    args = parser.parse_args()

    content = render_schema(stable_openapi_document())
    if args.check:
        if not args.output.is_file():
            print(f"OpenAPI snapshot missing: {args.output}", file=sys.stderr)
            return 1
        current = args.output.read_text(encoding="utf-8")
        if current != content:
            print(
                "OpenAPI snapshot is stale. Run: uv run python scripts/export_openapi.py",
                file=sys.stderr,
            )
            return 1
        return 0

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(content, encoding="utf-8")
    print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

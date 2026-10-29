"""Verify a rollback migration overlay without env.py, settings, or a database.

Local mode archives committed legacy API sources into a private temporary
directory under the report folder, adds only 0101, and verifies the revision
graph. Image mode verifies an already assembled /app tree. Neither mode calls a
migration upgrade/downgrade function or opens a database connection.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath

from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory

sys.dont_write_bytecode = True

REVISION = "0101_catalog_ai_ratings"
PARENT_REVISION = "0100_add_yiji_pochao"
MIGRATION_NAME = f"{REVISION}.py"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tree_digest(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*"), key=lambda item: item.relative_to(root).as_posix()):
        if path.is_file():
            digest.update(path.relative_to(root).as_posix().encode("utf-8"))
            digest.update(b"\0")
            digest.update(path.read_bytes())
            digest.update(b"\0")
    return digest.hexdigest()


def git(repository: Path, *args: str) -> bytes:
    return subprocess.run(
        ["git", "-C", str(repository), *args], check=True, capture_output=True,
    ).stdout


def script_directory(api_root: Path) -> ScriptDirectory:
    config = Config()  # Deliberately never read alembic.ini or execute env.py.
    config.set_main_option("script_location", str(api_root / "alembic"))
    return ScriptDirectory.from_config(config)


def verify_graph(api_root: Path, expected_sha256: str) -> dict[str, object]:
    migration = api_root / "alembic" / "versions" / MIGRATION_NAME
    actual_sha256 = sha256_file(migration)
    assert actual_sha256 == expected_sha256, "0101 snapshot hash does not match the reviewed file"
    assert "ck_catalog_ai_assessment_date" not in migration.read_text(encoding="utf-8"), (
        "obsolete date-presence constraint is still in the snapshot"
    )
    # Historical migration modules may import old application constants; no
    # application entry point, settings provider, env.py or engine is invoked.
    sys.path.insert(0, str(api_root))
    try:
        scripts = script_directory(api_root)
        assert scripts.get_heads() == [REVISION], "overlay must have one known head"
        revision = scripts.get_revision(REVISION)
        assert revision.down_revision == PARENT_REVISION
        offline_context = MigrationContext.configure(
            dialect_name="mysql",
            opts={"as_sql": True, "starting_rev": REVISION},
        )
        current_heads = offline_context.get_current_heads()
        assert current_heads == (REVISION,)
        pending = list(scripts.iterate_revisions("head", current_heads))
        assert pending == [], "database already at 0101 must have an empty upgrade plan"
        positive_control = [
            item.revision for item in scripts.iterate_revisions("head", (PARENT_REVISION,))
        ]
        assert positive_control == [REVISION]
        return {
            "migration_sha256": actual_sha256,
            "revision": revision.revision,
            "down_revision": revision.down_revision,
            "heads": scripts.get_heads(),
            "simulated_database_heads": list(current_heads),
            "pending_upgrade_revisions": [item.revision for item in pending],
            "positive_control_0100_to_head": positive_control,
            "obsolete_date_presence_check_absent": True,
            "migration_context_offline": offline_context.as_sql,
            "database_connection_created": False,
            "env_py_executed": False,
            "upgrade_or_downgrade_executed": False,
        }
    finally:
        sys.path.pop(0)


def verify_legacy_overlay(args) -> dict[str, object]:
    repository = args.repository.resolve()
    base_sha = git(repository, "rev-parse", f"{args.base_ref}^{{commit}}").decode().strip()
    source = args.migration_source.resolve()
    assert sha256_file(source) == args.expected_migration_sha256
    archive_bytes = git(
        repository, "archive", "--format=zip", base_sha, "--",
        "apps/api/app", "apps/api/alembic",
    )
    # This location and every extracted path stay under the deliverable report
    # directory. TemporaryDirectory removes only this newly created context.
    output_root = args.report.resolve().parent
    with tempfile.TemporaryDirectory(prefix="_rollback_verify_", dir=output_root) as temporary:
        temporary_root = Path(temporary).resolve()
        assert temporary_root.is_relative_to(output_root)
        with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
            for member in archive.infolist():
                path = PurePosixPath(member.filename)
                assert not path.is_absolute() and ".." not in path.parts
                assert (temporary_root / member.filename).resolve().is_relative_to(temporary_root)
            archive.extractall(temporary_root)
        api_root = temporary_root / "apps" / "api"
        sys.path.insert(0, str(api_root))
        try:
            baseline_heads = script_directory(api_root).get_heads()
        finally:
            sys.path.pop(0)
        assert baseline_heads == [PARENT_REVISION], "legacy source migration head changed"
        app_hash_before = tree_digest(api_root / "app")
        target = api_root / "alembic" / "versions" / MIGRATION_NAME
        assert not target.exists(), "base source already contains the proposed overlay"
        shutil.copyfile(source, target)
        result = verify_graph(api_root, args.expected_migration_sha256)
        app_hash_after = tree_digest(api_root / "app")
        assert app_hash_before == app_hash_after, "overlay changed legacy application code"
        result.update({
            "mode": "committed_legacy_source_plus_0101_overlay",
            "base_commit": base_sha,
            "base_app_git_tree": git(
                repository, "rev-parse", f"{base_sha}:apps/api/app",
            ).decode().strip(),
            "base_alembic_git_tree": git(
                repository, "rev-parse", f"{base_sha}:apps/api/alembic",
            ).decode().strip(),
            "baseline_heads": baseline_heads,
            "legacy_app_sha256_before": app_hash_before,
            "legacy_app_sha256_after": app_hash_after,
            "legacy_application_unchanged": True,
        })
        return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--repository", type=Path)
    mode.add_argument("--api-root", type=Path)
    parser.add_argument("--base-ref")
    parser.add_argument("--migration-source", type=Path)
    parser.add_argument("--expected-migration-sha256", required=True, type=str.lower)
    parser.add_argument("--expected-legacy-app-sha256", type=str.lower)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()
    if not __debug__:
        parser.error("run verification without Python optimization so assertions stay enabled")
    if re.fullmatch(r"[0-9a-f]{64}", args.expected_migration_sha256) is None:
        parser.error("expected migration SHA256 must contain exactly 64 hex characters")
    if args.repository and (not args.base_ref or not args.migration_source):
        parser.error("repository mode requires --base-ref and --migration-source")
    if args.api_root and not args.expected_legacy_app_sha256:
        parser.error("image mode requires the reviewed legacy application SHA256")
    args.report.resolve().parent.mkdir(parents=True, exist_ok=True)
    if args.repository:
        result = verify_legacy_overlay(args)
    else:
        app_sha256 = tree_digest(args.api_root.resolve() / "app")
        assert app_sha256 == args.expected_legacy_app_sha256, "base API code does not match legacy source"
        result = verify_graph(args.api_root.resolve(), args.expected_migration_sha256)
        result["mode"] = "assembled_api_tree_overlay_check"
        result["legacy_app_sha256"] = app_sha256
        result["legacy_application_matches_reviewed_source"] = True
    result["verified_at_utc"] = datetime.now(UTC).isoformat()
    args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

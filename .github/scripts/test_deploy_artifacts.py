"""仅用临时文件核对 CI/Deploy 交接，不访问 GitHub、Docker 或服务器。"""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import deploy_artifacts as artifacts


SHA = "a" * 40
BEFORE = "b" * 40
IMAGE_ID = "sha256:" + "c" * 64
REPOSITORY = "fixture/parallellines"
ROOT = Path(__file__).resolve().parents[2]


class DeployPlanTests(unittest.TestCase):
    def environment(self, **changes):
        return {"GITHUB_SHA": SHA, "GITHUB_REPOSITORY": REPOSITORY,
                "GITHUB_RUN_ID": "42", "GITHUB_EVENT_NAME": "push",
                "GITHUB_REF": "refs/heads/main", "BEFORE_SHA": BEFORE, **changes}

    def test_normal_scope_preserves_original_push_and_check_scope(self):
        plan = artifacts.make_plan(self.environment(
            BACKEND_CHANGED="true", FRONTEND_CHANGED="false", CHECK_FRONTEND="true"))
        self.assertEqual(plan["before"], BEFORE)
        self.assertEqual(plan["scopes"], {
            "backend": True, "frontend": False, "nginx": False, "compose": False})
        self.assertTrue(plan["checks"]["frontend"])
        self.assertEqual(artifacts.validate_plan(plan, SHA, REPOSITORY, "42", "workflow_run"),
                         plan["scopes"])

    def test_unavailable_base_and_manual_dispatch_are_full_scope(self):
        for env in (self.environment(FULL_SCOPE="true", BEFORE_SHA="0" * 40),
                    self.environment(GITHUB_EVENT_NAME="workflow_dispatch", BEFORE_SHA="")):
            with self.subTest(event=env["GITHUB_EVENT_NAME"]):
                plan = artifacts.make_plan(env)
                self.assertTrue(all(plan["scopes"].values()))
                self.assertTrue(all(plan["checks"].values()))
                event = "workflow_run" if env["GITHUB_EVENT_NAME"] == "push" else "workflow_dispatch"
                artifacts.validate_plan(plan, SHA, REPOSITORY, "42", event)

    def test_workflow_only_runs_checks_without_deploying_services(self):
        plan = artifacts.make_plan(self.environment(
            CHECK_BACKEND="true", CHECK_FRONTEND="true", CHECK_WORKFLOW="true"))
        self.assertTrue(all(plan["checks"].values()))
        self.assertFalse(any(plan["scopes"].values()))
        ci = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
        api_filter = ci.split("            api:\n", 1)[1].split("            frontend:\n", 1)[0]
        self.assertIn("'apps/api/**'", api_filter)
        self.assertNotIn("workflows", api_filter)
        self.assertIn("BACKEND_CHANGED: ${{ steps.filter.outputs.api || 'false' }}", ci)

    def test_wrong_source_and_pr_plans_cannot_enter_deployment(self):
        good = artifacts.make_plan(self.environment())
        for field, value in (("revision", BEFORE), ("repository", "other/repo"),
                             ("run_id", "43"), ("event", "pull_request"),
                             ("ref", "refs/heads/feature"), ("schema", 2)):
            plan = {**good, field: value}
            with self.subTest(field=field), self.assertRaises(ValueError):
                artifacts.validate_plan(plan, SHA, REPOSITORY, "42", "workflow_run")

    def test_missing_scope_and_string_boolean_are_rejected(self):
        good = artifacts.make_plan(self.environment())
        for scopes in ({"backend": True}, {**good["scopes"], "frontend": "true"}):
            with self.subTest(scopes=scopes), self.assertRaises(ValueError):
                artifacts.validate_plan({**good, "scopes": scopes}, SHA, REPOSITORY, "42", "workflow_run")

    def test_rejects_values_that_could_change_output_or_filename(self):
        for value in ("main", "a" * 39, "a" * 40 + "\n", "../image", "$(touch x)"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                artifacts.revision(value)
        with self.assertRaises(ValueError):
            artifacts.flag("yes")

    def test_cli_plan_and_read_emit_the_actual_workflow_outputs(self):
        with tempfile.TemporaryDirectory() as directory:
            plan = Path(directory) / "plan.json"
            created = Path(directory) / "created.txt"
            consumed = Path(directory) / "consumed.txt"
            env = {**os.environ, **self.environment(FULL_SCOPE="false", FRONTEND_CHANGED="true")}
            script = str(ROOT / ".github/scripts/deploy_artifacts.py")
            subprocess.run([sys.executable, script, "plan", "--output", str(plan),
                            "--github-output", str(created)], env=env, check=True, timeout=10)
            env.update(GITHUB_EVENT_NAME="workflow_run", DEPLOY_SHA=SHA, SOURCE_RUN_ID="42")
            subprocess.run([sys.executable, script, "read-plan", "--source", str(plan),
                            "--github-output", str(consumed)], env=env, check=True, timeout=10)
            values = dict(line.split("=", 1) for line in consumed.read_text().splitlines())
            self.assertEqual(values["sha"], SHA)
            self.assertEqual(values["source_run_id"], "42")
            self.assertEqual(values["web_required"], "true")
            self.assertEqual(values["backend"], "false")


class WebArtifactTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.directory = Path(self.temporary.name)
        self.archive = self.directory / artifacts.archive_name(SHA)
        self.archive.write_bytes(b"synthetic image archive for integrity tests")
        artifacts.write_receipt(self.directory, SHA, IMAGE_ID, SHA, "42")

    def tearDown(self):
        self.temporary.cleanup()

    def test_receipt_round_trip_and_wrong_commit_or_run(self):
        artifacts.verify_web(self.directory, SHA, "42")
        with self.assertRaises(ValueError):
            artifacts.verify_web(self.directory, SHA, "43")
        receipt = self.directory / "web-image.json"
        value = json.loads(receipt.read_text())
        value["revision"] = BEFORE
        receipt.write_text(json.dumps(value))
        with self.assertRaises(ValueError):
            artifacts.verify_web(self.directory, SHA, "42")

    def test_changed_archive_is_rejected(self):
        self.archive.write_bytes(b"corrupted")
        with self.assertRaisesRegex(ValueError, "archive_changed"):
            artifacts.verify_web(self.directory, SHA, "42")

    def test_changed_sidecars_and_missing_artifacts_fail(self):
        for name in (self.archive.name + ".sha256", f"parallellines-web-{SHA}.image-id"):
            with self.subTest(name=name):
                path = self.directory / name
                saved = path.read_bytes()
                path.write_bytes(b"wrong")
                with self.assertRaises(ValueError):
                    artifacts.verify_web(self.directory, SHA, "42")
                path.write_bytes(saved)
        self.archive.unlink()
        with self.assertRaises(FileNotFoundError):
            artifacts.verify_web(self.directory, SHA, "42")

    def test_built_image_revision_must_match(self):
        with self.assertRaises(ValueError):
            artifacts.write_receipt(self.directory, SHA, IMAGE_ID, BEFORE, "42")

    def test_context_contains_only_checked_dist_and_config(self):
        source = self.directory / "source"
        (source / "dist/assets").mkdir(parents=True)
        (source / "dist/index.html").write_text("checked build")
        (source / "dist/assets/entry.js").write_text("checked script")
        (source / "nginx.conf").write_text("checked nginx")
        (source / ".env").write_text("not a build input")
        destination = self.directory / "runtime-context"
        artifacts.prepare_context(source / "dist", source / "nginx.conf", destination)
        files = sorted(p.relative_to(destination).as_posix() for p in destination.rglob("*") if p.is_file())
        self.assertEqual(files, ["dist/assets/entry.js", "dist/index.html", "nginx.conf"])
        with self.assertRaises(FileExistsError):
            artifacts.prepare_context(source / "dist", source / "nginx.conf", destination)


class WorkflowWiringTests(unittest.TestCase):
    def test_automatic_deploy_uses_only_matching_successful_main_push(self):
        deploy = (ROOT / ".github/workflows/deploy.yml").read_text(encoding="utf-8")
        for guard in ("github.event.workflow_run.conclusion == 'success'",
                      "github.event.workflow_run.event == 'push'",
                      "github.event.workflow_run.head_branch == 'main'",
                      "github.event.workflow_run.head_repository.full_name == github.repository"):
            self.assertIn(guard, deploy)
        self.assertIn("run-id: ${{ env.SOURCE_RUN_ID }}", deploy)
        self.assertIn('CURRENT" != "$DEPLOY_SHA', deploy)
        self.assertIn("cancel-in-progress: false", deploy)
        self.assertNotIn("git reset --hard origin/main", deploy)
        self.assertEqual(deploy.count('git reset --hard "$DEPLOY_REVISION"'), 4)
        for job in ("deploy-frontend", "deploy-nginx"):
            condition = deploy.split(f"  {job}:\n", 1)[1].split("    steps:\n", 1)[0]
            self.assertIn("needs.changes.result == 'success'", condition)

    def test_ci_packages_same_dist_and_manual_build_remains_explicit(self):
        ci = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
        deploy = (ROOT / ".github/workflows/deploy.yml").read_text(encoding="utf-8")
        self.assertEqual(ci.count("run: pnpm --dir apps/web build"), 1)
        self.assertIn("file: apps/web/Dockerfile.prebuilt", ci)
        self.assertIn("VITE_API_BASE_URL: /api/v1", ci)
        self.assertIn("pnpm-workspace.yaml", ci)
        self.assertEqual(ci.count("overwrite: true"), 2)
        self.assertEqual(deploy.count("overwrite: true"), 1)
        self.assertEqual(deploy.count("uses: docker/build-push-action@v6"), 1)
        manual = deploy.split("- name: Build Web once for an explicit manual deployment", 1)[1].split("- name:", 1)[0]
        self.assertIn("github.event_name == 'workflow_dispatch'", manual)
        runtime = (ROOT / "apps/web/Dockerfile.prebuilt").read_text(encoding="utf-8")
        self.assertNotIn("RUN ", runtime)
        self.assertIn("COPY dist/", runtime)


if __name__ == "__main__":
    unittest.main()

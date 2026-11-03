"""仅用临时文件核对 CI/Deploy 交接，不访问 GitHub、Docker 或服务器。"""

import copy
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest import mock

import deploy_artifacts as artifacts


SHA = "a" * 40
BEFORE = "b" * 40
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


def raw_json(value):
    # 保留非紧凑格式，确保被测摘要来自原始 bytes，不是重新序列化后的 JSON。
    return (json.dumps(value, indent=1) + "\n").encode("utf-8")


def digest(value):
    return "sha256:" + hashlib.sha256(value).hexdigest()


def layer_bytes(value):
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode="w") as layer:
        member = tarfile.TarInfo("fixture.txt")
        member.size = len(value)
        layer.addfile(member, io.BytesIO(value))
    return stream.getvalue()


LAYERS = [layer_bytes(b"first public layer"), layer_bytes(b"second public layer")]
DIFF_IDS = [digest(layer) for layer in LAYERS]


def image_config(**changes):
    return {"os": "linux", "architecture": "amd64",
            "config": {"Labels": {artifacts.REVISION_LABEL: SHA}},
            "rootfs": {"type": "layers", "diff_ids": DIFF_IDS}, **changes}


def make_archive(path, config=None, tags=None, legacy=False, duplicate=False,
                 missing_layer=False, wrong_config_path=False):
    config_raw = raw_json(config if config is not None else image_config())
    config_digest = digest(config_raw)
    name = config_digest[7:] + ".json" if legacy else "blobs/sha256/" + config_digest[7:]
    if wrong_config_path:
        name = "blobs/sha256/" + "d" * 64
    layer_names = [f"blobs/sha256/{value[7:]}" for value in DIFF_IDS]
    entries = {"manifest.json": raw_json([{
        "Config": name, "RepoTags": tags if tags is not None else [
            f"parallellines-web:{SHA}", "parallellines-web:latest"], "Layers": layer_names}]),
        name: config_raw, **dict(zip(layer_names, LAYERS))}
    if missing_layer:
        del entries[layer_names[-1]]
    with tarfile.open(path, "w:gz") as bundle:
        for key, value in entries.items():
            member = tarfile.TarInfo(key)
            member.size = len(value)
            bundle.addfile(member, io.BytesIO(value))
        if duplicate:
            member = tarfile.TarInfo("manifest.json")
            member.size = len(entries["manifest.json"])
            bundle.addfile(member, io.BytesIO(entries["manifest.json"]))
    return config_digest


class WebArtifactTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.directory = Path(self.temporary.name)
        self.archive = self.directory / artifacts.archive_name(SHA)
        self.config_digest = make_archive(self.archive)
        self.native_id = "sha256:" + "c" * 64
        artifacts.write_receipt(self.directory, SHA, self.native_id, SHA, "42")

    def tearDown(self):
        self.temporary.cleanup()

    def test_receipt_round_trip_keeps_native_id_distinct_from_raw_config_digest(self):
        artifacts.verify_web(self.directory, SHA, "42")
        value = json.loads((self.directory / "web-image.json").read_text())
        self.assertEqual(value["schema"], 2)
        self.assertEqual(value["image_id"], self.native_id)
        self.assertEqual(value["image_config_digest"], self.config_digest)
        self.assertNotEqual(value["image_id"], value["image_config_digest"])
        self.assertNotEqual(self.config_digest, digest(json.dumps(image_config()).encode()))
        self.assertEqual(value["rootfs_diff_ids"], DIFF_IDS)
        for field, wrong in (("revision", BEFORE), ("run_id", "43"), ("schema", 1),
                             ("image_config_digest", self.native_id),
                             ("rootfs_diff_ids", list(reversed(DIFF_IDS)))):
            with self.subTest(field=field):
                original = json.loads((self.directory / "web-image.json").read_text())
                (self.directory / "web-image.json").write_text(json.dumps({**original, field: wrong}))
                with self.assertRaises(ValueError):
                    artifacts.verify_web(self.directory, SHA, "42")
                (self.directory / "web-image.json").write_text(json.dumps(original))

    def test_changed_archive_is_rejected(self):
        self.archive.write_bytes(b"corrupted")
        with self.assertRaisesRegex(ValueError, "archive_changed"):
            artifacts.verify_web(self.directory, SHA, "42")

    def test_changed_sidecars_and_missing_artifacts_fail(self):
        for name in (self.archive.name + ".sha256", f"parallellines-web-{SHA}.image-id",
                     f"parallellines-web-{SHA}.image-config-digest"):
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

    def test_built_image_revision_and_config_revision_must_match(self):
        with self.assertRaisesRegex(ValueError, "built_image_revision"):
            artifacts.write_receipt(self.directory, SHA, self.native_id, BEFORE, "42")
        make_archive(self.archive, config=image_config(config={"Labels": {artifacts.REVISION_LABEL: BEFORE}}))
        with self.assertRaisesRegex(ValueError, "image_revision"):
            artifacts.write_receipt(self.directory, SHA, self.native_id, SHA, "42")

    def test_real_legacy_save_config_layout_is_also_supported(self):
        make_archive(self.archive, legacy=True)
        self.assertEqual(artifacts.archive_identity(self.archive, SHA)["image_config_digest"],
                         self.config_digest)

    def test_archive_rejects_wrong_alias_platform_duplicate_and_missing_layer(self):
        for options in ({"tags": [f"parallellines-web:{SHA}"]},
                        {"config": image_config(architecture="arm64")},
                        {"duplicate": True}, {"missing_layer": True}, {"wrong_config_path": True}):
            with self.subTest(options=options):
                make_archive(self.archive, **options)
                with self.assertRaises((ValueError, KeyError)):
                    artifacts.archive_identity(self.archive, SHA)

    def test_archive_identity_cli_only_reads_the_existing_archive(self):
        result = subprocess.run([sys.executable, str(ROOT / ".github/scripts/deploy_artifacts.py"),
                                 "archive-identity", "--archive", str(self.archive), "--sha", SHA],
                                check=True, capture_output=True, text=True, timeout=10)
        self.assertEqual(json.loads(result.stdout)["image_config_digest"], self.config_digest)

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


class LoadedFixture:
    def __init__(self, config=None, classic=False):
        self.config_raw = raw_json(config if config is not None else image_config())
        self.config_digest = digest(self.config_raw)
        self.manifest = {"schemaVersion": 2, "mediaType": "application/vnd.oci.image.manifest.v1+json",
                         "config": {"mediaType": "application/vnd.oci.image.config.v1+json",
                                    "digest": self.config_digest, "size": len(self.config_raw)},
                         "layers": [{"mediaType": "application/vnd.oci.image.layer.v1.tar",
                                     "digest": digest(layer), "size": len(layer)} for layer in LAYERS]}
        self.classic = classic
        self.calls = []
        self.rebuild_manifest()

    def rebuild_manifest(self):
        self.manifest_raw = raw_json(self.manifest)
        self.native_id = self.config_digest if self.classic else digest(self.manifest_raw)
        descriptor = None if self.classic else {"digest": self.native_id,
                                               "mediaType": self.manifest["mediaType"],
                                               "size": len(self.manifest_raw)}
        record = {"id": self.native_id, "descriptor": descriptor, "os": "linux", "architecture": "amd64",
                  "variant": "", "revision": SHA, "rootfs": {"Type": "layers", "Layers": DIFF_IDS}}
        self.records = [copy.deepcopy(record), copy.deepcopy(record)]
        self.blobs = {self.native_id: self.manifest_raw, self.config_digest: self.config_raw}

    def run(self, command):
        self.calls.append(command)
        if command[:3] == ["docker", "image", "inspect"]:
            self.assert_public_template(command[4])
            return b"\n".join(raw_json(record).replace(b"\n", b"") for record in self.records)
        if command[:2] == ["docker", "info"]:
            return raw_json({"Address": "/run/fixture/containerd.sock", "Namespaces": {"Containers": "fixture"}})
        if command[:7] == ["fixture-ctr", "--address", "/run/fixture/containerd.sock", "--namespace",
                           "fixture", "content", "get"]:
            return self.blobs[command[-1]]
        raise AssertionError(command)

    @staticmethod
    def assert_public_template(template):
        if ".Env" in template or "{{json .}}" in template:
            raise AssertionError("must not read full private image configuration")


class LoadedImageTests(unittest.TestCase):
    def verify(self, fixture, identity=None):
        with mock.patch.object(artifacts.shutil, "which", return_value="fixture-ctr"):
            return artifacts.verify_loaded(SHA, fixture.config_digest, identity, run=fixture.run)

    def test_classic_native_config_identity_needs_no_ctr_or_info(self):
        fixture = LoadedFixture(classic=True)
        with mock.patch.object(artifacts.shutil, "which", side_effect=AssertionError("ctr must not be required")):
            result = artifacts.verify_loaded(SHA, fixture.config_digest, run=fixture.run)
        self.assertEqual(result["store"], "classic")
        self.assertEqual(len(fixture.calls), 1)
        fixture.records[0]["id"] = fixture.records[1]["id"] = "sha256:" + "f" * 64
        with self.assertRaisesRegex(ValueError, "classic_image_config"):
            self.verify(fixture)

    def test_containerd_different_native_id_validates_raw_manifest_config_and_rootfs(self):
        fixture = LoadedFixture()
        result = self.verify(fixture)
        self.assertEqual(result["store"], "containerd")
        self.assertNotEqual(result["native_image_id"], result["image_config_digest"])
        self.assertEqual(result["rootfs_diff_ids"], DIFF_IDS)
        self.assertEqual(len(fixture.calls), 4)
        self.assertEqual([call[-1] for call in fixture.calls[-2:]],
                         [fixture.native_id, fixture.config_digest])

    def test_docker_v2_single_manifest_is_supported_without_oci_only_assumption(self):
        fixture = LoadedFixture()
        fixture.manifest["mediaType"] = "application/vnd.docker.distribution.manifest.v2+json"
        fixture.manifest["config"]["mediaType"] = "application/vnd.docker.container.image.v1+json"
        fixture.rebuild_manifest()
        self.assertEqual(self.verify(fixture)["store"], "containerd")

    def test_alias_native_or_public_metadata_mismatch_fails(self):
        for field, value in (("id", "sha256:" + "d" * 64), ("revision", BEFORE),
                             ("architecture", "arm64"),
                             ("rootfs", {"Type": "layers", "Layers": list(reversed(DIFF_IDS))})):
            fixture = LoadedFixture()
            fixture.records[1][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.verify(fixture)

    def test_receipt_rootfs_and_config_identity_are_enforced(self):
        fixture = LoadedFixture()
        expected = {"image_config_digest": fixture.config_digest,
                    **artifacts.config_identity(image_config(), SHA)}
        self.verify(fixture, expected)
        for field, value in (("rootfs_diff_ids", list(reversed(DIFF_IDS))),
                             ("image_config_digest", "sha256:" + "e" * 64)):
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, "receipt_metadata"):
                self.verify(fixture, {**expected, field: value})

    def test_raw_manifest_and_config_corruption_cannot_pass_on_label_alone(self):
        for target in ("manifest", "config"):
            fixture = LoadedFixture()
            key = fixture.native_id if target == "manifest" else fixture.config_digest
            fixture.blobs[key] = fixture.blobs[key].replace(b"linux", b"linuz") if target == "config" else b"x" * len(fixture.manifest_raw)
            with self.subTest(target=target), self.assertRaisesRegex(ValueError, "blob_digest_or_size"):
                self.verify(fixture)

    def test_valid_manifest_pointing_to_other_config_is_rejected(self):
        fixture = LoadedFixture()
        fixture.manifest["config"]["digest"] = "sha256:" + "e" * 64
        fixture.rebuild_manifest()
        with self.assertRaisesRegex(ValueError, "manifest_config"):
            self.verify(fixture)

    def test_raw_config_platform_revision_rootfs_and_manifest_layer_count_are_checked(self):
        for config in (image_config(architecture="arm64"),
                       image_config(config={"Labels": {artifacts.REVISION_LABEL: BEFORE}}),
                       image_config(rootfs={"type": "layers", "diff_ids": list(reversed(DIFF_IDS))})):
            fixture = LoadedFixture(config=config)
            with self.subTest(config=config), self.assertRaises(ValueError):
                self.verify(fixture)
        fixture = LoadedFixture()
        fixture.manifest["layers"] = fixture.manifest["layers"][:-1]
        fixture.rebuild_manifest()
        with self.assertRaisesRegex(ValueError, "config_rootfs"):
            self.verify(fixture)
        fixture = LoadedFixture()
        fixture.manifest["layers"][0]["digest"] = "not-a-digest"
        fixture.rebuild_manifest()
        with self.assertRaisesRegex(ValueError, "invalid_content_digest"):
            self.verify(fixture)

    def test_index_descriptor_ambiguity_and_missing_ctr_fail_without_fallback(self):
        fixture = LoadedFixture()
        for record in fixture.records:
            record["descriptor"]["mediaType"] = "application/vnd.oci.image.index.v1+json"
        with self.assertRaisesRegex(ValueError, "not_single_manifest"):
            self.verify(fixture)
        fixture = LoadedFixture()
        with mock.patch.object(artifacts.shutil, "which", return_value=None):
            with self.assertRaisesRegex(ValueError, "ctr_missing"):
                artifacts.verify_loaded(SHA, fixture.config_digest, run=fixture.run)
        self.assertEqual(len(fixture.calls), 2)

    def test_missing_containerd_metadata_and_permission_errors_are_clear_and_redacted(self):
        fixture = LoadedFixture()

        def missing_info(command):
            return b"null" if command[:2] == ["docker", "info"] else fixture.run(command)

        with self.assertRaisesRegex(ValueError, "address_or_namespace"):
            artifacts.verify_loaded(SHA, fixture.config_digest, run=missing_info)
        for error in (FileNotFoundError(), PermissionError()):
            with self.subTest(error=error), mock.patch.object(artifacts.subprocess, "Popen", side_effect=error):
                with self.assertRaises(ValueError) as caught:
                    artifacts.read_metadata(["docker", "info"])
                self.assertNotIn("private-not-for-output", str(caught.exception))
        process = mock.MagicMock()
        process.stdout = io.BytesIO(b"private-not-for-output")
        process.returncode = 1
        with mock.patch.object(artifacts.subprocess, "Popen", return_value=process):
            with self.assertRaisesRegex(ValueError, "check_local_permissions") as caught:
                artifacts.read_metadata(["docker", "info"])
            self.assertNotIn("private-not-for-output", str(caught.exception))

    def test_metadata_reader_has_real_output_limit_and_deadline(self):
        process = mock.MagicMock()
        process.stdout = io.BytesIO(b"x" * (artifacts.METADATA_LIMIT + 2))
        process.returncode = 0
        with mock.patch.object(artifacts.subprocess, "Popen", return_value=process):
            with self.assertRaisesRegex(ValueError, "output_too_large"):
                artifacts.read_metadata(["docker", "info"])
        self.assertEqual(process.stdout.tell(), artifacts.METADATA_LIMIT + 1)
        process.kill.assert_called_once()
        process.stdout = io.BytesIO(b"")

        def immediate_deadline(seconds, callback):
            self.assertEqual(seconds, 30)
            timer = mock.Mock()
            timer.start.side_effect = callback
            return timer

        with mock.patch.object(artifacts.subprocess, "Popen", return_value=process), mock.patch.object(
                artifacts.threading, "Timer", side_effect=immediate_deadline):
            with self.assertRaisesRegex(ValueError, "command_timeout"):
                artifacts.read_metadata(["docker", "info"])

    def test_operator_cli_is_explicit_and_never_accepts_schema_1_receipt(self):
        fixture = LoadedFixture()
        argv = ["deploy_artifacts.py", "verify-loaded", "--sha", SHA,
                "--expected-config-digest", fixture.config_digest]
        with mock.patch.object(sys, "argv", argv), mock.patch.object(
                artifacts, "verify_loaded", return_value={"store": "fixture"}) as loaded:
            with mock.patch("sys.stdout", new_callable=io.StringIO) as output:
                artifacts.main()
            self.assertEqual(json.loads(output.getvalue())["mode"], "explicit_operator_config_digest")
            loaded.assert_called_once_with(SHA, fixture.config_digest, None)
        with mock.patch.object(sys, "argv", ["script", "verify-loaded", "--sha", SHA]):
            with mock.patch("sys.stderr", new_callable=io.StringIO), self.assertRaises(SystemExit):
                artifacts.main()
        with tempfile.TemporaryDirectory() as directory:
            old = Path(directory) / "old.json"
            old.write_text(json.dumps({"schema": 1, "revision": SHA, "image_id": fixture.config_digest}))
            with mock.patch.object(sys, "argv", argv + ["--receipt", str(old), "--run-id", "42"]):
                with self.assertRaisesRegex(ValueError, "schema_2_required"):
                    artifacts.main()


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
        self.assertEqual(deploy.count("deploy_artifacts.py verify-loaded"), 2)
        self.assertEqual(deploy.count('--receipt "$WEB_IMAGE_BASE.image.json"'), 2)
        self.assertEqual(deploy.count('--expected-config-digest "$(cat "$WEB_IMAGE_BASE.image-config-digest")"'), 2)
        self.assertEqual(deploy.count('"${ARTIFACT}.image-config-digest" "${ARTIFACT}.image.json"'), 2)
        self.assertNotIn("EXPECTED_WEB_IMAGE_ID", deploy)
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

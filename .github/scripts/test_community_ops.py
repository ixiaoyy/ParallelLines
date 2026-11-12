"""圈子运维纯回归：所有 Docker、Git、网络及数据库入口均用合成替身。"""

import contextlib
import copy
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest import mock


HERE = Path(__file__).resolve().parent
if sys.platform == "win32":
    sys.modules.setdefault("fcntl", types.SimpleNamespace())
spec = importlib.util.spec_from_file_location("community_ops", HERE / "community_ops.py")
ops = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ops)


def result(stdout="", code=0):
    return types.SimpleNamespace(stdout=stdout, stderr="", returncode=code)


def baseline_fixture():
    files = ",".join(map(str, ops.BASE_FILES))
    service = {"running": True, "working_directory": str(ops.MAIN), "compose_files": files,
               "networks": ["parallellines_default"], "hash": "a" * 64}
    return {"git": {"head": ops.BEFORE, "clean": True}, "config_sha256": ops.OLD_CONFIG,
            "forum": None, "api": {**service, "id": "b" * 64, "image_id": "sha256:" + "c" * 64},
            "gateway": {**service, "id": "d" * 64},
            "api_compose_hash": "a" * 64, "gateway_compose_hash": "a" * 64,
            "api_public_source_integrity": {"tree_sha256": ops.BASE_API_TREE},
            "database_revision": "0110_add_six_featured_games", "state_sha256": "e" * 64,
            "resources": {"memory": {"MemAvailable": 3 * 1024 ** 3}, "disk": {"free": 50 * 1024 ** 3}}}


class OperationGuards(unittest.TestCase):
    def test_unknown_or_other_revision_never_constructs_runner(self):
        for arguments in (("shell", ops.APP, "-"), ("deploy", "0" * 40, "-"), ("health",)):
            with self.subTest(arguments=arguments), mock.patch.object(ops, "Runner") as runner, contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(ops.main(list(arguments)), 2)
                runner.assert_not_called()

    def test_unreviewed_write_phase_cannot_execute(self):
        for operation in set(ops.OPERATIONS) - set(ops.READY_OPERATIONS):
            with self.subTest(operation=operation), mock.patch.object(ops, "Runner") as runner, contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(ops.main([operation, ops.APP, "a" * 64]), 2)
                runner.assert_not_called()

    def test_historical_untracked_are_not_a_tracked_dirty_gate(self):
        outputs = iter((ops.BEFORE, "refs/heads/main", "", "var.pre-data/\nstatic/old-image.png\n"))
        with mock.patch.object(ops, "git", side_effect=lambda *_args, **_kwargs: result(next(outputs))):
            value = ops.git_state(None)
        self.assertTrue(value["clean"])
        self.assertEqual(value["tracked_dirty_paths"], [])
        self.assertEqual(value["untracked_directory_entries"], 2)
        self.assertNotIn("var.pre-data", json.dumps(value))

    def test_baseline_rejects_real_tracked_or_runtime_drift(self):
        good = baseline_fixture()
        ops.baseline(good)
        for change in (lambda v: v["git"].update(clean=False),
                       lambda v: v["api"].update(hash="f" * 64),
                       lambda v: v["api_public_source_integrity"].update(tree_sha256="0" * 64)):
            value = copy.deepcopy(good)
            change(value)
            with self.assertRaises(ops.OperationError):
                ops.baseline(value)

    def test_api_only_allowed_identity_fields_can_change(self):
        before = {"id": "old", "image_id": "old-image", "image": "old-tag", "hash": "old-hash",
                  "compose_files": "old-files", "mounts": ["original-data"], "networks": ["original-network"],
                  "command": ["original-command"], "running": True}
        after = {**before, "id": "new", "image_id": "new-image", "image": "new-tag", "hash": "new-hash", "compose_files": "new-files"}
        self.assertTrue(ops.same_spec(before, after))
        for key in ("mounts", "networks", "command"):
            with self.subTest(key=key):
                self.assertFalse(ops.same_spec(before, {**after, key: []}))

    def test_forum_validation_does_not_accept_main_navigation(self):
        wrong = '<title>游戏</title><link rel="canonical" href="https://pingxingxian.space/"><a href="https://forum.pingxingxian.space/">圈子</a>'.encode()
        correct = '<title>平行线 · 圈子</title><link rel="canonical" href="https://forum.pingxingxian.space/">'.encode()
        self.assertFalse(ops.forum_document_valid(wrong))
        self.assertTrue(ops.forum_document_valid(correct))
        self.assertFalse(ops.forum_document_valid(correct + b" " * ops.BODY_LIMIT))

    def test_internal_probe_embedded_python_is_valid_and_read_only(self):
        runner = mock.Mock()
        runner.run.return_value = result('{"forum_root_and_same_origin_api":true}')
        self.assertTrue(ops.internal_forum(runner, {"id": "a" * 64})["forum_root_and_same_origin_api"])
        argv = runner.run.call_args.args[1]
        script = argv[-1]
        compile(script, "internal-read-only-probe", "exec")
        self.assertIn("/api/v1/boards", script)
        self.assertNotIn("POST", script)


class OwnedFilesystemTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.main = Path(self.directory.name)
        self.root = self.main / ".deployment/community" / ops.APP
        self.source = self.root / "source"
        self.config = self.main / "deploy/nginx/default.conf"
        self.config.parent.mkdir(parents=True)
        self.config.write_bytes(b"old-config\n")
        self.patches = mock.patch.multiple(ops, MAIN=self.main, ROOT=self.root, SOURCE=self.source,
                                           MAIN_CONFIG=self.config, PENDING=self.root / "pending.json",
                                           CURRENT=self.root / "current.json", MARKER=self.main / ".deployment/forum-enabled")
        self.patches.start()
        self.addCleanup(self.patches.stop)

    def test_outside_paths_are_rejected(self):
        with self.assertRaises(ops.OperationError):
            ops.safe_path(self.main.parent / "outside")

    def test_configuration_switch_preserves_inode_and_rejects_wrong_preimage(self):
        stat = self.config.stat()
        identity = {"device": stat.st_dev, "inode": stat.st_ino}
        runner = mock.Mock()
        runner.run.side_effect = lambda *_args, **_kwargs: result(ops.digest(self.config.read_bytes()) + "  config")
        ops.configuration_write(runner, {"id": "fixed"}, b"old-config\n", b"new-config\n", identity)
        self.assertEqual(self.config.stat().st_ino, stat.st_ino)
        self.assertEqual(self.config.read_bytes(), b"new-config\n")
        with self.assertRaises(ops.OperationError):
            ops.configuration_write(runner, {"id": "fixed"}, b"wrong", b"unsafe", identity)
        self.assertEqual(self.config.read_bytes(), b"new-config\n")

    def test_new_target_collision_is_not_read_or_overwritten(self):
        target = self.main / "new-file.py"
        target.write_bytes(b"someone-else")
        candidate = self.source / "new-file.py"
        candidate.parent.mkdir(parents=True)
        candidate.write_bytes(b"candidate")
        with mock.patch.object(ops, "changed_paths", return_value=["new-file.py"]), mock.patch.object(ops, "git", return_value=result(b"", 128)):
            with self.assertRaisesRegex(ops.OperationError, "new_application_path_collision"):
                ops.target_preimages(None)
        self.assertEqual(target.read_bytes(), b"someone-else")

    def test_target_guard_keeps_unrelated_old_data_untouched(self):
        (self.main / "tracked.py").write_bytes(b"old")
        old_data = self.main / "var.pre-data/data-file"
        old_data.parent.mkdir()
        old_data.write_bytes(b"historical-data")
        (self.source / "tracked.py").parent.mkdir(parents=True)
        (self.source / "tracked.py").write_bytes(b"new")
        with mock.patch.object(ops, "changed_paths", return_value=["tracked.py"]), mock.patch.object(ops, "git", return_value=result(b"old")):
            self.assertEqual(ops.target_preimages(None), ["tracked.py"])
        self.assertEqual(old_data.read_bytes(), b"historical-data")

    def test_source_alignment_and_restore_keep_config_inode(self):
        names = ("deploy/nginx/default.conf", "tracked.py", "new-file.py")
        (self.main / "tracked.py").write_bytes(b"old-code")
        for name in names:
            candidate = self.source / name
            candidate.parent.mkdir(parents=True, exist_ok=True)
            candidate.write_bytes(b"candidate-" + name.encode())
            old = self.main / name
            if old.exists():
                ops.atomic(self.root / "before" / name, old.read_bytes())
        stat = self.config.stat()
        state = {"paths": names, "before": {"gateway": {"id": "fixed"},
                 "config_identity": {"device": stat.st_dev, "inode": stat.st_ino}}}
        runner = mock.Mock()
        runner.run.side_effect = lambda *_args, **_kwargs: result(ops.digest(self.config.read_bytes()) + "  config")
        with mock.patch.object(ops, "git", return_value=result(ops.BEFORE)), mock.patch.object(ops, "git_state", return_value={"clean": True}):
            ops.align_source(runner, state)
        self.assertEqual(self.config.stat().st_ino, stat.st_ino)
        self.assertTrue((self.main / "new-file.py").exists())
        with mock.patch.object(ops, "git", return_value=result(ops.APP)), mock.patch.object(ops, "git_state", return_value={"clean": True}):
            ops.align_source(runner, state, restore=True)
        self.assertEqual(self.config.stat().st_ino, stat.st_ino)
        self.assertEqual(self.config.read_bytes(), b"old-config\n")
        self.assertEqual((self.main / "tracked.py").read_bytes(), b"old-code")
        self.assertFalse((self.main / "new-file.py").exists())

    def test_source_restore_rejects_outside_edit(self):
        (self.main / "tracked.py").write_bytes(b"someone-else")
        (self.source / "tracked.py").parent.mkdir(parents=True)
        (self.source / "tracked.py").write_bytes(b"candidate")
        ops.atomic(self.root / "before/tracked.py", b"old")
        with self.assertRaisesRegex(ops.OperationError, "changed_outside_attempt"):
            ops.align_source(None, {"paths": ["tracked.py"]}, restore=True)
        self.assertEqual((self.main / "tracked.py").read_bytes(), b"someone-else")

    def test_owned_layer_file_mismatch_stops_before_remove(self):
        file = self.source / "deploy/nginx/forum.conf"
        file.parent.mkdir(parents=True)
        file.write_bytes(b"candidate")
        runner = mock.Mock()
        runner.run.side_effect = (result(code=0), result("0" * 64 + " file"))
        with self.assertRaisesRegex(ops.OperationError, "layer_file_changed_outside_attempt"):
            ops.layer_files(runner, {"id": "fixed"}, remove=True)
        self.assertFalse(any("rm" in call.args[1] for call in runner.run.call_args_list))


class PreparationTests(unittest.TestCase):
    def test_low_memory_stops_before_source_or_docker_writes(self):
        value = baseline_fixture()
        value["resources"]["memory"]["MemAvailable"] = 1024 ** 3
        with mock.patch.object(ops, "inventory", return_value=value), mock.patch.object(ops, "source_prepare") as source:
            with self.assertRaisesRegex(ops.OperationError, "insufficient_headroom"):
                ops.prepare(mock.Mock(), value["state_sha256"])
            source.assert_not_called()

    def test_api_layer_recipe_is_fixed_four_files_and_has_no_run(self):
        recipe = "FROM " + ops.API_BASE_IMAGE + "\n" + "".join("COPY " + name + " /app/" + name[len("apps/api/"):] + "\n" for name in ops.API_CHANGED_FILES)
        self.assertEqual(recipe.count("COPY "), 4)
        self.assertNotIn("RUN ", recipe)
        self.assertNotIn(".env", recipe)
        self.assertNotIn("alembic/versions", recipe)

    def test_prepare_serializes_builds_and_keeps_source_recipe_unchanged(self):
        with tempfile.TemporaryDirectory() as directory:
            main = Path(directory)
            root = main / ".deployment/community" / ops.APP
            source = root / "source"
            recipe = source / "apps/web/Dockerfile.forum"
            recipe.parent.mkdir(parents=True)
            original = b"FROM node:22-alpine\nRUN pnpm --dir apps/web build:forum\n"
            recipe.write_bytes(original)
            with mock.patch.multiple(ops, MAIN=main, ROOT=root, SOURCE=source,
                                     PENDING=root / "pending.json", CURRENT=root / "current.json",
                                     MARKER=main / ".deployment/forum-enabled"):
                value = baseline_fixture()
                runner = mock.Mock()
                runner.run.side_effect = lambda label, *_args, **_kwargs: result(value["database_revision"] + " (head)\n" if label == "candidate_migration_heads" else "")
                with mock.patch.object(ops, "inventory", side_effect=lambda *_args: copy.deepcopy(value)), mock.patch.object(ops, "source_prepare"), mock.patch.object(ops, "target_preimages"), mock.patch.object(ops, "image_id", return_value="sha256:" + "f" * 64):
                    report = ops.prepare(runner, value["state_sha256"])
                self.assertTrue(report["complete"])
                labels = [call.args[0] for call in runner.run.call_args_list]
                self.assertEqual(labels, ["build_forum", "pin_unchanged_api_base", "build_api", "candidate_migration_heads"])
                self.assertEqual(recipe.read_bytes(), original)
                self.assertIn(b"--max-old-space-size=1536", (root / "forum.build.Dockerfile").read_bytes())
                self.assertEqual((root / "api.build.Dockerfile").read_text().count("COPY "), 4)
                self.assertNotIn("RUN ", (root / "api.build.Dockerfile").read_text())

    def run_tls(self, body=b"fixture-token"):
        value = baseline_fixture()
        tls = mock.Mock()
        tls.configuration_may_reload.return_value = True
        tls.context_preflight.return_value = {"certbot": "fixed-certbot"}
        @contextlib.contextmanager
        def probe():
            yield "http://tools.pingxingxian.space/.well-known/acme-challenge/fixture", b"fixture-token"
        tls.owned_probe.side_effect = probe
        response = mock.MagicMock()
        response.__enter__.return_value = response
        response.status = 200
        response.read.return_value = body
        opener = mock.Mock()
        opener.open.return_value = response
        runner = mock.Mock()
        runner.run.side_effect = lambda label, *_args, **_kwargs: result("DNS:forum.pingxingxian.space" if label == "public_community_certificate" else "")
        with mock.patch.object(ops, "inventory", return_value=value), mock.patch.object(ops, "tools_lock", return_value=contextlib.nullcontext(tls)), mock.patch.object(ops, "request_deadline", return_value=contextlib.nullcontext()), mock.patch.object(ops.urllib.request, "build_opener", return_value=opener):
            if body != b"fixture-token":
                with self.assertRaisesRegex(ops.OperationError, "http01_probe_mismatch"):
                    ops.prepare_tls(runner, value["state_sha256"])
                runner.run.assert_not_called()
            else:
                report = ops.prepare_tls(runner, value["state_sha256"])
                self.assertTrue(report["complete"])
        return runner, opener

    def test_tls_only_requests_fixed_new_domain_after_probe(self):
        runner, opener = self.run_tls()
        url = opener.open.call_args.args[0]
        self.assertTrue(url.startswith("http://forum.pingxingxian.space/.well-known/acme-challenge/"))
        arguments = runner.run.call_args_list[0].args[1]
        self.assertIn("--no-directory-hooks", arguments)
        self.assertEqual(arguments[-2:], ["-d", ops.DOMAIN])
        self.assertNotIn("nginx", arguments)

    def test_tls_probe_failure_never_calls_certbot(self):
        self.run_tls(b"wrong-probe")


class WorkflowContractTests(unittest.TestCase):
    def test_no_generic_shell_or_credentials_input(self):
        source = (HERE.parent / "workflows/community-ops.yml").read_text(encoding="utf-8")
        self.assertIn("github.repository == 'ixiaoyy/ParallelLines'", source)
        self.assertIn("github.ref == 'refs/heads/main'", source)
        self.assertIn("'community-read-health'", source)
        self.assertIn("'deploy-production'", source)
        self.assertIn("revision != '" + ops.APP + "'", source)
        self.assertNotIn("inputs.command", source)
        self.assertNotIn("inputs.host", source)
        self.assertIn("script_stop: false", source)


if __name__ == "__main__":
    unittest.main()

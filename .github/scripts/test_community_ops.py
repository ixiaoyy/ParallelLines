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
import os
import subprocess
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
    value = {"git": {"head": ops.BEFORE, "clean": True}, "config_sha256": ops.OLD_CONFIG,
            "config_identity": {"device": 64769, "inode": 1049133},
            "forum": None, "api": {**service, "id": "b" * 64, "image_id": "sha256:" + "c" * 64},
            "gateway": {**service, "id": "d" * 64},
            "api_compose_hash": "a" * 64, "gateway_compose_hash": "a" * 64,
            "api_public_source_integrity": {"tree_sha256": ops.BASE_API_TREE},
            "database_revision": "0110_add_six_featured_games", "state_sha256": "e" * 64,
            "resources": {"memory": {"MemAvailable": 3 * 1024 ** 3}, "disk": {"free": 50 * 1024 ** 3}}}
    value["approval_sha256"] = ops.digest(ops.approval_identity(value))
    return value


def alignment_git(head):
    def invoke(_runner, args, **_kwargs):
        if args[0] == "rev-parse":
            return result(head)
        if args[0] == "symbolic-ref":
            return result("refs/heads/main")
        return result("")
    return invoke


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

    def test_transparent_approval_rejects_changed_cid_configuration_or_database(self):
        value = baseline_fixture()
        expected = value["approval_sha256"]
        ops.expect_snapshot(value, expected)
        for change in (lambda v: v["api"].update(id="f" * 64),
                       lambda v: v.update(config_sha256="0" * 64),
                       lambda v: v.update(database_revision="unexpected_revision")):
            altered = copy.deepcopy(value)
            change(altered)
            with self.subTest(change=change), self.assertRaisesRegex(ops.OperationError, "approval_identity_mismatch"):
                ops.expect_snapshot(altered, expected)
        with self.assertRaisesRegex(ops.OperationError, "approval_identity_mismatch"):
            ops.expect_snapshot(value, value["state_sha256"])

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
        with mock.patch.object(ops, "git", side_effect=alignment_git(ops.BEFORE)), mock.patch.object(ops, "git_state", return_value={"clean": True}):
            ops.align_source(runner, state)
        self.assertEqual(self.config.stat().st_ino, stat.st_ino)
        self.assertTrue((self.main / "new-file.py").exists())
        with mock.patch.object(ops, "git", side_effect=alignment_git(ops.APP)), mock.patch.object(ops, "git_state", return_value={"clean": True}):
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
        with mock.patch.object(ops, "git", side_effect=alignment_git(ops.APP)), self.assertRaisesRegex(ops.OperationError, "changed_outside_attempt"):
            ops.align_source(None, {"paths": ["tracked.py"]}, restore=True)
        self.assertEqual((self.main / "tracked.py").read_bytes(), b"someone-else")

    def test_unknown_head_stops_before_any_source_mutation(self):
        before = self.config.read_bytes()
        with mock.patch.object(ops, "git", side_effect=alignment_git("f" * 40)), mock.patch.object(ops, "configuration_write") as write:
            with self.assertRaisesRegex(ops.OperationError, "main_branch_changed_outside_attempt"):
                ops.align_source(mock.Mock(), {"paths": ["deploy/nginx/default.conf"]}, restore=True)
            write.assert_not_called()
        self.assertEqual(self.config.read_bytes(), before)

    def test_unknown_last_file_stops_before_first_file_mutation(self):
        names = ("deploy/nginx/default.conf", "last.py")
        before = self.config.read_bytes()
        for name in names:
            candidate = self.source / name
            candidate.parent.mkdir(parents=True, exist_ok=True)
            candidate.write_bytes(b"candidate")
            ops.atomic(self.root / "before" / name, before if name == names[0] else b"old-code")
        (self.main / "last.py").write_bytes(b"external-edit")
        with mock.patch.object(ops, "git", side_effect=alignment_git(ops.APP)) as git, mock.patch.object(ops, "configuration_write") as write:
            with self.assertRaisesRegex(ops.OperationError, "changed_outside_attempt:last.py"):
                ops.align_source(mock.Mock(), {"paths": names}, restore=True)
            write.assert_not_called()
            self.assertFalse(any(call.args[1][0] in ("read-tree", "update-ref") for call in git.call_args_list))
        self.assertEqual(self.config.read_bytes(), before)
        self.assertEqual((self.main / "last.py").read_bytes(), b"external-edit")

    def test_interrupted_short_config_restore_uses_durable_known_transition(self):
        name = "deploy/nginx/default.conf"
        old, new = b"old\n", b"new-configuration-with-a-long-tail\n"
        self.config.write_bytes(new)
        candidate = self.source / name
        candidate.parent.mkdir(parents=True)
        candidate.write_bytes(new)
        ops.atomic(self.root / "before" / name, old)
        stat = self.config.stat()
        identity = {"device": stat.st_dev, "inode": stat.st_ino}
        state = {"paths": [name], "before": {"gateway": {"id": "fixed"}, "config_identity": identity}}
        original_open = Path.open
        class InterruptedStream:
            def __enter__(self):
                self.stream = original_open(self_path, "r+b")
                return self
            def __exit__(self, *_args):
                self.stream.close()
            def __getattr__(self, key):
                return getattr(self.stream, key)
            def write(self, value):
                written = self.stream.write(value)
                self.stream.flush()
                return written
            def truncate(self):
                raise RuntimeError("simulated-exit-before-truncate")
        self_path = self.config
        def intercepted(path, *args, **kwargs):
            if path == self.config and args and args[0] == "r+b":
                return InterruptedStream()
            return original_open(path, *args, **kwargs)
        with mock.patch.object(Path, "open", new=intercepted), self.assertRaisesRegex(RuntimeError, "before-truncate"):
            ops.configuration_write(mock.Mock(), {"id": "fixed"}, new, old, identity)
        self.assertEqual(self.config.read_bytes(), old + new[len(old):])
        self.assertTrue(ops.interrupted_configuration_owned(self.config.read_bytes(), state))
        self.assertFalse(ops.known_write_transition(b"unknown-external", new, old))
        runner = mock.Mock()
        runner.run.side_effect = lambda *_args, **_kwargs: result(ops.digest(self.config.read_bytes()) + " config")
        with mock.patch.object(ops, "git", side_effect=alignment_git(ops.APP)), mock.patch.object(ops, "git_state", return_value={"clean": True}):
            ops.align_source(runner, state, restore=True)
        self.assertEqual(self.config.read_bytes(), old)
        self.assertEqual(self.config.stat().st_ino, stat.st_ino)
        self.assertFalse((self.root / "config-write.json").exists())

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
    def test_real_isolated_shallow_repositories_import_candidate_without_switching_main(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            origin, main, source = root / "origin", root / "main", root / "source"
            environment = {**os.environ, "GIT_AUTHOR_NAME": "fixture", "GIT_AUTHOR_EMAIL": "fixture@example.invalid",
                           "GIT_COMMITTER_NAME": "fixture", "GIT_COMMITTER_EMAIL": "fixture@example.invalid",
                           "GIT_TERMINAL_PROMPT": "0", "GIT_ALLOW_PROTOCOL": "file"}
            def local_git(args, *, cwd=None, accepted=(0,)):
                value = subprocess.run(["git", *args], cwd=cwd, env=environment, capture_output=True, text=True, timeout=15)
                self.assertIn(value.returncode, accepted, value.stderr)
                return value
            local_git(["init", str(origin)])
            names = ["deploy/nginx/default.conf"] + [f"files/item-{i}.txt" for i in range(38)]
            for name in names:
                path = origin / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("before\n", encoding="utf-8")
            local_git(["add", "."], cwd=origin)
            local_git(["commit", "-m", "fixture-before"], cwd=origin)
            before = local_git(["rev-parse", "HEAD"], cwd=origin).stdout.strip()
            local_git(["branch", "before"], cwd=origin)
            for name in names:
                (origin / name).write_text("candidate\n", encoding="utf-8")
            local_git(["add", "."], cwd=origin)
            local_git(["commit", "-m", "fixture-app"], cwd=origin)
            app = local_git(["rev-parse", "HEAD"], cwd=origin).stdout.strip()
            local_git(["branch", "app"], cwd=origin)
            local_git(["clone", "--no-local", "--depth=1", "--branch", "before", origin.as_uri(), str(main)])
            local_git(["clone", "--no-local", "--depth=1", "--branch", "app", origin.as_uri(), str(source)])
            self.assertNotEqual(local_git(["cat-file", "-e", app], cwd=main, accepted=(0, 1, 128)).returncode, 0)
            self.assertNotEqual(local_git(["cat-file", "-e", before], cwd=source, accepted=(0, 1, 128)).returncode, 0)
            index_before = local_git(["write-tree"], cwd=main).stdout
            original_run = subprocess.run
            observed = []
            def recording_run(*args, **kwargs):
                value = original_run(*args, **kwargs)
                observed.append(value)
                return value
            with mock.patch.multiple(ops, MAIN=main, SOURCE=source, BEFORE=before, APP=app), mock.patch.dict(os.environ, environment), mock.patch.object(ops.subprocess, "run", side_effect=recording_run):
                try:
                    changed = ops.changed_paths(ops.Runner())
                except ops.OperationError:
                    self.fail(observed[-1].stderr)
            self.assertEqual(set(changed), set(names))
            local_git(["cat-file", "-e", app], cwd=main)
            self.assertEqual(local_git(["rev-parse", "HEAD"], cwd=main).stdout.strip(), before)
            self.assertEqual(local_git(["write-tree"], cwd=main).stdout, index_before)
            self.assertEqual((main / "deploy/nginx/default.conf").read_text(), "before\n")

    def test_low_memory_stops_before_source_or_docker_writes(self):
        value = baseline_fixture()
        value["resources"]["memory"]["MemAvailable"] = 1024 ** 3
        with mock.patch.object(ops, "inventory", return_value=value), mock.patch.object(ops, "source_prepare") as source:
            with self.assertRaisesRegex(ops.OperationError, "insufficient_headroom"):
                ops.prepare(mock.Mock(), value["approval_sha256"])
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
                    report = ops.prepare(runner, value["approval_sha256"])
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
                    ops.prepare_tls(runner, value["approval_sha256"])
                runner.run.assert_not_called()
            else:
                report = ops.prepare_tls(runner, value["approval_sha256"])
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

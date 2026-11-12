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
    def test_ownership_inventory_reads_only_numeric_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            main = Path(directory)
            for name in (".git/index", ".git/refs/heads/main", "deploy/nginx/default.conf"):
                path = main / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"body-must-not-be-read")
            before = {str(path): path.stat().st_mode for path in main.rglob("*")}
            with mock.patch.multiple(ops, MAIN=main, MAIN_CONFIG=main / "deploy/nginx/default.conf"), mock.patch.object(Path, "read_bytes", side_effect=AssertionError("unexpected-content-read")):
                value = ops.ownership_metadata()
            for entry in value.values():
                if entry["exists"]:
                    self.assertIsInstance(entry["uid"], int)
                    self.assertIsInstance(entry["gid"], int)
                    self.assertIsInstance(entry["mode"], int)
            self.assertFalse(value["fetch_head"]["exists"])
            self.assertEqual({str(path): path.stat().st_mode for path in main.rglob("*")}, before)

    def test_unknown_or_other_revision_never_constructs_runner(self):
        for arguments in (("shell", ops.APP, "-"), ("deploy", "0" * 40, "-"), ("health",)):
            with self.subTest(arguments=arguments), mock.patch.object(ops, "Runner") as runner, contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(ops.main(list(arguments)), 2)
                runner.assert_not_called()

    def test_unreviewed_write_phase_cannot_execute(self):
        # 真实阶段已开放全部受审操作；收窄阶段的拒绝边界仍须有效，不能随开放而删掉断言。
        self.assertEqual(set(ops.READY_OPERATIONS), set(ops.OPERATIONS))
        with mock.patch.object(ops, "READY_OPERATIONS", ("inventory", "health")):
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
        runner.run.side_effect = (result(code=1), result(code=1), result(code=1), result(code=0), result("0" * 64 + " file"))
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
            yield "http://tools.pingxingxian.space/.well-known/acme-challenge/tools-probe-" + "a" * 32, b"fixture-token"
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
        url = opener.open.call_args.args[0].full_url
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


class RestoreHealthTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        main = Path(self.directory.name)
        root = main / ".deployment/community" / ops.APP
        self.patches = mock.patch.multiple(ops, MAIN=main, ROOT=root, PENDING=root / "pending.json",
                                           CURRENT=root / "current.json", MARKER=main / ".deployment/forum-enabled")
        self.patches.start()
        self.addCleanup(self.patches.stop)
        api = {"id": "a" * 64, "image_id": "sha256:" + "b" * 64, "running": True,
               "project": "parallellines", "service": "api", "hash": "c" * 64, "mounts": []}
        self.api = api
        self.state = {"schema": 1, "source_revision": ops.APP, "status": "snapshotted",
                      "before": {"api": api, "gateway": {"id": "g" * 64}},
                      "prepared": {"api_image_id": "sha256:" + "d" * 64},
                      "after_api_hash": "e" * 64, "restore_api_hash": "f" * 64}
        ops.save(ops.PENDING, self.state)

    def run_restore(self, *, running=True, unhealthy=False, bad_preflight=False):
        live = {**self.api, "running": running}
        runner = mock.Mock()
        with contextlib.ExitStack() as stack:
            stack.enter_context(mock.patch.object(ops, "tools_lock", return_value=contextlib.nullcontext()))
            stack.enter_context(mock.patch.object(ops, "guard_gateway"))
            stack.enter_context(mock.patch.object(ops, "containers", return_value=[live]))
            preflight = stack.enter_context(mock.patch.object(ops, "alignment_preflight"))
            if bad_preflight:
                preflight.side_effect = ops.OperationError("main_branch_changed_outside_attempt")
            stack.enter_context(mock.patch.object(ops, "renewal_preflight"))
            remove = stack.enter_context(mock.patch.object(ops, "remove_renewal"))
            layer = stack.enter_context(mock.patch.object(ops, "layer_files"))
            align = stack.enter_context(mock.patch.object(ops, "align_source"))
            compose = stack.enter_context(mock.patch.object(ops, "compose"))
            wait = stack.enter_context(mock.patch.object(ops, "wait_api", return_value={**live, "running": True}))
            stack.enter_context(mock.patch.object(ops, "health", return_value={"complete": True}))
            if unhealthy:
                wait.side_effect = ops.OperationError("api_health_deadline")
            if unhealthy or bad_preflight:
                with self.assertRaises(ops.OperationError):
                    ops.restore(runner)
                self.assertTrue(ops.PENDING.exists())
                self.assertFalse((ops.ROOT / "rolled-back.json").exists())
            else:
                self.assertTrue(ops.restore(runner)["complete"])
            return compose, wait, remove, layer, align

    def test_stopped_old_image_is_started_and_health_checked(self):
        compose, wait, *_ = self.run_restore(running=False)
        self.assertEqual(compose.call_args.args[1], ["up", "-d", "--no-deps", "--no-build", "api"])
        wait.assert_called_once()

    def test_running_but_unhealthy_old_image_never_reports_restored(self):
        compose, wait, *_ = self.run_restore(unhealthy=True)
        compose.assert_not_called()
        wait.assert_called_once()

    def test_restore_unknown_head_stops_before_layer_or_consumer_mutation(self):
        compose, wait, remove, layer, align = self.run_restore(bad_preflight=True)
        for method in (compose, wait, remove, layer, align):
            method.assert_not_called()


class CheckRenewalEntryTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        main = Path(self.directory.name)
        root = main / ".deployment/community" / ops.APP
        cron = main / "cron.d/community"
        cron.parent.mkdir()
        root.mkdir(parents=True)
        program = root / "renew-community.py"
        program.write_bytes(b"reviewed-consumer")
        cron.write_bytes(b"owned-cron")
        self.program, self.cron, self.root = program, cron, root
        self.patch = mock.patch.multiple(ops, MAIN=main, ROOT=root, PENDING=root / "pending.json",
                                        CURRENT=root / "current.json", RENEW_CRON=cron)
        self.patch.start()
        self.addCleanup(self.patch.stop)
        stat = cron.stat()
        self.state = {"schema": 1, "source_revision": ops.APP, "status": "committed", "renewal": {
                      "script_sha256": ops.digest(program.read_bytes()), "cron_sha256": ops.digest(cron.read_bytes()),
                      "cron_identity": {"device": stat.st_dev, "inode": stat.st_ino}}}
        ops.save(ops.CURRENT, self.state)

    def test_fixed_check_entry_and_result_classification(self):
        runner = mock.Mock()
        runner.run.return_value = result('{"complete":true,"reloaded":false,"errors":[]}')
        output = io.StringIO()
        with mock.patch.object(ops, "Runner", return_value=runner), contextlib.redirect_stdout(output):
            self.assertEqual(ops.main(["check-renewal", ops.APP, "-"]), 0)
        runner.run.assert_called_once_with("check_installed_community_renewal", ["/usr/bin/python3", "-B", str(self.program), "check"], timeout=90)
        report = json.loads(output.getvalue())
        self.assertTrue(report["runtime_read_only"])
        self.assertTrue(report["writes_owned_report"])
        self.assertFalse(report["reloaded"])
        self.assertEqual(self.program.read_bytes(), b"reviewed-consumer")
        self.assertEqual(self.cron.read_bytes(), b"owned-cron")
        for response in ('{"complete":false,"reloaded":false}', '{"complete":true,"reloaded":true}'):
            runner.run.return_value = result(response)
            with self.subTest(response=response), self.assertRaisesRegex(ops.OperationError, "renewal_check_failed"):
                ops.check_renewal(runner)

    def test_unknown_pending_or_unowned_state_never_executes(self):
        runner = mock.Mock()
        changes = (lambda value: value.update(status="switching"),
                   lambda value: value.update(source_revision="0" * 40),
                   lambda value: value.pop("renewal"))
        for change in changes:
            value = copy.deepcopy(self.state)
            change(value)
            ops.save(ops.CURRENT, value)
            with self.assertRaises(ops.OperationError):
                ops.check_renewal(runner)
        ops.save(ops.CURRENT, self.state)
        ops.save(ops.PENDING, {"status": "unfinished"})
        with self.assertRaisesRegex(ops.OperationError, "pending_transaction"):
            ops.check_renewal(runner)
        ops.PENDING.unlink()
        self.program.write_bytes(b"outside-change")
        with self.assertRaisesRegex(ops.OperationError, "consumer_preimage_changed"):
            ops.check_renewal(runner)
        runner.run.assert_not_called()


class RenewalConsumerTests(unittest.TestCase):
    def program(self):
        namespace = {"__name__": "community_renewal_fixture"}
        exec(compile(ops.renewal_program(), "reviewed-community-renewal", "exec"), namespace)
        return namespace

    def run_consumer(self, mode, *, changed=False, rejected=False, delayed=False):
        namespace = self.program()
        state = {"source_revision": ops.APP, "status": "committed"}
        namespace["record"] = mock.Mock(return_value=state)
        namespace["file_certificate"] = mock.Mock(return_value="new" if changed else "same")
        sequence = ["old", "old", "old", "new"] if delayed else ["old", "old", "new"]
        namespace["loaded_certificate"] = mock.Mock(side_effect=sequence if changed else None,
                                                     return_value="same")
        namespace["guard"] = mock.Mock(return_value="fixed-gateway")
        if rejected:
            namespace["guard"].side_effect = namespace["RenewalError"]("gateway_identity_or_mounts_changed")
        namespace["command"] = mock.Mock()
        namespace["save_report"] = mock.Mock()
        tls = types.SimpleNamespace(tls_lock=lambda: contextlib.nullcontext())
        with mock.patch.dict(sys.modules, {"tls": tls}), mock.patch.object(namespace["signal"], "signal"), mock.patch.object(namespace["signal"], "setitimer", create=True), mock.patch.object(namespace["signal"], "SIGALRM", 14, create=True), mock.patch.object(namespace["signal"], "ITIMER_REAL", 0, create=True), mock.patch.object(namespace["time"], "sleep"), contextlib.redirect_stdout(io.StringIO()):
            code = namespace["main"]([mode])
        return code, namespace

    def test_fixed_consumer_has_no_key_or_arbitrary_command_input(self):
        source = ops.renewal_program().decode()
        compile(source, "consumer", "exec")
        self.assertIn("fullchain.pem", source)
        self.assertNotIn("privkey.pem", source)
        self.assertIn("configuration_may_reload", source)
        self.assertIn("loaded_certificate()==public", source)
        self.assertNotIn("shell=True", source)

    def test_unchanged_certificate_never_reloads(self):
        code, namespace = self.run_consumer("renew")
        self.assertEqual(code, 0)
        namespace["command"].assert_not_called()

    def test_changed_certificate_checks_then_reloads_then_confirms_loaded(self):
        code, namespace = self.run_consumer("renew", changed=True)
        self.assertEqual(code, 0)
        calls = namespace["command"].call_args_list
        self.assertEqual([call.args[0] for call in calls], ["nginx_test", "nginx_reload"])
        self.assertEqual(namespace["loaded_certificate"].call_count, 3)

    def test_check_mode_never_reloads_changed_certificate(self):
        code, namespace = self.run_consumer("check", changed=True)
        self.assertEqual(code, 2)
        namespace["command"].assert_not_called()

    def test_reload_waits_for_graceful_worker_without_reloading_again(self):
        code, namespace = self.run_consumer("renew", changed=True, delayed=True)
        self.assertEqual(code, 0)
        self.assertEqual(namespace["loaded_certificate"].call_count, 4)
        self.assertEqual([call.args[0] for call in namespace["command"].call_args_list], ["nginx_test", "nginx_reload"])

    def test_changed_gateway_stops_before_test_or_reload(self):
        code, namespace = self.run_consumer("renew", changed=True, rejected=True)
        self.assertEqual(code, 2)
        namespace["command"].assert_not_called()

    def test_unknown_existing_cron_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cron = root / "cron.d/community"
            cron.parent.mkdir()
            cron.write_bytes(b"existing-foreign-cron")
            (root / "state").mkdir()
            with mock.patch.multiple(ops, ROOT=root / "state", RENEW_CRON=cron):
                with self.assertRaisesRegex(ops.OperationError, "consumer_preimage_changed"):
                    ops.renewal_preflight({})
            self.assertEqual(cron.read_bytes(), b"existing-foreign-cron")

    def test_cron_is_atomically_published_and_prepublication_exit_is_recoverable(self):
        for interrupted in (False, True):
            with self.subTest(interrupted=interrupted), tempfile.TemporaryDirectory() as directory:
                main = Path(directory)
                root = main / ".deployment/community" / ops.APP
                source = root / "source"
                cron = main / "cron.d/community"
                cron.parent.mkdir()
                for name in ("forum.conf", "forum-main-redirects.conf"):
                    path = source / "deploy/nginx" / name
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(b"fixture-owned-nginx")
                tls = mock.Mock()
                tls.renewal_environment.return_value = {"cron_active": True, "cron_directory_available": True}
                state = {}
                with mock.patch.multiple(ops, MAIN=main, ROOT=root, SOURCE=source, RENEW_CRON=cron, PENDING=root / "pending.json"):
                    if interrupted:
                        with mock.patch.object(ops.os, "link", side_effect=RuntimeError("exit-before-publication")), self.assertRaisesRegex(RuntimeError, "before-publication"):
                            ops.install_renewal(state, tls)
                        self.assertFalse(cron.exists())
                    else:
                        ops.install_renewal(state, tls)
                        self.assertEqual(ops.digest(cron.read_bytes()), state["renewal"]["cron_sha256"])
                        self.assertEqual(cron.stat().st_nlink, 1)
                        self.assertFalse((root / "renew-community.cron").exists())
                    ops.remove_renewal(state)
                    self.assertFalse(cron.exists())
                    self.assertFalse((root / "renew-community.py").exists())
                    self.assertFalse((root / "renew-community.cron").exists())

    def test_cron_link_window_exit_remains_owned_and_recoverable(self):
        with tempfile.TemporaryDirectory() as directory:
            main = Path(directory)
            root = main / ".deployment/community" / ops.APP
            source = root / "source"
            cron = main / "cron.d/community"
            cron.parent.mkdir()
            for name in ("forum.conf", "forum-main-redirects.conf"):
                path = source / "deploy/nginx" / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"owned-nginx")
            tls = mock.Mock()
            tls.renewal_environment.return_value = {"cron_active": True, "cron_directory_available": True}
            state = {}
            original_unlink = Path.unlink
            def interrupted(path, *_args, **_kwargs):
                if path == root / "renew-community.cron":
                    raise RuntimeError("exit-after-link-before-unlink")
                return original_unlink(path, *_args, **_kwargs)
            with mock.patch.multiple(ops, MAIN=main, ROOT=root, SOURCE=source, RENEW_CRON=cron, PENDING=root / "pending.json"):
                with mock.patch.object(Path, "unlink", new=interrupted), self.assertRaisesRegex(RuntimeError, "after-link"):
                    ops.install_renewal(state, tls)
                self.assertEqual(cron.stat().st_nlink, 2)
                self.assertEqual({"device": cron.stat().st_dev, "inode": cron.stat().st_ino}, state["renewal"]["cron_identity"])
                ops.remove_renewal(state)
                self.assertFalse(cron.exists())
                self.assertFalse((root / "renew-community.py").exists())
                self.assertFalse((root / "renew-community.cron").exists())

    def test_identical_foreign_cron_collision_is_not_deleted(self):
        with tempfile.TemporaryDirectory() as directory:
            main = Path(directory)
            root = main / ".deployment/community" / ops.APP
            source = root / "source"
            cron = main / "cron.d/community"
            cron.parent.mkdir()
            for name in ("forum.conf", "forum-main-redirects.conf"):
                path = source / "deploy/nginx" / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"owned-nginx")
            tls = mock.Mock()
            tls.renewal_environment.return_value = {"cron_active": True, "cron_directory_available": True}
            state = {}
            def foreign_link(source_path, target):
                Path(target).write_bytes(Path(source_path).read_bytes())
                raise FileExistsError("simulated-foreign-identical-collision")
            with mock.patch.multiple(ops, MAIN=main, ROOT=root, SOURCE=source, RENEW_CRON=cron, PENDING=root / "pending.json"):
                with mock.patch.object(ops.os, "link", side_effect=foreign_link), self.assertRaises(FileExistsError):
                    ops.install_renewal(state, tls)
                with self.assertRaisesRegex(ops.OperationError, "cron_identity_changed"):
                    ops.remove_renewal(state)
                self.assertTrue(cron.exists())


class ProbeProtocolTests(unittest.TestCase):
    URL = "http://forum.pingxingxian.space/.well-known/acme-challenge/tools-probe-" + "a" * 32

    def verify(self, responses):
        opener = mock.Mock()
        opener.open.side_effect = responses
        with mock.patch.object(ops.urllib.request, "build_opener", return_value=opener), mock.patch.object(ops, "request_deadline", return_value=contextlib.nullcontext()):
            value = ops.verify_forum_probe(self.URL, b"token")
        return value, opener

    def response(self):
        response = mock.MagicMock()
        response.__enter__.return_value = response
        response.status = 200
        response.read.return_value = b"token"
        return response

    def test_legitimate_same_host_https_redirect_uses_project_headers(self):
        redirect = ops.urllib.error.HTTPError(self.URL, 301, "fixture", {"Location": self.URL.replace("http:", "https:")}, None)
        checks, opener = self.verify([redirect, self.response()])
        self.assertEqual([x["status"] for x in checks], [301, 200])
        self.assertTrue(checks[0]["same_host"])
        first = opener.open.call_args_list[0].args[0]
        second = opener.open.call_args_list[1].args[0]
        self.assertEqual(first.get_header("User-agent"), "ParallelLinesCommunityHTTP01/1")
        self.assertEqual(first.get_header("Cache-control"), "no-cache")
        self.assertEqual(second.full_url, self.URL.replace("http:", "https:"))

    def test_403_is_reported_explicitly_without_reading_body(self):
        error = ops.urllib.error.HTTPError(self.URL, 403, "fixture", {}, None)
        with self.assertRaises(ops.ProbeError) as caught:
            self.verify([error])
        self.assertEqual(str(caught.exception), "forum_http01_status_403")
        self.assertEqual(caught.exception.checks[0]["status"], 403)

    def test_cross_host_or_login_path_is_not_followed(self):
        for destination in ("https://outside.example/", "https://forum.pingxingxian.space/auth", self.URL + "?private=never-log"):
            with self.subTest(destination=destination):
                error = ops.urllib.error.HTTPError(self.URL, 302, "fixture", {"Location": destination}, None)
                with self.assertRaisesRegex(ops.ProbeError, "outside_fixed_contract") as caught:
                    self.verify([error])
                self.assertNotIn("never-log", str(caught.exception.checks))

    def test_redirect_chain_is_bounded(self):
        error = lambda: ops.urllib.error.HTTPError(self.URL, 302, "fixture", {"Location": self.URL}, None)
        with self.assertRaisesRegex(ops.ProbeError, "redirect_missing_or_limit") as caught:
            self.verify([error(), error(), error(), error()])
        self.assertEqual(len(caught.exception.checks), 4)


class TransactionModelTests(unittest.TestCase):
    def test_activation_and_independent_rollback_preserve_unrelated_services(self):
        for fail_nginx_test in (False, True):
            with self.subTest(fail_nginx_test=fail_nginx_test), tempfile.TemporaryDirectory() as directory, contextlib.ExitStack() as stack:
                main = Path(directory)
                root = main / ".deployment/community" / ops.APP
                source = root / "source"
                config = main / "deploy/nginx/default.conf"
                config.parent.mkdir(parents=True)
                config.write_bytes(b"old-config\n")
                cron = main / "cron.d/community"
                cron.parent.mkdir()
                paths = ["deploy/nginx/default.conf", "tracked.py", "new-file.py"]
                (main / "tracked.py").write_bytes(b"old-code")
                for name in paths:
                    path = source / name
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(b"candidate-" + name.encode())
                for name in ("forum.conf", "forum-main-redirects.conf"):
                    (source / "deploy/nginx" / name).write_bytes(b"owned-" + name.encode())
                data = main / "var.pre-data/untouched"
                data.parent.mkdir()
                data.write_bytes(b"historical-data")
                stack.enter_context(mock.patch.multiple(ops, MAIN=main, ROOT=root, SOURCE=source, MAIN_CONFIG=config,
                                    PENDING=root / "pending.json", CURRENT=root / "current.json",
                                    MARKER=main / ".deployment/forum-enabled", RENEW_CRON=cron,
                                    OLD_CONFIG=ops.digest(config.read_bytes()),
                                    NEW_CONFIG=ops.digest((source / "deploy/nginx/default.conf").read_bytes())))
                before = baseline_fixture()
                stat = config.stat()
                before["config_identity"] = {"device": stat.st_dev, "inode": stat.st_ino}
                before["config_sha256"] = ops.OLD_CONFIG
                before["approval_sha256"] = ops.digest(ops.approval_identity(before))
                before["forum_certificate_present"] = True
                before["api"].update(project="parallellines", service="api", image="old-api")
                before["gateway"].update(project="parallellines", service="nginx", image_id="sha256:" + "1" * 64)
                unrelated = [{"id": "2" * 64, "service": "web", "project": "parallellines"},
                             {"id": "3" * 64, "service": "db", "project": "parallellines"},
                             {"id": "4" * 64, "service": "api", "project": "some-other-project"}]
                before["other_container_ids"] = sorted([before["gateway"]["id"], *[x["id"] for x in unrelated]])
                prepared = {"source_revision": ops.APP, "candidate_database_revision": before["database_revision"],
                            "forum_image_id": "sha256:" + "f" * 64, "api_image_id": "sha256:" + "e" * 64}
                ops.save(root / "prepared.json", prepared)
                model = {"api": copy.deepcopy(before["api"]), "forum": None, "head": ops.BEFORE,
                         "index": ops.BEFORE, "layer": {}, "internal_verified": False, "nginx_test_failed": False}
                trace = []
                def records(_runner):
                    value = [copy.deepcopy(model["api"]), copy.deepcopy(before["gateway"]), *copy.deepcopy(unrelated)]
                    if model["forum"]:
                        value.append(copy.deepcopy(model["forum"]))
                    return value
                def fake_git(_runner, args, **_kwargs):
                    if args[0] == "rev-parse": return result(model["head"])
                    if args[0] == "symbolic-ref": return result("refs/heads/main")
                    if args[:3] == ["diff", "--cached", "--quiet"]: return result(code=0 if model["index"] == args[-1] else 1)
                    if args[0] == "read-tree": model["index"] = args[1]
                    if args[0] == "update-ref":
                        self.assertEqual(model["head"], args[3]); model["head"] = args[2]
                    return result("")
                def fake_compose(_runner, args, override=None):
                    self.assertEqual(args[:4], ["up", "-d", "--no-deps", "--no-build"])
                    target = args[-1]
                    self.assertIn(target, ("api", "forum-web"))
                    trace.append("up:" + target)
                    if target == "forum-web":
                        model["forum"] = {"id": "5" * 64, "project": "parallellines", "service": "forum-web",
                                          "image_id": prepared["forum_image_id"], "hash": "6" * 64, "running": True}
                    else:
                        restoring = Path(override).name == "restore.override.json"
                        model["api"].update(id="7" * 64 if restoring else "8" * 64,
                                            image_id=before["api"]["image_id"] if restoring else prepared["api_image_id"],
                                            hash="9" * 64 if restoring else "0" * 64,
                                            compose_files="owned-override", running=True)
                    return result()
                def fake_hash(_runner, name, override=None):
                    if name == "forum-web": return "6" * 64
                    return "9" * 64 if Path(override).name == "restore.override.json" else "0" * 64
                def internal(_runner, api):
                    self.assertEqual(api["image_id"], prepared["api_image_id"])
                    self.assertIsNotNone(model["forum"])
                    model["internal_verified"] = True
                    trace.append("internal-forum")
                    return {"forum_root_and_same_origin_api": True}
                def native(_runner, expected):
                    self.assertEqual(model["api"]["image_id"], expected)
                    self.assertTrue(model["api"]["running"])
                    return copy.deepcopy(model["api"])
                def command(label, arguments, **_kwargs):
                    trace.append(label)
                    if label == "bound_configuration_digest": return result(ops.digest(config.read_bytes()) + " config")
                    if label == "layer_symlink_guard": return result(code=1)
                    if label in ("layer_file_presence", "layer_file_absent"):
                        return result(code=0 if arguments[-1] in model["layer"] else 1)
                    if label == "layer_file_digest": return result(ops.digest(model["layer"][arguments[-1]]) + " file")
                    if label == "install_owned_layer_file":
                        self.assertTrue(model["internal_verified"])
                        model["layer"][arguments[-1].split(":", 1)[1]] = Path(arguments[-2]).read_bytes()
                    if label == "remove_owned_layer_file": model["layer"].pop(arguments[-1])
                    if label == "remove_owned_forum_instance":
                        self.assertEqual(arguments[-1], model["forum"]["id"]); model["forum"] = None
                    if label == "community_nginx_test" and fail_nginx_test and not model["nginx_test_failed"]:
                        model["nginx_test_failed"] = True
                        raise ops.OperationError("synthetic-nginx-test-failure")
                    return result("{}")
                runner = mock.Mock()
                runner.run.side_effect = command
                tls = mock.Mock()
                tls.configuration_may_reload.return_value = True
                tls.renewal_environment.return_value = {"cron_active": True, "cron_directory_available": True}
                stack.enter_context(mock.patch.object(ops, "inventory", side_effect=lambda _runner: copy.deepcopy(before)))
                stack.enter_context(mock.patch.object(ops, "source_prepare"))
                stack.enter_context(mock.patch.object(ops, "target_preimages", return_value=paths))
                stack.enter_context(mock.patch.object(ops, "git", side_effect=fake_git))
                stack.enter_context(mock.patch.object(ops, "compose", side_effect=fake_compose))
                stack.enter_context(mock.patch.object(ops, "compose_hash", side_effect=fake_hash))
                stack.enter_context(mock.patch.object(ops, "containers", side_effect=records))
                stack.enter_context(mock.patch.object(ops, "current_revision", return_value=before["database_revision"]))
                stack.enter_context(mock.patch.object(ops, "internal_forum", side_effect=internal))
                stack.enter_context(mock.patch.object(ops, "wait_api", side_effect=native))
                stack.enter_context(mock.patch.object(ops, "image_id", side_effect=lambda _runner, name: prepared["forum_image_id"] if name == ops.FORUM_IMAGE else prepared["api_image_id"]))
                stack.enter_context(mock.patch.object(ops, "tools_lock", side_effect=lambda: contextlib.nullcontext(tls)))
                stack.enter_context(mock.patch.object(ops, "health", return_value={"complete": True}))
                if fail_nginx_test:
                    with self.assertRaisesRegex(ops.OperationError, "synthetic-nginx"):
                        ops.deploy(runner, before["approval_sha256"])
                    self.assertTrue(ops.PENDING.exists())
                    self.assertNotIn("community_nginx_reload", trace)
                else:
                    report = ops.deploy(runner, before["approval_sha256"])
                    self.assertTrue(report["complete"])
                    self.assertTrue(report["gateway_not_recreated"])
                    self.assertTrue(ops.CURRENT.exists())
                    self.assertEqual(ops.MARKER.read_text(), ops.TAG + "\n")
                    self.assertTrue(cron.exists())
                    self.assertLess(trace.index("internal-forum"), trace.index("community_nginx_reload"))
                self.assertEqual(config.stat().st_ino, stat.st_ino)
                self.assertTrue(ops.restore(runner)["complete"])
                self.assertEqual(model["api"]["image_id"], before["api"]["image_id"])
                self.assertIsNone(model["forum"])
                self.assertEqual(model["head"], ops.BEFORE)
                self.assertEqual(config.read_bytes(), b"old-config\n")
                self.assertEqual(config.stat().st_ino, stat.st_ino)
                self.assertEqual((main / "tracked.py").read_bytes(), b"old-code")
                self.assertFalse((main / "new-file.py").exists())
                self.assertFalse(ops.MARKER.exists())
                self.assertFalse(cron.exists())
                self.assertEqual(data.read_bytes(), b"historical-data")


if __name__ == "__main__":
    unittest.main()

"""仅验证主站 Web 窄发布的新边界，不连接生产、Docker、GitHub 或数据库。"""

import contextlib
import hashlib
import importlib.util
import io
import urllib.request
import json
from pathlib import Path
import subprocess
import tempfile
import types
import unittest
from unittest.mock import patch


SPEC = importlib.util.spec_from_file_location("main_web", Path(__file__).with_name("main_web.py"))
MAIN = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MAIN)
CONFIG_SPEC = importlib.util.spec_from_file_location("managed_config", Path(__file__).with_name("managed_config.py"))
CONFIG = importlib.util.module_from_spec(CONFIG_SPEC)
CONFIG_SPEC.loader.exec_module(CONFIG)


class MainWebTests(unittest.TestCase):
    def test_restore_actual_caller_recovers_stopped_and_missing_after_owned_recreate(self):
        for missing in (False, True):
            with self.subTest(missing=missing), tempfile.TemporaryDirectory() as temp, contextlib.ExitStack() as stack:
                root = Path(temp)
                ops, state_dir, attempt = root / "ops", root / "ops/main-web", root / "releases/attempt"
                (attempt / "ops-before").mkdir(parents=True)
                state_dir.mkdir(parents=True)
                before = b"# main\n" + b"\n".join(CONFIG.OLD_TOOL_ENTRIES)
                fragment = CONFIG.BEGIN + b"\nserver { listen 443; }\n" + CONFIG.END + b"\n"
                configuration = root / "default.conf"
                configuration.write_bytes(before + fragment)
                (attempt / "gateway.before").write_bytes(before + fragment)
                (ops / "managed-vhost.conf").write_bytes(fragment)
                (ops / "tls.py").write_bytes(b"new consumer")
                (attempt / "ops-before/tls.py").write_bytes(b"old consumer")
                old_image, new_image = "sha256:" + "a" * 64, "sha256:" + "b" * 64
                old = {"id": "a" * 64, "image_id": old_image, "image": "parallellines-web:latest", "running": True,
                       "compose_files": "base,production", "memory": 0, "project": "parallellines", "service": "web"}
                override = str(attempt / "override.json")
                stopped = {**old, "id": "b" * 64, "image_id": new_image, "running": False,
                           "image": "parallellines-web:" + "d" * 40, "compose_files": old["compose_files"] + "," + override}
                restored = {**old, "id": "c" * 64}
                state = {"attempt": str(attempt), "revision": "d" * 40, "status": "switching_web", "gateway": {"id": "9" * 64},
                         "before_web": old, "image_id": new_image, "override": override,
                         "before_compose_hash": "e" * 64, "after_compose_hash": "f" * 64,
                         "before_redirects": None, "before_current": None, "consumer_hashes": {"tls.py": {
                             "before": hashlib.sha256(b"old consumer").hexdigest(), "after": hashlib.sha256(b"new consumer").hexdigest()}}}
                for name, value in {"APP": root, "OPS": ops, "STATE": state_dir, "PENDING": state_dir / "pending.json",
                                    "CURRENT": state_dir / "current.json", "REDIRECTS": state_dir / "redirects.json",
                                    "MAIN_CONFIG": configuration}.items():
                    stack.enter_context(patch.object(MAIN, name, value))
                MAIN.save(MAIN.PENDING, state)
                phase = {"restored": False}
                def run(label, arguments, **_options):
                    value = "" if missing else stopped["id"]
                    return subprocess.CompletedProcess(arguments, 0, value if label == "main_web_recovery_presence" else "", "")
                def start(_override=None):
                    phase["restored"] = True
                stack.enter_context(patch.object(MAIN, "modules", return_value=(None, types.SimpleNamespace(run_health=lambda: {"healthy": True}), CONFIG, None)))
                stack.enter_context(patch.object(MAIN, "guard"))
                stack.enter_context(patch.object(MAIN, "command", side_effect=run))
                stack.enter_context(patch.object(MAIN, "compose_hash", return_value="e" * 64))
                stack.enter_context(patch.object(MAIN, "running_hash", side_effect=lambda: ("e" if phase["restored"] else "f") * 64))
                stack.enter_context(patch.object(MAIN, "image_id", side_effect=lambda value: new_image if value.endswith(":latest") else value))
                metadata = stack.enter_context(patch.object(MAIN, "web_metadata", side_effect=lambda **_options: restored if phase["restored"] else stopped))
                up = stack.enter_context(patch.object(MAIN, "up", side_effect=start))
                wait = stack.enter_context(patch.object(MAIN, "wait_web", return_value=restored))
                report = {}
                MAIN.restore(state, report)
                up.assert_called_once_with()
                wait.assert_called_once_with(old_image)
                metadata.assert_any_call(require_running=False)
                self.assertTrue(report["recovery"]["complete"])
                self.assertFalse(MAIN.PENDING.exists())
                self.assertEqual((ops / "tls.py").read_bytes(), b"old consumer")

    def test_recovery_after_snapshot_rejects_successor_id_spec_or_hash(self):
        before = {"id": "a" * 64, "image_id": "sha256:" + "a" * 64, "image": "parallellines-web:latest",
                  "compose_files": "base,production", "running": True, "memory": 0}
        after = {**before, "id": "b" * 64, "image_id": "sha256:" + "b" * 64,
                 "image": "parallellines-web:" + "d" * 40, "compose_files": "base,production,/owned/override"}
        state = {"attempt": "/owned/attempt", "status": "committed", "before_web": before, "after_web": after,
                 "image_id": after["image_id"], "revision": "d" * 40, "override": "/owned/override", "after_compose_hash": "f" * 64}
        for value, digest in (({**after, "id": "c" * 64}, "f" * 64), ({**after, "memory": 512}, "f" * 64), (after, "0" * 64)):
            with self.subTest(value=value, digest=digest), \
                 patch.object(MAIN, "command", return_value=subprocess.CompletedProcess([], 0, value["id"], "")), \
                 patch.object(MAIN, "web_metadata", return_value=value), patch.object(MAIN, "running_hash", return_value=digest):
                with self.assertRaisesRegex(MAIN.MainWebError, "after_instance_or_spec_changed"):
                    MAIN.recovery_web(state)

    def test_recorded_two_exact_delta_preserves_other_bytes_and_rejects_foreign_changes(self):
        before = b"# main unchanged  \n" + b"\n".join(CONFIG.OLD_TOOL_ENTRIES) + b"# final unchanged\n"
        after = CONFIG.replace_tool_entries(before)
        fragment = CONFIG.BEGIN + b"\nserver { listen 443; }\n" + CONFIG.END + b"\n"
        record = {"schema": 1, "operation": "main-web-redirects", "revision": "a" * 40,
                  "before_outside_sha256": hashlib.sha256(before).hexdigest(),
                  "after_outside_sha256": hashlib.sha256(after).hexdigest()}
        self.assertEqual(CONFIG.replace_tool_entries(after, forward=False), before)
        self.assertTrue(CONFIG.owned_delta_allowed(after + fragment, before, fragment, record))
        self.assertTrue(CONFIG.owned_delta_allowed(after + fragment, after, fragment, record))
        self.assertFalse(CONFIG.owned_delta_allowed(after + fragment, before, fragment))
        self.assertFalse(CONFIG.owned_delta_allowed(b"# foreign\n" + after + fragment, before, fragment, record))
        self.assertFalse(CONFIG.owned_delta_allowed(after + fragment, before, None, record))
        for bad in (after + CONFIG.NEW_TOOL_ENTRIES[0], before.replace(CONFIG.OLD_TOOL_ENTRIES[0], CONFIG.NEW_TOOL_ENTRIES[0])):
            with self.assertRaises(CONFIG.ManagedConfigError):
                CONFIG.replace_tool_entries(bad)

    def test_up_uses_existing_project_and_only_web_without_build_pull_or_dependencies(self):
        base = ["docker", "compose", "--project-name", "parallellines", "--file", "original-compose.yml"]
        with patch.object(MAIN, "compose", return_value=base), patch.object(MAIN, "command") as run:
            MAIN.up(Path("/owned/image.override.json"))
        argv = run.call_args.args[1]
        self.assertEqual(argv[-1], "web")
        self.assertIn("--no-deps", argv)
        self.assertIn("--no-build", argv)
        self.assertEqual(argv[argv.index("--pull") + 1], "never")
        self.assertNotIn("--build", argv)
        self.assertNotIn("nginx", argv)

    def test_main_archive_download_uses_900_total_and_30_idle_without_retry(self):
        response = io.BytesIO(b"verified archive fixture")
        response.status = 200
        with tempfile.TemporaryDirectory() as temp, patch.object(MAIN, "owned", side_effect=Path), \
             patch.object(MAIN, "deadline", return_value=contextlib.nullcontext()) as total, \
             patch.object(MAIN.urllib.request, "build_opener") as opener, \
             patch("github_assets.request", side_effect=lambda url, _opener: urllib.request.Request(url)):
            opener.return_value.open.return_value = response
            target = Path(temp) / "archive.tar.gz"
            MAIN.download("https://github.com/public/release", target, 1024,
                          hashlib.sha256(response.getvalue()).hexdigest(), seconds=900)
            self.assertEqual(target.read_bytes(), b"verified archive fixture")
        total.assert_called_once_with(900)
        self.assertEqual(opener.return_value.open.call_args.kwargs["timeout"], 30)
        self.assertEqual(opener.return_value.open.call_count, 1)

    def test_restore_stops_before_any_mutation_when_gateway_was_replaced(self):
        with patch.object(MAIN, "modules", return_value=(None, None, CONFIG, None)), \
             patch.object(MAIN, "lease"), \
             patch.object(MAIN, "guard", side_effect=MAIN.MainWebError("gateway changed")), \
             patch.object(MAIN, "command") as run, patch.object(MAIN, "up") as up, \
             patch.object(MAIN, "atomic") as write, patch.object(MAIN, "save") as save:
            with self.assertRaisesRegex(MAIN.MainWebError, "gateway changed"):
                MAIN.restore({"attempt": "/owned/attempt", "gateway": {}}, {})
        self.assertFalse(run.called or up.called or write.called or save.called)

    def test_same_revision_later_attempt_cannot_be_restored_by_old_parent(self):
        with patch.object(MAIN, "modules", return_value=(None, None, CONFIG, None)), \
             patch.object(MAIN, "read", return_value={"attempt": "/owned/new-attempt"}), \
             patch.object(MAIN, "guard") as guard, patch.object(MAIN, "command") as run:
            with self.assertRaisesRegex(MAIN.MainWebError, "attempt_replaced"):
                MAIN.restore({"attempt": "/owned/old-attempt", "gateway": {}}, {})
        self.assertFalse(guard.called or run.called)

    def test_actual_same_inode_write_only_changes_two_exact_blocks(self):
        before = b"# preserved prefix  \n" + b"\n".join(CONFIG.OLD_TOOL_ENTRIES) + b"# preserved suffix\n"
        after = CONFIG.replace_tool_entries(before)
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "default.conf"
            target.write_bytes(before)
            info = target.stat()
            gateway = {"id": "a" * 64, "config_identity": {"device": info.st_dev, "inode": info.st_ino}}
            answer = hashlib.sha256(after).hexdigest() + "  default.conf\n"
            with patch.object(MAIN, "MAIN_CONFIG", target), patch.object(MAIN, "guard"), \
                 patch.object(MAIN, "command", return_value=subprocess.CompletedProcess([], 0, answer, "")):
                MAIN.write_config(before, after, gateway)
            self.assertEqual(target.read_bytes(), after)
            self.assertEqual(target.stat().st_ino, info.st_ino)

    def test_inventory_inspect_fields_exclude_environment_and_unbounded_labels(self):
        record = {"id": "a" * 64, "project": "parallellines", "service": "web", "running": True,
                  "networks": "parallellines_default ", "entrypoint": ["/docker-entrypoint.sh"],
                  "command": ["nginx", "-g", "daemon off;"], "healthcheck": {
                      "Test": ["CMD-SHELL", "wget -qO- http://127.0.0.1/ >/dev/null || exit 1"]}}
        def inspect(label, arguments, **_options):
            output = "parallellines_default" if label == "main_web_networks" else json.dumps(record)
            return subprocess.CompletedProcess(arguments, 0, output, "")
        with patch.object(MAIN, "command", side_effect=inspect) as run:
            self.assertEqual(MAIN.web_metadata()["service"], "web")
        template = run.call_args_list[0].args[1][3]
        self.assertNotIn(".Config.Env", template)
        self.assertNotIn("json .Config.Labels", template)
        self.assertIn("com.docker.compose.project", template)

    def test_optional_template_failure_reports_only_field_name(self):
        def inspect(_label, arguments, **_options):
            template = arguments[3]
            if ".Missing" in template:
                return subprocess.CompletedProcess(arguments, 1, "", "PRIVATE_ERROR_NOT_LOGGED")
            return subprocess.CompletedProcess(arguments, 0, "7", "")
        with patch.object(MAIN, "command", side_effect=inspect):
            values, unavailable = MAIN.inspect_fields("spec", {"valid": ".Known", "unsupported": ".Missing"}, optional=True)
        self.assertEqual(values, {"valid": 7})
        self.assertEqual(unavailable, ["unsupported"])

    def test_unknown_web_command_is_not_echoed(self):
        record = {"id": "a" * 64, "project": "parallellines", "service": "web", "running": True,
                  "networks": "parallellines_default", "entrypoint": ["private-command-value"], "command": []}
        def inspect(label, arguments, **_options):
            output = "parallellines_default" if label == "main_web_networks" else json.dumps(record)
            return subprocess.CompletedProcess(arguments, 0, output, "")
        with patch.object(MAIN, "command", side_effect=inspect):
            with self.assertRaisesRegex(MAIN.MainWebError, "^main_web_command_not_approved$"):
                MAIN.web_metadata()

    def test_unfinished_write_entry_is_not_exposed(self):
        with patch.object(MAIN, "inventory") as read, contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(MAIN.main(["deploy-main-web"]), 2)
        self.assertFalse(read.called)
        self.assertEqual(json.loads(output.getvalue())["errors"], ["unsupported_main_web_operation"])


if __name__ == "__main__":
    unittest.main()

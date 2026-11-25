"""只用本地替身验证 inventory 的白名单与固定操作，不连接 Docker、DNS 或服务器。"""

import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import textwrap
import unittest
from unittest.mock import patch


SPEC = importlib.util.spec_from_file_location("tools_inventory", Path(__file__).with_name("inventory.py"))
INVENTORY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(INVENTORY)


class InventoryTests(unittest.TestCase):
    def test_nginx_allowlist_does_not_export_secrets_or_private_key_paths(self):
        text = """# configuration file /etc/nginx/conf.d/default.conf:
server {
    listen 443 ssl;
    server_name pingxingxian.space;
    ssl_certificate /etc/letsencrypt/live/pingxingxian.space/fullchain.pem;
    ssl_certificate_key /SECRET_PRIVATE_KEY_LOCATION;
    proxy_set_header Authorization "Bearer SECRET_HEADER_VALUE";
    include /etc/nginx/conf.d/*.conf;
    location ^~ /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }
}
"""
        result = INVENTORY.summarize_nginx(text)
        serialized = json.dumps(result)
        self.assertIn("pingxingxian.space", serialized)
        self.assertIn("/var/www/certbot", serialized)
        self.assertNotIn("SECRET", serialized)
        self.assertNotIn("Authorization", serialized)
        self.assertNotIn("ssl_certificate_key", serialized)
        self.assertTrue(any(item["directive"] == "document_directory" for item in result))

    def test_other_operations_stop_before_any_inventory(self):
        with patch.object(INVENTORY, "storage_inventory") as storage:
            with contextlib.redirect_stdout(io.StringIO()) as stream:
                code = INVENTORY.main(["deploy"])
        self.assertEqual(code, 2)
        self.assertFalse(storage.called)
        self.assertEqual(json.loads(stream.getvalue())["operation"], "rejected")

    def test_reader_does_not_expose_stderr_on_failure(self):
        failed = subprocess.CompletedProcess(["docker"], 1, "", "SECRET_RUNTIME_VALUE")
        with patch.object(INVENTORY.subprocess, "run", return_value=failed):
            with self.assertRaisesRegex(INVENTORY.InventoryError, "docker_metadata:exit_1") as caught:
                INVENTORY.Reader().run("docker_metadata", ["docker", "ps"])
        self.assertNotIn("SECRET", str(caught.exception))

    def test_inspect_uses_selected_fields_not_environment(self):
        identifier = "a" * 64
        record = {"id": identifier, "name": "/parallellines-nginx-1", "image": "edge:test",
                  "state": "running", "service": "nginx", "project": "parallellines", "networks": "main official "}

        class FakeReader:
            def __init__(self):
                self.calls = []

            def run(self, label, arguments):
                self.calls.append(arguments)
                value = identifier + "\n" if label == "docker_ps" else json.dumps(record)
                return subprocess.CompletedProcess(arguments, 0, value, "")

        reader = FakeReader()
        result = INVENTORY.container_inventory(reader)
        self.assertEqual(result[0]["networks"], ["main", "official"])
        template = reader.calls[1][3]
        self.assertNotIn(".Config.Env", template)
        self.assertNotIn("json .Config.Labels", template)
        self.assertIn("com.docker.compose.service", template)

    def test_recovery_inventory_compares_exact_image_without_exporting_state(self):
        container = {"id": "c" * 64, "name": INVENTORY.TOOLS_NAME, "image": "parallellines-tools:123abcd",
                     "project": "parallellines-tools", "service": "tools-static", "networks": ["parallellines_default"]}
        image_id = "sha256:" + "a" * 64
        detail = {"image_id": image_id, "source": INVENTORY.TOOLS_SOURCE, "revision": "123abcd",
                  "running": True, "health": "healthy", "memory": 268435456, "cpu": 500000000, "pids": 64,
                  "read_only": True, "privileged": False, "ports": {}, "mount_types": ["tmpfs"]}

        class FakeReader:
            def run(self, label, arguments):
                return subprocess.CompletedProcess(arguments, 0, json.dumps(detail), "")

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            (root / "ops").mkdir()
            cron = root / "tools-cron"
            cron.write_bytes(b"private cron bytes")
            current_path = root / "ops/current.json"
            current = {"image_id": "sha256:" + "b" * 64, "applicationRevision": "e" * 40,
                       "cron_sha256": INVENTORY.hashlib.sha256(cron.read_bytes()).hexdigest(),
                       "private_example": "PRIVATE_RECORD"}
            current_path.write_text(json.dumps(current), encoding="utf-8")
            with patch.multiple(INVENTORY, TOOLS_ROOT=root, TOOLS_CRON=cron):
                observed = INVENTORY.tools_recovery_inventory(FakeReader(), [container])
                self.assertEqual(observed["revision_label"], "123abcd")
                self.assertTrue(observed["image_tag_matches_label"])
                self.assertTrue(observed["cron_matches_record"])
                self.assertTrue(observed["runtime_limits_match"])
                self.assertFalse(observed["recorded_image_matches"])
                self.assertFalse(observed["pending_present"])
                self.assertNotIn(image_id, json.dumps(observed))
                self.assertNotIn("PRIVATE_RECORD", json.dumps(observed))

                (root / "ops/pending.json").write_bytes(b"{}")
                current["image_id"] = image_id
                current_path.write_text(json.dumps(current), encoding="utf-8")
                cron.write_bytes(b"changed cron")
                observed = INVENTORY.tools_recovery_inventory(FakeReader(), [container])
                self.assertTrue(observed["recorded_image_matches"])
                self.assertTrue(observed["pending_present"])
                self.assertFalse(observed["cron_matches_record"])

    def test_recovery_inventory_reports_no_tools_without_reading_files(self):
        with patch.object(INVENTORY, "recovery_file") as recovery:
            self.assertEqual(INVENTORY.tools_recovery_inventory(None, []), {"container_present": False})
        recovery.assert_not_called()

    def test_transport_preserves_python_heredoc_without_line_injection(self):
        project = Path(__file__).resolve().parents[2]
        workflow = (project / ".github/workflows/tools-ops.yml").read_text(encoding="utf-8")
        self.assertIn("script_stop: false", workflow)
        self.assertNotIn("script_stop: true", workflow)
        runner_python = textwrap.dedent(
            workflow.split("          python3 - <<'PY'\n", 1)[1].split("\n          PY", 1)[0]
        )
        source = (project / "deploy/tools/inventory.py").read_text(encoding="utf-8")
        # 只执行 runner 侧的传输组装，输出到临时文件；不执行 inventory 或 SSH。
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "step-output"
            previous = Path.cwd()
            try:
                os.chdir(project)
                with patch.dict(os.environ, {"GITHUB_OUTPUT": str(output), "OPERATION": "inventory"}):
                    exec(compile(runner_python, "workflow-payload", "exec"), {})
            finally:
                os.chdir(previous)
            lines = output.read_text(encoding="utf-8").splitlines()
        output_marker = lines[0].removeprefix("script<<")
        self.assertEqual(lines[-1], output_marker)
        payload = "\n".join(lines[1:-1]) + "\n"
        self.assertTrue(payload.startswith("set -eu\nsudo -n python3 -B - inventory <<'"))
        self.assertNotIn("DRONE_SSH_PREV_COMMAND_EXIT_CODE", payload)
        command, body = payload.split("\n", 2)[1:]
        marker = command.split("<<'", 1)[1].removesuffix("'")
        self.assertTrue(body.endswith(marker + "\n"))
        self.assertEqual(body.removesuffix(marker + "\n"), source + "\n")


if __name__ == "__main__":
    unittest.main()

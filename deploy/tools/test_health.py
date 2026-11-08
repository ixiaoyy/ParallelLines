"""只用本地替身验证健康检查，不连接 Docker、DNS、HTTP 或生产服务器。"""

import contextlib
import importlib.util
import io
import json
from pathlib import Path
import ssl
import subprocess
import unittest
from unittest.mock import MagicMock, patch
import urllib.error


SPEC = importlib.util.spec_from_file_location("tools_health", Path(__file__).with_name("health.py"))
HEALTH = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(HEALTH)


class HealthTests(unittest.TestCase):
    def metadata(self, tools=False):
        return {"image_id": "sha256:" + "a" * 64, "running": True,
                "source": HEALTH.TOOLS_SOURCE if tools else None,
                "revision": "b" * 40 if tools else None, "networks": HEALTH.NETWORK + " "}

    def test_unknown_operation_does_not_probe(self):
        with patch.object(HEALTH, "run_health") as probe, contextlib.redirect_stdout(io.StringIO()) as stream:
            status = HEALTH.main(["deploy"])
        self.assertEqual(status, 2)
        probe.assert_not_called()
        self.assertEqual(json.loads(stream.getvalue())["operation"], "rejected")

    def test_selected_inspect_fields_exclude_environment(self):
        with patch.object(HEALTH, "command", return_value=json.dumps(self.metadata(True)).encode()) as command:
            result = HEALTH.container_metadata(HEALTH.TOOLS_CONTAINER, HEALTH.Budget(), True)
        arguments = command.call_args.args[0]
        self.assertEqual(arguments[:3], ["docker", "inspect", "--format"])
        self.assertNotIn(".Config.Env", arguments[3])
        self.assertNotIn("json .Config.Labels", arguments[3])
        self.assertEqual(result["networks"], [HEALTH.NETWORK])

    def test_wrong_source_is_a_failure(self):
        metadata = self.metadata(True)
        metadata["source"] = "unrelated"
        with patch.object(HEALTH, "command", return_value=json.dumps(metadata).encode()):
            with self.assertRaisesRegex(HEALTH.HealthError, "tools_source_label_mismatch"):
                HEALTH.container_metadata(HEALTH.TOOLS_CONTAINER, HEALTH.Budget(), True)

    def test_origin_tls_keeps_sni_host_and_verification(self):
        raw = MagicMock()
        tls_socket = MagicMock()
        context = MagicMock()
        context.wrap_socket.return_value = tls_socket
        with patch.object(HEALTH.socket, "create_connection", return_value=raw) as connect:
            connection = HEALTH.OriginHTTPSConnection(HEALTH.TOOLS_DOMAIN, timeout=6, context=context)
            connection.connect()
        connect.assert_called_once_with(("127.0.0.1", 443), timeout=6)
        context.wrap_socket.assert_called_once_with(raw, server_hostname=HEALTH.TOOLS_DOMAIN)
        self.assertEqual(connection.host, HEALTH.TOOLS_DOMAIN)
        self.assertIs(connection.sock, tls_socket)

        with patch.object(HEALTH, "OriginHTTPSConnection") as factory, patch.object(HEALTH.ssl, "create_default_context") as secure:
            factory.return_value.getresponse.return_value.status = 200
            factory.return_value.getresponse.return_value.read.return_value = b"ok\n"
            HEALTH.tools_origin_tls(HEALTH.Budget())
        secure.assert_called_once_with()
        factory.return_value.request.assert_called_once_with("GET", "/healthz", headers={"Host": HEALTH.TOOLS_DOMAIN})

    def test_public_client_does_not_follow_redirect(self):
        self.assertIsNone(HEALTH.NoRedirect().redirect_request(None, None, 302, "Found", {}, "https://elsewhere.invalid"))
        opener = MagicMock()
        opener.open.side_effect = urllib.error.HTTPError("https://tools.invalid", 302, "Found", {}, None)
        with patch.object(HEALTH.urllib.request, "build_opener", return_value=opener):
            with self.assertRaisesRegex(HEALTH.HealthError, "http_status_302"):
                HEALTH.public_get("https://" + HEALTH.TOOLS_DOMAIN + "/healthz", HEALTH.Budget(), True)
        self.assertEqual(opener.open.call_count, 1)

    def test_command_failure_never_exposes_stderr(self):
        result = subprocess.CompletedProcess(["docker"], 1, b"", b"PRIVATE_DIAGNOSTIC_VALUE")
        with patch.object(HEALTH.subprocess, "run", return_value=result):
            with self.assertRaisesRegex(HEALTH.HealthError, "command_exit_1") as caught:
                HEALTH.command(["docker", "inspect"], HEALTH.Budget())
        self.assertNotIn("PRIVATE", str(caught.exception))

    def test_gateway_http_requires_existing_204(self):
        with patch.object(HEALTH.http.client, "HTTPConnection") as factory:
            factory.return_value.getresponse.return_value.status = 204
            self.assertEqual(HEALTH.gateway_http(HEALTH.Budget()), {"status": 204})
            factory.return_value.getresponse.return_value.status = 200
            with self.assertRaisesRegex(HEALTH.HealthError, "gateway_http_status_200"):
                HEALTH.gateway_http(HEALTH.Budget())

    def test_check_matrix_success_with_local_stubs(self):
        patches = (
            patch.object(HEALTH, "check_deadline", side_effect=lambda _seconds: contextlib.nullcontext()),
            patch.object(HEALTH, "container_metadata", return_value={"running": True}),
            patch.object(HEALTH, "command", return_value=b"ok\n"),
            patch.object(HEALTH, "gateway_http", return_value={"status": 204}),
            patch.object(HEALTH, "tools_container_http", return_value={"body_matches": True}),
            patch.object(HEALTH, "tools_origin_tls", return_value={"ca_verified": True}),
            patch.object(HEALTH, "tools_public_health", return_value={"body_matches": True}),
            patch.object(HEALTH, "tools_public_title", return_value={"title_matches": True}),
            patch.object(HEALTH, "public_get", return_value=b""),
        )
        with contextlib.ExitStack() as stack:
            for entry in patches:
                stack.enter_context(entry)
            result = HEALTH.run_health()
        self.assertTrue(result["healthy"])
        self.assertEqual(len(result["checks"]), 12)
        self.assertEqual(result["errors"], [])

    def test_missing_container_is_not_success_and_skips_its_exec(self):
        def metadata(name, _budget, require_tools_source=False):
            if require_tools_source:
                raise HEALTH.HealthError("command_exit_1")
            return {"running": True}

        with contextlib.ExitStack() as stack:
            stack.enter_context(patch.object(HEALTH, "check_deadline", side_effect=lambda _seconds: contextlib.nullcontext()))
            stack.enter_context(patch.object(HEALTH, "container_metadata", side_effect=metadata))
            stack.enter_context(patch.object(HEALTH, "command", return_value=b""))
            for name in ("gateway_http", "tools_origin_tls", "tools_public_health", "tools_public_title"):
                stack.enter_context(patch.object(HEALTH, name, return_value={}))
            stack.enter_context(patch.object(HEALTH, "public_get", return_value=b""))
            tools_request = stack.enter_context(patch.object(HEALTH, "tools_container_http"))
            result = HEALTH.run_health()
        self.assertFalse(result["healthy"])
        tools_request.assert_not_called()
        self.assertTrue(any(item.get("skipped") == "tools_container_failed" for item in result["checks"]))
        self.assertIn("tools_container:command_exit_1", result["errors"])

    def test_wrong_public_title_fails_without_echoing_body(self):
        with patch.object(HEALTH, "public_get", return_value=b"<title>PRIVATE_WRONG_SITE</title>"):
            with self.assertRaisesRegex(HEALTH.HealthError, "public_title_mismatch") as caught:
                HEALTH.tools_public_title(HEALTH.Budget())
        self.assertNotIn("PRIVATE", str(caught.exception))


if __name__ == "__main__":
    unittest.main()

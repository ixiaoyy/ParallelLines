"""TLS 写阶段只在本地替身/临时目录验证，绝不访问生产、CA、Docker 或公网。"""

import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import patch
import urllib.error


SPEC = importlib.util.spec_from_file_location("tools_tls", Path(__file__).with_name("tls.py"))
TLS = importlib.util.module_from_spec(SPEC)
if sys.platform == "win32":
    # 生产已明确为 Linux；仅隔离 Windows 本地测试导入，不为生产增加锁降级。
    with patch.dict(sys.modules, {"fcntl": types.SimpleNamespace()}):
        SPEC.loader.exec_module(TLS)
else:
    SPEC.loader.exec_module(TLS)


class TlsTests(unittest.TestCase):
    def test_certbot_scope_is_dedicated_and_all_legacy_hooks_disabled(self):
        arguments = TLS.certbot_arguments("certonly")
        self.assertEqual(arguments[arguments.index("--config-dir") + 1], "/etc/letsencrypt/parallellines-tools")
        self.assertEqual(arguments[arguments.index("--config") + 1], "/dev/null")
        self.assertEqual(arguments[arguments.index("-d") + 1], TLS.DOMAIN)
        self.assertIn("--no-directory-hooks", arguments)
        self.assertIn("--register-unsafely-without-email", arguments)
        for option in ("--pre-hook", "--post-hook", "--deploy-hook"):
            self.assertEqual(arguments[arguments.index(option) + 1], "")
        self.assertNotIn("--nginx", arguments)
        self.assertNotIn("--standalone", arguments)
        self.assertNotIn("--force-renewal", arguments)

    def test_renewal_targets_one_certificate_without_random_sleep(self):
        arguments = TLS.certbot_arguments("renew")
        self.assertEqual(arguments[arguments.index("--cert-name") + 1], TLS.DOMAIN)
        self.assertIn("--no-random-sleep-on-renew", arguments)

    def test_preimage_mismatch_stops_before_any_write_or_container_command(self):
        report = {}
        with patch.object(TLS, "expected_preimage", return_value=(False, b"not output")), \
             patch.object(TLS, "backup_preimage") as backup, \
             patch.object(TLS, "context_preflight") as commands:
            with self.assertRaisesRegex(TLS.OperationError, "preimage"):
                TLS.prepare_tls("a" * 64, report)
        self.assertIs(report["expectedPreimage"], False)
        self.assertFalse(backup.called)
        self.assertFalse(commands.called)

    def test_missing_scheduler_does_not_request_a_one_time_certificate(self):
        report = {}
        with patch.object(TLS, "expected_preimage", return_value=(True, b"source")), \
             patch.object(TLS, "clean_main_configuration", return_value=True), \
             patch.object(TLS, "context_preflight", return_value={}), \
             patch.object(TLS, "renewal_environment", return_value={"cron_active": False, "cron_directory_available": True}), \
             patch.object(TLS, "backup_preimage") as backup, \
             patch.object(TLS, "request_certificate") as request:
            with self.assertRaisesRegex(TLS.OperationError, "scheduler"):
                TLS.prepare_tls("a" * 64, report)
        self.assertFalse(backup.called)
        self.assertFalse(request.called)

    def test_probe_cleanup_only_removes_its_owned_file(self):
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(TLS, "PUBLIC_DIRECTORY", Path(directory)), \
             patch.object(TLS.os, "fchmod", create=True):
            with TLS.owned_probe() as (url, body):
                file = Path(directory) / ".well-known/acme-challenge" / url.rsplit("/", 1)[1]
                self.assertEqual(file.read_bytes(), body)
            self.assertFalse(file.exists())

    def test_cross_domain_public_probe_redirect_is_rejected(self):
        opener = types.SimpleNamespace(open=lambda *_args, **_kwargs: (_ for _ in ()).throw(
            urllib.error.HTTPError("http://" + TLS.DOMAIN, 302, "redirect", {"Location": "http://example.org/"}, None)))
        with patch.object(TLS.urllib.request, "build_opener", return_value=opener):
            with self.assertRaisesRegex(TLS.OperationError, "outside_authorized_domain"):
                TLS.verify_public_probe("http://" + TLS.DOMAIN + "/.well-known/acme-challenge/test", b"probe")

    def test_renewal_reloads_only_after_changed_certificate_and_successful_config_test(self):
        certificate = types.SimpleNamespace(read_bytes=unittest.mock.Mock(side_effect=[b"before", b"after"]))
        report = {}
        with patch.object(TLS, "context_preflight", return_value={}), \
             patch.object(TLS, "clean_main_configuration", return_value=True), \
             patch.object(TLS, "certificate_status", return_value={"exists": True}), \
             patch.object(TLS, "tls_lock", return_value=contextlib.nullcontext()), \
             patch.object(TLS, "PUBLIC_CERTIFICATE", certificate), \
             patch.object(TLS, "request_certificate"), \
             patch.object(TLS, "command", return_value=subprocess.CompletedProcess([], 0, "", "")) as commands:
            TLS.renew_tools(report)
        self.assertTrue(report["gateway_reloaded"])
        self.assertEqual(commands.call_args_list[0].args[0], "nginx_test")
        self.assertEqual(commands.call_args_list[1].args[0], "nginx_reload")

    def test_unchanged_certificate_does_not_reload(self):
        report = {}
        certificate = types.SimpleNamespace(read_bytes=lambda: b"unchanged")
        with patch.object(TLS, "context_preflight", return_value={}), \
             patch.object(TLS, "clean_main_configuration", return_value=True), \
             patch.object(TLS, "certificate_status", return_value={"exists": True}), \
             patch.object(TLS, "tls_lock", return_value=contextlib.nullcontext()), \
             patch.object(TLS, "PUBLIC_CERTIFICATE", certificate), \
             patch.object(TLS, "request_certificate"), \
             patch.object(TLS, "command") as commands:
            TLS.renew_tools(report)
        self.assertFalse(report["gateway_reloaded"])
        self.assertFalse(commands.called)

    def test_unknown_operation_is_rejected_without_touching_the_server(self):
        with patch.object(TLS, "prepare_tls") as prepare, contextlib.redirect_stdout(io.StringIO()) as output:
            code = TLS.main(["deploy"])
        self.assertEqual(code, 2)
        self.assertFalse(prepare.called)
        self.assertEqual(json.loads(output.getvalue())["operation"], "rejected")


if __name__ == "__main__":
    unittest.main()

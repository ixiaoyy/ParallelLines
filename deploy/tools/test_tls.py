"""TLS 写阶段只在本地替身/临时目录验证，绝不访问生产、CA、Docker 或公网。"""

import contextlib
import hashlib
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
        report = {}
        with patch.object(TLS, "context_preflight", return_value={}), \
             patch.object(TLS, "clean_main_configuration", return_value=True), \
             patch.object(TLS, "certificate_status", return_value={"exists": True}), \
             patch.object(TLS, "tls_lock", return_value=contextlib.nullcontext()), \
             patch.object(TLS, "certificate_identity", side_effect=["a" * 64, "b" * 64]), \
             patch.object(TLS, "certificate_record", return_value=None), \
             patch.object(TLS, "save_certificate_record"), \
             patch.object(TLS, "confirm_loaded_certificate", return_value=True), \
             patch.object(TLS, "request_certificate"), \
             patch.object(TLS, "command", return_value=subprocess.CompletedProcess([], 0, "", "")) as commands:
            TLS.renew_tools(report)
        self.assertTrue(report["gateway_reloaded"])
        self.assertEqual(commands.call_args_list[0].args[0], "nginx_test")
        self.assertEqual(commands.call_args_list[1].args[0], "nginx_reload")

    def test_unchanged_certificate_does_not_reload(self):
        report = {}
        with patch.object(TLS, "context_preflight", return_value={}), \
             patch.object(TLS, "clean_main_configuration", return_value=True), \
             patch.object(TLS, "certificate_status", return_value={"exists": True}), \
             patch.object(TLS, "tls_lock", return_value=contextlib.nullcontext()), \
             patch.object(TLS, "certificate_identity", return_value="a" * 64), \
             patch.object(TLS, "certificate_record", return_value=None), \
             patch.object(TLS, "request_certificate"), patch.object(TLS, "command") as commands:
            TLS.renew_tools(report)
        self.assertFalse(report["gateway_reloaded"])
        self.assertFalse(commands.called)

    def test_failed_reload_keeps_identity_and_next_unchanged_run_retries(self):
        for failure in ("nginx_test", "nginx_reload", "confirmation"):
            with self.subTest(failure=failure):
                records = {"loaded": {"domain": TLS.DOMAIN, "identity": "a" * 64}}
                second = [False]

                def save(name, identity):
                    records[name] = {"domain": TLS.DOMAIN, "identity": identity}

                def confirm():
                    if failure == "confirmation" and not second[0]:
                        raise TLS.OperationError("origin_still_serves_previous_certificate")
                    save("loaded", "b" * 64)
                    records.pop("pending", None)
                    return True

                def command(label, arguments, **_kwargs):
                    if label == failure and not second[0]:
                        raise TLS.OperationError(label + ":exit_1")
                    return subprocess.CompletedProcess(arguments, 0, "", "")

                with patch.object(TLS, "context_preflight", return_value={}), \
                     patch.object(TLS, "configuration_may_reload", return_value=True), \
                     patch.object(TLS, "certificate_status", return_value={"exists": True}), \
                     patch.object(TLS, "tls_lock", side_effect=lambda: contextlib.nullcontext()), \
                     patch.object(TLS, "certificate_identity", side_effect=["a" * 64, "b" * 64, "b" * 64, "b" * 64]), \
                     patch.object(TLS, "certificate_record", side_effect=lambda name: records.get(name)), \
                     patch.object(TLS, "save_certificate_record", side_effect=save), \
                     patch.object(TLS, "confirm_loaded_certificate", side_effect=confirm), \
                     patch.object(TLS, "request_certificate"), patch.object(TLS, "command", side_effect=command) as commands:
                    with self.assertRaises(TLS.OperationError):
                        TLS.renew_tools({})
                    self.assertEqual(records["pending"]["identity"], "b" * 64)
                    self.assertEqual(records["loaded"]["identity"], "a" * 64)
                    second[0] = True
                    commands.reset_mock()
                    report = {}
                    TLS.renew_tools(report)
                    self.assertFalse(report["certificate_changed"])
                    self.assertTrue(report["gateway_reloaded"])
                    self.assertNotIn("pending", records)
                    self.assertEqual(records["loaded"]["identity"], "b" * 64)

    def test_origin_confirmation_uses_sni_and_only_then_records_loaded_identity(self):
        der = b"public-certificate-der"
        identity = hashlib.sha256(der).hexdigest()
        with tempfile.TemporaryDirectory() as temporary, \
             patch.object(TLS, "APPLICATION", Path(temporary)), \
             patch.object(TLS, "certificate_identity", return_value=identity), \
             patch.object(TLS.socket, "create_connection") as connect, \
             patch.object(TLS.ssl, "create_default_context") as context, \
             patch.object(TLS, "save_certificate_record") as save:
            context.return_value.wrap_socket.return_value.__enter__.return_value.getpeercert.return_value = der
            self.assertTrue(TLS.confirm_loaded_certificate())
        self.assertEqual(connect.call_args.args[0], ("127.0.0.1", 443))
        self.assertEqual(context.return_value.wrap_socket.call_args.kwargs["server_hostname"], TLS.DOMAIN)
        save.assert_called_once_with("loaded", identity)

    def test_unknown_operation_is_rejected_without_touching_the_server(self):
        with patch.object(TLS, "prepare_tls") as prepare, contextlib.redirect_stdout(io.StringIO()) as output:
            code = TLS.main(["deploy"])
        self.assertEqual(code, 2)
        self.assertFalse(prepare.called)
        self.assertEqual(json.loads(output.getvalue())["operation"], "rejected")


if __name__ == "__main__":
    unittest.main()

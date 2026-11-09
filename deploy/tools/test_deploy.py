"""仅用本地替身验证部署边界/字节恢复，不访问服务器、Docker、CA 或 GitHub。"""

import importlib.util
import contextlib
import io
import json
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import patch


with patch.dict(sys.modules, {"fcntl": types.SimpleNamespace()} if sys.platform == "win32" else {}):
    SPEC = importlib.util.spec_from_file_location("tools_deploy", Path(__file__).with_name("deploy.py"))
    DEPLOY = importlib.util.module_from_spec(SPEC)
    SPEC.loader.exec_module(DEPLOY)


class DeployTests(unittest.TestCase):
    def test_download_keeps_integrity_and_declared_network_bounds(self):
        data = b"small public fixture"
        response = io.BytesIO(data)
        response.status = 200
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(DEPLOY, "deadline", return_value=contextlib.nullcontext()) as bound, \
             patch.object(DEPLOY.urllib.request, "build_opener") as opener:
            opener.return_value.open.return_value = response
            target = Path(directory) / "toolbox-dist.tar.gz"
            self.assertEqual(DEPLOY.download("https://github.com/public/fixture", target, len(data), hashlib.sha256(data).hexdigest(), len(data)), len(data))
            self.assertEqual(target.read_bytes(), data)
            bound.assert_called_once_with(300)
            self.assertEqual(opener.return_value.open.call_args.kwargs["timeout"], 30)

    def test_download_reports_http_status_and_asset_without_response_body(self):
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(DEPLOY, "deadline", return_value=contextlib.nullcontext()), \
             patch.object(DEPLOY.urllib.request, "build_opener") as opener:
            opener.return_value.open.side_effect = DEPLOY.urllib.error.HTTPError("https://github.com/public/fixture", 504, "private response not logged", None, None)
            target = Path(directory) / "deployment-receipt.json"
            with self.assertRaisesRegex(DEPLOY.DeployError, "^release_download_http_504:deployment-receipt.json$"):
                DEPLOY.download("https://github.com/public/fixture", target, 10, "a" * 64)
            self.assertFalse(target.exists())

    def test_fixed_runtime_has_only_one_service_and_declared_resource_limits(self):
        spec = DEPLOY.compose_spec()
        self.assertEqual(set(spec["services"]), {"tools-static"})
        service = spec["services"]["tools-static"]
        self.assertEqual((service["cpus"], service["mem_limit"], service["pids_limit"]), (0.5, "256m", 64))
        self.assertTrue(service["read_only"])
        self.assertNotIn("env_file", service)
        self.assertNotIn("volumes", service)
        self.assertNotIn("ports", service)
        self.assertNotIn("build", service)
        self.assertNotIn("depends_on", service)

    def test_compose_never_builds_or_starts_dependencies_or_loads_env_file(self):
        with patch.object(DEPLOY, "run", return_value=subprocess.CompletedProcess([], 0, "", "")) as command:
            DEPLOY.up_application(Path("/owned/compose.json"), "sha256:" + "a" * 64)
        arguments = command.call_args.args[1]
        self.assertEqual(arguments[-1], "tools-static")
        self.assertIn("--no-deps", arguments)
        self.assertIn("--no-build", arguments)
        self.assertEqual(arguments[arguments.index("--env-file") + 1], "/dev/null")
        self.assertEqual(arguments[arguments.index("--pull") + 1], "never")

    def test_inplace_write_keeps_inode_and_preserves_other_bytes(self):
        before = b"# main untouched  \nserver { listen 80; }\n"
        after = before + b"# tools appended\n"
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "default.conf"
            target.write_bytes(before)
            inode = target.stat().st_ino
            answer = hashlib.sha256(after).hexdigest() + "  /etc/nginx/conf.d/default.conf\n"
            with patch.object(DEPLOY, "MAIN_CONFIG", target), \
                 patch.object(DEPLOY, "run", return_value=subprocess.CompletedProcess([], 0, answer, "")):
                DEPLOY.inplace_configuration(before, after)
            self.assertEqual(target.read_bytes(), after)
            self.assertEqual(target.stat().st_ino, inode)

    def test_changed_preimage_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "default.conf"
            target.write_bytes(b"foreign change\n")
            with patch.object(DEPLOY, "MAIN_CONFIG", target), patch.object(DEPLOY, "run") as command:
                with self.assertRaisesRegex(DEPLOY.DeployError, "changed_before"):
                    DEPLOY.inplace_configuration(b"old\n", b"candidate\n")
            self.assertEqual(target.read_bytes(), b"foreign change\n")
            self.assertFalse(command.called)

    def test_foreign_named_container_stops_before_service_mutation(self):
        identity = "a" * 64
        results = [subprocess.CompletedProcess([], 0, identity + "\n", ""),
                   subprocess.CompletedProcess([], 0, json.dumps({"source": "https://example.org/other"}), "")]
        with patch.object(DEPLOY, "run", side_effect=results) as command:
            with self.assertRaisesRegex(DEPLOY.DeployError, "another_source"):
                DEPLOY.tools_metadata()
        self.assertTrue(all("inspect" in call.args[1] or "ps" in call.args[1] for call in command.call_args_list))

    def transaction(self, fail_health=False):
        """整条事务用替身推进，实际文件仅位于测试临时目录。"""
        with tempfile.TemporaryDirectory() as temporary, contextlib.ExitStack() as stack:
            base = Path(temporary)
            app, ops = base / "tools", base / "tools/ops"
            config, cron = base / "default.conf", base / "tools.cron"
            before = b"# main whitespace preserved  \nserver { listen 80; }\n"
            config.write_bytes(before)
            fragment = b"# BEGIN parallellines-tools-managed\nserver { listen 443; }\n# END parallellines-tools-managed\n"
            image = "sha256:" + "b" * 64
            tag, application = "site-" + "a" * 40, "a" * 40
            record = {"schema": 1, "applicationRevision": application, "expectedTitle": "平行线工具箱",
                      "coreVersion": "fixture", "coreSourceURL": "https://example.org/source.tar.gz",
                      "nginxImage": "nginx@sha256:" + "c" * 64,
                      "bundle": {"file": "toolbox-dist.tar.gz", "sha256": "d" * 64, "bytes": 1,
                                 "url": DEPLOY.SOURCE_REPOSITORY + "/releases/download/" + tag + "/toolbox-dist.tar.gz"}}
            container = [None]
            lock_depth = [0]
            commands = []

            @contextlib.contextmanager
            def fake_lock():
                self.assertEqual(lock_depth[0], 0)
                lock_depth[0] += 1
                try:
                    yield
                finally:
                    lock_depth[0] -= 1

            def make_directory(path):
                Path(path).mkdir(parents=True, exist_ok=True)
                return Path(path)

            def fake_download(url, target, *_args):
                Path(target).write_bytes(json.dumps(record).encode() if url.endswith("deployment-receipt.json") else b"x")

            def fake_extract(_archive, destination):
                Path(destination).mkdir()

            def fake_run(label, arguments, **_kwargs):
                commands.append(label)
                output = ""
                if label == "copy_only_build":
                    Path(arguments[arguments.index("--iidfile") + 1]).write_text(image)
                    self.assertEqual(arguments[arguments.index("--network") + 1], "none")
                elif label == "gateway_binding_snapshot":
                    output = json.dumps({"id": "f" * 64, "mounts": [{"Type": "bind", "Source": str(config), "Destination": "/etc/nginx/conf.d/default.conf", "RW": False}], "networks": DEPLOY.NETWORK})
                elif label == "gateway_binding_inode":
                    stat = config.stat()
                    output = str(stat.st_dev) + ":" + str(stat.st_ino)
                elif label == "tools_compose_up":
                    container[0] = {"image": image, "running": True, "health": "healthy", "memory": 268435456,
                                    "cpu": 500000000, "pids": 64, "read_only": True, "privileged": False, "ports": {}}
                elif label == "tools_http_probe":
                    output = "ok\n"
                elif label == "gateway_bound_postimage":
                    output = hashlib.sha256(config.read_bytes()).hexdigest()
                elif label == "installed_renewal_consumer_check":
                    # 实际消费者是独立进程，父锁必须已释放，不得靠跳过子进程锁来过测试。
                    self.assertEqual(lock_depth[0], 0)
                    (ops / "last-renewal.json").write_text(json.dumps({"operation": "scheduled-renew", "complete": True}))
                elif label == "remove_only_new_owned_tools_container":
                    container[0] = None
                return subprocess.CompletedProcess(arguments, 0, output, "")

            replacements = {"APP": app, "OPS": ops, "CURRENT": ops / "current.json", "PENDING": ops / "pending.json",
                            "MAIN_CONFIG": config, "CRON": cron, "TIMEOUT": config}
            for name, value in replacements.items():
                stack.enter_context(patch.object(DEPLOY, name, value))
            stack.enter_context(patch.object(DEPLOY, "directory", side_effect=make_directory))
            stack.enter_context(patch.object(DEPLOY, "source_bundle", return_value={name: fragment.decode() if name == "vhost.conf" else "# fixture\n" for name in DEPLOY.SOURCE_NAMES}))
            stack.enter_context(patch.object(DEPLOY, "gateway_guard", return_value=(before, {"id": "f" * 64, "config_identity": {"device": config.stat().st_dev, "inode": config.stat().st_ino}})))
            stack.enter_context(patch.object(DEPLOY, "tools_metadata", side_effect=lambda: container[0]))
            stack.enter_context(patch.object(DEPLOY, "download", side_effect=fake_download))
            # 全部 IO 已是本地替身，不在 Windows 夹具模拟 Linux SIGALRM；生产时限不降级。
            stack.enter_context(patch.object(DEPLOY, "deadline", side_effect=lambda _seconds: contextlib.nullcontext()))
            stack.enter_context(patch.object(DEPLOY, "safe_extract_bundle", side_effect=fake_extract))
            stack.enter_context(patch.object(DEPLOY, "validate_descriptors", return_value=True))
            stack.enter_context(patch.object(DEPLOY, "verify_image", return_value=image))
            stack.enter_context(patch.object(DEPLOY, "known_configuration", return_value=True))
            stack.enter_context(patch.object(DEPLOY, "run", side_effect=fake_run))
            stack.enter_context(patch.object(DEPLOY.tls, "certificate_status", return_value={"valid_more_than_30_days": True}))
            stack.enter_context(patch.object(DEPLOY.tls, "renewal_environment", return_value={"cron_active": True, "cron_directory_available": True}))
            stack.enter_context(patch.object(DEPLOY.tls, "request_certificate"))
            stack.enter_context(patch.object(DEPLOY.tls, "confirm_loaded_certificate", return_value=True))
            stack.enter_context(patch.object(DEPLOY.tls, "tls_lock", side_effect=fake_lock))
            stack.enter_context(patch.object(DEPLOY.health, "run_health", return_value={"healthy": not fail_health}))
            report = {"complete": False}
            if fail_health:
                with self.assertRaisesRegex(DEPLOY.DeployError, "post_deploy_health_failed"):
                    DEPLOY.perform_deploy(tag, "e" * 64, "f" * 64, report)
                self.assertEqual(config.read_bytes(), before)
                self.assertIsNone(container[0])
                self.assertTrue(report["recovery"]["complete"])
                self.assertFalse((ops / "pending.json").exists())
            else:
                DEPLOY.perform_deploy(tag, "e" * 64, "f" * 64, report)
                self.assertEqual(config.read_bytes(), before + fragment)
                self.assertTrue(report["complete"])
                self.assertTrue((ops / "current.json").exists())
                self.assertFalse((ops / "pending.json").exists())
                self.assertLess(commands.index("nginx_test"), commands.index("nginx_reload"))
                self.assertIn("installed_renewal_consumer_check", commands)

    def test_complete_transaction_and_independent_consumer(self):
        self.transaction()

    def test_failed_health_restores_only_the_new_service_and_owned_fragment(self):
        self.transaction(fail_health=True)

    def recovery_fixture(self, temporary):
        app = Path(temporary) / "tools"
        attempt, ops = app / "releases" / ("a" * 40) / "attempts/test", app / "ops"
        attempt.mkdir(parents=True)
        ops.mkdir()
        before = b"# main preserved  \nserver { listen 80; }\n"
        fragment = b"# BEGIN parallellines-tools-managed\nserver { listen 443; }\n# END parallellines-tools-managed\n"
        config, backup = Path(temporary) / "default.conf", attempt / "before.conf"
        config.write_bytes(before)
        backup.write_bytes(before)
        state = {"schema": 1, "source": DEPLOY.SOURCE_REPOSITORY, "applicationRevision": "a" * 40,
                 "attempt": str(attempt), "before_config": str(backup), "new_fragment": fragment.decode(),
                 "image_id": "sha256:" + "b" * 64, "before_container": None, "before_current": None,
                 "before_saved_fragment": None, "before_cron_present": False, "gateway_id": "f" * 64,
                 "config_identity": {"device": config.stat().st_dev, "inode": config.stat().st_ino}}
        (ops / "pending.json").write_text(json.dumps(state))
        (attempt / "transaction.json").write_text(json.dumps(state))
        return app, attempt, ops, config, before, fragment, state

    def recovery_patches(self, stack, app, ops, config):
        for name, value in {"APP": app, "OPS": ops, "CURRENT": ops / "current.json", "PENDING": ops / "pending.json",
                            "CRON": ops / "unused.cron", "MAIN_CONFIG": config}.items():
            stack.enter_context(patch.object(DEPLOY, name, value))

    def recovery_command(self, config, label, arguments, changed_gateway=False):
        if label == "gateway_binding_snapshot":
            output = json.dumps({"id": ("e" if changed_gateway else "f") * 64, "mounts": [{"Type": "bind", "Source": str(config), "Destination": "/etc/nginx/conf.d/default.conf", "RW": False}], "networks": DEPLOY.NETWORK})
        elif label == "gateway_binding_inode":
            stat = config.stat()
            output = str(stat.st_dev) + ":" + str(stat.st_ino)
        else:
            output = hashlib.sha256(config.read_bytes()).hexdigest()
        return subprocess.CompletedProcess(arguments, 0, output, "")

    def test_interrupted_first_append_can_restore_only_the_proven_owned_partial_tail(self):
        with tempfile.TemporaryDirectory() as temporary, contextlib.ExitStack() as stack:
            app, attempt, ops, config, before, fragment, state = self.recovery_fixture(temporary)
            self.recovery_patches(stack, app, ops, config)
            stack.enter_context(patch.object(DEPLOY, "tools_metadata", return_value=None))
            stack.enter_context(patch.object(DEPLOY, "known_configuration", return_value=True))
            stack.enter_context(patch.object(DEPLOY, "run", side_effect=lambda label,args,**kw: self.recovery_command(config,label,args)))
            real_fdopen = os.fdopen
            truncations = []
            testcase = self

            class InterruptedAppend:
                def __init__(self, inner):
                    self.inner = inner
                def __enter__(self):
                    self.inner.__enter__()
                    return self
                def __exit__(self, *arguments):
                    return self.inner.__exit__(*arguments)
                def __getattr__(self, name):
                    return getattr(self.inner, name)
                def write(self, data):
                    testcase.assertEqual(self.inner.tell(), len(before))
                    self.inner.write(data[:55])
                    self.inner.flush()
                    raise InterruptedError("simulated termination after actual partial append")
                def truncate(self, *arguments):
                    truncations.append(arguments)
                    return self.inner.truncate(*arguments)

            with patch.object(DEPLOY.os, "fdopen", side_effect=lambda *args,**kw: InterruptedAppend(real_fdopen(*args,**kw))):
                with self.assertRaises(InterruptedError):
                    DEPLOY.inplace_configuration(before, before + fragment)
            self.assertEqual(truncations, [])
            self.assertEqual(config.read_bytes(), before + fragment[:55])
            self.assertEqual(config.stat().st_ino, state["config_identity"]["inode"])
            DEPLOY.restore_state(state, {})
            self.assertEqual(config.read_bytes(), before)

    def test_changed_gateway_stops_all_compensation_mutations(self):
        with tempfile.TemporaryDirectory() as temporary, contextlib.ExitStack() as stack:
            app, attempt, ops, config, before, fragment, state = self.recovery_fixture(temporary)
            self.recovery_patches(stack, app, ops, config)
            commands = stack.enter_context(patch.object(DEPLOY, "run", side_effect=lambda label,args,**kw: self.recovery_command(config,label,args,True)))
            metadata = stack.enter_context(patch.object(DEPLOY, "tools_metadata"))
            writer = stack.enter_context(patch.object(DEPLOY, "inplace_configuration"))
            state_writer = stack.enter_context(patch.object(DEPLOY, "atomic_bytes"))
            with self.assertRaisesRegex(DEPLOY.DeployError, "gateway_instance_changed"):
                DEPLOY.restore_state(state, {})
            self.assertFalse(metadata.called)
            self.assertFalse(writer.called)
            self.assertFalse(state_writer.called)
            self.assertEqual([item.args[0] for item in commands.call_args_list], ["gateway_binding_snapshot"])
            self.assertEqual(config.read_bytes(), before)
            self.assertTrue((ops / "pending.json").exists())

    def test_same_revision_new_attempt_cannot_be_rolled_back_by_old_compensation(self):
        with tempfile.TemporaryDirectory() as temporary, contextlib.ExitStack() as stack:
            app, attempt, ops, config, before, fragment, state = self.recovery_fixture(temporary)
            self.recovery_patches(stack, app, ops, config)
            newer = {**state, "attempt": str(attempt.with_name("new-attempt"))}
            (ops / "pending.json").write_text(json.dumps(newer))
            (ops / "current.json").write_text(json.dumps(newer))
            commands = stack.enter_context(patch.object(DEPLOY, "run"))
            writer = stack.enter_context(patch.object(DEPLOY, "atomic_bytes"))
            services = stack.enter_context(patch.object(DEPLOY, "tools_metadata"))
            with self.assertRaisesRegex(DEPLOY.DeployError, "attempt_replaced"):
                DEPLOY.restore_state(state, {})
            self.assertFalse(commands.called)
            self.assertFalse(writer.called)
            self.assertFalse(services.called)
            self.assertEqual(json.loads((ops / "pending.json").read_text())["attempt"], newer["attempt"])

    def test_same_bytes_replaced_inode_stops_compensation(self):
        with tempfile.TemporaryDirectory() as temporary, contextlib.ExitStack() as stack:
            app, attempt, ops, config, before, fragment, state = self.recovery_fixture(temporary)
            self.recovery_patches(stack, app, ops, config)
            replacement = config.with_name("replacement.conf")
            replacement.write_bytes(before)
            self.assertEqual(replacement.resolve().parent, config.resolve().parent)
            os.replace(replacement, config)
            commands = stack.enter_context(patch.object(DEPLOY, "run", side_effect=lambda label,args,**kw: self.recovery_command(config,label,args)))
            writer = stack.enter_context(patch.object(DEPLOY, "atomic_bytes"))
            services = stack.enter_context(patch.object(DEPLOY, "tools_metadata"))
            with self.assertRaisesRegex(DEPLOY.DeployError, "host_inode_changed"):
                DEPLOY.restore_state(state, {})
            self.assertFalse(writer.called)
            self.assertFalse(services.called)
            self.assertEqual(config.read_bytes(), before)
            self.assertTrue((ops / "pending.json").exists())

    def test_no_pending_new_same_sha_current_attempt_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as temporary, contextlib.ExitStack() as stack:
            app, attempt, ops, config, before, fragment, state = self.recovery_fixture(temporary)
            self.recovery_patches(stack, app, ops, config)
            (ops / "pending.json").unlink()
            newer = {**state, "attempt": str(attempt.with_name("new-attempt"))}
            (ops / "current.json").write_text(json.dumps(newer))
            commands = stack.enter_context(patch.object(DEPLOY, "run"))
            writer = stack.enter_context(patch.object(DEPLOY, "atomic_bytes"))
            with self.assertRaisesRegex(DEPLOY.DeployError, "attempt_is_not_current"):
                DEPLOY.restore_state(state, {})
            self.assertFalse(commands.called)
            self.assertFalse(writer.called)
            self.assertEqual(json.loads((ops / "current.json").read_text())["attempt"], newer["attempt"])


if __name__ == "__main__":
    unittest.main()

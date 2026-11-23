"""论坛部署选型的离线回归；sudo、证书和镜像全部使用临时替身。"""

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
HELPER = ROOT / ".github/scripts/select_compose_files.sh"
git = shutil.which("git")
git_shell = Path(git).resolve().parents[1] / "bin/bash.exe" if git else None
SHELL = str(git_shell) if git_shell and git_shell.is_file() else shutil.which("sh")


@unittest.skipUnless(SHELL, "需要本地 POSIX shell；不安装或启动外部运行环境")
class ForumComposeSelectionTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        for name in ("deploy/docker-compose.migration.yml", "docker-compose.forum.yml",
                     "docker-compose.gateway-sites.yml",
                     "deploy/nginx/forum.conf", "deploy/nginx/forum-main-redirects.conf",
                     "certificates/fullchain.pem", "certificates/privkey.pem"):
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("fixture-only\n", encoding="utf-8")
        for name in ("deploy/nginx/sites.d/00-include-sites.conf",
                     "deploy/nginx/sites.d/verify-gateway-sites.mjs"):
            target = self.root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / name, target)
        self.sites_dir = self.root / "host-sites.d"
        self.sites_dir.mkdir(parents=True, exist_ok=True)

    def enable(self, tag="forum-release-1"):
        marker = self.root / ".deployment/forum-enabled"
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text(tag + "\n", encoding="utf-8")

    def run_selection(self, *, image_present=True):
        # 替身只模拟固定的 sudo test 和 docker image inspect，不接触 Docker/服务器。
        script = '''
set -eu
sudo() {
    if test "$1" = test; then
        test -s "$FIXTURE_CERT_ROOT/${3##*/}"
    elif test "$1" = docker; then
        test "$FIXTURE_IMAGE_PRESENT" = 1
    else
        return 99
    fi
}
. "$HELPER"
printf '%s\n%s\n%s\n' "$COMPOSE_FILES" "$FORUM_ENABLED" "${FORUM_IMAGE_TAG:-unset}"
'''
        return subprocess.run(
            [SHELL, "-c", script], cwd=self.root, text=True, capture_output=True,
            timeout=10, env={**os.environ, "HELPER": HELPER.as_posix(),
                             "GATEWAY_SITES_DIR": self.sites_dir.as_posix(),
                             "FIXTURE_CERT_ROOT": (self.root / "certificates").as_posix(),
                             "FIXTURE_IMAGE_PRESENT": "1" if image_present else "0"},
        )

    def test_disabled_preserves_original_files_without_forum_prerequisites(self):
        shutil.rmtree(self.root / "certificates")
        (self.root / "docker-compose.forum.yml").unlink()
        result = self.run_selection(image_present=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.splitlines(), [
            "-f docker-compose.yml -f deploy/docker-compose.migration.yml", "false", "unset"])

    def test_enabled_preserves_existing_files_and_pins_independent_image(self):
        self.enable()
        result = self.run_selection()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.splitlines(), [
            "-f docker-compose.yml -f deploy/docker-compose.migration.yml -f docker-compose.forum.yml",
            "true", "forum-release-1"])

    def test_invalid_tags_are_not_executed_or_silently_ignored(self):
        for tag in ("", "$(touch injected)", "tag with spaces", "../other", "x\nsecond", "a" * 129):
            with self.subTest(tag=tag):
                self.enable(tag)
                result = self.run_selection()
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(result.stdout, "")
        self.assertFalse((self.root / "injected").exists())

    def test_directory_marker_is_rejected(self):
        (self.root / ".deployment/forum-enabled").mkdir(parents=True)
        result = self.run_selection()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("regular image-tag file", result.stderr)

    def test_missing_enabled_recipe_stops(self):
        self.enable()
        (self.root / "deploy/nginx/forum-main-redirects.conf").unlink()
        result = self.run_selection()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("missing recipe", result.stderr)

    def test_missing_enabled_certificate_stops(self):
        self.enable()
        (self.root / "certificates/privkey.pem").unlink()
        result = self.run_selection()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("certificate is missing", result.stderr)

    def test_missing_enabled_image_stops(self):
        self.enable()
        result = self.run_selection(image_present=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("image is not loaded", result.stderr)

    def test_helper_shell_syntax(self):
        result = subprocess.run([SHELL, "-n", str(HELPER)], capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_gateway_sites_marker_enforces_required_route_ownership(self):
        marker = self.root / ".deployment/gateway-sites-enabled"
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text(
            "parallellines-entertainment.conf=tavern.pingxingxian.space,matrix.pingxingxian.space\n",
            encoding="utf-8",
        )
        # Non-empty directory with another site only must be rejected
        (self.sites_dir / "other.conf").write_text(
            "server { server_name other.pingxingxian.space; }\n", encoding="utf-8"
        )
        failed = self.run_selection()
        self.assertNotEqual(failed.returncode, 0)
        self.assertIn("gateway sites preflight verification failed", failed.stderr)

        # Target file with exact Tavern + Matrix domains passes
        (self.sites_dir / "parallellines-entertainment.conf").write_text(
            "server { server_name tavern.pingxingxian.space matrix.pingxingxian.space; }\n",
            encoding="utf-8",
        )
        passed = self.run_selection()
        self.assertEqual(passed.returncode, 0, passed.stderr)
        self.assertIn("-f docker-compose.gateway-sites.yml", passed.stdout.splitlines()[0])


@unittest.skipUnless(SHELL, "需要本地 POSIX shell；不安装或启动外部运行环境")
class GatewayTlsActivationTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.lock = self.root / "tls.lock"
        self.lock.write_bytes(b"fixture-lock\n")
        self.trace = self.root / "trace"
        for name in ("real", "fallback", "active"):
            (self.root / name).mkdir()
        for filename in ("fullchain.pem", "privkey.pem"):
            for name in ("real", "fallback"):
                (self.root / name / filename).write_text("fixture-only", encoding="utf-8")
            (self.root / "active" / filename).write_text(
                (self.root / "fallback" / filename).as_posix() + "\n", encoding="utf-8", newline="\n")

    def run_activation(self, *, lock_status=0, test_status=0, reload_status=0, use_lock=True):
        source = (ROOT / "deploy/nginx/start-nginx.sh").read_text(encoding="utf-8")
        helpers, separator, _ = source.partition('\nmkdir -p "${FALLBACK_DIR}" "${ACTIVE_DIR}"\n')
        self.assertTrue(separator, "启动逻辑和证书切换函数须保持分离")
        self.assertIn("\nactivate_with_tls_lock()", helpers)
        # 只加载启动前的定义；模拟链接目标、FD 9 与 Nginx 调用，不依赖 Windows 建软链权限。
        script = helpers + r'''
REAL_CERT="$FIXTURE_ROOT/real/fullchain.pem"
REAL_KEY="$FIXTURE_ROOT/real/privkey.pem"
ACTIVE_CERT="$FIXTURE_ROOT/active/fullchain.pem"
ACTIVE_KEY="$FIXTURE_ROOT/active/privkey.pem"
flock() {
    [ "$*" = '-n -E 75 9' ] && [ "$(cat <&9)" = fixture-lock ] || return 99
    printf 'flock\n' >> "$FIXTURE_TRACE"
    return "$FIXTURE_LOCK_STATUS"
}
readlink() {
    cat "$1"
}
ln() {
    [ "$1" = '-sf' ] || return 98
    printf '%s\n' "$2" > "$3"
}
nginx() {
    [ "$(readlink "$ACTIVE_CERT")" = "$REAL_CERT" ] &&
        [ "$(readlink "$ACTIVE_KEY")" = "$REAL_KEY" ] || return 97
    printf 'nginx %s\n' "$*" >> "$FIXTURE_TRACE"
    case "$*" in
        '-t') return "$FIXTURE_TEST_STATUS" ;;
        '-s reload') return "$FIXTURE_RELOAD_STATUS" ;;
        *) return 96 ;;
    esac
}
activate_with_tls_lock
'''
        self.trace.write_text("", encoding="utf-8")
        env = {**os.environ, "FIXTURE_ROOT": self.root.as_posix(),
               "FIXTURE_TRACE": self.trace.as_posix(), "FIXTURE_LOCK_STATUS": str(lock_status),
               "FIXTURE_TEST_STATUS": str(test_status), "FIXTURE_RELOAD_STATUS": str(reload_status)}
        env.pop("GATEWAY_TLS_LOCK_FILE", None)
        if use_lock:
            env["GATEWAY_TLS_LOCK_FILE"] = self.lock.as_posix()
        return subprocess.run([SHELL, "-c", script], cwd=self.root, env=env,
                              capture_output=True, text=True, timeout=10)

    def assert_links_point_to(self, directory):
        for filename in ("fullchain.pem", "privkey.pem"):
            self.assertEqual((self.root / "active" / filename).read_text(encoding="utf-8").strip(),
                             (self.root / directory / filename).as_posix())

    def test_contended_lock_does_not_switch_links_or_reload(self):
        self.run_activation(lock_status=75)
        self.assertEqual(self.trace.read_text(encoding="utf-8").splitlines(), ["flock"])
        self.assert_links_point_to("fallback")

    def test_lock_then_switch_validate_reload_and_do_not_reload_twice(self):
        result = self.run_activation()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.trace.read_text(encoding="utf-8").splitlines(),
                         ["flock", "nginx -t", "nginx -s reload"])
        self.assert_links_point_to("real")

        result = self.run_activation()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.trace.read_text(encoding="utf-8").splitlines(), ["flock"])

    def test_reload_failure_restores_both_links_and_next_pass_retries(self):
        result = self.run_activation(reload_status=1)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.trace.read_text(encoding="utf-8").splitlines(),
                         ["flock", "nginx -t", "nginx -s reload"])
        self.assert_links_point_to("fallback")

        result = self.run_activation()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.trace.read_text(encoding="utf-8").splitlines(),
                         ["flock", "nginx -t", "nginx -s reload"])
        self.assert_links_point_to("real")

    def test_config_validation_failure_restores_links_without_reload(self):
        result = self.run_activation(test_status=1)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.trace.read_text(encoding="utf-8").splitlines(), ["flock", "nginx -t"])
        self.assert_links_point_to("fallback")

    def test_missing_production_lock_does_not_fall_back_to_unlocked_activation(self):
        self.lock.unlink()
        result = self.run_activation()
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.trace.read_text(encoding="utf-8"))
        self.assert_links_point_to("fallback")

    def test_symlink_production_lock_is_not_followed(self):
        target = self.lock.with_name("other.lock")
        self.lock.rename(target)
        try:
            self.lock.symlink_to(target)
        except OSError as error:
            if os.name == "nt" and error.winerror == 1314:
                self.skipTest("当前 Windows 用户不能创建软链接")
            raise
        result = self.run_activation()
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.trace.read_text(encoding="utf-8"))
        self.assert_links_point_to("fallback")

    def test_local_base_compose_can_activate_without_tools_lock(self):
        self.lock.unlink()
        result = self.run_activation(use_lock=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.trace.read_text(encoding="utf-8").splitlines(), ["nginx -t", "nginx -s reload"])
        self.assert_links_point_to("real")


class ForumWorkflowContractTests(unittest.TestCase):
    def test_production_only_mounts_existing_tools_tls_lock_read_only(self):
        compose = (ROOT / "deploy/docker-compose.migration.yml").read_text(encoding="utf-8")
        nginx = compose.split("\n  nginx:\n", 1)[1].split("\nnetworks:\n", 1)[0]
        self.assertIn("GATEWAY_TLS_LOCK_FILE: /run/parallellines-tls.lock", nginx)
        self.assertIn(
            "source: /opt/parallellines-tools/ops/tls.lock\n"
            "        target: /run/parallellines-tls.lock\n"
            "        read_only: true\n"
            "        bind: {create_host_path: false}", nginx,
        )
        base = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
        self.assertNotIn("GATEWAY_TLS_LOCK_FILE", base)

    def test_all_remote_deployment_paths_preserve_enabled_forum(self):
        workflow = (ROOT / ".github/workflows/deploy.yml").read_text(encoding="utf-8")
        self.assertEqual(workflow.count(". .github/scripts/select_compose_files.sh"), 1)
        self.assertNotIn('COMPOSE_FILES="-f docker-compose.yml', workflow)
        # 显式全栈恢复和正常前端替换仍接入论坛；增量路径缺网关时不隐式重建 Web。
        apply = workflow.split("        with: &apply_main_release\n", 1)[1].split(
            "      - name: Upload frontend image archive to server", 1)[0]
        self.assertIn('"parallellines-forum-web:$DEPLOY_REVISION" "parallellines-forum-web:$FORUM_IMAGE_TAG"', apply)
        self.assertIn("$COMPOSE $COMPOSE_FILES up -d --no-build", apply)
        self.assertIn("$COMPOSE $COMPOSE_FILES up -d --no-deps --no-build --force-recreate forum-web", workflow)
        self.assertIn('[ "$DEPLOY_JOB" != deploy-full-stack ] &&', apply)
        self.assertEqual(workflow.count("gateway is not running. Use the authorized manual full-stack Deploy"), 1)
        self.assertNotIn("$COMPOSE $COMPOSE_FILES up -d --build\n", workflow)
        self.assertNotIn("--build forum-web", workflow)


if __name__ == "__main__":
    unittest.main()

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
                     "deploy/nginx/forum.conf", "deploy/nginx/forum-main-redirects.conf",
                     "certificates/fullchain.pem", "certificates/privkey.pem"):
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("fixture-only\n", encoding="utf-8")

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


class ForumWorkflowContractTests(unittest.TestCase):
    def test_all_remote_deployment_paths_preserve_enabled_forum(self):
        workflow = (ROOT / ".github/workflows/deploy.yml").read_text(encoding="utf-8")
        self.assertEqual(workflow.count(". .github/scripts/select_compose_files.sh"), 4)
        self.assertNotIn('COMPOSE_FILES="-f docker-compose.yml', workflow)
        # 两个全量 bootstrap 使用锁定镜像，前端 bootstrap 单独恢复论坛静态容器。
        self.assertEqual(workflow.count("$COMPOSE $COMPOSE_FILES build api worker web nginx"), 2)
        self.assertIn("$COMPOSE $COMPOSE_FILES up -d --no-deps --no-build forum-web", workflow)
        self.assertNotIn("--build forum-web", workflow)


if __name__ == "__main__":
    unittest.main()

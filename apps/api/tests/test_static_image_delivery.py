"""离线核对静态图片清单与定向预览，不读取环境配置、不连接存储或数据库。"""

import argparse
import ast
import unittest
from contextlib import redirect_stdout
from dataclasses import dataclass
from io import StringIO
from pathlib import Path
from types import SimpleNamespace

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/upload_static_web_assets.py"


def load_manifest():
    """加载真实脚本的清单和筛选函数；外部配置及存储替换为禁止写入的本地边界。"""

    tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
    nodes = [
        node for node in tree.body
        if isinstance(node, (ast.Assign, ast.ClassDef, ast.FunctionDef))
    ]
    namespace = {
        "__file__": str(SCRIPT),
        "__name__": __name__,
        "Path": Path,
        "argparse": argparse,
        "dataclass": dataclass,
        "Settings": lambda: SimpleNamespace(upload_cdn_base_url="https://images.invalid"),
        "public_storage_url": lambda base, key: f"{base}/{key}",
    }

    def reject_storage(_settings):
        raise AssertionError("dry-run must not construct writable storage")

    namespace["S3UploadStorage"] = reject_storage
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(SCRIPT), "exec"), namespace)
    return namespace


class StaticImageDeliveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = load_manifest()

    def test_declared_sources_exist_and_keys_are_unique(self):
        assets = self.module["STATIC_ASSETS"]
        self.assertEqual(len(assets), len({asset.key for asset in assets}))
        root = self.module["repo_root"]()
        for asset in assets:
            with self.subTest(key=asset.key):
                self.assertTrue((root / asset.source).is_file())
                if asset.key.endswith(".webp"):
                    self.assertEqual(asset.media_type, "image/webp")
                    content = (root / asset.source).read_bytes()
                    self.assertEqual(content[:4], b"RIFF")
                    self.assertEqual(content[8:12], b"WEBP")

    def test_legacy_png_and_brand_addresses_remain_available(self):
        keys = {asset.key for asset in self.module["STATIC_ASSETS"]}
        for key in (
            "auth-visual/parallel-auth-pc-bg.png",
            "auth-visual/parallel-auth-h5-bg.png",
            "auth-visual/auth-mark.png",
            "private-space-entry-b7d15288.png",
        ):
            self.assertIn(key, keys)

    def test_catalog_preview_includes_public_webp_without_storage_access(self):
        output = StringIO()
        with redirect_stdout(output):
            self.module["upload_static_assets"](
                prefix="static/web", dry_run=True, verify=True,
                catalog_only=True, catalog_version="2026-10-30-folklore",
            )
        lines = output.getvalue().splitlines()
        uploads = [line for line in lines if line.startswith("would upload ")]
        self.assertEqual(len(uploads), 8)
        self.assertTrue(all("apps/web/public/catalog/2026-10-30-folklore/" in line
                            for line in uploads))
        self.assertTrue(all(".webp" in line for line in uploads))
        self.assertFalse(any("auth-visual" in line for line in lines))

    def test_existing_catalog_version_filter_is_preserved(self):
        output = StringIO()
        with redirect_stdout(output):
            self.module["upload_static_assets"](
                prefix="static/web", dry_run=True, verify=False,
                catalog_only=True, catalog_version="2026-11-03-v1",
            )
        uploads = [line for line in output.getvalue().splitlines()
                   if line.startswith("would upload ")]
        self.assertEqual(len(uploads), 5)
        self.assertTrue(all("static/web/catalog/2026-11-03-v1/" in line for line in uploads))
        # 四款原游戏封面保留，压缩后的新地址属于同一款游戏的独立发布版本。
        for filename in (
            "gd-spectrum.webp", "gd-fungi-run.webp", "gd-super-chicken-td.webp",
            "gd-golf-adventures-2.webp", "gd-super-chicken-td-optimized.webp",
        ):
            self.assertTrue(any(filename in line for line in uploads))

    def test_unknown_catalog_version_still_stops(self):
        with self.assertRaisesRegex(ValueError, "no catalog assets"):
            self.module["upload_static_assets"](
                prefix="static/web", dry_run=True, verify=False,
                catalog_only=True, catalog_version="missing-version",
            )

    def test_birdland_prefix_preview_does_not_touch_other_assets(self):
        output = StringIO()
        with redirect_stdout(output):
            self.module["upload_static_assets"](
                prefix="static/web", dry_run=True, verify=True,
                asset_prefix="games/birdland/2026-11-05-v1",
            )
        uploads = [line for line in output.getvalue().splitlines()
                   if line.startswith("would upload ")]
        self.assertEqual(len(uploads), 20)
        self.assertTrue(all("static/web/games/birdland/2026-11-05-v1/" in line
                            for line in uploads))
        self.assertTrue(all(".webp" in line for line in uploads))

    def test_invalid_prefix_and_mixed_filters_stop_before_storage(self):
        for prefix in ("", "/", "games/../birdland", "missing-version"):
            with self.subTest(prefix=prefix), self.assertRaises(ValueError):
                self.module["upload_static_assets"](
                    prefix="static/web", dry_run=True, verify=False, asset_prefix=prefix,
                )
        with self.assertRaisesRegex(ValueError, "cannot be combined"):
            self.module["upload_static_assets"](
                prefix="static/web", dry_run=True, verify=False,
                asset_prefix="games/birdland", catalog_only=True,
            )


if __name__ == "__main__":
    unittest.main()

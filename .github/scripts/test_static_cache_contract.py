"""离线核对共享 Nginx 静态缓存合同；不连接服务，实际 Nginx 另做运行验收。"""

from pathlib import Path
import re
import unittest


CONFIG = Path(__file__).resolve().parents[2] / "deploy/nginx/default.conf"


class StaticCacheContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = CONFIG.read_text(encoding="utf-8")
        body = cls.text.split("map $upstream_http_content_type $official_static_content_type {", 1)[1].split("\n}", 1)[0]
        cls.static_type = re.compile(re.search(r'"~\*(.+)" 1;', body).group(1), re.I)
        cls.policies = {}
        for name in ("chat", "api"):
            marker = f'map "$status:$official_static_content_type:$uri" $official_{name}_cache_control {{'
            body = cls.text.split(marker, 1)[1].split("\n}", 1)[0]
            default = re.search(r'default "([^"]+)";', body).group(1)
            matched = re.search(r'"~([^"]+)" "([^"]+)";', body)
            cls.policies[name] = (re.compile(matched.group(1)), matched.group(2), default)

    def policy(self, name, status, content_type, uri):
        """按 chat/api、状态、类型及路径返回配置里的 Cache-Control，不复制规则。"""
        pattern, public, default = self.policies[name]
        qualified = int(bool(self.static_type.match(content_type)))
        return public if pattern.match(f"{status}:{qualified}:{uri}") else default

    def test_current_svelte_fingerprint_shapes_keep_long_cache(self):
        # SvelteKit 同时产出 name.HASH 和纯 HASH.js，二者都必须保留缓存资格。
        cases = (
            ("text/javascript; charset=utf-8", "/_app/immutable/entry/start.ABCDef12.js"),
            ("text/javascript", "/_app/immutable/chunks/0fgqCtPx.js"),
            ("text/javascript", "/_app/immutable/workers/chunks/9wXp6ZBx.js"),
            ("text/css", "/_app/immutable/assets/Chat.tuQ10ys-.css"),
            ("font/woff2", "/_app/immutable/assets/KaTeX_AMS-Regular.BQhdFMY1.woff2"),
            ("application/wasm", "/_app/immutable/assets/module.ABCDef12.wasm"),
            ("application/javascript", "/_app/immutable/assets/worker.ABCDef12.mjs"),
        )
        for content_type, uri in cases:
            with self.subTest(uri=uri):
                self.assertEqual(self.policy("chat", 200, content_type, uri),
                                 "public, max-age=31536000, s-maxage=31536000, immutable")

    def test_vite_successful_static_files_keep_long_cache(self):
        for content_type, uri in (
            ("APPLICATION/JAVASCRIPT; charset=utf-8", "/assets/_baseUniq-CDJh-vEn.js"),
            ("text/css", "/assets/index-AbCd1234.css"),
            ("image/svg+xml", "/assets/logo-AbCd1234.svg"),
            ("application/octet-stream", "/assets/font-AbCd1234.woff2"),
        ):
            with self.subTest(uri=uri):
                self.assertEqual(self.policy("api", 200, content_type, uri),
                                 "public, max-age=31536000, immutable")

    def test_html_json_unknown_types_and_errors_never_get_long_cache(self):
        for name, uri in (("chat", "/_app/immutable/chunks/missing-ABCDEFGH.js"),
                          ("api", "/assets/missing-ABCDEFGH.js")):
            for content_type in ("text/html; charset=utf-8", "application/json", "text/plain", ""):
                with self.subTest(name=name, content_type=content_type):
                    self.assertEqual(self.policy(name, 200, content_type, uri), "no-store")
            for status in (304, 401, 403, 404, 500, 503):
                with self.subTest(name=name, status=status):
                    self.assertEqual(self.policy(name, status, "text/javascript", uri), "no-store")

    def test_maps_nonfingerprinted_paths_and_api_endpoints_are_not_public(self):
        for name, uri in (
            ("chat", "/_app/immutable/chunks/performance-missing-ABCDEFGH.js.map"),
            ("chat", "/_app/immutable/chunks/plain.js"),
            ("chat", "/api/config"),
            ("api", "/assets/plain.js"),
            ("api", "/api/status"),
            ("api", "/"),
        ):
            with self.subTest(name=name, uri=uri):
                self.assertEqual(self.policy(name, 200, "text/javascript", uri), "no-store")

    def test_actual_chat_location_preserves_authentication_isolation(self):
        block = self.text.split("location ^~ /_app/immutable/ {", 1)[1].split("\n    }", 1)[0]
        for directive in ('proxy_set_header Cookie "";', 'proxy_set_header Authorization "";',
                          "proxy_hide_header Set-Cookie;",
                          "add_header Cache-Control $official_chat_cache_control always;"):
            self.assertIn(directive, block)


if __name__ == "__main__":
    unittest.main()

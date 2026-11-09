import io
import json
import unittest
from unittest.mock import Mock
import github_assets


class AssetTests(unittest.TestCase):
    def test_same_published_asset_uses_anonymous_official_api(self):
        for repo, kind in [("ParallelLines", "main-web"), ("parallel-lines-tools", "site")]:
            tag = kind + "-" + "a" * 40
            data = io.BytesIO(json.dumps({"draft": False, "tag_name": tag, "assets": [{"name": "asset.gz", "state": "uploaded", "id": 123}]}).encode())
            data.status = 200
            opener = Mock(); opener.open.return_value = data
            request = github_assets.request("https://github.com/ixiaoyy/" + repo + "/releases/download/" + tag + "/asset.gz", opener)
            self.assertEqual(request.full_url, "https://api.github.com/repos/ixiaoyy/" + repo + "/releases/assets/123")
            self.assertEqual(request.get_header("Accept"), "application/octet-stream")
            self.assertIsNone(request.get_header("Authorization"))
            self.assertEqual(opener.open.call_args.kwargs["timeout"], 30)

    def test_unknown_host_is_rejected_before_network(self):
        opener = Mock()
        with self.assertRaises(ValueError):
            github_assets.request("https://example.com/asset.gz", opener)
        opener.open.assert_not_called()


if __name__ == "__main__": unittest.main()

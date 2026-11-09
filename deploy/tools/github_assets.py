"""固定公开发行资产的官方 API 传输；不认证、不切换版本或校验身份。"""
import json
import re
import urllib.parse
import urllib.request


def request(url, opener):
    """将已选定发行文件解析为同一公开资产；调用者继续执行原 hash/大小校验和总时限。"""
    parsed = urllib.parse.urlsplit(url)
    match = re.fullmatch(r"/ixiaoyy/(ParallelLines|parallel-lines-tools)/releases/download/((?:main-web|site)-[0-9a-f]{40})/([^/]+)", parsed.path)
    if parsed.scheme != "https" or parsed.hostname != "github.com" or parsed.username or parsed.password or parsed.port or parsed.query or parsed.fragment or match is None:
        raise ValueError("public_release_url_invalid")
    repo, tag, name = match.groups()
    if tag.startswith("main-web-") != (repo == "ParallelLines"):
        raise ValueError("public_release_repository_mismatch")
    base = "https://api.github.com/repos/ixiaoyy/" + repo + "/releases/"
    metadata = urllib.request.Request(base + "tags/" + tag, headers={"Accept": "application/vnd.github+json", "User-Agent": "ParallelLinesRelease/1"})
    with opener.open(metadata, timeout=30) as response:
        data = response.read(1024 * 1024 + 1)
        if response.status != 200 or len(data) > 1024 * 1024:
            raise ValueError("public_release_metadata_invalid")
    release = json.loads(data)
    if release.get("draft") is not False or release.get("tag_name") != tag:
        raise ValueError("public_release_not_published")
    assets = [a for a in release.get("assets", []) if a.get("name") == name and a.get("state") == "uploaded"]
    if len(assets) != 1 or type(assets[0].get("id")) is not int or assets[0]["id"] <= 0:
        raise ValueError("public_release_asset_not_unique")
    return urllib.request.Request(base + "assets/" + str(assets[0]["id"]), headers={"Accept": "application/octet-stream", "User-Agent": "ParallelLinesRelease/1"})

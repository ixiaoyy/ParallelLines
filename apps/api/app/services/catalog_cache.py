"""仅缓存无访客身份的公开目录；跨进程变更最多等待本地 60 秒 TTL。"""

from collections.abc import Hashable
from hashlib import sha256

from fastapi import Response

from app.core.response_cache import ResponseHotCache, cached_json_response

PUBLIC_CATALOG_CACHE_TTL_SECONDS = 60
_PUBLIC_CATALOG_RESPONSE_CACHE = ResponseHotCache[str](
    ttl_seconds=PUBLIC_CATALOG_CACHE_TTL_SECONDS, max_entries=256,
)
_cache_generation = 0


def read_public_catalog_cache(key: Hashable) -> tuple[str | None, int]:
    """按完整请求键读取 JSON 和本地代次；不包含 IP、令牌或个人评分。"""

    return _PUBLIC_CATALOG_RESPONSE_CACHE.get(key), _cache_generation


def store_public_catalog_cache(key: Hashable, content: str, generation: int) -> None:
    """仅保存成功 JSON；加载期间若已有提交失效，则拒绝旧快照重新进入缓存。"""

    if generation == _cache_generation:
        _PUBLIC_CATALOG_RESPONSE_CACHE.set(key, content)


def invalidate_public_catalog_cache() -> None:
    """在目录相关写事务成功后清理本进程缓存；不声称跨 worker 即时失效。"""

    global _cache_generation
    _cache_generation += 1
    _PUBLIC_CATALOG_RESPONSE_CACHE.clear()


def public_catalog_json_response(
    content: str, *, if_none_match: str | None, cache_status: str,
) -> Response:
    """返回公开 JSON 或协商缓存 304；ETag 只同步公开字节，不含访客身份。"""

    etag = f'"{sha256(content.encode("utf-8")).hexdigest()}"'
    headers = {
        "Cache-Control": "public, no-cache",
        "ETag": etag,
        "X-ParallelLines-Cache": cache_status,
    }
    # GET 的 If-None-Match 使用弱比较；浏览器继续复用既有响应正文。
    validators = (if_none_match or "").split(",")
    if any(value.strip().removeprefix("W/") in {etag, "*"} for value in validators):
        return Response(status_code=304, headers=headers)
    response = cached_json_response(
        content, cache_control=headers["Cache-Control"], cache_status=cache_status,
    )
    response.headers["ETag"] = etag
    return response

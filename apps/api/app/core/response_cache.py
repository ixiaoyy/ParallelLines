from __future__ import annotations

from collections.abc import Hashable
from time import monotonic


class ResponseHotCache[T]:
    """Small in-process TTL cache for hot API response objects.

    Key parameters are `ttl_seconds` and `max_entries`. Return values are read
    with `get()` and stored with `set()`. Side effects are intentionally limited
    to this process memory, so stale data naturally expires without cross-worker
    invalidation.
    """

    def __init__(self, *, ttl_seconds: int, max_entries: int = 128) -> None:
        """Create an empty response cache.

        `ttl_seconds` controls freshness, and `max_entries` caps memory use.
        The constructor only initializes local process state.
        """
        self.ttl_seconds = ttl_seconds
        self.max_entries = max_entries
        self._entries: dict[Hashable, tuple[float, T]] = {}

    def get(self, key: Hashable) -> T | None:
        """Read a fresh cached value for `key`.

        Return value is the cached response object, or `None` on miss/expiry.
        Side effect: removes the expired entry for this key.
        """
        cached = self._entries.get(key)
        if cached is None:
            return None
        expires_at, value = cached
        if expires_at <= monotonic():
            self._entries.pop(key, None)
            return None
        return value

    def set(self, key: Hashable, value: T) -> None:
        """Store `value` under `key` until this cache's TTL expires.

        Key parameter `key` must be hashable. Side effects: expired entries are
        pruned, and the cache is cleared if it reaches `max_entries`.
        """
        now = monotonic()
        self._prune_expired(now)
        if len(self._entries) >= self.max_entries:
            self._entries.clear()
        self._entries[key] = (now + self.ttl_seconds, value)

    def clear(self) -> None:
        """Remove every cached response from this in-process hot cache.

        There are no parameters and no return value. Side effect: all entries in
        this process are invalidated immediately after write actions that change
        list or counter responses.
        """
        self._entries.clear()

    def _prune_expired(self, now: float) -> None:
        """Remove expired entries using caller-supplied monotonic time `now`.

        Return value is `None`. Side effect: mutates only this cache's internal
        entry dictionary.
        """
        expired_keys = [
            key for key, (expires_at, _value) in self._entries.items() if expires_at <= now
        ]
        for key in expired_keys:
            self._entries.pop(key, None)


# Scope caches by authenticated user to avoid leaking private-board visibility.
def user_cache_scope(current_user: object | None) -> str:
    """Return the hot-cache visibility scope for `current_user`.

    Anonymous requests share one scope; authenticated requests are per-user.
    The function has no side effects.
    """
    user_id = getattr(current_user, "id", None)
    return f"user:{user_id}" if user_id is not None else "anonymous"


# Produce matching browser cache headers for anonymous and authenticated requests.
def scoped_cache_control(
    current_user: object | None,
    *,
    max_age: int,
    stale_while_revalidate: int,
) -> str:
    """Return a Cache-Control header value for scoped API responses.

    Key parameters are freshness seconds and stale revalidation seconds. Return
    value is public for anonymous traffic and private for authenticated traffic;
    the function has no side effects.
    """
    visibility = "private" if current_user is not None else "public"
    return f"{visibility}, max-age={max_age}, stale-while-revalidate={stale_while_revalidate}"

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import parse_qs, urlsplit

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.visitors import visitor_key_for_anonymous, visitor_key_for_user
from app.models.analytics import SiteVisit
from app.models.user import User
from app.schemas.analytics import SiteVisitCreateRequest, SiteVisitRecordResponse

SEARCH_HOST_MARKERS = (
    "baidu.",
    "bing.",
    "duckduckgo.",
    "google.",
    "sogou.",
    "so.com",
    "yahoo.",
)
SOCIAL_HOST_MARKERS = (
    "bilibili.com",
    "douban.com",
    "facebook.com",
    "juejin.cn",
    "linkedin.com",
    "reddit.com",
    "sspai.com",
    "toutiao.com",
    "twitter.com",
    "v2ex.com",
    "weibo.com",
    "wechat.com",
    "weixin.qq.com",
    "x.com",
    "xiaohongshu.com",
    "zhihu.com",
)
BOT_USER_AGENT_MARKERS = (
    "bot",
    "crawler",
    "spider",
    "slurp",
    "headlesschrome",
    "curl/",
    "wget/",
    "python-requests",
    "go-http-client",
)


@dataclass(frozen=True)
class VisitSource:
    source_type: str
    source_name: str
    referrer_host: str | None


class SiteVisitService:
    def __init__(self, session: AsyncSession) -> None:
        """Create a site visit service bound to one database session.

        Key parameter `session` is the request-scoped async session. Return
        value is none. Side effect: stores the session reference.
        """

        self.session = session

    async def record_visit(
        self,
        payload: SiteVisitCreateRequest,
        *,
        visitor_id: str | None,
        current_user: User | None,
        origin: str | None,
        request_host: str | None,
        user_agent: str | None,
    ) -> SiteVisitRecordResponse:
        """Persist one site page-view event for traffic analytics.

        Key parameters are the frontend payload, optional anonymous visitor id,
        optional authenticated user, request origin/host, and user agent used to
        reject known automation. Return value reports whether an event was
        stored. Side effect: inserts a `site_visits` row and commits it.
        """

        if is_probable_bot_user_agent(user_agent):
            return SiteVisitRecordResponse(recorded=False)

        visitor_key = self._visitor_key(visitor_id=visitor_id, current_user=current_user)
        path = normalize_site_visit_path(
            payload.path,
            origin=origin,
            request_host=request_host,
        )
        if visitor_key is None or path is None:
            return SiteVisitRecordResponse(recorded=False)

        utm_params = parse_qs(urlsplit(path).query)
        source = classify_visit_source(
            referrer=payload.referrer,
            utm_source=first_query_value(utm_params, "utm_source", 128),
            origin=origin,
            request_host=request_host,
        )
        visit = SiteVisit(
            visitor_key=visitor_key,
            user_id=current_user.id if current_user is not None else None,
            path=path,
            title=trim_or_none(payload.title, 180),
            referrer_host=source.referrer_host,
            source_type=source.source_type,
            source_name=source.source_name,
            utm_source=first_query_value(utm_params, "utm_source", 128),
            utm_medium=first_query_value(utm_params, "utm_medium", 128),
            utm_campaign=first_query_value(utm_params, "utm_campaign", 180),
        )
        self.session.add(visit)
        await self.session.commit()
        return SiteVisitRecordResponse(recorded=True)

    def _visitor_key(self, *, visitor_id: str | None, current_user: User | None) -> str | None:
        """Resolve the privacy-preserving visitor key for this request.

        Key parameters are the authenticated user and browser visitor id. Return
        value is the stable hash key stored in analytics, or None when the
        anonymous id is absent/invalid. Side effect: none.
        """

        if current_user is not None:
            return visitor_key_for_user(current_user.id)
        return visitor_key_for_anonymous(visitor_id)


def is_probable_bot_user_agent(user_agent: str | None) -> bool:
    """Return whether a request identifies as a known crawler or automation client.

    Key parameter `user_agent` is the request header. Return value is true only
    for conservative marker matches. Side effect: none.
    """

    normalized = (user_agent or "").strip().lower()
    return bool(normalized) and any(marker in normalized for marker in BOT_USER_AGENT_MARKERS)


def normalize_site_visit_path(
    path: str,
    *,
    origin: str | None,
    request_host: str | None,
) -> str | None:
    """Normalize a browser location into an internal site path.

    Key parameters include `path` and the trusted origin/request host used to
    reject absolute external URLs. Return value keeps path plus query without
    the fragment, capped for storage, or None when the value is not an internal
    HTTP path. Side effect: none.
    """

    raw_path = path.strip()
    if not raw_path:
        return None

    parsed = urlsplit(raw_path)
    if parsed.scheme or parsed.netloc:
        if parsed.scheme not in {"http", "https"}:
            return None
        path_host = normalize_host(parsed.hostname)
        internal_hosts = {
            host
            for host in (normalize_host_from_url(origin), normalize_host(request_host))
            if host is not None
        }
        if internal_hosts and path_host not in internal_hosts:
            return None
        normalized = f"{parsed.path or '/'}"
        if parsed.query:
            normalized = f"{normalized}?{parsed.query}"
    else:
        normalized = raw_path.split("#", 1)[0]

    if not normalized.startswith("/") or normalized.startswith("//"):
        return None
    return normalized[:512]


def classify_visit_source(
    *,
    referrer: str | None,
    utm_source: str | None,
    origin: str | None,
    request_host: str | None,
) -> VisitSource:
    """Classify a visit source for acquisition reporting.

    Key parameters include the browser referrer, optional UTM source, frontend
    origin, and API request host. Return value contains source type/name and the
    normalized referrer host. Side effect: none.
    """

    referrer_host = normalize_host_from_url(referrer)
    if utm_source:
        return VisitSource("campaign", utm_source, referrer_host)
    if referrer_host is None:
        return VisitSource("direct", "Direct", None)

    internal_hosts = {
        host
        for host in (normalize_host_from_url(origin), normalize_host(request_host))
        if host is not None
    }
    if referrer_host in internal_hosts:
        return VisitSource("internal", "Internal", referrer_host)
    if any(marker in referrer_host for marker in SEARCH_HOST_MARKERS):
        return VisitSource("search", referrer_host, referrer_host)
    if any(marker in referrer_host for marker in SOCIAL_HOST_MARKERS):
        return VisitSource("social", referrer_host, referrer_host)
    return VisitSource("referral", referrer_host, referrer_host)


def first_query_value(
    params: dict[str, list[str]],
    key: str,
    max_length: int,
) -> str | None:
    """Return the first non-empty query value for a bounded analytics field.

    Key parameters are parsed query params, the desired key, and maximum stored
    length. Return value is trimmed text or None. Side effect: none.
    """

    for value in params.get(key, []):
        normalized = trim_or_none(value, max_length)
        if normalized is not None:
            return normalized
    return None


def normalize_host_from_url(url: str | None) -> str | None:
    """Extract and normalize the host from an absolute URL-like value.

    Key parameter `url` is a browser-provided URL such as referrer or origin.
    Return value is a lowercase host without leading `www.`, or None when the
    URL is empty/unparseable. Side effect: none.
    """

    raw_url = (url or "").strip()
    if not raw_url:
        return None
    try:
        parsed = urlsplit(raw_url)
    except ValueError:
        return None
    return normalize_host(parsed.hostname)


def normalize_host(host: str | None) -> str | None:
    """Normalize a hostname for same-site and source comparisons.

    Key parameter `host` may include mixed case or a leading `www.`. Return
    value is the comparable host string, or None when empty. Side effect: none.
    """

    normalized = (host or "").strip().lower().rstrip(".")
    if not normalized:
        return None
    if normalized.startswith("www."):
        return normalized[4:]
    return normalized


def trim_or_none(value: str | None, max_length: int) -> str | None:
    """Trim optional text for analytics storage.

    Key parameters are the optional text and maximum length. Return value is
    trimmed text capped to length, or None for blank input. Side effect: none.
    """

    normalized = (value or "").strip()
    if not normalized:
        return None
    return normalized[:max_length]

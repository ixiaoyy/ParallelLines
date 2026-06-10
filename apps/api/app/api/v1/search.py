from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Query, Response

from app.api.v1.dependencies import OptionalCurrentUserDep, SessionDep
from app.core.response_cache import ResponseHotCache, user_cache_scope
from app.schemas.common import ApiResponse
from app.schemas.forum import TopicResponse, TopicSort
from app.services.search import SearchFilters, SearchService, normalize_search_query
from app.services.topic_cursor import encode_topic_cursor

router = APIRouter(prefix="/search", tags=["search"])

SEARCH_RESPONSE_CACHE_TTL_SECONDS = 15

_SEARCH_RESPONSE_CACHE = ResponseHotCache[tuple[str, int]](
    ttl_seconds=SEARCH_RESPONSE_CACHE_TTL_SECONDS,
    max_entries=256,
)


def invalidate_search_response_cache() -> None:
    """Clear cached search response JSON after searchable content changes.

    There are no parameters and no return value. Side effect: invalidates this
    process' short-lived `/search` response cache while preserving per-request
    search-log writes.
    """

    _SEARCH_RESPONSE_CACHE.clear()


# Return JSON without client caching so every search still reaches the API logger.
def _json_search_response(content: str, *, cache_status: str) -> Response:
    """Build a JSON search response with server-cache observability headers.

    Key parameters are encoded JSON `content` and cache hit/miss status. Return
    value is a FastAPI response; side effect is none.
    """

    return Response(
        content=content,
        media_type="application/json",
        headers={
            "Cache-Control": "no-store",
            "X-ParallelLines-Cache": cache_status,
        },
    )


@router.get("", response_model=ApiResponse[list[TopicResponse]])
async def search_topics(
    session: SessionDep,
    current_user: OptionalCurrentUserDep,
    q: Annotated[str, Query(min_length=1, max_length=120)],
    board: str | None = None,
    tag: str | None = None,
    author: str | None = None,
    status: Annotated[str | None, Query(pattern="^(open|closed|archived)$")] = None,
    created_after: datetime | None = None,
    created_before: datetime | None = None,
    sort: TopicSort = "relevance",
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
) -> Response:
    filters = SearchFilters(
        board_slug=board,
        tag=tag,
        author=author,
        created_after=created_after,
        created_before=created_before,
        status=status,
    )
    cache_key = _search_response_cache_key(
        current_user=current_user,
        q=q,
        filters=filters,
        sort=sort,
        cursor=cursor,
        limit=limit,
    )
    service = SearchService(session)
    cached = _SEARCH_RESPONSE_CACHE.get(cache_key)
    if cached is not None:
        cached_json, result_count = cached
        await service.log_search(
            query=q,
            normalized_query=normalize_search_query(q),
            filters=filters,
            result_count=result_count,
            current_user=current_user,
        )
        return _json_search_response(cached_json, cache_status="hit")

    topics = await service.search_topics(
        query=q,
        filters=filters,
        sort=sort,
        cursor=cursor,
        limit=limit,
        current_user=current_user,
    )
    payload = ApiResponse(
        data=[TopicResponse.from_model(topic) for topic in topics],
        meta={
            "next_cursor": encode_topic_cursor(topics[-1]) if len(topics) == limit else None
        },
    )
    json_content = payload.model_dump_json()
    _SEARCH_RESPONSE_CACHE.set(cache_key, (json_content, len(topics)))
    return _json_search_response(json_content, cache_status="miss")


# Build a server-cache key that keeps all filters and user visibility isolated.
def _search_response_cache_key(
    *,
    current_user: object | None,
    q: str,
    filters: SearchFilters,
    sort: TopicSort,
    cursor: str | None,
    limit: int,
) -> tuple[object, ...]:
    """Return the hot-cache key for one search request.

    Key parameters mirror the route query string and current user scope. Return
    value includes every filter that can affect visibility or ordering; the
    function has no side effects.
    """

    return (
        user_cache_scope(current_user),
        normalize_search_query(q),
        filters.board_slug or "",
        filters.tag or "",
        filters.author or "",
        filters.created_after.isoformat() if filters.created_after else "",
        filters.created_before.isoformat() if filters.created_before else "",
        filters.status or "",
        sort,
        cursor or "",
        limit,
    )

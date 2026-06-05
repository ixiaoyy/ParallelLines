from typing import Annotated

from fastapi import APIRouter, Query, Response

from app.api.v1.dependencies import OptionalCurrentUserDep, SessionDep
from app.core.response_cache import ResponseHotCache, scoped_cache_control, user_cache_scope
from app.schemas.common import ApiResponse
from app.schemas.forum import TagResponse
from app.services.forum import ForumService

router = APIRouter(prefix="/tags", tags=["tags"])

TAG_RESPONSE_CACHE_TTL_SECONDS = 60

_TAG_RESPONSE_CACHE = ResponseHotCache[list[TagResponse]](
    ttl_seconds=TAG_RESPONSE_CACHE_TTL_SECONDS,
    max_entries=128,
)


def invalidate_tag_response_cache() -> None:
    """Clear cached tag-cloud responses after topic visibility/tag writes.

    There are no parameters and no return value. Side effect: invalidates this
    process' `/tags` hot-cache entries so tag discovery reflects current visible
    topics instead of waiting for the TTL.
    """

    _TAG_RESPONSE_CACHE.clear()


@router.get("", response_model=ApiResponse[list[TagResponse]])
async def list_tags(
    session: SessionDep,
    current_user: OptionalCurrentUserDep,
    response: Response,
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
) -> ApiResponse[list[TagResponse]]:
    response.headers["Cache-Control"] = scoped_cache_control(
        current_user,
        max_age=TAG_RESPONSE_CACHE_TTL_SECONDS,
        stale_while_revalidate=300,
    )
    cache_key = (user_cache_scope(current_user), limit)
    cached = _TAG_RESPONSE_CACHE.get(cache_key)
    if cached is not None:
        response.headers["X-ParallelLines-Cache"] = "hit"
        return ApiResponse(data=cached)

    tags = await ForumService(session).list_tags(limit=limit, current_user=current_user)
    data = [TagResponse.model_validate(tag) for tag in tags]
    _TAG_RESPONSE_CACHE.set(cache_key, data)
    response.headers["X-ParallelLines-Cache"] = "miss"
    return ApiResponse(data=data)

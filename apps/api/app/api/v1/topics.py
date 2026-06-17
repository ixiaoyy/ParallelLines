from typing import Annotated

from fastapi import APIRouter, Query, Request, Response, status

from app.api.v1.dependencies import CurrentUserDep, OptionalCurrentUserDep, SessionDep
from app.core.response_cache import (
    ResponseHotCache,
    cached_json_response,
    scoped_cache_control,
    user_cache_scope,
)
from app.schemas.common import ApiResponse
from app.schemas.forum import (
    ImmersiveTopicFeedItemResponse,
    ImmersiveTopicFeedSort,
    PollResponse,
    PollVoteRequest,
    PostCreateRequest,
    PostResponse,
    PostSort,
    TopicLifecycleRequest,
    TopicLifecycleResponse,
    TopicMergeRequest,
    TopicMoveRequest,
    TopicReadStateRequest,
    TopicReadStateResponse,
    TopicResponse,
    TopicSolutionRequest,
    TopicSort,
    TopicSplitRequest,
)
from app.schemas.interactions import (
    TopicNotificationLevelRequest,
    TopicNotificationLevelResponse,
)
from app.services.forum import ForumService
from app.services.topic_cursor import encode_topic_cursor

router = APIRouter(prefix="/topics", tags=["topics"])

TOPIC_LIST_CACHE_TTL_SECONDS = 15
IMMERSIVE_TOPIC_FEED_CACHE_TTL_SECONDS = TOPIC_LIST_CACHE_TTL_SECONDS
TOPIC_POST_LIST_CACHE_TTL_SECONDS = 15

_TOPIC_LIST_RESPONSE_CACHE = ResponseHotCache[str](
    ttl_seconds=TOPIC_LIST_CACHE_TTL_SECONDS,
    max_entries=256,
)
_IMMERSIVE_TOPIC_FEED_RESPONSE_CACHE = ResponseHotCache[str](
    ttl_seconds=IMMERSIVE_TOPIC_FEED_CACHE_TTL_SECONDS,
    max_entries=256,
)
_TOPIC_POST_LIST_RESPONSE_CACHE = ResponseHotCache[str](
    ttl_seconds=TOPIC_POST_LIST_CACHE_TTL_SECONDS,
    max_entries=512,
)


def invalidate_topic_list_response_cache() -> None:
    """Clear cached global topic feed responses after topic/post write actions.

    There are no parameters and no return value. Side effect: invalidates this
    process' `/topics` and `/topics/immersive-feed` hot-cache entries so
    hidden, moved, or updated topics do not remain visible until TTL expiry.
    """

    _TOPIC_LIST_RESPONSE_CACHE.clear()
    _IMMERSIVE_TOPIC_FEED_RESPONSE_CACHE.clear()


# Clear cached post-list envelopes after any post content or per-user state write.
def invalidate_topic_post_list_response_cache() -> None:
    """Clear cached topic post-list responses after post state changes.

    There are no parameters and no return value. Side effect: invalidates this
    process' `/topics/{id}/posts` hot-cache entries so replies, edits,
    moderation state, likes, and votes are visible immediately.
    """

    _TOPIC_POST_LIST_RESPONSE_CACHE.clear()


def invalidate_topic_write_response_caches(*, include_tags: bool = False) -> None:
    """Clear topic-related public caches after topic or reply write actions.

    Key parameter `include_tags` should be true only when visible topic/tag
    membership changes. Return value is none. Side effect: invalidates global
    topic/feed/post caches, board caches, and the public sitemap; tag cache is
    also cleared when requested. Local imports avoid route-module import cycles
    during application startup.
    """

    invalidate_topic_list_response_cache()
    invalidate_topic_post_list_response_cache()
    from app.api.v1.boards import invalidate_board_response_caches

    invalidate_board_response_caches()
    from app.api.seo import invalidate_sitemap_response_cache

    invalidate_sitemap_response_cache()
    from app.api.v1.search import invalidate_search_response_cache

    invalidate_search_response_cache()
    if include_tags:
        from app.api.v1.tags import invalidate_tag_response_cache

        invalidate_tag_response_cache()


@router.get("", response_model=ApiResponse[list[TopicResponse]])
async def list_topics(
    session: SessionDep,
    current_user: OptionalCurrentUserDep,
    response: Response,
    board: str | None = None,
    q: str | None = None,
    tag: str | None = None,
    author: str | None = None,
    sort: TopicSort = "latest",
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
) -> Response:
    cache_control = scoped_cache_control(
        current_user,
        max_age=TOPIC_LIST_CACHE_TTL_SECONDS,
        stale_while_revalidate=60,
    )
    cache_key = _topic_list_cache_key(
        current_user=current_user,
        board=board,
        q=q,
        tag=tag,
        author=author,
        sort=sort,
        cursor=cursor,
        limit=limit,
    )
    cached_json = _TOPIC_LIST_RESPONSE_CACHE.get(cache_key)
    if cached_json is not None:
        return cached_json_response(
            cached_json,
            cache_control=cache_control,
            cache_status="hit",
        )

    topics = await ForumService(session).list_topics(
        board_slug=board,
        sort=sort,
        limit=limit,
        query=q,
        tag=tag,
        author=author,
        cursor=cursor,
        current_user=current_user,
    )
    payload = ApiResponse(
        data=[TopicResponse.from_model(topic) for topic in topics],
        meta={
            "next_cursor": encode_topic_cursor(
                topics[-1],
                include_pinned=sort == "latest",
            )
            if len(topics) == limit
            else None
        },
    )
    json_content = payload.model_dump_json()
    _TOPIC_LIST_RESPONSE_CACHE.set(cache_key, json_content)
    return cached_json_response(
        json_content,
        cache_control=cache_control,
        cache_status="miss",
    )


@router.get("/immersive-feed", response_model=ApiResponse[list[ImmersiveTopicFeedItemResponse]])
async def list_immersive_topic_feed(
    session: SessionDep,
    current_user: OptionalCurrentUserDep,
    response: Response,
    board: str | None = None,
    q: str | None = None,
    tag: str | None = None,
    author: str | None = None,
    sort: ImmersiveTopicFeedSort = "latest",
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> Response:
    """Return the full-screen topic feed with first posts and read state.

    Key parameters are public topic filters, `sort`, `cursor`, and `limit`.
    Return value is an API envelope with feed items and `next_cursor`. Side
    effect: none; this route does not count views or mark topics read.
    """

    cache_control = scoped_cache_control(
        current_user,
        max_age=IMMERSIVE_TOPIC_FEED_CACHE_TTL_SECONDS,
        stale_while_revalidate=60,
    )
    cache_key = _topic_list_cache_key(
        current_user=current_user,
        board=board,
        q=q,
        tag=tag,
        author=author,
        sort=sort,
        cursor=cursor,
        limit=limit,
    )
    cached_json = _IMMERSIVE_TOPIC_FEED_RESPONSE_CACHE.get(cache_key)
    if cached_json is not None:
        return cached_json_response(
            cached_json,
            cache_control=cache_control,
            cache_status="hit",
        )

    feed_rows = await ForumService(session).list_immersive_feed(
        board_slug=board,
        sort=sort,
        limit=limit,
        query=q,
        tag=tag,
        author=author,
        cursor=cursor,
        current_user=current_user,
    )
    topics = [topic for topic, _lead_post, _read_state in feed_rows]
    payload = ApiResponse(
        data=[
            ImmersiveTopicFeedItemResponse.from_models(topic, lead_post, read_state)
            for topic, lead_post, read_state in feed_rows
        ],
        meta={
            "next_cursor": encode_topic_cursor(
                topics[-1],
                include_pinned=sort == "latest",
            )
            if len(topics) == limit
            else None
        },
    )
    json_content = payload.model_dump_json()
    _IMMERSIVE_TOPIC_FEED_RESPONSE_CACHE.set(cache_key, json_content)
    return cached_json_response(
        json_content,
        cache_control=cache_control,
        cache_status="miss",
    )


# Build an auth-scoped cache key for global topic feed/filter responses.
def _topic_list_cache_key(
    *,
    current_user: object | None,
    board: str | None,
    q: str | None,
    tag: str | None,
    author: str | None,
    sort: str,
    cursor: str | None,
    limit: int,
) -> tuple[object, ...]:
    """Return the hot-cache key for a topic list request.

    Key parameters mirror the route filters and cursor. Return value includes
    the current user scope, so private-board visibility and per-user state do
    not leak across sessions; the function has no side effects.
    """
    return (
        user_cache_scope(current_user),
        _normalized_cache_part(board),
        _normalized_cache_part(q),
        _normalized_cache_part(tag),
        _normalized_cache_part(author),
        sort,
        cursor or "",
        limit,
    )


# Normalize optional string filters before they become cache key parts.
def _normalized_cache_part(value: str | None) -> str:
    """Return a trimmed cache-key string for an optional route filter.

    Key parameter `value` may be `None`; return value is always a string. The
    function has no side effects.
    """
    return value.strip() if value else ""


@router.get("/{topic_id}", response_model=ApiResponse[TopicResponse])
async def get_topic(
    topic_id: str,
    request: Request,
    session: SessionDep,
    current_user: OptionalCurrentUserDep,
) -> ApiResponse[TopicResponse]:
    topic = await ForumService(session).view_topic(
        topic_id,
        current_user=current_user,
        visitor_id=request.headers.get("X-ParallelLines-Visitor"),
    )
    return ApiResponse(data=TopicResponse.from_model(topic))


@router.put("/{topic_id}/read-state", response_model=ApiResponse[TopicReadStateResponse])
async def mark_topic_read_state(
    topic_id: str,
    payload: TopicReadStateRequest,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> ApiResponse[TopicReadStateResponse]:
    """Persist the authenticated user's read marker for one topic.

    Key parameters are `topic_id`, request `payload`, and `current_user`.
    Return value is the updated read-state envelope. Side effect: upserts the
    `topic_reads` row and commits.
    """

    topic, read_state = await ForumService(session).mark_topic_read(
        topic_id,
        current_user,
        post_number=payload.last_read_post_number,
    )
    invalidate_topic_list_response_cache()
    return ApiResponse(data=TopicReadStateResponse.from_topic_and_state(topic, read_state))


@router.put("/{topic_id}/solution", response_model=ApiResponse[TopicResponse])
async def set_topic_solution(
    topic_id: str,
    payload: TopicSolutionRequest,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> ApiResponse[TopicResponse]:
    topic = await ForumService(session).set_topic_solution(topic_id, payload, current_user)
    invalidate_topic_write_response_caches()
    return ApiResponse(data=TopicResponse.from_model(topic))


@router.get("/{topic_id}/poll", response_model=ApiResponse[PollResponse])
async def get_topic_poll(
    topic_id: str,
    session: SessionDep,
    current_user: OptionalCurrentUserDep,
) -> ApiResponse[PollResponse]:
    poll = await ForumService(session).get_topic_poll(topic_id, current_user=current_user)
    return ApiResponse(data=PollResponse.from_model(poll))


@router.put("/{topic_id}/poll/vote", response_model=ApiResponse[PollResponse])
async def vote_topic_poll(
    topic_id: str,
    payload: PollVoteRequest,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> ApiResponse[PollResponse]:
    poll = await ForumService(session).vote_topic_poll(topic_id, payload, current_user)
    invalidate_topic_write_response_caches()
    return ApiResponse(data=PollResponse.from_model(poll))


@router.put("/{topic_id}/lifecycle", response_model=ApiResponse[TopicResponse])
async def update_topic_lifecycle(
    topic_id: str,
    payload: TopicLifecycleRequest,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> ApiResponse[TopicResponse]:
    topic = await ForumService(session).update_topic_lifecycle(topic_id, payload, current_user)
    invalidate_topic_write_response_caches()
    return ApiResponse(data=TopicResponse.from_model(topic))


@router.post("/{topic_id}/move", response_model=ApiResponse[TopicResponse])
async def move_topic(
    topic_id: str,
    payload: TopicMoveRequest,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> ApiResponse[TopicResponse]:
    topic = await ForumService(session).move_topic(topic_id, payload, current_user)
    invalidate_topic_write_response_caches()
    return ApiResponse(data=TopicResponse.from_model(topic))


@router.post("/{topic_id}/split", response_model=ApiResponse[TopicLifecycleResponse])
async def split_topic(
    topic_id: str,
    payload: TopicSplitRequest,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> ApiResponse[TopicLifecycleResponse]:
    source_topic, target_topic, moved_post_count = await ForumService(session).split_topic(
        topic_id,
        payload,
        current_user,
    )
    invalidate_topic_write_response_caches()
    return ApiResponse(
        data=TopicLifecycleResponse(
            source_topic=TopicResponse.from_model(source_topic),
            target_topic=TopicResponse.from_model(target_topic),
            moved_post_count=moved_post_count,
            audit_action="topic_split",
        )
    )


@router.post("/{topic_id}/merge", response_model=ApiResponse[TopicLifecycleResponse])
async def merge_topic(
    topic_id: str,
    payload: TopicMergeRequest,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> ApiResponse[TopicLifecycleResponse]:
    target_topic, moved_post_count = await ForumService(session).merge_topic(
        topic_id,
        payload,
        current_user,
    )
    invalidate_topic_write_response_caches()
    return ApiResponse(
        data=TopicLifecycleResponse(
            source_topic=None,
            target_topic=TopicResponse.from_model(target_topic),
            moved_post_count=moved_post_count,
            audit_action="topic_merged",
        )
    )


@router.get("/{topic_id}/posts", response_model=ApiResponse[list[PostResponse]])
async def list_posts(
    topic_id: str,
    session: SessionDep,
    current_user: OptionalCurrentUserDep,
    response: Response,
    sort: PostSort = "chronological",
) -> Response:
    cache_control = scoped_cache_control(
        current_user,
        max_age=TOPIC_POST_LIST_CACHE_TTL_SECONDS,
        stale_while_revalidate=60,
    )
    cache_key = _topic_post_list_cache_key(
        current_user=current_user,
        topic_id=topic_id,
        sort=sort,
    )
    cached_json = _TOPIC_POST_LIST_RESPONSE_CACHE.get(cache_key)
    if cached_json is not None:
        return cached_json_response(
            cached_json,
            cache_control=cache_control,
            cache_status="hit",
        )

    posts = await ForumService(session).list_posts(
        topic_id, current_user=current_user, sort=sort
    )
    payload = ApiResponse(data=[PostResponse.from_model(post) for post in posts])
    json_content = payload.model_dump_json()
    _TOPIC_POST_LIST_RESPONSE_CACHE.set(cache_key, json_content)
    return cached_json_response(
        json_content,
        cache_control=cache_control,
        cache_status="miss",
    )


# Build an auth-scoped cache key for one topic's post stream.
def _topic_post_list_cache_key(
    *,
    current_user: object | None,
    topic_id: str,
    sort: PostSort,
) -> tuple[object, ...]:
    """Return the hot-cache key for a topic post-list request.

    Key parameters are the current user scope, topic id, and post sort mode.
    Return value keeps per-user reaction/vote state isolated; the function has
    no side effects.
    """

    return (user_cache_scope(current_user), topic_id, sort)


@router.post(
    "/{topic_id}/posts",
    response_model=ApiResponse[PostResponse],
    status_code=status.HTTP_201_CREATED,
)
async def reply_to_topic(
    topic_id: str,
    payload: PostCreateRequest,
    request: Request,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> ApiResponse[PostResponse]:
    post = await ForumService(session).reply_to_topic(topic_id, payload, current_user, request)
    invalidate_topic_write_response_caches()
    return ApiResponse(data=PostResponse.from_model(post))


@router.get(
    "/{topic_id}/notification-level",
    response_model=ApiResponse[TopicNotificationLevelResponse],
)
async def get_topic_notification_level(
    topic_id: str,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> ApiResponse[TopicNotificationLevelResponse]:
    result = await ForumService(session).get_topic_notification_level(topic_id, current_user)
    return ApiResponse(data=result)


@router.put(
    "/{topic_id}/notification-level",
    response_model=ApiResponse[TopicNotificationLevelResponse],
)
async def set_topic_notification_level(
    topic_id: str,
    payload: TopicNotificationLevelRequest,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> ApiResponse[TopicNotificationLevelResponse]:
    result = await ForumService(session).set_topic_notification_level(
        topic_id, payload.notification_level, current_user
    )
    return ApiResponse(data=result)

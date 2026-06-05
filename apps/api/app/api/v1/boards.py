from typing import Annotated

from fastapi import APIRouter, Query, Request, Response, status

from app.api.v1.dependencies import CurrentUserDep, OptionalCurrentUserDep, SessionDep
from app.api.v1.tags import invalidate_tag_response_cache
from app.api.v1.topics import invalidate_topic_list_response_cache
from app.core.response_cache import ResponseHotCache, scoped_cache_control, user_cache_scope
from app.schemas.common import ApiResponse
from app.schemas.forum import (
    BoardCreateRequest,
    BoardDetailResponse,
    BoardMemberRemoveResponse,
    BoardMemberResponse,
    BoardMemberUpdateRequest,
    BoardResponse,
    BoardSettingsResponse,
    BoardSettingsUpdateRequest,
    TopicCreateRequest,
    TopicResponse,
    TopicSort,
)
from app.schemas.interactions import BoardFollowRequest, BoardFollowResponse
from app.services.forum import ForumService
from app.services.interactions import InteractionService
from app.services.topic_cursor import encode_topic_cursor

router = APIRouter(prefix="/boards", tags=["boards"])

BOARD_LIST_CACHE_TTL_SECONDS = 60
BOARD_DETAIL_CACHE_TTL_SECONDS = 30
BOARD_TOPIC_LIST_CACHE_TTL_SECONDS = 15

_BOARD_LIST_RESPONSE_CACHE = ResponseHotCache[ApiResponse[list[BoardResponse]]](
    ttl_seconds=BOARD_LIST_CACHE_TTL_SECONDS,
    max_entries=128,
)
_BOARD_DETAIL_RESPONSE_CACHE = ResponseHotCache[ApiResponse[BoardDetailResponse]](
    ttl_seconds=BOARD_DETAIL_CACHE_TTL_SECONDS,
    max_entries=256,
)
_BOARD_TOPIC_LIST_RESPONSE_CACHE = ResponseHotCache[ApiResponse[list[TopicResponse]]](
    ttl_seconds=BOARD_TOPIC_LIST_CACHE_TTL_SECONDS,
    max_entries=256,
)


def invalidate_board_response_caches() -> None:
    """Clear board directory, board detail, and board topic-list hot caches.

    There are no parameters and no return value. Side effect: invalidates this
    process' board-related cache entries after writes that change board counters,
    latest topics, or topic visibility.
    """

    _BOARD_LIST_RESPONSE_CACHE.clear()
    _BOARD_DETAIL_RESPONSE_CACHE.clear()
    _BOARD_TOPIC_LIST_RESPONSE_CACHE.clear()


@router.get("", response_model=ApiResponse[list[BoardResponse]])
async def list_boards(
    session: SessionDep,
    current_user: OptionalCurrentUserDep,
    response: Response,
) -> ApiResponse[list[BoardResponse]]:
    response.headers["Cache-Control"] = scoped_cache_control(
        current_user,
        max_age=BOARD_LIST_CACHE_TTL_SECONDS,
        stale_while_revalidate=300,
    )
    cache_key = (user_cache_scope(current_user),)
    cached = _BOARD_LIST_RESPONSE_CACHE.get(cache_key)
    if cached is not None:
        response.headers["X-ParallelLines-Cache"] = "hit"
        return cached

    service = ForumService(session)
    boards = await service.list_boards(current_user)
    memberships = await service.board_memberships_for_user(
        [board.id for board in boards],
        current_user,
    )
    payload = ApiResponse(
        data=[
            BoardResponse.from_board(
                board,
                memberships.get(board.id),
                can_create_topic=service.can_create_topic_in_board(board, current_user),
            )
            for board in boards
        ]
    )
    _BOARD_LIST_RESPONSE_CACHE.set(cache_key, payload)
    response.headers["X-ParallelLines-Cache"] = "miss"
    return payload


@router.post(
    "",
    response_model=ApiResponse[BoardResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_board(
    payload: BoardCreateRequest,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> ApiResponse[BoardResponse]:
    service = ForumService(session)
    board = await service.create_board(payload, current_user)
    memberships = await service.board_memberships_for_user([board.id], current_user)
    return ApiResponse(
        data=BoardResponse.from_board(
            board,
            memberships.get(board.id),
            can_create_topic=service.can_create_topic_in_board(board, current_user),
        )
    )


@router.get("/{slug}", response_model=ApiResponse[BoardDetailResponse])
async def get_board(
    slug: str,
    session: SessionDep,
    current_user: OptionalCurrentUserDep,
    response: Response,
) -> ApiResponse[BoardDetailResponse]:
    response.headers["Cache-Control"] = scoped_cache_control(
        current_user,
        max_age=BOARD_DETAIL_CACHE_TTL_SECONDS,
        stale_while_revalidate=120,
    )
    cache_key = (user_cache_scope(current_user), slug)
    cached = _BOARD_DETAIL_RESPONSE_CACHE.get(cache_key)
    if cached is not None:
        response.headers["X-ParallelLines-Cache"] = "hit"
        return cached

    service = ForumService(session)
    board, latest_topics, child_boards = await service.get_board_detail(
        slug,
        current_user=current_user,
    )
    memberships = await service.board_memberships_for_user(
        [board.id, *[child.id for child in child_boards]],
        current_user,
    )
    child_can_create_topics = {
        child.id: service.can_create_topic_in_board(child, current_user) for child in child_boards
    }
    payload = ApiResponse(
        data=BoardDetailResponse.from_board_and_topics(
            board,
            latest_topics,
            memberships.get(board.id),
            child_boards,
            memberships,
            can_create_topic=service.can_create_topic_in_board(board, current_user),
            child_can_create_topics=child_can_create_topics,
        )
    )
    _BOARD_DETAIL_RESPONSE_CACHE.set(cache_key, payload)
    response.headers["X-ParallelLines-Cache"] = "miss"
    return payload


@router.get("/{slug}/settings", response_model=ApiResponse[BoardSettingsResponse])
async def get_board_settings(
    slug: str,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> ApiResponse[BoardSettingsResponse]:
    settings = await ForumService(session).get_board_settings(slug, current_user)
    return ApiResponse(data=settings)


@router.put("/{slug}/settings", response_model=ApiResponse[BoardResponse])
async def update_board_settings(
    slug: str,
    payload: BoardSettingsUpdateRequest,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> ApiResponse[BoardResponse]:
    service = ForumService(session)
    board = await service.update_board_settings(slug, payload, current_user)
    memberships = await service.board_memberships_for_user([board.id], current_user)
    return ApiResponse(
        data=BoardResponse.from_board(
            board,
            memberships.get(board.id),
            can_create_topic=service.can_create_topic_in_board(board, current_user),
        )
    )


@router.put(
    "/{slug}/members/{username}",
    response_model=ApiResponse[BoardMemberResponse],
)
async def update_board_member(
    slug: str,
    username: str,
    payload: BoardMemberUpdateRequest,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> ApiResponse[BoardMemberResponse]:
    member = await ForumService(session).update_board_member(
        slug,
        username,
        payload,
        current_user,
    )
    return ApiResponse(data=BoardMemberResponse.from_member(member))


@router.delete(
    "/{slug}/members/{username}",
    response_model=ApiResponse[BoardMemberRemoveResponse],
)
async def remove_board_member(
    slug: str,
    username: str,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> ApiResponse[BoardMemberRemoveResponse]:
    board = await ForumService(session).get_board_by_slug(slug, current_user=current_user)
    await ForumService(session).remove_board_member(slug, username, current_user)
    return ApiResponse(
        data=BoardMemberRemoveResponse(
            board_id=board.id,
            username=username,
            removed=True,
        )
    )


@router.put("/{slug}/follow", response_model=ApiResponse[BoardFollowResponse])
async def follow_board(
    slug: str,
    payload: BoardFollowRequest,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> ApiResponse[BoardFollowResponse]:
    state = await InteractionService(session).follow_board(
        slug,
        current_user,
        notification_level=payload.notification_level,
    )
    return ApiResponse(data=state)


@router.delete("/{slug}/follow", response_model=ApiResponse[BoardFollowResponse])
async def unfollow_board(
    slug: str,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> ApiResponse[BoardFollowResponse]:
    state = await InteractionService(session).unfollow_board(slug, current_user)
    return ApiResponse(data=state)


@router.get("/{slug}/topics", response_model=ApiResponse[list[TopicResponse]])
async def list_board_topics(
    slug: str,
    session: SessionDep,
    current_user: OptionalCurrentUserDep,
    response: Response,
    q: str | None = None,
    tag: str | None = None,
    author: str | None = None,
    sort: TopicSort = "latest",
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
) -> ApiResponse[list[TopicResponse]]:
    response.headers["Cache-Control"] = scoped_cache_control(
        current_user,
        max_age=BOARD_TOPIC_LIST_CACHE_TTL_SECONDS,
        stale_while_revalidate=60,
    )
    cache_key = _board_topic_list_cache_key(
        current_user=current_user,
        slug=slug,
        q=q,
        tag=tag,
        author=author,
        sort=sort,
        cursor=cursor,
        limit=limit,
    )
    cached = _BOARD_TOPIC_LIST_RESPONSE_CACHE.get(cache_key)
    if cached is not None:
        response.headers["X-ParallelLines-Cache"] = "hit"
        return cached

    topics = await ForumService(session).list_topics(
        board_slug=slug,
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
            "next_cursor": encode_topic_cursor(topics[-1], include_pinned=sort == "latest")
            if len(topics) == limit
            else None
        },
    )
    _BOARD_TOPIC_LIST_RESPONSE_CACHE.set(cache_key, payload)
    response.headers["X-ParallelLines-Cache"] = "miss"
    return payload


# Build an auth-scoped cache key for board-scoped topic list responses.
def _board_topic_list_cache_key(
    *,
    current_user: object | None,
    slug: str,
    q: str | None,
    tag: str | None,
    author: str | None,
    sort: TopicSort,
    cursor: str | None,
    limit: int,
) -> tuple[object, ...]:
    """Return the hot-cache key for a board topic list request.

    Key parameters mirror the route filters and cursor. Return value includes
    the current user scope, so private boards and per-user reaction state do not
    leak across sessions; the function has no side effects.
    """
    return (
        user_cache_scope(current_user),
        slug,
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


@router.post(
    "/{slug}/topics",
    response_model=ApiResponse[TopicResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_topic(
    slug: str,
    payload: TopicCreateRequest,
    request: Request,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> ApiResponse[TopicResponse]:
    topic = await ForumService(session).create_topic(slug, payload, current_user, request)
    invalidate_topic_list_response_cache()
    invalidate_board_response_caches()
    invalidate_tag_response_cache()
    return ApiResponse(data=TopicResponse.from_model(topic))

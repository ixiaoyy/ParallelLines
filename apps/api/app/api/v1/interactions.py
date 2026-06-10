from fastapi import APIRouter

from app.api.v1.dependencies import CurrentUserDep, SessionDep
from app.schemas.common import ApiResponse
from app.schemas.interactions import InteractionStateResponse, VoteRequest, VoteStateResponse
from app.services.interactions import InteractionService

router = APIRouter(tags=["interactions"])


# Clear cached read models after reactions, votes, or bookmarks mutate counts.
def invalidate_interaction_response_caches(*, include_post_lists: bool = False) -> None:
    """Clear cached topic and optional post-list responses after interactions.

    Key parameter `include_post_lists` should be true when post like/vote state
    changes. Return value is none. Side effect: invalidates in-process topic,
    immersive-feed, board, and optionally topic-post caches.
    """

    from app.api.v1.boards import invalidate_board_response_caches
    from app.api.v1.topics import (
        invalidate_topic_list_response_cache,
        invalidate_topic_post_list_response_cache,
    )

    invalidate_topic_list_response_cache()
    invalidate_board_response_caches()
    if include_post_lists:
        invalidate_topic_post_list_response_cache()


@router.put("/posts/{post_id}/like", response_model=ApiResponse[InteractionStateResponse])
async def like_post(
    post_id: str,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> ApiResponse[InteractionStateResponse]:
    state = await InteractionService(session).like_post(post_id, current_user)
    invalidate_interaction_response_caches(include_post_lists=True)
    return ApiResponse(data=state)


@router.delete("/posts/{post_id}/like", response_model=ApiResponse[InteractionStateResponse])
async def unlike_post(
    post_id: str,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> ApiResponse[InteractionStateResponse]:
    state = await InteractionService(session).unlike_post(post_id, current_user)
    invalidate_interaction_response_caches(include_post_lists=True)
    return ApiResponse(data=state)


@router.put("/posts/{post_id}/vote", response_model=ApiResponse[VoteStateResponse])
async def vote_post(
    post_id: str,
    payload: VoteRequest,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> ApiResponse[VoteStateResponse]:
    state = await InteractionService(session).vote_post(post_id, payload.value, current_user)
    invalidate_interaction_response_caches(include_post_lists=True)
    return ApiResponse(data=state)


@router.put("/topics/{topic_id}/vote", response_model=ApiResponse[VoteStateResponse])
async def vote_topic(
    topic_id: str,
    payload: VoteRequest,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> ApiResponse[VoteStateResponse]:
    state = await InteractionService(session).vote_topic(topic_id, payload.value, current_user)
    invalidate_interaction_response_caches()
    return ApiResponse(data=state)


@router.put("/topics/{topic_id}/like", response_model=ApiResponse[InteractionStateResponse])
async def like_topic(
    topic_id: str,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> ApiResponse[InteractionStateResponse]:
    state = await InteractionService(session).like_topic(topic_id, current_user)
    invalidate_interaction_response_caches()
    return ApiResponse(data=state)


@router.delete("/topics/{topic_id}/like", response_model=ApiResponse[InteractionStateResponse])
async def unlike_topic(
    topic_id: str,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> ApiResponse[InteractionStateResponse]:
    state = await InteractionService(session).unlike_topic(topic_id, current_user)
    invalidate_interaction_response_caches()
    return ApiResponse(data=state)


@router.put("/topics/{topic_id}/bookmark", response_model=ApiResponse[InteractionStateResponse])
async def bookmark_topic(
    topic_id: str,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> ApiResponse[InteractionStateResponse]:
    state = await InteractionService(session).bookmark_topic(topic_id, current_user)
    invalidate_interaction_response_caches()
    return ApiResponse(data=state)


@router.delete("/topics/{topic_id}/bookmark", response_model=ApiResponse[InteractionStateResponse])
async def unbookmark_topic(
    topic_id: str,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> ApiResponse[InteractionStateResponse]:
    state = await InteractionService(session).unbookmark_topic(topic_id, current_user)
    invalidate_interaction_response_caches()
    return ApiResponse(data=state)

from fastapi import APIRouter

from app.api.v1.dependencies import CurrentUserDep, SessionDep
from app.schemas.common import ApiResponse
from app.schemas.interactions import InteractionStateResponse
from app.services.interactions import InteractionService

router = APIRouter(tags=["interactions"])


@router.put("/posts/{post_id}/like", response_model=ApiResponse[InteractionStateResponse])
async def like_post(
    post_id: str,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> ApiResponse[InteractionStateResponse]:
    state = await InteractionService(session).like_post(post_id, current_user)
    return ApiResponse(data=state)


@router.delete("/posts/{post_id}/like", response_model=ApiResponse[InteractionStateResponse])
async def unlike_post(
    post_id: str,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> ApiResponse[InteractionStateResponse]:
    state = await InteractionService(session).unlike_post(post_id, current_user)
    return ApiResponse(data=state)


@router.put("/topics/{topic_id}/bookmark", response_model=ApiResponse[InteractionStateResponse])
async def bookmark_topic(
    topic_id: str,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> ApiResponse[InteractionStateResponse]:
    state = await InteractionService(session).bookmark_topic(topic_id, current_user)
    return ApiResponse(data=state)


@router.delete("/topics/{topic_id}/bookmark", response_model=ApiResponse[InteractionStateResponse])
async def unbookmark_topic(
    topic_id: str,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> ApiResponse[InteractionStateResponse]:
    state = await InteractionService(session).unbookmark_topic(topic_id, current_user)
    return ApiResponse(data=state)

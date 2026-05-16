from fastapi import APIRouter

from app.api.v1.dependencies import CurrentUserDep, SessionDep
from app.schemas.common import ApiResponse
from app.schemas.forum import PostResponse, PostUpdateRequest
from app.services.forum import ForumService

router = APIRouter(prefix="/posts", tags=["posts"])


@router.patch("/{post_id}", response_model=ApiResponse[PostResponse])
async def update_post(
    post_id: str,
    payload: PostUpdateRequest,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> ApiResponse[PostResponse]:
    post = await ForumService(session).update_post(post_id, payload, current_user)
    return ApiResponse(data=PostResponse.from_model(post))

from fastapi import APIRouter, Request

from app.api.v1.boards import invalidate_board_response_caches
from app.api.v1.dependencies import CurrentUserDep, SessionDep
from app.api.v1.topics import invalidate_topic_list_response_cache
from app.schemas.common import ApiResponse
from app.schemas.forum import (
    PostResponse,
    PostRevisionResponse,
    PostRevisionRestoreRequest,
    PostUpdateRequest,
)
from app.services.forum import ForumService

router = APIRouter(prefix="/posts", tags=["posts"])


def invalidate_post_write_response_caches() -> None:
    """Clear topic and board list caches after post write actions.

    There are no parameters and no return value. Side effect: invalidates
    in-process caches whose cards can include first-post excerpts, reply counts,
    or latest-activity ordering.
    """

    invalidate_topic_list_response_cache()
    invalidate_board_response_caches()


@router.patch("/{post_id}", response_model=ApiResponse[PostResponse])
async def update_post(
    post_id: str,
    payload: PostUpdateRequest,
    request: Request,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> ApiResponse[PostResponse]:
    post = await ForumService(session).update_post(post_id, payload, current_user, request)
    invalidate_post_write_response_caches()
    return ApiResponse(data=PostResponse.from_model(post))


@router.get("/{post_id}/revisions", response_model=ApiResponse[list[PostRevisionResponse]])
async def list_post_revisions(
    post_id: str,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> ApiResponse[list[PostRevisionResponse]]:
    revisions = await ForumService(session).list_post_revisions(post_id, current_user)
    return ApiResponse(data=[PostRevisionResponse.from_model(revision) for revision in revisions])


@router.get(
    "/{post_id}/revisions/{revision_id}",
    response_model=ApiResponse[PostRevisionResponse],
)
async def get_post_revision(
    post_id: str,
    revision_id: str,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> ApiResponse[PostRevisionResponse]:
    revision = await ForumService(session).get_post_revision(post_id, revision_id, current_user)
    return ApiResponse(data=PostRevisionResponse.from_model(revision))


@router.post(
    "/{post_id}/revisions/{revision_id}/restore",
    response_model=ApiResponse[PostResponse],
)
async def restore_post_revision(
    post_id: str,
    revision_id: str,
    payload: PostRevisionRestoreRequest,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> ApiResponse[PostResponse]:
    post = await ForumService(session).restore_post_revision(
        post_id,
        revision_id,
        payload,
        current_user,
    )
    invalidate_post_write_response_caches()
    return ApiResponse(data=PostResponse.from_model(post))


@router.delete("/{post_id}", response_model=ApiResponse[PostResponse])
async def delete_post(
    post_id: str,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> ApiResponse[PostResponse]:
    post = await ForumService(session).delete_post(post_id, current_user)
    invalidate_post_write_response_caches()
    return ApiResponse(data=PostResponse.from_model(post))

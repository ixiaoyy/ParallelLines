from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Query, Request, status

from app.api.v1.dependencies import CurrentUserDep, OptionalCurrentUserDep, SessionDep
from app.schemas.common import ApiResponse
from app.schemas.forum import (
    BoardCreateRequest,
    BoardDetailResponse,
    BoardResponse,
    TopicCreateRequest,
    TopicResponse,
    TopicSort,
)
from app.schemas.interactions import BoardFollowRequest, BoardFollowResponse
from app.services.forum import ForumService
from app.services.interactions import InteractionService

router = APIRouter(prefix="/boards", tags=["boards"])


@router.get("", response_model=ApiResponse[list[BoardResponse]])
async def list_boards(
    session: SessionDep,
    current_user: OptionalCurrentUserDep,
) -> ApiResponse[list[BoardResponse]]:
    boards = await ForumService(session).list_boards(current_user)
    return ApiResponse(data=[BoardResponse.model_validate(board) for board in boards])


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
    board = await ForumService(session).create_board(payload, current_user)
    return ApiResponse(data=BoardResponse.model_validate(board))


@router.get("/{slug}", response_model=ApiResponse[BoardDetailResponse])
async def get_board(
    slug: str,
    session: SessionDep,
    current_user: OptionalCurrentUserDep,
) -> ApiResponse[BoardDetailResponse]:
    board, latest_topics = await ForumService(session).get_board_detail(
        slug,
        current_user=current_user,
    )
    return ApiResponse(data=BoardDetailResponse.from_board_and_topics(board, latest_topics))


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
    q: str | None = None,
    tag: str | None = None,
    author: str | None = None,
    sort: TopicSort = "latest",
    cursor: datetime | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
) -> ApiResponse[list[TopicResponse]]:
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
    return ApiResponse(
        data=[TopicResponse.from_model(topic) for topic in topics],
        meta={
            "next_cursor": topics[-1].last_posted_at.isoformat()
            if len(topics) == limit
            else None
        },
    )


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
    return ApiResponse(data=TopicResponse.from_model(topic))

from typing import Annotated

from fastapi import APIRouter, Query, status

from app.api.v1.dependencies import CurrentUserDep, SessionDep
from app.schemas.common import ApiResponse
from app.schemas.forum import (
    BoardCreateRequest,
    BoardDetailResponse,
    BoardResponse,
    TopicCreateRequest,
    TopicResponse,
    TopicSort,
)
from app.services.forum import ForumService

router = APIRouter(prefix="/boards", tags=["boards"])


@router.get("", response_model=ApiResponse[list[BoardResponse]])
async def list_boards(session: SessionDep) -> ApiResponse[list[BoardResponse]]:
    boards = await ForumService(session).list_boards()
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
async def get_board(slug: str, session: SessionDep) -> ApiResponse[BoardDetailResponse]:
    board, latest_topics = await ForumService(session).get_board_detail(slug)
    return ApiResponse(data=BoardDetailResponse.from_board_and_topics(board, latest_topics))


@router.get("/{slug}/topics", response_model=ApiResponse[list[TopicResponse]])
async def list_board_topics(
    slug: str,
    session: SessionDep,
    sort: TopicSort = "latest",
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
) -> ApiResponse[list[TopicResponse]]:
    topics = await ForumService(session).list_topics(board_slug=slug, sort=sort, limit=limit)
    return ApiResponse(data=[TopicResponse.from_model(topic) for topic in topics])


@router.post(
    "/{slug}/topics",
    response_model=ApiResponse[TopicResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_topic(
    slug: str,
    payload: TopicCreateRequest,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> ApiResponse[TopicResponse]:
    topic = await ForumService(session).create_topic(slug, payload, current_user)
    return ApiResponse(data=TopicResponse.from_model(topic))

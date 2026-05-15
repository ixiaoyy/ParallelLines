from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Query, status

from app.api.v1.dependencies import CurrentUserDep, SessionDep
from app.schemas.common import ApiResponse
from app.schemas.forum import PostCreateRequest, PostResponse, TopicResponse, TopicSort
from app.services.forum import ForumService

router = APIRouter(prefix="/topics", tags=["topics"])


@router.get("", response_model=ApiResponse[list[TopicResponse]])
async def list_topics(
    session: SessionDep,
    board: str | None = None,
    q: str | None = None,
    tag: str | None = None,
    author: str | None = None,
    sort: TopicSort = "latest",
    cursor: datetime | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
) -> ApiResponse[list[TopicResponse]]:
    topics = await ForumService(session).list_topics(
        board_slug=board,
        sort=sort,
        limit=limit,
        query=q,
        tag=tag,
        author=author,
        cursor=cursor,
    )
    return ApiResponse(
        data=[TopicResponse.from_model(topic) for topic in topics],
        meta={
            "next_cursor": topics[-1].last_posted_at.isoformat()
            if len(topics) == limit
            else None
        },
    )


@router.get("/{topic_id}", response_model=ApiResponse[TopicResponse])
async def get_topic(topic_id: str, session: SessionDep) -> ApiResponse[TopicResponse]:
    topic = await ForumService(session).get_topic(topic_id)
    return ApiResponse(data=TopicResponse.from_model(topic))


@router.get("/{topic_id}/posts", response_model=ApiResponse[list[PostResponse]])
async def list_posts(topic_id: str, session: SessionDep) -> ApiResponse[list[PostResponse]]:
    posts = await ForumService(session).list_posts(topic_id)
    return ApiResponse(data=[PostResponse.from_model(post) for post in posts])


@router.post(
    "/{topic_id}/posts",
    response_model=ApiResponse[PostResponse],
    status_code=status.HTTP_201_CREATED,
)
async def reply_to_topic(
    topic_id: str,
    payload: PostCreateRequest,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> ApiResponse[PostResponse]:
    post = await ForumService(session).reply_to_topic(topic_id, payload, current_user)
    return ApiResponse(data=PostResponse.from_model(post))

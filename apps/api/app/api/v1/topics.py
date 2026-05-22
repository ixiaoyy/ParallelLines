from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Query, Request, status

from app.api.v1.dependencies import CurrentUserDep, OptionalCurrentUserDep, SessionDep
from app.schemas.common import ApiResponse
from app.schemas.forum import (
    PostCreateRequest,
    PostResponse,
    TopicLifecycleRequest,
    TopicLifecycleResponse,
    TopicMergeRequest,
    TopicMoveRequest,
    TopicResponse,
    TopicSort,
    TopicSplitRequest,
)
from app.services.forum import ForumService

router = APIRouter(prefix="/topics", tags=["topics"])


@router.get("", response_model=ApiResponse[list[TopicResponse]])
async def list_topics(
    session: SessionDep,
    current_user: OptionalCurrentUserDep,
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
        current_user=current_user,
    )
    return ApiResponse(
        data=[TopicResponse.from_model(topic) for topic in topics],
        meta={
            "next_cursor": topics[-1].last_posted_at.isoformat() if len(topics) == limit else None
        },
    )


@router.get("/{topic_id}", response_model=ApiResponse[TopicResponse])
async def get_topic(
    topic_id: str,
    session: SessionDep,
    current_user: OptionalCurrentUserDep,
) -> ApiResponse[TopicResponse]:
    topic = await ForumService(session).get_topic(topic_id, current_user=current_user)
    return ApiResponse(data=TopicResponse.from_model(topic))


@router.put("/{topic_id}/lifecycle", response_model=ApiResponse[TopicResponse])
async def update_topic_lifecycle(
    topic_id: str,
    payload: TopicLifecycleRequest,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> ApiResponse[TopicResponse]:
    topic = await ForumService(session).update_topic_lifecycle(topic_id, payload, current_user)
    return ApiResponse(data=TopicResponse.from_model(topic))


@router.post("/{topic_id}/move", response_model=ApiResponse[TopicResponse])
async def move_topic(
    topic_id: str,
    payload: TopicMoveRequest,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> ApiResponse[TopicResponse]:
    topic = await ForumService(session).move_topic(topic_id, payload, current_user)
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
) -> ApiResponse[list[PostResponse]]:
    posts = await ForumService(session).list_posts(topic_id, current_user=current_user)
    return ApiResponse(data=[PostResponse.from_model(post) for post in posts])


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
    return ApiResponse(data=PostResponse.from_model(post))

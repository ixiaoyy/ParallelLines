from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Query

from app.api.v1.dependencies import OptionalCurrentUserDep, SessionDep
from app.schemas.common import ApiResponse
from app.schemas.forum import TopicResponse, TopicSort
from app.services.forum import ForumService

router = APIRouter(prefix="/search", tags=["search"])


@router.get("", response_model=ApiResponse[list[TopicResponse]])
async def search_topics(
    session: SessionDep,
    current_user: OptionalCurrentUserDep,
    q: Annotated[str, Query(min_length=1, max_length=120)],
    board: str | None = None,
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
            "next_cursor": topics[-1].last_posted_at.isoformat()
            if len(topics) == limit
            else None
        },
    )

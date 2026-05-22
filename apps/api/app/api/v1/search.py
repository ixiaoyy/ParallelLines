from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Query

from app.api.v1.dependencies import OptionalCurrentUserDep, SessionDep
from app.schemas.common import ApiResponse
from app.schemas.forum import TopicResponse, TopicSort
from app.services.search import SearchFilters, SearchService

router = APIRouter(prefix="/search", tags=["search"])


@router.get("", response_model=ApiResponse[list[TopicResponse]])
async def search_topics(
    session: SessionDep,
    current_user: OptionalCurrentUserDep,
    q: Annotated[str, Query(min_length=1, max_length=120)],
    board: str | None = None,
    tag: str | None = None,
    author: str | None = None,
    status: Annotated[str | None, Query(pattern="^(open|closed|archived)$")] = None,
    created_after: datetime | None = None,
    created_before: datetime | None = None,
    sort: TopicSort = "relevance",
    cursor: datetime | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
) -> ApiResponse[list[TopicResponse]]:
    topics = await SearchService(session).search_topics(
        query=q,
        filters=SearchFilters(
            board_slug=board,
            tag=tag,
            author=author,
            created_after=created_after,
            created_before=created_before,
            status=status,
        ),
        sort=sort,
        cursor=cursor,
        limit=limit,
        current_user=current_user,
    )
    return ApiResponse(
        data=[TopicResponse.from_model(topic) for topic in topics],
        meta={
            "next_cursor": topics[-1].last_posted_at.isoformat() if len(topics) == limit else None
        },
    )

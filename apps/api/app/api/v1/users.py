from typing import Annotated

from fastapi import APIRouter, Query

from app.api.v1.dependencies import SessionDep
from app.schemas.common import ApiResponse
from app.schemas.forum import TopicResponse
from app.schemas.users import UserProfileResponse
from app.services.forum import ForumService

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/{username}", response_model=ApiResponse[UserProfileResponse])
async def get_user_profile(username: str, session: SessionDep) -> ApiResponse[UserProfileResponse]:
    user, topic_count, post_count = await ForumService(session).get_user_content_counts(username)
    return ApiResponse(
        data=UserProfileResponse(
            id=user.id,
            username=user.username,
            avatar_url=user.avatar_url,
            role=user.role,
            status=user.status,
            created_at=user.created_at,
            topic_count=topic_count,
            post_count=post_count,
        )
    )


@router.get("/{username}/topics", response_model=ApiResponse[list[TopicResponse]])
async def list_user_topics(
    username: str,
    session: SessionDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
) -> ApiResponse[list[TopicResponse]]:
    topics = await ForumService(session).list_user_topics(username, limit=limit)
    return ApiResponse(data=[TopicResponse.from_model(topic) for topic in topics])

from typing import Annotated

from fastapi import APIRouter, Query
from starlette.responses import Response

from app.api.v1.dependencies import CurrentUserDep, OptionalCurrentUserDep, SessionDep, SettingsDep
from app.schemas.common import ApiResponse
from app.schemas.forum import TopicResponse
from app.schemas.users import (
    PrivateMessageCreateRequest,
    PrivateMessageTopicResponse,
    UserProfileResponse,
    UserRelationshipStateResponse,
)
from app.services.backups import BackupService
from app.services.forum import ForumService
from app.services.social import SocialService

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me/export")
async def export_current_user(
    session: SessionDep,
    settings: SettingsDep,
    current_user: CurrentUserDep,
) -> Response:
    archive = await BackupService(session, settings).build_user_export(current_user)
    return Response(
        content=archive.content,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{archive.filename}"',
            "X-Export-SHA256": archive.sha256,
        },
    )


@router.get("/messages", response_model=ApiResponse[list[PrivateMessageTopicResponse]])
async def list_private_messages(
    session: SessionDep,
    current_user: CurrentUserDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
) -> ApiResponse[list[PrivateMessageTopicResponse]]:
    messages = await SocialService(session).list_private_messages(current_user, limit=limit)
    return ApiResponse(data=messages)


@router.post("/messages", response_model=ApiResponse[PrivateMessageTopicResponse], status_code=201)
async def create_private_message(
    payload: PrivateMessageCreateRequest,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> ApiResponse[PrivateMessageTopicResponse]:
    message = await SocialService(session).create_private_message(payload, current_user)
    return ApiResponse(data=message)


@router.get("/{username}/relationship", response_model=ApiResponse[UserRelationshipStateResponse])
async def get_user_relationship(
    username: str,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> ApiResponse[UserRelationshipStateResponse]:
    state = await SocialService(session).relationship_state(username, current_user)
    return ApiResponse(data=state)


@router.put("/{username}/follow", response_model=ApiResponse[UserRelationshipStateResponse])
async def follow_user(
    username: str,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> ApiResponse[UserRelationshipStateResponse]:
    state = await SocialService(session).set_relationship(username, "follow", current_user)
    return ApiResponse(data=state)


@router.delete("/{username}/follow", response_model=ApiResponse[UserRelationshipStateResponse])
async def unfollow_user(
    username: str,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> ApiResponse[UserRelationshipStateResponse]:
    state = await SocialService(session).clear_relationship(username, "follow", current_user)
    return ApiResponse(data=state)


@router.put("/{username}/ignore", response_model=ApiResponse[UserRelationshipStateResponse])
async def ignore_user(
    username: str,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> ApiResponse[UserRelationshipStateResponse]:
    state = await SocialService(session).set_relationship(username, "ignore", current_user)
    return ApiResponse(data=state)


@router.delete("/{username}/ignore", response_model=ApiResponse[UserRelationshipStateResponse])
async def unignore_user(
    username: str,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> ApiResponse[UserRelationshipStateResponse]:
    state = await SocialService(session).clear_relationship(username, "ignore", current_user)
    return ApiResponse(data=state)


@router.put("/{username}/block", response_model=ApiResponse[UserRelationshipStateResponse])
async def block_user(
    username: str,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> ApiResponse[UserRelationshipStateResponse]:
    state = await SocialService(session).set_relationship(username, "block", current_user)
    return ApiResponse(data=state)


@router.delete("/{username}/block", response_model=ApiResponse[UserRelationshipStateResponse])
async def unblock_user(
    username: str,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> ApiResponse[UserRelationshipStateResponse]:
    state = await SocialService(session).clear_relationship(username, "block", current_user)
    return ApiResponse(data=state)


@router.get("/{username}", response_model=ApiResponse[UserProfileResponse])
async def get_user_profile(
    username: str,
    session: SessionDep,
    current_user: OptionalCurrentUserDep,
) -> ApiResponse[UserProfileResponse]:
    user, topic_count, post_count = await ForumService(session).get_user_content_counts(
        username,
        current_user=current_user,
    )
    return ApiResponse(
        data=UserProfileResponse(
            id=user.id,
            username=user.username,
            avatar_url=user.avatar_url,
            role=user.role,
            level=user.level,
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
    current_user: OptionalCurrentUserDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
) -> ApiResponse[list[TopicResponse]]:
    topics = await ForumService(session).list_user_topics(
        username,
        limit=limit,
        current_user=current_user,
    )
    return ApiResponse(data=[TopicResponse.from_model(topic) for topic in topics])

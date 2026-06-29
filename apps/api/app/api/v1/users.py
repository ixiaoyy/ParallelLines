from typing import Annotated, Literal

from fastapi import APIRouter, Query
from starlette.responses import Response

from app.api.v1.dependencies import CurrentUserDep, OptionalCurrentUserDep, SessionDep, SettingsDep
from app.schemas.common import ApiResponse
from app.schemas.forum import TopicResponse
from app.schemas.privacy import (
    PrivacyActionRequest,
    PrivacyActionResponse,
    RetentionPolicyResponse,
)
from app.schemas.users import (
    PrivateMessageCreateRequest,
    PrivateMessageTopicResponse,
    UserActivityItemResponse,
    UserDirectoryResponse,
    UserProfileResponse,
    UserProfileUpdateRequest,
    UserRelationshipStateResponse,
    UserRelationshipUserResponse,
)
from app.services.backups import BackupService
from app.services.forum import ForumService
from app.services.privacy import PrivacyService
from app.services.social import SocialService
from app.services.users import UserProfileService

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


@router.delete("/me", response_model=ApiResponse[PrivacyActionResponse])
async def delete_current_user(
    session: SessionDep,
    settings: SettingsDep,
    current_user: CurrentUserDep,
    payload: PrivacyActionRequest | None = None,
) -> ApiResponse[PrivacyActionResponse]:
    result = await PrivacyService(session, settings).delete_current_user(
        current_user,
        reason=payload.reason if payload else None,
    )
    return ApiResponse(data=result)


@router.get("/privacy/retention", response_model=ApiResponse[RetentionPolicyResponse])
async def privacy_retention_policy(
    session: SessionDep,
    settings: SettingsDep,
) -> ApiResponse[RetentionPolicyResponse]:
    return ApiResponse(data=await PrivacyService(session, settings).retention_policy())


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
    from app.api.v1.topics import invalidate_topic_write_response_caches

    invalidate_topic_write_response_caches()
    return ApiResponse(data=message)


@router.get("/directory", response_model=ApiResponse[list[UserDirectoryResponse]])
async def list_user_directory(
    session: SessionDep,
    sort: Annotated[str, Query(pattern="^(active|level|contribution)$")] = "active",
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> ApiResponse[list[UserDirectoryResponse]]:
    users = await UserProfileService(session).list_directory(sort=sort, limit=limit)
    return ApiResponse(data=users)


@router.patch("/me/profile", response_model=ApiResponse[UserProfileResponse])
async def update_my_profile(
    payload: UserProfileUpdateRequest,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> ApiResponse[UserProfileResponse]:
    profile = await UserProfileService(session).update_my_profile(payload, current_user)
    return ApiResponse(data=profile)


# get_user_profile_by_id 用途：按稳定用户 ID 返回公开资料，供浏览器 `/members/:id` 使用。
# 关键参数：user_id 来自成员页路由，current_user 用于隐私字段可见性判定。
# 返回值/副作用：返回用户资料响应，无写入副作用。
@router.get("/id/{user_id}", response_model=ApiResponse[UserProfileResponse])
async def get_user_profile_by_id(
    user_id: str,
    session: SessionDep,
    current_user: OptionalCurrentUserDep,
) -> ApiResponse[UserProfileResponse]:
    profile = await UserProfileService(session).get_profile_by_id(
        user_id,
        current_user=current_user,
    )
    return ApiResponse(data=profile)


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


# list_user_relationships 用途：返回用户关注/粉丝列表。
# 关键参数：kind 限定列表方向，current_user 用于资料隐私判定。
# 返回值/副作用：返回公开安全的用户卡片数组，无写入副作用。
@router.get(
    "/{username}/relationships/{kind}",
    response_model=ApiResponse[list[UserRelationshipUserResponse]],
)
async def list_user_relationships(
    username: str,
    kind: Literal["following", "followers"],
    session: SessionDep,
    current_user: OptionalCurrentUserDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> ApiResponse[list[UserRelationshipUserResponse]]:
    users = await UserProfileService(session).list_relationship_users(
        username,
        kind=kind,
        current_user=current_user,
        limit=limit,
    )
    return ApiResponse(data=users)


@router.get("/{username}", response_model=ApiResponse[UserProfileResponse])
async def get_user_profile(
    username: str,
    session: SessionDep,
    current_user: OptionalCurrentUserDep,
) -> ApiResponse[UserProfileResponse]:
    profile = await UserProfileService(session).get_profile(username, current_user=current_user)
    return ApiResponse(data=profile)


@router.get("/{username}/activity", response_model=ApiResponse[list[UserActivityItemResponse]])
async def list_user_activity(
    username: str,
    session: SessionDep,
    current_user: OptionalCurrentUserDep,
    activity_type: Annotated[
        str,
        Query(alias="type", pattern="^(posts|likes|bookmarks)$"),
    ] = "posts",
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
) -> ApiResponse[list[UserActivityItemResponse]]:
    activity = await UserProfileService(session).list_activity(
        username,
        current_user=current_user,
        activity_type=activity_type,
        limit=limit,
    )
    return ApiResponse(data=activity)


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

from typing import Annotated

from fastapi import APIRouter, File, Form, Query, Request, UploadFile, status
from fastapi.responses import FileResponse

from app.api.v1.dependencies import CurrentUserDep, OptionalCurrentUserDep, SessionDep, SettingsDep
from app.schemas.common import ApiResponse
from app.schemas.uploads import UploadKind, UploadResponse
from app.schemas.users import UserPublic
from app.services.uploads import UploadService, content_disposition

router = APIRouter(prefix="/uploads", tags=["uploads"])


@router.post(
    "",
    response_model=ApiResponse[UploadResponse],
    status_code=status.HTTP_201_CREATED,
)
async def upload_file(
    request: Request,
    session: SessionDep,
    settings: SettingsDep,
    current_user: CurrentUserDep,
    file: Annotated[UploadFile, File()],
    kind: Annotated[UploadKind, Form()] = "post_attachment",
) -> ApiResponse[UploadResponse]:
    if kind == "avatar":
        upload = await UploadService(session, settings).update_avatar(file, current_user, request)
    else:
        upload = await UploadService(session, settings).create_post_upload(
            file,
            current_user,
            request,
        )
        await session.commit()
    return ApiResponse(data=UploadResponse.from_model(upload))


@router.post(
    "/avatar",
    response_model=ApiResponse[UserPublic],
    status_code=status.HTTP_200_OK,
)
async def upload_avatar(
    request: Request,
    session: SessionDep,
    settings: SettingsDep,
    current_user: CurrentUserDep,
    file: Annotated[UploadFile, File()],
) -> ApiResponse[UserPublic]:
    await UploadService(session, settings).update_avatar(file, current_user, request)
    return ApiResponse(data=UserPublic.model_validate(current_user))


@router.get("/{upload_id}/content")
async def get_upload_content(
    upload_id: str,
    session: SessionDep,
    settings: SettingsDep,
    current_user: OptionalCurrentUserDep,
    download: Annotated[bool, Query()] = False,
) -> FileResponse:
    content = await UploadService(session, settings).get_upload_content(upload_id, current_user)
    inline = content.upload.is_image and not download
    headers = {
        "Content-Disposition": content_disposition(
            content.upload.original_filename,
            inline=inline,
        )
    }
    return FileResponse(
        content.path,
        media_type=content.upload.media_type,
        filename=content.upload.original_filename,
        headers=headers,
    )

from typing import Annotated

from fastapi import APIRouter, File, Form, Query, Request, UploadFile, status
from fastapi.responses import RedirectResponse, Response

from app.api.v1.dependencies import CurrentUserDep, OptionalCurrentUserDep, SessionDep, SettingsDep
from app.core.response_cache import scoped_cache_control
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
    service = UploadService(session, settings)
    if kind == "avatar":
        upload = await service.update_avatar(file, current_user, request)
    else:
        upload = await service.create_post_upload(
            file,
            current_user,
            request,
        )
        await session.commit()
    public_url = (
        service.public_upload_url(upload)
        if settings.upload_public_cdn_urls and upload.is_image
        else None
    )
    return ApiResponse(data=UploadResponse.from_model(upload, url=public_url))


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
) -> Response:
    service = UploadService(session, settings)
    upload = await service.get_upload_for_delivery(upload_id, current_user)
    inline = upload.is_image and not download
    public_url = service.public_upload_url(upload)
    if public_url and inline:
        return RedirectResponse(
            public_url,
            status_code=status.HTTP_302_FOUND,
            headers=upload_redirect_headers(current_user),
        )

    content = await service.read_upload_content(upload)
    headers = upload_file_headers(
        current_user,
        content_disposition=content_disposition(
            upload.original_filename,
            inline=inline,
        ),
    )
    return Response(
        content.content,
        media_type=upload.media_type,
        headers=headers,
    )


@router.get("/{upload_id}/thumbnail")
async def get_upload_thumbnail(
    upload_id: str,
    session: SessionDep,
    settings: SettingsDep,
    current_user: OptionalCurrentUserDep,
) -> Response:
    service = UploadService(session, settings)
    thumbnail = await service.get_upload_thumbnail(
        upload_id,
        current_user,
    )
    public_url = service.public_upload_url(thumbnail.upload, thumbnail=True)
    if public_url:
        return RedirectResponse(
            public_url,
            status_code=status.HTTP_302_FOUND,
            headers=upload_redirect_headers(current_user),
        )

    headers = upload_file_headers(
        current_user,
        content_disposition=content_disposition(
            f"{thumbnail.upload.id}-thumbnail.webp",
            inline=True,
        ),
    )
    return Response(
        thumbnail.content,
        media_type=thumbnail.media_type,
        headers=headers,
    )


def upload_file_headers(current_user: object | None, *, content_disposition: str) -> dict[str, str]:
    """Build safe cache and disposition headers for upload file responses.

    Key parameters are the optional current user and final Content-Disposition
    value. Return value is a response header dict. Side effect: none.
    """
    return {
        "Cache-Control": scoped_cache_control(
            current_user,
            max_age=86_400,
            stale_while_revalidate=604_800,
        ),
        "Content-Disposition": content_disposition,
        "X-Content-Type-Options": "nosniff",
    }


def upload_redirect_headers(current_user: object | None) -> dict[str, str]:
    """Build cache headers for short API redirects to public upload objects.

    Key parameter is the optional current user. Return value is a response header
    dict for the redirect itself. Side effect: none.
    """
    return {
        "Cache-Control": scoped_cache_control(
            current_user,
            max_age=300,
            stale_while_revalidate=3600,
        ),
        "X-Content-Type-Options": "nosniff",
    }

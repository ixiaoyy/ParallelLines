from typing import Annotated

from fastapi import APIRouter, File, Form, Request, Response, UploadFile, status
from pydantic import ValidationError as PydanticValidationError

from app.api.v1.dependencies import CurrentUserDep, SessionDep, SettingsDep
from app.core.exceptions import AppError
from app.schemas.catalog import (
    AdminCatalogCategoryResponse,
    AdminCatalogProjectResponse,
    AdminCatalogResponse,
    AdminCatalogSubmissionResponse,
    CatalogCategoryCreateRequest,
    CatalogCategoryUpdateRequest,
    CatalogProjectCreateRequest,
    CatalogProjectUpdateRequest,
    CatalogRatingCreateRequest,
    CatalogRatingStateResponse,
    CatalogResponse,
    CatalogSubmissionCreateRequest,
    CatalogSubmissionCreateResponse,
    CatalogSubmissionReviewRequest,
    CatalogViewStateResponse,
)
from app.schemas.common import ApiResponse
from app.services.catalog import CatalogService
from app.services.catalog_submissions import CatalogSubmissionError, CatalogSubmissionService

router = APIRouter(prefix="/catalog", tags=["catalog"])
admin_router = APIRouter(prefix="/admin/catalog", tags=["admin"])


@router.get("", response_model=ApiResponse[CatalogResponse])
async def get_catalog(
    request: Request, response: Response, session: SessionDep, settings: SettingsDep
) -> ApiResponse[CatalogResponse]:
    """公开可见目录及当前访客的历史评分；响应不得由共享缓存保存。"""

    response.headers["Cache-Control"] = "private, no-store"
    return ApiResponse(data=await CatalogService(session, settings).public_catalog(request))


@router.post(
    "/projects/{project_id}/views",
    response_model=ApiResponse[CatalogViewStateResponse],
)
async def record_catalog_project_view(
    project_id: str,
    response: Response,
    session: SessionDep,
    settings: SettingsDep,
) -> ApiResponse[CatalogViewStateResponse]:
    """为公开项目的一次打开累计计数，返回提交后的总次数。"""

    response.headers["Cache-Control"] = "private, no-store"
    state = await CatalogService(session, settings).record_view(project_id)
    return ApiResponse(data=state)


@router.post(
    "/projects/{project_id}/ratings",
    response_model=ApiResponse[CatalogRatingStateResponse],
)
async def rate_catalog_project(
    project_id: str,
    payload: CatalogRatingCreateRequest,
    request: Request,
    response: Response,
    session: SessionDep,
    settings: SettingsDep,
) -> ApiResponse[CatalogRatingStateResponse]:
    """保存访客对可见项目的首次评分，重复提交只返回原分数。"""

    response.headers["Cache-Control"] = "private, no-store"
    state = await CatalogService(session, settings).rate_project(project_id, payload.score, request)
    return ApiResponse(data=state)


@router.post(
    "/submissions",
    response_model=ApiResponse[CatalogSubmissionCreateResponse],
    status_code=status.HTTP_201_CREATED,
)
async def submit_catalog_project(
    category_name: Annotated[str, Form(min_length=1, max_length=120)],
    project_name: Annotated[str, Form(min_length=1, max_length=120)],
    url: Annotated[str, Form(min_length=9, max_length=2048)],
    request: Request,
    response: Response,
    session: SessionDep,
    settings: SettingsDep,
    author_name: Annotated[str | None, Form(max_length=120)] = None,
    contact: Annotated[str | None, Form(max_length=200)] = None,
    cover: Annotated[UploadFile | None, File()] = None,
) -> ApiResponse[CatalogSubmissionCreateResponse]:
    """游客提交待审目录项目；可选封面与投稿记录在同一事务绑定。"""

    response.headers["Cache-Control"] = "private, no-store"
    try:
        payload = CatalogSubmissionCreateRequest(
            category_name=category_name,
            project_name=project_name,
            url=url,
            author_name=author_name,
            contact=contact,
        )
    except PydanticValidationError as exc:
        raise AppError("validation_error", "Request validation failed", status_code=422) from exc
    try:
        result = await CatalogSubmissionService(session, settings).create_submission(
            payload, request, cover
        )
    except CatalogSubmissionError as exc:
        raise _submission_api_error(exc) from exc
    return ApiResponse(data=result)


@admin_router.get("", response_model=ApiResponse[AdminCatalogResponse])
async def get_admin_catalog(
    response: Response,
    session: SessionDep,
    settings: SettingsDep,
    current_user: CurrentUserDep,
) -> ApiResponse[AdminCatalogResponse]:
    """仅管理员可查看含隐藏内容的完整目录。"""

    response.headers["Cache-Control"] = "private, no-store"
    return ApiResponse(data=await CatalogService(session, settings).admin_catalog(current_user))


@admin_router.post(
    "/categories",
    response_model=ApiResponse[AdminCatalogCategoryResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_catalog_category(
    payload: CatalogCategoryCreateRequest,
    session: SessionDep,
    settings: SettingsDep,
    current_user: CurrentUserDep,
) -> ApiResponse[AdminCatalogCategoryResponse]:
    """新增目录分类。"""

    data = await CatalogService(session, settings).create_category(payload, current_user)
    return ApiResponse(data=data)


@admin_router.put(
    "/categories/{category_id}", response_model=ApiResponse[AdminCatalogCategoryResponse]
)
async def update_catalog_category(
    category_id: str,
    payload: CatalogCategoryUpdateRequest,
    session: SessionDep,
    settings: SettingsDep,
    current_user: CurrentUserDep,
) -> ApiResponse[AdminCatalogCategoryResponse]:
    """编辑或隐藏目录分类。"""

    data = await CatalogService(session, settings).update_category(
        category_id, payload, current_user
    )
    return ApiResponse(data=data)


@admin_router.post(
    "/projects",
    response_model=ApiResponse[AdminCatalogProjectResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_catalog_project(
    payload: CatalogProjectCreateRequest,
    session: SessionDep,
    settings: SettingsDep,
    current_user: CurrentUserDep,
) -> ApiResponse[AdminCatalogProjectResponse]:
    """新增目录项目。"""

    data = await CatalogService(session, settings).create_project(payload, current_user)
    return ApiResponse(data=data)


@admin_router.put("/projects/{project_id}", response_model=ApiResponse[AdminCatalogProjectResponse])
async def update_catalog_project(
    project_id: str,
    payload: CatalogProjectUpdateRequest,
    session: SessionDep,
    settings: SettingsDep,
    current_user: CurrentUserDep,
) -> ApiResponse[AdminCatalogProjectResponse]:
    """编辑或隐藏目录项目。"""

    data = await CatalogService(session, settings).update_project(project_id, payload, current_user)
    return ApiResponse(data=data)


@admin_router.get(
    "/submissions",
    response_model=ApiResponse[list[AdminCatalogSubmissionResponse]],
)
async def get_pending_catalog_submissions(
    response: Response,
    session: SessionDep,
    settings: SettingsDep,
    current_user: CurrentUserDep,
) -> ApiResponse[list[AdminCatalogSubmissionResponse]]:
    """仅管理员读取待审投稿及封面预览地址。"""

    response.headers["Cache-Control"] = "private, no-store"
    try:
        data = await CatalogSubmissionService(session, settings).list_pending(current_user)
    except CatalogSubmissionError as exc:
        raise _submission_api_error(exc) from exc
    return ApiResponse(data=data)


@admin_router.get("/submissions/{submission_id}/cover")
async def get_catalog_submission_cover(
    submission_id: str,
    session: SessionDep,
    settings: SettingsDep,
    current_user: CurrentUserDep,
) -> Response:
    """管理员从 API 读取待审封面字节，不暴露未批准的 CDN 地址。"""

    try:
        content = await CatalogSubmissionService(session, settings).get_cover(
            submission_id, current_user
        )
    except CatalogSubmissionError as exc:
        raise _submission_api_error(exc) from exc
    return Response(
        content=content.content,
        media_type=content.upload.media_type,
        headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"},
    )


@admin_router.post(
    "/submissions/{submission_id}/review",
    response_model=ApiResponse[AdminCatalogSubmissionResponse],
)
async def review_catalog_submission(
    submission_id: str,
    payload: CatalogSubmissionReviewRequest,
    response: Response,
    session: SessionDep,
    settings: SettingsDep,
    current_user: CurrentUserDep,
) -> ApiResponse[AdminCatalogSubmissionResponse]:
    """管理员审核；通过时创建可见目录项目并公开已压缩封面。"""

    response.headers["Cache-Control"] = "private, no-store"
    try:
        data = await CatalogSubmissionService(session, settings).review_submission(
            submission_id, payload.decision, current_user
        )
    except CatalogSubmissionError as exc:
        raise _submission_api_error(exc) from exc
    return ApiResponse(data=data)


def _submission_api_error(exc: CatalogSubmissionError) -> AppError:
    """将审核服务的内部结果映射为现有通用文案和稳定 HTTP 状态。"""

    status_codes = {
        "invalid": 422,
        "duplicate": 409,
        "conflict": 409,
        "hidden_category": 409,
        "rate_limited": 429,
        "not_found": 404,
        "forbidden": 403,
        "unavailable": 503,
    }
    messages = {
        "not_found": "Resource not found",
        "forbidden": "Permission denied",
        "rate_limited": "Too many requests",
        "unavailable": "保存失败，请稍后重试。",
    }
    return AppError(
        f"catalog_submission_{exc.code}",
        messages.get(exc.code, "Validation failed"),
        status_code=status_codes.get(exc.code, 503),
    )

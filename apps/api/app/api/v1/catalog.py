from fastapi import APIRouter, Request, Response, status

from app.api.v1.dependencies import CurrentUserDep, SessionDep, SettingsDep
from app.schemas.catalog import (
    AdminCatalogCategoryResponse,
    AdminCatalogProjectResponse,
    AdminCatalogResponse,
    CatalogCategoryCreateRequest,
    CatalogCategoryUpdateRequest,
    CatalogProjectCreateRequest,
    CatalogProjectUpdateRequest,
    CatalogRatingCreateRequest,
    CatalogRatingStateResponse,
    CatalogResponse,
)
from app.schemas.common import ApiResponse
from app.services.catalog import CatalogService

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

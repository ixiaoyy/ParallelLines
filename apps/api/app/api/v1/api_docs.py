from fastapi import APIRouter

from app.core.openapi_contract import (
    AUTH_EXAMPLE,
    COMPATIBILITY_POLICY,
    ERROR_EXAMPLE,
    PAGINATION_EXAMPLE,
    REQUEST_EXAMPLES,
)
from app.schemas.api_docs import PublicApiDocsResponse
from app.schemas.common import ApiResponse

router = APIRouter(prefix="/docs", tags=["docs"])


@router.get("/public", response_model=ApiResponse[PublicApiDocsResponse])
async def public_api_docs() -> ApiResponse[PublicApiDocsResponse]:
    return ApiResponse(
        data=PublicApiDocsResponse(
            api_version=str(COMPATIBILITY_POLICY["api_version"]),
            openapi_url="/api/v1/openapi.json",
            authentication=AUTH_EXAMPLE,
            pagination=PAGINATION_EXAMPLE,
            error_shape=ERROR_EXAMPLE,
            compatibility_policy=COMPATIBILITY_POLICY,
            examples=REQUEST_EXAMPLES,
        )
    )

from fastapi import APIRouter

from app.schemas.common import ApiResponse

router = APIRouter(tags=["health"])


@router.get("/healthz", response_model=ApiResponse[dict[str, str]])
async def healthz() -> ApiResponse[dict[str, str]]:
    return ApiResponse(data={"status": "ok", "service": "parallellines-api"})

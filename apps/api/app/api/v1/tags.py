from typing import Annotated

from fastapi import APIRouter, Query

from app.api.v1.dependencies import SessionDep
from app.schemas.common import ApiResponse
from app.schemas.forum import TagResponse
from app.services.forum import ForumService

router = APIRouter(prefix="/tags", tags=["tags"])


@router.get("", response_model=ApiResponse[list[TagResponse]])
async def list_tags(
    session: SessionDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
) -> ApiResponse[list[TagResponse]]:
    tags = await ForumService(session).list_tags(limit=limit)
    return ApiResponse(data=[TagResponse.model_validate(tag) for tag in tags])

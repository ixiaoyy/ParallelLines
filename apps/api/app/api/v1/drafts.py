from fastapi import APIRouter, Query

from app.api.v1.dependencies import CurrentUserDep, SessionDep
from app.schemas.common import ApiResponse
from app.schemas.drafts import DraftResponse, DraftSaveRequest
from app.services.draft import DraftService

router = APIRouter(prefix="/drafts", tags=["drafts"])


@router.get("/lookup", response_model=ApiResponse[DraftResponse | None])
async def lookup_draft(
    target_type: str,
    target_id: str = Query(default=""),
    session: SessionDep = None,
    current_user: CurrentUserDep = None,
) -> ApiResponse[DraftResponse | None]:
    draft = await DraftService(session).get_draft(
        user_id=current_user.id,
        target_type=target_type,
        target_id=target_id,
    )
    if not draft:
        return ApiResponse(data=None)
    return ApiResponse(data=DraftResponse.model_validate(draft))


@router.get("", response_model=ApiResponse[list[DraftResponse]])
async def list_drafts(
    session: SessionDep,
    current_user: CurrentUserDep,
) -> ApiResponse[list[DraftResponse]]:
    drafts = await DraftService(session).list_drafts_by_user(user_id=current_user.id)
    return ApiResponse(data=[DraftResponse.model_validate(d) for d in drafts])


@router.put("", response_model=ApiResponse[DraftResponse])
async def save_draft(
    payload: DraftSaveRequest,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> ApiResponse[DraftResponse]:
    draft = await DraftService(session).save_draft(
        user_id=current_user.id,
        target_type=payload.target_type,
        target_id=payload.target_id,
        draft_type=payload.draft_type,
        data=payload.data,
        version=payload.version,
    )
    return ApiResponse(data=DraftResponse.model_validate(draft))


@router.delete("", response_model=ApiResponse[bool])
async def delete_draft(
    target_type: str,
    target_id: str = Query(default=""),
    session: SessionDep = None,
    current_user: CurrentUserDep = None,
) -> ApiResponse[bool]:
    success = await DraftService(session).delete_draft(
        user_id=current_user.id,
        target_type=target_type,
        target_id=target_id,
    )
    return ApiResponse(data=success)

from typing import Annotated

from fastapi import APIRouter, Query

from app.api.v1.dependencies import CurrentUserDep, OptionalCurrentUserDep, SessionDep
from app.schemas.common import ApiResponse
from app.schemas.space import (
    SpaceJournalCreateRequest,
    SpaceJournalItemResponse,
    SpaceJournalUpdateRequest,
    SpaceLedgerCreateRequest,
    SpaceLedgerItemResponse,
    SpaceMyWorkspaceResponse,
    SpacePublicProfileResponse,
    SpaceSettingResponse,
    SpaceSettingUpdateRequest,
)
from app.services.space import SpaceService

router = APIRouter(prefix="/space", tags=["space"])


@router.get("/me", response_model=ApiResponse[SpaceMyWorkspaceResponse])
async def get_my_space_workspace(
    session: SessionDep,
    current_user: CurrentUserDep,
    month: Annotated[str | None, Query(pattern=r"^\d{4}-\d{2}$")] = None,
) -> ApiResponse[SpaceMyWorkspaceResponse]:
    workspace = await SpaceService(session).get_my_workspace(current_user, month=month)
    return ApiResponse(data=workspace)


@router.put("/settings", response_model=ApiResponse[SpaceSettingResponse])
async def update_my_space_settings(
    payload: SpaceSettingUpdateRequest,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> ApiResponse[SpaceSettingResponse]:
    settings = await SpaceService(session).update_settings(current_user.id, payload)
    return ApiResponse(data=settings)


@router.post("/journals", response_model=ApiResponse[SpaceJournalItemResponse], status_code=201)
async def create_journal_entry(
    payload: SpaceJournalCreateRequest,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> ApiResponse[SpaceJournalItemResponse]:
    entry = await SpaceService(session).create_journal(current_user, payload)
    return ApiResponse(data=entry)


@router.patch("/journals/{entry_id}", response_model=ApiResponse[SpaceJournalItemResponse])
async def update_journal_entry(
    entry_id: str,
    payload: SpaceJournalUpdateRequest,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> ApiResponse[SpaceJournalItemResponse]:
    entry = await SpaceService(session).update_journal(current_user, entry_id, payload)
    return ApiResponse(data=entry)


@router.delete("/journals/{entry_id}", response_model=ApiResponse[bool])
async def delete_journal_entry(
    entry_id: str,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> ApiResponse[bool]:
    deleted = await SpaceService(session).delete_journal(current_user, entry_id)
    return ApiResponse(data=deleted)


@router.post("/journals/{entry_id}/like", response_model=ApiResponse[SpaceJournalItemResponse])
async def like_journal_entry(
    entry_id: str,
    session: SessionDep,
    viewer: OptionalCurrentUserDep = None,
) -> ApiResponse[SpaceJournalItemResponse]:
    entry = await SpaceService(session).like_journal(entry_id, viewer=viewer)
    return ApiResponse(data=entry)


@router.post("/ledger", response_model=ApiResponse[SpaceLedgerItemResponse], status_code=201)
async def create_ledger_entry(
    payload: SpaceLedgerCreateRequest,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> ApiResponse[SpaceLedgerItemResponse]:
    entry = await SpaceService(session).create_ledger_entry(current_user, payload)
    return ApiResponse(data=entry)


@router.delete("/ledger/{entry_id}", response_model=ApiResponse[bool])
async def delete_ledger_entry(
    entry_id: str,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> ApiResponse[bool]:
    deleted = await SpaceService(session).delete_ledger_entry(current_user, entry_id)
    return ApiResponse(data=deleted)


@router.get("/feed", response_model=ApiResponse[list[SpaceJournalItemResponse]])
async def list_public_space_feed(
    session: SessionDep,
    limit: Annotated[int, Query(ge=1, le=80)] = 30,
) -> ApiResponse[list[SpaceJournalItemResponse]]:
    feed = await SpaceService(session).list_public_feed(limit=limit)
    return ApiResponse(data=feed)


@router.get("/users/{identifier}", response_model=ApiResponse[SpacePublicProfileResponse])
async def get_public_user_space(
    identifier: str,
    session: SessionDep,
    viewer: OptionalCurrentUserDep = None,
) -> ApiResponse[SpacePublicProfileResponse]:
    space = await SpaceService(session).get_public_user_space(identifier, viewer=viewer)
    return ApiResponse(data=space)

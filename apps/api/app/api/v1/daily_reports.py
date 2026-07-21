from fastapi import APIRouter, Query, Request, status

from app.api.v1.dependencies import CurrentUserDep, SessionDep, SettingsDep
from app.schemas.common import ApiResponse
from app.schemas.daily_report import (
    DailyReportPreferenceAcceptRequest,
    DailyReportProfileResponse,
    DailyReportProfileUpdateRequest,
    DailyReportResponse,
    DailyReportSessionConfirmRequest,
    DailyReportSessionFollowupRequest,
    DailyReportSessionResponse,
    DailyReportSessionStartRequest,
)
from app.services.daily_reports import DailyReportService
from app.services.spam import SpamPreventionService

router = APIRouter(prefix="/daily-reports", tags=["daily-reports"])


@router.get("/profile", response_model=ApiResponse[DailyReportProfileResponse])
async def get_daily_report_profile(
    session: SessionDep,
    current_user: CurrentUserDep,
    settings: SettingsDep,
) -> ApiResponse[DailyReportProfileResponse]:
    return ApiResponse(data=await DailyReportService(session, settings).get_profile(current_user))


@router.put("/profile", response_model=ApiResponse[DailyReportProfileResponse])
async def update_daily_report_profile(
    payload: DailyReportProfileUpdateRequest,
    session: SessionDep,
    current_user: CurrentUserDep,
    settings: SettingsDep,
) -> ApiResponse[DailyReportProfileResponse]:
    return ApiResponse(
        data=await DailyReportService(session, settings).update_profile(payload, current_user)
    )


@router.post("/profile/reset", response_model=ApiResponse[DailyReportProfileResponse])
async def reset_daily_report_profile(
    session: SessionDep,
    current_user: CurrentUserDep,
    settings: SettingsDep,
) -> ApiResponse[DailyReportProfileResponse]:
    return ApiResponse(data=await DailyReportService(session, settings).reset_profile(current_user))


@router.post("/profile/preferences", response_model=ApiResponse[DailyReportProfileResponse])
async def accept_daily_report_preference(
    payload: DailyReportPreferenceAcceptRequest,
    session: SessionDep,
    current_user: CurrentUserDep,
    settings: SettingsDep,
) -> ApiResponse[DailyReportProfileResponse]:
    return ApiResponse(
        data=await DailyReportService(session, settings).accept_preference(payload, current_user)
    )


@router.post(
    "/sessions",
    response_model=ApiResponse[DailyReportSessionResponse],
    status_code=status.HTTP_201_CREATED,
)
async def start_daily_report_session(
    request: Request,
    payload: DailyReportSessionStartRequest,
    session: SessionDep,
    current_user: CurrentUserDep,
    settings: SettingsDep,
) -> ApiResponse[DailyReportSessionResponse]:
    await SpamPreventionService(session, settings).enforce_daily_report(
        request,
        current_user=current_user,
    )
    return ApiResponse(
        data=await DailyReportService(session, settings).start_session(payload, current_user)
    )


@router.get("/sessions/{session_id}", response_model=ApiResponse[DailyReportSessionResponse])
async def get_daily_report_session(
    session_id: str,
    session: SessionDep,
    current_user: CurrentUserDep,
    settings: SettingsDep,
) -> ApiResponse[DailyReportSessionResponse]:
    return ApiResponse(
        data=await DailyReportService(session, settings).get_session(session_id, current_user)
    )


@router.post(
    "/sessions/{session_id}/messages",
    response_model=ApiResponse[DailyReportSessionResponse],
)
async def continue_daily_report_session(
    request: Request,
    session_id: str,
    payload: DailyReportSessionFollowupRequest,
    session: SessionDep,
    current_user: CurrentUserDep,
    settings: SettingsDep,
) -> ApiResponse[DailyReportSessionResponse]:
    await SpamPreventionService(session, settings).enforce_daily_report(
        request,
        current_user=current_user,
    )
    return ApiResponse(
        data=await DailyReportService(session, settings).followup(
            session_id,
            payload,
            current_user,
        )
    )


@router.post(
    "/sessions/{session_id}/confirm",
    response_model=ApiResponse[DailyReportResponse],
)
async def confirm_daily_report_session(
    session_id: str,
    payload: DailyReportSessionConfirmRequest,
    session: SessionDep,
    current_user: CurrentUserDep,
    settings: SettingsDep,
) -> ApiResponse[DailyReportResponse]:
    return ApiResponse(
        data=await DailyReportService(session, settings).confirm(
            session_id,
            payload,
            current_user,
        )
    )


@router.get("", response_model=ApiResponse[list[DailyReportResponse]])
async def list_daily_reports(
    session: SessionDep,
    current_user: CurrentUserDep,
    settings: SettingsDep,
    limit: int = Query(default=30, ge=1, le=100),
) -> ApiResponse[list[DailyReportResponse]]:
    return ApiResponse(
        data=await DailyReportService(session, settings).list_reports(current_user, limit)
    )


@router.delete("/history", response_model=ApiResponse[bool])
async def clear_daily_report_history(
    session: SessionDep,
    current_user: CurrentUserDep,
    settings: SettingsDep,
) -> ApiResponse[bool]:
    return ApiResponse(data=await DailyReportService(session, settings).clear_history(current_user))


@router.delete("/{report_id}", response_model=ApiResponse[bool])
async def delete_daily_report(
    report_id: str,
    session: SessionDep,
    current_user: CurrentUserDep,
    settings: SettingsDep,
) -> ApiResponse[bool]:
    return ApiResponse(
        data=await DailyReportService(session, settings).delete_report(report_id, current_user)
    )

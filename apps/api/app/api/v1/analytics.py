from datetime import date
from typing import Annotated

from fastapi import APIRouter, Query
from starlette.responses import Response

from app.api.v1.dependencies import CurrentUserDep, SessionDep
from app.schemas.analytics import (
    AnalyticsOverviewResponse,
    DataExplorerReportResponse,
    DataExplorerReportSummary,
)
from app.schemas.common import ApiResponse
from app.services.analytics import AnalyticsService

router = APIRouter(prefix="/admin/analytics", tags=["admin"])


@router.get("", response_model=ApiResponse[AnalyticsOverviewResponse])
async def analytics_overview(
    session: SessionDep,
    current_user: CurrentUserDep,
    start_date: date | None = None,
    end_date: date | None = None,
) -> ApiResponse[AnalyticsOverviewResponse]:
    return ApiResponse(
        data=await AnalyticsService(session).overview(
            current_user,
            start_date=start_date,
            end_date=end_date,
        )
    )


@router.get("/reports", response_model=ApiResponse[list[DataExplorerReportSummary]])
async def list_data_explorer_reports(
    session: SessionDep,
    current_user: CurrentUserDep,
) -> ApiResponse[list[DataExplorerReportSummary]]:
    return ApiResponse(data=await AnalyticsService(session).report_summaries(current_user))


@router.get("/reports/{report_id}", response_model=ApiResponse[DataExplorerReportResponse])
async def run_data_explorer_report(
    report_id: str,
    session: SessionDep,
    current_user: CurrentUserDep,
    start_date: date | None = None,
    end_date: date | None = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> ApiResponse[DataExplorerReportResponse]:
    return ApiResponse(
        data=await AnalyticsService(session).run_report(
            current_user,
            report_id,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
        )
    )


@router.get("/reports/{report_id}/export.csv")
async def export_data_explorer_report(
    report_id: str,
    session: SessionDep,
    current_user: CurrentUserDep,
    start_date: date | None = None,
    end_date: date | None = None,
    limit: Annotated[int, Query(ge=1, le=5000)] = 1000,
) -> Response:
    csv_text = await AnalyticsService(session).export_report_csv(
        current_user,
        report_id,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
    )
    return Response(
        content=csv_text.encode("utf-8-sig"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{report_id}.csv"'},
    )

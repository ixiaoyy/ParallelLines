from typing import Annotated

from fastapi import APIRouter, Header, Request

from app.api.v1.dependencies import CurrentUserDep, SessionDep, SettingsDep
from app.schemas.common import ApiResponse
from app.schemas.payments import (
    PaymentEventResponse,
    PaymentWebhookResponse,
    SubscriptionPlanResponse,
    UserSubscriptionResponse,
)
from app.services.payments import PaymentService

router = APIRouter(tags=["payments"])


@router.get("/subscriptions/plans", response_model=ApiResponse[list[SubscriptionPlanResponse]])
async def list_subscription_plans(
    session: SessionDep,
    settings: SettingsDep,
) -> ApiResponse[list[SubscriptionPlanResponse]]:
    return ApiResponse(data=await PaymentService(session, settings).list_plans())


@router.get("/subscriptions/me", response_model=ApiResponse[UserSubscriptionResponse])
async def my_subscription(
    session: SessionDep,
    settings: SettingsDep,
    current_user: CurrentUserDep,
) -> ApiResponse[UserSubscriptionResponse]:
    return ApiResponse(
        data=await PaymentService(session, settings).current_subscription(current_user)
    )


@router.get("/admin/payments/events", response_model=ApiResponse[list[PaymentEventResponse]])
async def list_payment_events(
    session: SessionDep,
    settings: SettingsDep,
    current_user: CurrentUserDep,
) -> ApiResponse[list[PaymentEventResponse]]:
    return ApiResponse(
        data=await PaymentService(session, settings).list_payment_events(current_user)
    )


@router.post("/payments/webhooks/{provider}", response_model=ApiResponse[PaymentWebhookResponse])
async def payment_webhook(
    provider: str,
    request: Request,
    session: SessionDep,
    settings: SettingsDep,
    signature: Annotated[str | None, Header(alias="X-ParallelLines-Signature")] = None,
) -> ApiResponse[PaymentWebhookResponse]:
    body = await request.body()
    result = await PaymentService(session, settings).handle_webhook(provider, body, signature)
    return ApiResponse(data=result)

from typing import Annotated

from fastapi import APIRouter, Header

from app.api.v1.dependencies import CurrentUserDep, SessionDep, SettingsDep
from app.core.exceptions import PermissionDeniedError
from app.schemas.common import ApiResponse
from app.schemas.email import (
    EmailDeliveryEventResponse,
    EmailDeliveryWebhookRequest,
    EmailPreferenceResponse,
    EmailPreferenceUpdateRequest,
    InboundEmailResponse,
    InboundEmailWebhookRequest,
)
from app.services.email_notifications import EmailNotificationService

router = APIRouter(prefix="/email", tags=["email"])


@router.get("/preferences", response_model=ApiResponse[EmailPreferenceResponse])
async def get_email_preferences(
    session: SessionDep,
    settings: SettingsDep,
    current_user: CurrentUserDep,
) -> ApiResponse[EmailPreferenceResponse]:
    return ApiResponse(
        data=await EmailNotificationService(session, settings).get_preferences(current_user)
    )


@router.put("/preferences", response_model=ApiResponse[EmailPreferenceResponse])
async def update_email_preferences(
    payload: EmailPreferenceUpdateRequest,
    session: SessionDep,
    settings: SettingsDep,
    current_user: CurrentUserDep,
) -> ApiResponse[EmailPreferenceResponse]:
    return ApiResponse(
        data=await EmailNotificationService(session, settings).update_preferences(
            current_user,
            payload,
        )
    )


@router.post("/webhooks/delivery", response_model=ApiResponse[EmailDeliveryEventResponse])
async def record_delivery_webhook(
    payload: EmailDeliveryWebhookRequest,
    session: SessionDep,
    settings: SettingsDep,
    webhook_secret: Annotated[str | None, Header(alias="X-Email-Webhook-Secret")] = None,
) -> ApiResponse[EmailDeliveryEventResponse]:
    _require_webhook_secret(settings.email_webhook_secret, webhook_secret)
    return ApiResponse(
        data=await EmailNotificationService(session, settings).record_delivery_webhook(payload)
    )


@router.post("/webhooks/inbound-reply", response_model=ApiResponse[InboundEmailResponse])
async def record_inbound_reply_webhook(
    payload: InboundEmailWebhookRequest,
    session: SessionDep,
    settings: SettingsDep,
    webhook_secret: Annotated[str | None, Header(alias="X-Email-Webhook-Secret")] = None,
) -> ApiResponse[InboundEmailResponse]:
    _require_webhook_secret(settings.email_webhook_secret, webhook_secret)
    return ApiResponse(
        data=await EmailNotificationService(session, settings).record_inbound_reply(payload)
    )


def _require_webhook_secret(expected: str | None, received: str | None) -> None:
    if expected and received != expected:
        raise PermissionDeniedError(
            "email_webhook_secret_invalid",
            "Email webhook secret is invalid",
        )

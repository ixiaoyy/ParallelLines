from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Header, Query, Request

from app.api.v1.dependencies import CurrentUserDep, SessionDep
from app.schemas.common import ApiResponse
from app.schemas.integrations import (
    ApiKeyCreateRequest,
    ApiKeyCreateResponse,
    ApiKeyResponse,
    ExternalIntegrationEventResponse,
    ExternalIntegrationResponse,
    ExternalIntegrationUpdateRequest,
    ExternalWebhookResponse,
    GitHubIssuePreviewResponse,
    WebhookDeliveryResponse,
    WebhookEndpointCreateRequest,
    WebhookEndpointCreateResponse,
    WebhookEndpointResponse,
)
from app.services.integrations import IntegrationService

router = APIRouter(tags=["integrations"])


@router.get("/integrations/me", response_model=ApiResponse[ApiKeyResponse])
async def api_key_me(
    request: Request,
    session: SessionDep,
    x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
) -> ApiResponse[ApiKeyResponse]:
    api_key = await IntegrationService(session).authenticate_api_key(
        _api_key_from_request(request, x_api_key),
        required_scope="read",
    )
    return ApiResponse(data=ApiKeyResponse.from_model(api_key))


@router.get("/admin/api-keys", response_model=ApiResponse[list[ApiKeyResponse]])
async def list_api_keys(
    session: SessionDep,
    current_user: CurrentUserDep,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> ApiResponse[list[ApiKeyResponse]]:
    return ApiResponse(
        data=await IntegrationService(session).list_api_keys(current_user, limit=limit)
    )


@router.post("/admin/api-keys", response_model=ApiResponse[ApiKeyCreateResponse], status_code=201)
async def create_api_key(
    payload: ApiKeyCreateRequest,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> ApiResponse[ApiKeyCreateResponse]:
    return ApiResponse(data=await IntegrationService(session).create_api_key(payload, current_user))


@router.post("/admin/api-keys/{key_id}/disable", response_model=ApiResponse[ApiKeyResponse])
async def disable_api_key(
    key_id: str,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> ApiResponse[ApiKeyResponse]:
    return ApiResponse(data=await IntegrationService(session).disable_api_key(key_id, current_user))


@router.get("/admin/webhooks", response_model=ApiResponse[list[WebhookEndpointResponse]])
async def list_webhooks(
    session: SessionDep,
    current_user: CurrentUserDep,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> ApiResponse[list[WebhookEndpointResponse]]:
    return ApiResponse(
        data=await IntegrationService(session).list_webhooks(current_user, limit=limit)
    )


@router.post(
    "/admin/webhooks",
    response_model=ApiResponse[WebhookEndpointCreateResponse],
    status_code=201,
)
async def create_webhook(
    payload: WebhookEndpointCreateRequest,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> ApiResponse[WebhookEndpointCreateResponse]:
    return ApiResponse(data=await IntegrationService(session).create_webhook(payload, current_user))


@router.post(
    "/admin/webhooks/{webhook_id}/disable",
    response_model=ApiResponse[WebhookEndpointResponse],
)
async def disable_webhook(
    webhook_id: str,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> ApiResponse[WebhookEndpointResponse]:
    return ApiResponse(
        data=await IntegrationService(session).disable_webhook(webhook_id, current_user)
    )


@router.get("/admin/webhook-deliveries", response_model=ApiResponse[list[WebhookDeliveryResponse]])
async def list_webhook_deliveries(
    session: SessionDep,
    current_user: CurrentUserDep,
    delivery_status: Annotated[str | None, Query(alias="status")] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> ApiResponse[list[WebhookDeliveryResponse]]:
    return ApiResponse(
        data=await IntegrationService(session).list_webhook_deliveries(
            current_user,
            status=delivery_status,
            limit=limit,
        )
    )


@router.get(
    "/admin/external-integrations",
    response_model=ApiResponse[list[ExternalIntegrationResponse]],
)
async def list_external_integrations(
    session: SessionDep,
    current_user: CurrentUserDep,
) -> ApiResponse[list[ExternalIntegrationResponse]]:
    return ApiResponse(
        data=await IntegrationService(session).list_external_integrations(current_user)
    )


@router.put(
    "/admin/external-integrations/{provider}",
    response_model=ApiResponse[ExternalIntegrationResponse],
)
async def update_external_integration(
    provider: str,
    payload: ExternalIntegrationUpdateRequest,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> ApiResponse[ExternalIntegrationResponse]:
    return ApiResponse(
        data=await IntegrationService(session).update_external_integration(
            provider,
            payload,
            current_user,
        )
    )


@router.get(
    "/admin/external-integrations/events",
    response_model=ApiResponse[list[ExternalIntegrationEventResponse]],
)
async def list_external_integration_events(
    session: SessionDep,
    current_user: CurrentUserDep,
    provider: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> ApiResponse[list[ExternalIntegrationEventResponse]]:
    return ApiResponse(
        data=await IntegrationService(session).list_external_events(
            current_user,
            provider=provider,
            limit=limit,
        )
    )


@router.post(
    "/admin/external-integrations/events/{event_id}/retry",
    response_model=ApiResponse[ExternalIntegrationEventResponse],
)
async def retry_external_integration_event(
    event_id: str,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> ApiResponse[ExternalIntegrationEventResponse]:
    return ApiResponse(
        data=await IntegrationService(session).retry_external_event(event_id, current_user)
    )


@router.post(
    "/integrations/{provider}/webhook",
    response_model=ApiResponse[ExternalWebhookResponse],
)
async def external_provider_webhook(
    provider: str,
    request: Request,
    session: SessionDep,
    x_hub_signature_256: Annotated[str | None, Header(alias="X-Hub-Signature-256")] = None,
    x_github_delivery: Annotated[str | None, Header(alias="X-GitHub-Delivery")] = None,
    x_github_event: Annotated[str | None, Header(alias="X-GitHub-Event")] = None,
) -> ApiResponse[ExternalWebhookResponse]:
    body = await request.body()
    result = await IntegrationService(session).handle_external_webhook(
        provider,
        body,
        {
            "x-hub-signature-256": x_hub_signature_256,
            "x-github-delivery": x_github_delivery,
            "x-github-event": x_github_event,
        },
    )
    return ApiResponse(data=result)


@router.get(
    "/integrations/github/issue",
    response_model=ApiResponse[GitHubIssuePreviewResponse],
)
async def github_issue_preview(
    session: SessionDep,
    url: Annotated[str, Query(min_length=10, max_length=1024)],
) -> ApiResponse[GitHubIssuePreviewResponse]:
    return ApiResponse(data=await IntegrationService(session).unfurl_github_issue(url))


def _api_key_from_request(request: Request, x_api_key: str | None) -> str | None:
    if x_api_key:
        return x_api_key
    authorization = request.headers.get("authorization") or ""
    scheme, _, value = authorization.partition(" ")
    if scheme.lower() == "bearer" and value:
        return value
    return None

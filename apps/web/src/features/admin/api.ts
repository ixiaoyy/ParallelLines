import { apiGet, apiPost, apiPut } from "@/shared/api/client";

import type { BadgeGrantRequest, BadgeResponse, BadgeRevokeRequest } from "@/features/badges/model";
import type {
  AdminEmailLogResponse,
  ApiKeyCreateRequest,
  ApiKeyCreateResponse,
  ApiKeyResponse,
  AdminSystemOverviewResponse,
  AdminUserResponse,
  AdminUsersParams,
  AdminUserUpdateRequest,
  AuditLogResponse,
  PublicSiteSettingsResponse,
  SiteSettingResponse,
  SiteSettingUpdateRequest,
  WebhookDeliveryResponse,
  WebhookEndpointCreateRequest,
  WebhookEndpointCreateResponse,
  WebhookEndpointResponse,
} from "./model";

export function fetchPublicSiteSettings(): Promise<PublicSiteSettingsResponse> {
  return apiGet<PublicSiteSettingsResponse>("/site/settings");
}

export function fetchAdminSettings(): Promise<SiteSettingResponse[]> {
  return apiGet<SiteSettingResponse[]>("/admin/settings");
}

export function updateAdminSetting(
  key: string,
  payload: SiteSettingUpdateRequest,
): Promise<SiteSettingResponse> {
  return apiPut<SiteSettingResponse, SiteSettingUpdateRequest>(`/admin/settings/${key}`, payload);
}

export function fetchAdminUsers(params: AdminUsersParams): Promise<AdminUserResponse[]> {
  const query = new URLSearchParams({ limit: String(params.limit ?? 50) });
  if (params.query) {
    query.set("query", params.query);
  }
  if (params.role) {
    query.set("role", params.role);
  }
  if (params.status) {
    query.set("status", params.status);
  }
  return apiGet<AdminUserResponse[]>(`/admin/users?${query.toString()}`);
}

export function updateAdminUser(
  userId: string,
  payload: AdminUserUpdateRequest,
): Promise<AdminUserResponse> {
  return apiPut<AdminUserResponse, AdminUserUpdateRequest>(`/admin/users/${userId}`, payload);
}

export function fetchAdminBadges(): Promise<BadgeResponse[]> {
  return apiGet<BadgeResponse[]>("/admin/badges");
}

export function grantAdminUserBadge(
  userId: string,
  payload: BadgeGrantRequest,
): Promise<AdminUserResponse> {
  return apiPost<AdminUserResponse, BadgeGrantRequest>(`/admin/users/${userId}/badges`, payload);
}

export function revokeAdminUserBadge(
  userId: string,
  badgeSlug: string,
  payload: BadgeRevokeRequest,
): Promise<AdminUserResponse> {
  return apiPost<AdminUserResponse, BadgeRevokeRequest>(
    `/admin/users/${userId}/badges/${encodeURIComponent(badgeSlug)}/revoke`,
    payload,
  );
}

export function fetchAdminApiKeys(): Promise<ApiKeyResponse[]> {
  return apiGet<ApiKeyResponse[]>("/admin/api-keys");
}

export function createAdminApiKey(
  payload: ApiKeyCreateRequest,
): Promise<ApiKeyCreateResponse> {
  return apiPost<ApiKeyCreateResponse, ApiKeyCreateRequest>("/admin/api-keys", payload);
}

export function disableAdminApiKey(keyId: string): Promise<ApiKeyResponse> {
  return apiPost<ApiKeyResponse, Record<string, never>>(
    `/admin/api-keys/${keyId}/disable`,
    {},
  );
}

export function fetchAdminWebhooks(): Promise<WebhookEndpointResponse[]> {
  return apiGet<WebhookEndpointResponse[]>("/admin/webhooks");
}

export function createAdminWebhook(
  payload: WebhookEndpointCreateRequest,
): Promise<WebhookEndpointCreateResponse> {
  return apiPost<WebhookEndpointCreateResponse, WebhookEndpointCreateRequest>(
    "/admin/webhooks",
    payload,
  );
}

export function disableAdminWebhook(webhookId: string): Promise<WebhookEndpointResponse> {
  return apiPost<WebhookEndpointResponse, Record<string, never>>(
    `/admin/webhooks/${webhookId}/disable`,
    {},
  );
}

export function fetchAdminWebhookDeliveries(limit = 20): Promise<WebhookDeliveryResponse[]> {
  return apiGet<WebhookDeliveryResponse[]>(`/admin/webhook-deliveries?limit=${limit}`);
}

export function fetchAdminSystem(): Promise<AdminSystemOverviewResponse> {
  return apiGet<AdminSystemOverviewResponse>("/admin/system");
}

export function fetchAdminAuditLogs(limit = 50): Promise<AuditLogResponse[]> {
  return apiGet<AuditLogResponse[]>(`/admin/audit-logs?limit=${limit}`);
}

export function fetchAdminEmailLogs(limit = 50): Promise<AdminEmailLogResponse[]> {
  return apiGet<AdminEmailLogResponse[]>(`/admin/email-logs?limit=${limit}`);
}

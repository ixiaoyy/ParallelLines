import { apiDelete, apiGet, apiPost, apiPut } from "@/shared/api/client";

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
  FrontierNewsCollectResponse,
  FrontierNewsItemResponse,
  FrontierNewsItemsParams,
  FrontierNewsSourceCreateRequest,
  FrontierNewsSourceResponse,
  FrontierNewsSourceUpdateRequest,
  PublicSiteSettingsResponse,
  WebhookDeliveryResponse,
  WebhookEndpointCreateRequest,
  WebhookEndpointCreateResponse,
  WebhookEndpointResponse,
} from "./model";

export function fetchPublicSiteSettings(): Promise<PublicSiteSettingsResponse> {
  return apiGet<PublicSiteSettingsResponse>("/site/settings");
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

/**
 * Fetches the admin-managed frontier source whitelist.
 *
 * @returns Promise resolving to configured source rows for the admin panel.
 */
export function fetchFrontierNewsSources(): Promise<FrontierNewsSourceResponse[]> {
  return apiGet<FrontierNewsSourceResponse[]>("/admin/frontier-news/sources");
}

/**
 * Creates one frontier source row from administrator input.
 *
 * @param payload - Source identity, kind, URL, config, and fetch cadence.
 * @returns Promise resolving to the created source.
 */
export function createFrontierNewsSource(
  payload: FrontierNewsSourceCreateRequest,
): Promise<FrontierNewsSourceResponse> {
  return apiPost<FrontierNewsSourceResponse, FrontierNewsSourceCreateRequest>(
    "/admin/frontier-news/sources",
    payload,
  );
}

/**
 * Updates one frontier source and preserves unspecified fields.
 *
 * @param sourceId - Source ID returned by the admin source list.
 * @param payload - Partial changes to source metadata or enabled state.
 * @returns Promise resolving to the updated source.
 */
export function updateFrontierNewsSource(
  sourceId: string,
  payload: FrontierNewsSourceUpdateRequest,
): Promise<FrontierNewsSourceResponse> {
  return apiPut<FrontierNewsSourceResponse, FrontierNewsSourceUpdateRequest>(
    `/admin/frontier-news/sources/${sourceId}`,
    payload,
  );
}

/**
 * Removes one frontier source from the admin source list.
 *
 * @param sourceId - Source ID returned by the admin source list.
 * @returns Promise resolving to the removed source row.
 */
export function deleteFrontierNewsSource(sourceId: string): Promise<FrontierNewsSourceResponse> {
  return apiDelete<FrontierNewsSourceResponse>(`/admin/frontier-news/sources/${sourceId}`);
}

/**
 * Triggers a manual collection pass for every enabled frontier source.
 *
 * @returns Promise resolving to the collection summary counters.
 */
export function collectFrontierNews(): Promise<FrontierNewsCollectResponse> {
  return apiPost<FrontierNewsCollectResponse, Record<string, never>>(
    "/admin/frontier-news/collect",
    {},
  );
}

/**
 * Triggers a manual collection pass for one frontier source.
 *
 * @param sourceId - Source ID to fetch immediately.
 * @returns Promise resolving to the collection summary counters.
 */
export function collectFrontierNewsSource(sourceId: string): Promise<FrontierNewsCollectResponse> {
  return apiPost<FrontierNewsCollectResponse, Record<string, never>>(
    `/admin/frontier-news/sources/${sourceId}/collect`,
    {},
  );
}

/**
 * Fetches collected frontier materials for the admin素材池 table.
 *
 * @param params - Optional status filter and page-size limit.
 * @returns Promise resolving to recent material rows.
 */
export function fetchFrontierNewsItems(
  params: FrontierNewsItemsParams,
): Promise<FrontierNewsItemResponse[]> {
  const query = new URLSearchParams({ limit: String(params.limit ?? 50) });
  if (params.status && params.status !== "all") {
    query.set("status", params.status);
  }
  return apiGet<FrontierNewsItemResponse[]>(`/admin/frontier-news/items?${query.toString()}`);
}

/**
 * Re-runs AI整理 for one material and lets the API enqueue it if ready.
 *
 * @param itemId - Material ID to enrich.
 * @returns Promise resolving to the updated material.
 */
export function enrichFrontierNewsItem(itemId: string): Promise<FrontierNewsItemResponse> {
  return apiPost<FrontierNewsItemResponse, Record<string, never>>(
    `/admin/frontier-news/items/${itemId}/enrich`,
    {},
  );
}

/**
 * Sends one prepared material to the existing moderation queue.
 *
 * @param itemId - Material ID to queue for review.
 * @param note - Optional administrator note stored in the generated draft.
 * @returns Promise resolving to the updated material.
 */
export function queueFrontierNewsItem(
  itemId: string,
  note?: string,
): Promise<FrontierNewsItemResponse> {
  return apiPost<FrontierNewsItemResponse, { note?: string | null }>(
    `/admin/frontier-news/items/${itemId}/queue`,
    { note: note ?? null },
  );
}

export function fetchAdminAuditLogs(limit = 50): Promise<AuditLogResponse[]> {
  return apiGet<AuditLogResponse[]>(`/admin/audit-logs?limit=${limit}`);
}

export function fetchAdminEmailLogs(limit = 50): Promise<AdminEmailLogResponse[]> {
  return apiGet<AdminEmailLogResponse[]>(`/admin/email-logs?limit=${limit}`);
}

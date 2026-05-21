import { apiGet, apiPut } from "@/shared/api/client";

import type {
  AdminEmailLogResponse,
  AdminSystemOverviewResponse,
  AdminUserResponse,
  AdminUsersParams,
  AdminUserUpdateRequest,
  AuditLogResponse,
  PublicSiteSettingsResponse,
  SiteSettingResponse,
  SiteSettingUpdateRequest,
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

export function fetchAdminSystem(): Promise<AdminSystemOverviewResponse> {
  return apiGet<AdminSystemOverviewResponse>("/admin/system");
}

export function fetchAdminAuditLogs(limit = 50): Promise<AuditLogResponse[]> {
  return apiGet<AuditLogResponse[]>(`/admin/audit-logs?limit=${limit}`);
}

export function fetchAdminEmailLogs(limit = 50): Promise<AdminEmailLogResponse[]> {
  return apiGet<AdminEmailLogResponse[]>(`/admin/email-logs?limit=${limit}`);
}

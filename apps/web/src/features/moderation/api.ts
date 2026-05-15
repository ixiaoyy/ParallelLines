import { apiGet, apiPost, apiPut } from "@/shared/api/client";

import type {
  AuditLogResponse,
  FlagCreateRequest,
  FlagResponse,
  FlagStatus,
  FlagStatusUpdateRequest,
  FlagTargetType,
  HideContentRequest,
  ModerationActionResponse,
  UserStatusResponse,
  UserStatusUpdateRequest,
} from "./model";

export function createFlag(payload: FlagCreateRequest): Promise<FlagResponse> {
  return apiPost<FlagResponse, FlagCreateRequest>("/moderation/flags", payload);
}

export function fetchModerationQueue(status?: FlagStatus, limit = 50): Promise<FlagResponse[]> {
  const query = new URLSearchParams({ limit: String(limit) });
  if (status) {
    query.set("status", status);
  }
  return apiGet<FlagResponse[]>(`/moderation/queue?${query.toString()}`);
}

export function updateFlagStatus(
  flagId: string,
  payload: FlagStatusUpdateRequest,
): Promise<FlagResponse> {
  return apiPut<FlagResponse, FlagStatusUpdateRequest>(`/moderation/flags/${flagId}/status`, payload);
}

export function setContentHidden(
  targetType: FlagTargetType,
  targetId: string,
  hidden: boolean,
  payload: HideContentRequest = {},
): Promise<ModerationActionResponse> {
  const path = targetType === "topic" ? "topics" : "posts";
  const action = hidden ? "hide" : "restore";
  return apiPut<ModerationActionResponse, HideContentRequest>(`/moderation/${path}/${targetId}/${action}`, payload);
}

export function updateUserStatus(
  userId: string,
  payload: UserStatusUpdateRequest,
): Promise<UserStatusResponse> {
  return apiPut<UserStatusResponse, UserStatusUpdateRequest>(`/moderation/users/${userId}/status`, payload);
}

export function fetchAuditLogs(limit = 50): Promise<AuditLogResponse[]> {
  return apiGet<AuditLogResponse[]>(`/moderation/audit-logs?limit=${limit}`);
}

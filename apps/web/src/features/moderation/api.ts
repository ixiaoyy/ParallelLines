import { apiGet, apiPost, apiPut, apiRequest } from "@/shared/api/client";

import type {
  AuditLogResponse,
  FlagCreateRequest,
  FlagResponse,
  FlagStatus,
  FlagStatusUpdateRequest,
  FlagTargetType,
  HideContentRequest,
  ModerationActionResponse,
  ReviewableAppealRequest,
  ReviewableBulkDecisionRequest,
  ReviewableBulkDecisionResponse,
  ReviewableDecisionRequest,
  ReviewableResponse,
  ReviewableStatus,
  ReviewableType,
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

export function fetchReviewables(
  status?: ReviewableStatus,
  reviewableType?: ReviewableType,
  limit = 50,
): Promise<ReviewableResponse[]> {
  const query = new URLSearchParams({ limit: String(limit) });
  if (status) {
    query.set("status", status);
  }
  if (reviewableType) {
    query.set("type", reviewableType);
  }
  return apiGet<ReviewableResponse[]>(`/moderation/reviewables?${query.toString()}`);
}

export function fetchMyReviewables(limit = 50): Promise<ReviewableResponse[]> {
  return apiGet<ReviewableResponse[]>(`/moderation/reviewables/me?limit=${limit}`);
}

export function claimReviewable(reviewableId: string): Promise<ReviewableResponse> {
  return apiRequest<ReviewableResponse>(`/moderation/reviewables/${reviewableId}/claim`, {
    method: "POST",
  });
}

export function releaseReviewable(reviewableId: string): Promise<ReviewableResponse> {
  return apiRequest<ReviewableResponse>(`/moderation/reviewables/${reviewableId}/release`, {
    method: "POST",
  });
}

export function decideReviewable(
  reviewableId: string,
  payload: ReviewableDecisionRequest,
): Promise<ReviewableResponse> {
  return apiPost<ReviewableResponse, ReviewableDecisionRequest>(
    `/moderation/reviewables/${reviewableId}/decide`,
    payload,
  );
}

// Apply one moderation decision to a selected group of reviewables.
// Key parameter `payload` contains selected ids and action. Return value is the
// backend batch summary. Side effect: performs the bulk moderation request.
export function decideReviewablesBulk(
  payload: ReviewableBulkDecisionRequest,
): Promise<ReviewableBulkDecisionResponse> {
  return apiPost<ReviewableBulkDecisionResponse, ReviewableBulkDecisionRequest>(
    "/moderation/reviewables/bulk-decide",
    payload,
  );
}

export function appealReviewable(
  reviewableId: string,
  payload: ReviewableAppealRequest,
): Promise<ReviewableResponse> {
  return apiPost<ReviewableResponse, ReviewableAppealRequest>(
    `/moderation/reviewables/${reviewableId}/appeal`,
    payload,
  );
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

// Deletes moderated content through moderation-owned endpoints.
// Key parameters identify the target content and audit payload. Return value
// mirrors hide/restore responses; side effect: may hide a topic or erase a post body.
export function deleteModeratedContent(
  targetType: FlagTargetType,
  targetId: string,
  payload: HideContentRequest = {},
): Promise<ModerationActionResponse> {
  const path = targetType === "topic" ? "topics" : "posts";
  return apiPut<ModerationActionResponse, HideContentRequest>(`/moderation/${path}/${targetId}/delete`, payload);
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

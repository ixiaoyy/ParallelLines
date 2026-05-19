import { apiGet, apiPut } from "@/shared/api/client";

import type { NotificationListResponse, NotificationReadResponse } from "./model";

export function fetchNotifications(): Promise<NotificationListResponse> {
  return apiGet<NotificationListResponse>("/notifications?limit=20");
}

export function markNotificationsRead(ids?: string[]): Promise<NotificationReadResponse> {
  return apiPut<NotificationReadResponse, { ids: string[] | null }>("/notifications/read", {
    ids: ids ?? null,
  });
}

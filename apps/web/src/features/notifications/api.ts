import { apiGet, apiPut } from "@/shared/api/client";

import type {
  NotificationLevel,
  NotificationListResponse,
  NotificationReadResponse,
} from "./model";

export function fetchNotifications(): Promise<NotificationListResponse> {
  return apiGet<NotificationListResponse>("/notifications?limit=20");
}

export function markNotificationsRead(ids?: string[]): Promise<NotificationReadResponse> {
  return apiPut<NotificationReadResponse, { ids: string[] | null }>("/notifications/read", {
    ids: ids ?? null,
  });
}

export interface TopicNotificationLevelResponse {
  topic_id: string;
  notification_level: NotificationLevel;
  last_read_post_number: number;
}

export function getTopicNotificationLevel(
  topicId: string,
): Promise<TopicNotificationLevelResponse> {
  return apiGet<TopicNotificationLevelResponse>(`/topics/${topicId}/notification-level`);
}

export function setTopicNotificationLevel(
  topicId: string,
  level: NotificationLevel,
): Promise<TopicNotificationLevelResponse> {
  return apiPut<TopicNotificationLevelResponse, { notification_level: string }>(
    `/topics/${topicId}/notification-level`,
    { notification_level: level },
  );
}

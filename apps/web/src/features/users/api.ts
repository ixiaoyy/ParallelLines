import { apiGet, apiPatch } from "@/shared/api/client";

import type { TopicResponse } from "@/features/topics/model";
import type {
  UserActivityItem,
  UserActivityType,
  UserDirectoryEntry,
  UserDirectorySort,
  UserProfile,
  UserProfileUpdateRequest,
} from "./model";

export function fetchUserProfile(username: string): Promise<UserProfile> {
  return apiGet<UserProfile>(`/users/${encodeURIComponent(username)}`);
}

export function fetchUserTopics(username: string): Promise<TopicResponse[]> {
  return apiGet<TopicResponse[]>(`/users/${encodeURIComponent(username)}/topics`);
}

export function updateMyProfile(payload: UserProfileUpdateRequest): Promise<UserProfile> {
  return apiPatch<UserProfile, UserProfileUpdateRequest>("/users/me/profile", payload);
}

export function fetchUserDirectory(sort: UserDirectorySort): Promise<UserDirectoryEntry[]> {
  return apiGet<UserDirectoryEntry[]>(`/users/directory?sort=${encodeURIComponent(sort)}`);
}

export function fetchUserActivity(
  username: string,
  type: UserActivityType,
): Promise<UserActivityItem[]> {
  const query = new URLSearchParams({ type });
  return apiGet<UserActivityItem[]>(`/users/${encodeURIComponent(username)}/activity?${query.toString()}`);
}

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

// fetchUserProfileById 用途：按稳定用户 ID 读取公开资料，供 `/members/:id` 页面使用；返回用户资料且无本地副作用。
export function fetchUserProfileById(userId: string): Promise<UserProfile> {
  return apiGet<UserProfile>(`/users/id/${encodeURIComponent(userId)}`);
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

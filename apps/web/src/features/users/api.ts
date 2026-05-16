import { apiGet } from "@/shared/api/client";

import type { TopicResponse } from "@/features/topics/model";
import type { UserProfile } from "./model";

export function fetchUserProfile(username: string): Promise<UserProfile> {
  return apiGet<UserProfile>(`/users/${encodeURIComponent(username)}`);
}

export function fetchUserTopics(username: string): Promise<TopicResponse[]> {
  return apiGet<TopicResponse[]>(`/users/${encodeURIComponent(username)}/topics`);
}

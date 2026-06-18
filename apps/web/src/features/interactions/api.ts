import { apiDelete, apiPut } from "@/shared/api/client";

import type { InteractionStateResponse, VoteStateResponse } from "./model";

export function setPostLike(postId: string, active: boolean): Promise<InteractionStateResponse> {
  const path = `/posts/${postId}/like`;
  return active
    ? apiPut<InteractionStateResponse, Record<string, never>>(path)
    : apiDelete<InteractionStateResponse>(path);
}

export function setTopicLike(topicId: string, active: boolean): Promise<InteractionStateResponse> {
  const path = `/topics/${topicId}/like`;
  return active
    ? apiPut<InteractionStateResponse, Record<string, never>>(path)
    : apiDelete<InteractionStateResponse>(path);
}

export function setTopicBookmark(
  topicId: string,
  active: boolean,
): Promise<InteractionStateResponse> {
  const path = `/topics/${topicId}/bookmark`;
  return active
    ? apiPut<InteractionStateResponse, Record<string, never>>(path)
    : apiDelete<InteractionStateResponse>(path);
}

export function setPostVote(postId: string, value: -1 | 0 | 1): Promise<VoteStateResponse> {
  return apiPut<VoteStateResponse, { value: -1 | 0 | 1 }>(`/posts/${postId}/vote`, { value });
}

export function setTopicVote(topicId: string, value: -1 | 0 | 1): Promise<VoteStateResponse> {
  return apiPut<VoteStateResponse, { value: -1 | 0 | 1 }>(`/topics/${topicId}/vote`, { value });
}

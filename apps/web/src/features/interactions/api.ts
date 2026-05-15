import { apiDelete, apiPut } from "@/shared/api/client";

import type { BoardFollowResponse, InteractionStateResponse } from "./model";

export function setPostLike(postId: string, active: boolean): Promise<InteractionStateResponse> {
  const path = `/posts/${postId}/like`;
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

export function setBoardFollow(
  boardSlug: string,
  active: boolean,
  notificationLevel = "watching",
): Promise<BoardFollowResponse> {
  const path = `/boards/${boardSlug}/follow`;
  return active
    ? apiPut<BoardFollowResponse, { notification_level: string }>(path, {
        notification_level: notificationLevel,
      })
    : apiDelete<BoardFollowResponse>(path);
}

import { apiGet, apiPost } from "@/shared/api/client";

import type { CreatePostRequest, PostResponse } from "./model";

export function fetchPosts(topicId: string): Promise<PostResponse[]> {
  return apiGet<PostResponse[]>(`/topics/${topicId}/posts`);
}

export function createPost(topicId: string, payload: CreatePostRequest): Promise<PostResponse> {
  return apiPost<PostResponse, CreatePostRequest>(`/topics/${topicId}/posts`, payload);
}

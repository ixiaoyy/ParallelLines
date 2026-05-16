import { apiGet, apiPost, apiRequest } from "@/shared/api/client";

import type { CreatePostRequest, PostResponse, UpdatePostRequest } from "./model";

export function fetchPosts(topicId: string): Promise<PostResponse[]> {
  return apiGet<PostResponse[]>(`/topics/${topicId}/posts`);
}

export function createPost(topicId: string, payload: CreatePostRequest): Promise<PostResponse> {
  return apiPost<PostResponse, CreatePostRequest>(`/topics/${topicId}/posts`, payload);
}

export function updatePost(postId: string, payload: UpdatePostRequest): Promise<PostResponse> {
  return apiRequest<PostResponse>(`/posts/${postId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

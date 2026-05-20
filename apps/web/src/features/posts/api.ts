import { apiDelete, apiGet, apiPost, apiRequest } from "@/shared/api/client";

import type {
  CreatePostRequest,
  PostResponse,
  PostRevisionResponse,
  RestorePostRevisionRequest,
  UpdatePostRequest,
} from "./model";

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

export function fetchPostRevisions(postId: string): Promise<PostRevisionResponse[]> {
  return apiGet<PostRevisionResponse[]>(`/posts/${postId}/revisions`);
}

export function fetchPostRevision(
  postId: string,
  revisionId: string,
): Promise<PostRevisionResponse> {
  return apiGet<PostRevisionResponse>(`/posts/${postId}/revisions/${revisionId}`);
}

export function restorePostRevision(
  postId: string,
  revisionId: string,
  payload: RestorePostRevisionRequest,
): Promise<PostResponse> {
  return apiPost<PostResponse, RestorePostRevisionRequest>(
    `/posts/${postId}/revisions/${revisionId}/restore`,
    payload,
  );
}

export function deletePost(postId: string): Promise<PostResponse> {
  return apiDelete<PostResponse>(`/posts/${postId}`);
}

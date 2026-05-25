import { useMutation, useQuery, useQueryClient } from "@tanstack/vue-query";
import { computed, toValue } from "vue";
import type { MaybeRefOrGetter } from "vue";

import { hasAccessToken } from "@/shared/api/client";
import { queryKeys } from "@/shared/api/queryKeys";

import {
  createPost,
  deletePost,
  fetchPostRevision,
  fetchPostRevisions,
  fetchPosts,
  restorePostRevision,
  updatePost,
} from "./api";
import type { PostSort } from "./api";
import { toPostItem, toPostRevision } from "./model";
import type {
  CreatePostRequest,
  PostResponse,
  PostRevisionVM,
  RestorePostRevisionRequest,
  UpdatePostRequest,
} from "./model";

export function useTopicPosts(
  topicId: MaybeRefOrGetter<string>,
  sort: MaybeRefOrGetter<PostSort> = "chronological",
) {
  return useQuery({
    queryKey: computed(() => queryKeys.posts(toValue(topicId), toValue(sort))),
    queryFn: async () => {
      const id = toValue(topicId);
      return (await fetchPosts(id, toValue(sort))).map(toPostItem);
    },
    enabled: computed(() => Boolean(toValue(topicId))),
    staleTime: 20_000,
  });
}

export function useCreatePost(topicId: MaybeRefOrGetter<string>) {
  const queryClient = useQueryClient();

  return useMutation<PostResponse, Error, CreatePostRequest>({
    mutationFn: (payload) => {
      const id = toValue(topicId);
      if (!id || !hasAccessToken()) {
        throw new Error("authentication_required");
      }

      return createPost(id, payload);
    },
    onSuccess: () => {
      const id = toValue(topicId);
      void queryClient.invalidateQueries({ queryKey: queryKeys.posts(id) });
      void queryClient.invalidateQueries({ queryKey: queryKeys.topic(id) });
    },
  });
}


export function useUpdatePost(topicId: MaybeRefOrGetter<string>) {
  const queryClient = useQueryClient();

  return useMutation<PostResponse, Error, { postId: string; payload: UpdatePostRequest }>({
    mutationFn: ({ postId, payload }) => {
      if (!postId || !hasAccessToken()) {
        throw new Error("authentication_required");
      }

      return updatePost(postId, payload);
    },
    onSuccess: () => {
      const id = toValue(topicId);
      void queryClient.invalidateQueries({ queryKey: queryKeys.posts(id) });
      void queryClient.invalidateQueries({ queryKey: queryKeys.topic(id) });
    },
  });
}

export function usePostRevisions(
  postId: MaybeRefOrGetter<string>,
  enabled: MaybeRefOrGetter<boolean> = true,
) {
  return useQuery<PostRevisionVM[], Error>({
    queryKey: computed(() => queryKeys.postRevisions(toValue(postId))),
    queryFn: async () => (await fetchPostRevisions(toValue(postId))).map(toPostRevision),
    enabled: computed(() => Boolean(toValue(postId)) && Boolean(toValue(enabled))),
    staleTime: 10_000,
  });
}

export function usePostRevision(
  postId: MaybeRefOrGetter<string>,
  revisionId: MaybeRefOrGetter<string>,
  enabled: MaybeRefOrGetter<boolean> = true,
) {
  return useQuery<PostRevisionVM, Error>({
    queryKey: computed(() => queryKeys.postRevision(toValue(postId), toValue(revisionId))),
    queryFn: async () =>
      toPostRevision(await fetchPostRevision(toValue(postId), toValue(revisionId))),
    enabled: computed(
      () => Boolean(toValue(postId)) && Boolean(toValue(revisionId)) && Boolean(toValue(enabled)),
    ),
    staleTime: 10_000,
  });
}

export function useRestorePostRevision(topicId: MaybeRefOrGetter<string>) {
  const queryClient = useQueryClient();

  return useMutation<
    PostResponse,
    Error,
    { postId: string; revisionId: string; payload: RestorePostRevisionRequest }
  >({
    mutationFn: ({ postId, revisionId, payload }) => {
      if (!postId || !revisionId || !hasAccessToken()) {
        throw new Error("authentication_required");
      }

      return restorePostRevision(postId, revisionId, payload);
    },
    onSuccess: (_post, variables) => {
      const id = toValue(topicId);
      void queryClient.invalidateQueries({ queryKey: queryKeys.posts(id) });
      void queryClient.invalidateQueries({ queryKey: queryKeys.topic(id) });
      void queryClient.invalidateQueries({ queryKey: queryKeys.postRevisions(variables.postId) });
    },
  });
}

export function useDeletePost(topicId: MaybeRefOrGetter<string>) {
  const queryClient = useQueryClient();

  return useMutation<PostResponse, Error, string>({
    mutationFn: (postId) => {
      if (!postId || !hasAccessToken()) {
        throw new Error("authentication_required");
      }

      return deletePost(postId);
    },
    onSuccess: () => {
      const id = toValue(topicId);
      void queryClient.invalidateQueries({ queryKey: queryKeys.posts(id) });
      void queryClient.invalidateQueries({ queryKey: queryKeys.topic(id) });
    },
  });
}

import { useMutation, useQuery, useQueryClient } from "@tanstack/vue-query";
import { computed, toValue } from "vue";
import type { MaybeRefOrGetter } from "vue";

import { hasAccessToken } from "@/shared/api/client";
import { queryKeys } from "@/shared/api/queryKeys";

import { createPost, deletePost, fetchPosts, updatePost } from "./api";
import { toPostItem } from "./model";
import type { CreatePostRequest, PostResponse, UpdatePostRequest } from "./model";

export function useTopicPosts(topicId: MaybeRefOrGetter<string>) {
  return useQuery({
    queryKey: computed(() => queryKeys.posts(toValue(topicId))),
    queryFn: async () => {
      const id = toValue(topicId);
      return (await fetchPosts(id)).map(toPostItem);
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

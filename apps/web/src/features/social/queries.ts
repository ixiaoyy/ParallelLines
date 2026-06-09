import { useMutation, useQuery, useQueryClient } from "@tanstack/vue-query";
import { computed, toValue } from "vue";
import type { MaybeRefOrGetter } from "vue";

import { hasAccessToken } from "@/shared/api/client";
import { queryKeys } from "@/shared/api/queryKeys";

import {
  createPrivateMessage,
  fetchPrivateMessages,
  fetchUserRelationship,
  fetchUserRelationshipUsers,
  setUserRelationship,
} from "./api";
import type {
  PrivateMessageCreateRequest,
  PrivateMessageTopic,
  UserRelationshipKind,
  UserRelationshipListKind,
  UserRelationshipState,
  UserRelationshipUser,
} from "./model";

export function useUserRelationship(
  username: MaybeRefOrGetter<string>,
  enabled: MaybeRefOrGetter<boolean> = true,
) {
  return useQuery<UserRelationshipState | null, Error>({
    queryKey: computed(() => queryKeys.userRelationship(toValue(username))),
    queryFn: async () => {
      const currentUsername = toValue(username);
      if (!currentUsername || !toValue(enabled)) {
        return null;
      }

      return fetchUserRelationship(currentUsername);
    },
    enabled: computed(() => Boolean(toValue(username)) && toValue(enabled)),
    retry: false,
    staleTime: 30_000,
  });
}

export function useUpdateUserRelationship(username: MaybeRefOrGetter<string>) {
  const queryClient = useQueryClient();
  return useMutation<
    UserRelationshipState,
    Error,
    { kind: UserRelationshipKind; active: boolean }
  >({
    mutationFn: ({ kind, active }) => setUserRelationship(toValue(username), kind, active),
    onSuccess: (response) => {
      queryClient.setQueryData(queryKeys.userRelationship(response.target_username), response);
      void queryClient.invalidateQueries({ queryKey: queryKeys.usersRoot });
      void queryClient.invalidateQueries({ queryKey: queryKeys.userRelationshipUsersRoot });
      void queryClient.invalidateQueries({ queryKey: queryKeys.user(toValue(username)) });
      void queryClient.invalidateQueries({ queryKey: queryKeys.userTopics(toValue(username)) });
      void queryClient.invalidateQueries({ queryKey: queryKeys.notifications });
    },
  });
}

// useUserRelationshipUsers 用途：按方向查询用户的关注/粉丝列表。
// 关键参数：username 为资料用户名，kind 为 following/followers，enabled 控制懒加载。
// 返回值/副作用：返回 TanStack Query 对象，仅读取服务端状态。
export function useUserRelationshipUsers(
  username: MaybeRefOrGetter<string>,
  kind: MaybeRefOrGetter<UserRelationshipListKind>,
  enabled: MaybeRefOrGetter<boolean> = true,
) {
  return useQuery<UserRelationshipUser[], Error>({
    queryKey: computed(() => queryKeys.userRelationshipUsers(toValue(username), toValue(kind))),
    queryFn: async () => {
      if (!toValue(username) || !toValue(enabled)) {
        return [];
      }

      return fetchUserRelationshipUsers(toValue(username), toValue(kind));
    },
    enabled: computed(() => Boolean(toValue(username)) && toValue(enabled)),
    retry: false,
    staleTime: 20_000,
  });
}

export function usePrivateMessages(enabled: MaybeRefOrGetter<boolean> = true) {
  return useQuery<PrivateMessageTopic[], Error>({
    queryKey: queryKeys.privateMessages,
    queryFn: async () => {
      if (!hasAccessToken()) {
        return [];
      }

      return fetchPrivateMessages();
    },
    enabled: computed(() => toValue(enabled)),
    staleTime: 20_000,
  });
}

export function useCreatePrivateMessage() {
  const queryClient = useQueryClient();
  return useMutation<PrivateMessageTopic, Error, PrivateMessageCreateRequest>({
    mutationFn: createPrivateMessage,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.privateMessages });
      void queryClient.invalidateQueries({ queryKey: queryKeys.notifications });
    },
  });
}

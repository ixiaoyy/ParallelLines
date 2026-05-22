import { useMutation, useQuery, useQueryClient } from "@tanstack/vue-query";
import { computed, toValue } from "vue";
import type { MaybeRefOrGetter } from "vue";

import { hasAccessToken } from "@/shared/api/client";
import { queryKeys } from "@/shared/api/queryKeys";

import {
  createPrivateMessage,
  fetchPrivateMessages,
  fetchUserRelationship,
  setUserRelationship,
} from "./api";
import type {
  PrivateMessageCreateRequest,
  PrivateMessageTopic,
  UserRelationshipKind,
  UserRelationshipState,
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
      void queryClient.invalidateQueries({ queryKey: queryKeys.user(toValue(username)) });
      void queryClient.invalidateQueries({ queryKey: queryKeys.userTopics(toValue(username)) });
      void queryClient.invalidateQueries({ queryKey: queryKeys.notifications });
    },
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

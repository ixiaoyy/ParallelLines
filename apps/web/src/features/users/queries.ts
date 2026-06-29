import { useMutation, useQuery, useQueryClient } from "@tanstack/vue-query";
import { computed, toValue } from "vue";
import type { MaybeRefOrGetter } from "vue";

import { toTopicCard } from "@/features/topics/model";
import { queryKeys } from "@/shared/api/queryKeys";

import {
  fetchUserActivity,
  fetchUserDirectory,
  fetchUserProfile,
  fetchUserProfileById,
  fetchUserTopics,
  updateMyProfile,
} from "./api";
import type { UserActivityType, UserDirectorySort, UserProfile, UserProfileUpdateRequest } from "./model";

export function useUserProfile(username: MaybeRefOrGetter<string>) {
  return useQuery({
    queryKey: computed(() => queryKeys.user(toValue(username))),
    queryFn: () => fetchUserProfile(toValue(username)),
    enabled: computed(() => Boolean(toValue(username))),
    retry: false,
    staleTime: 60_000,
  });
}

// useUserProfileById 用途：为公开成员页按稳定用户 ID 管理资料查询；参数为用户 ID ref/getter，返回 TanStack Query 状态且无写入副作用。
export function useUserProfileById(userId: MaybeRefOrGetter<string>) {
  return useQuery({
    queryKey: computed(() => queryKeys.userById(toValue(userId))),
    queryFn: () => fetchUserProfileById(toValue(userId)),
    enabled: computed(() => Boolean(toValue(userId))),
    retry: false,
    staleTime: 60_000,
  });
}

export function useUserTopics(username: MaybeRefOrGetter<string>) {
  return useQuery({
    queryKey: computed(() => queryKeys.userTopics(toValue(username))),
    queryFn: async () => (await fetchUserTopics(toValue(username))).map(toTopicCard),
    enabled: computed(() => Boolean(toValue(username))),
    retry: false,
    staleTime: 30_000,
  });
}

export function useUpdateMyProfile(username: MaybeRefOrGetter<string>) {
  const queryClient = useQueryClient();
  return useMutation<UserProfile, Error, UserProfileUpdateRequest>({
    mutationFn: updateMyProfile,
    onSuccess: async (profile) => {
      queryClient.setQueryData(queryKeys.user(profile.username), profile);
      await queryClient.invalidateQueries({ queryKey: queryKeys.currentUser });
      await queryClient.invalidateQueries({ queryKey: queryKeys.user(toValue(username)) });
      await queryClient.invalidateQueries({ queryKey: queryKeys.userDirectoryRoot });
    },
  });
}

export function useUserDirectory(sort: MaybeRefOrGetter<UserDirectorySort>) {
  return useQuery({
    queryKey: computed(() => queryKeys.userDirectory(toValue(sort))),
    queryFn: () => fetchUserDirectory(toValue(sort)),
    retry: false,
    staleTime: 30_000,
  });
}

export function useUserActivity(
  username: MaybeRefOrGetter<string>,
  type: MaybeRefOrGetter<UserActivityType>,
  enabled: MaybeRefOrGetter<boolean> = true,
) {
  return useQuery({
    queryKey: computed(() => queryKeys.userActivity(toValue(username), toValue(type))),
    queryFn: () => fetchUserActivity(toValue(username), toValue(type)),
    enabled: computed(() => Boolean(toValue(username)) && toValue(enabled)),
    retry: false,
    staleTime: 30_000,
  });
}

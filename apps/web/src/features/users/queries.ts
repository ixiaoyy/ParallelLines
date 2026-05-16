import { useQuery } from "@tanstack/vue-query";
import { computed, toValue } from "vue";
import type { MaybeRefOrGetter } from "vue";

import { toTopicCard } from "@/features/topics/model";
import { queryKeys } from "@/shared/api/queryKeys";

import { fetchUserProfile, fetchUserTopics } from "./api";

export function useUserProfile(username: MaybeRefOrGetter<string>) {
  return useQuery({
    queryKey: computed(() => queryKeys.user(toValue(username))),
    queryFn: () => fetchUserProfile(toValue(username)),
    enabled: computed(() => Boolean(toValue(username))),
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

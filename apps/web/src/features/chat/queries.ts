import { useMutation, useQuery, useQueryClient } from "@tanstack/vue-query";
import { computed, onBeforeUnmount, toValue, watch } from "vue";
import type { MaybeRefOrGetter } from "vue";

import { createApiHeaders, getApiUrl, hasAccessToken } from "@/shared/api/client";
import { queryKeys } from "@/shared/api/queryKeys";

import {
  createChatChannel,
  fetchChatChannels,
  fetchChatMessages,
  fetchChatPresence,
  sendChatMessage,
  updateChatPresence,
} from "./api";
import { parseChatStreamPayload } from "./model";
import type {
  ChatChannel,
  ChatChannelCreateRequest,
  ChatMessage,
  ChatMessageCreateRequest,
  ChatMessagePage,
  ChatPresence,
  ChatPresenceUpdateRequest,
  ChatStreamSnapshot,
} from "./model";

export function useChatChannels(enabled: MaybeRefOrGetter<boolean> = true) {
  return useQuery<ChatChannel[], Error>({
    queryKey: queryKeys.chatChannels,
    queryFn: async () => {
      if (!hasAccessToken()) {
        return [];
      }
      return fetchChatChannels();
    },
    enabled: computed(() => toValue(enabled)),
    staleTime: 20_000,
  });
}

export function useCreateChatChannel() {
  const queryClient = useQueryClient();
  return useMutation<ChatChannel, Error, ChatChannelCreateRequest>({
    mutationFn: createChatChannel,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.chatChannels });
    },
  });
}

export function useChatMessages(
  channelId: MaybeRefOrGetter<string>,
  q: MaybeRefOrGetter<string> = "",
) {
  return useQuery<ChatMessagePage, Error>({
    queryKey: computed(() => queryKeys.chatMessages(toValue(channelId), toValue(q))),
    queryFn: async () => {
      const id = toValue(channelId);
      if (!id || !hasAccessToken()) {
        return emptyMessagePage();
      }
      return fetchChatMessages(id, { q: toValue(q), limit: 80 });
    },
    enabled: computed(() => Boolean(toValue(channelId))),
    staleTime: 8_000,
  });
}

export function useSendChatMessage(channelId: MaybeRefOrGetter<string>) {
  const queryClient = useQueryClient();
  return useMutation<ChatMessage, Error, ChatMessageCreateRequest>({
    mutationFn: (payload) => sendChatMessage(toValue(channelId), payload),
    onSuccess: (message) => {
      queryClient.setQueryData<ChatMessagePage>(
        queryKeys.chatMessages(message.channel_id, ""),
        (current) => mergeMessagePage(current, [message]),
      );
      void queryClient.invalidateQueries({ queryKey: queryKeys.chatChannels });
    },
  });
}

export function useChatPresence(channelId: MaybeRefOrGetter<string>) {
  return useQuery<ChatPresence[], Error>({
    queryKey: computed(() => queryKeys.chatPresence(toValue(channelId))),
    queryFn: async () => {
      const id = toValue(channelId);
      if (!id || !hasAccessToken()) {
        return [];
      }
      return fetchChatPresence(id);
    },
    enabled: computed(() => Boolean(toValue(channelId))),
    staleTime: 5_000,
  });
}

export function useUpdateChatPresence(channelId: MaybeRefOrGetter<string>) {
  const queryClient = useQueryClient();
  return useMutation<ChatPresence, Error, ChatPresenceUpdateRequest>({
    mutationFn: (payload) => updateChatPresence(toValue(channelId), payload),
    onSuccess: (presence) => {
      queryClient.setQueryData<ChatPresence[]>(
        queryKeys.chatPresence(presence.channel_id),
        (current) => mergePresence(current, [presence]),
      );
    },
  });
}

export function useChatStream(
  channelId: MaybeRefOrGetter<string>,
  enabled: MaybeRefOrGetter<boolean> = true,
) {
  const queryClient = useQueryClient();
  let controller: AbortController | null = null;

  function stop() {
    controller?.abort();
    controller = null;
  }

  watch(
    () => ({ id: toValue(channelId), enabled: toValue(enabled) }),
    ({ id, enabled: streamEnabled }) => {
      stop();
      if (!id || !streamEnabled || !hasAccessToken() || typeof ReadableStream === "undefined") {
        return;
      }
      controller = new AbortController();
      const cached = queryClient.getQueryData<ChatMessagePage>(queryKeys.chatMessages(id, ""));
      const afterId = cached?.messages.at(-1)?.id;
      void readChatStream(id, afterId, controller.signal, (snapshot) => {
        queryClient.setQueryData<ChatMessagePage>(
          queryKeys.chatMessages(id, ""),
          (current) => mergeMessagePage(current, snapshot.messages),
        );
        queryClient.setQueryData<ChatPresence[]>(
          queryKeys.chatPresence(id),
          (current) => mergePresence(current, snapshot.presence),
        );
      });
    },
    { immediate: true },
  );

  onBeforeUnmount(stop);
}

function mergeMessagePage(
  current: ChatMessagePage | undefined,
  incoming: ChatMessage[],
): ChatMessagePage {
  const byId = new Map<string, ChatMessage>();
  for (const message of current?.messages ?? []) {
    byId.set(message.id, message);
  }
  for (const message of incoming) {
    byId.set(message.id, message);
  }
  const messages = [...byId.values()].sort((left, right) =>
    left.created_at.localeCompare(right.created_at),
  );
  return {
    messages,
    has_more: current?.has_more ?? false,
    next_before_id: current?.next_before_id ?? null,
  };
}

function mergePresence(
  current: ChatPresence[] | undefined,
  incoming: ChatPresence[],
): ChatPresence[] {
  const byUser = new Map<string, ChatPresence>();
  for (const item of current ?? []) {
    byUser.set(item.user.id, item);
  }
  for (const item of incoming) {
    byUser.set(item.user.id, item);
  }
  return [...byUser.values()].sort((left, right) =>
    right.last_seen_at.localeCompare(left.last_seen_at),
  );
}

async function readChatStream(
  channelId: string,
  afterId: string | undefined,
  signal: AbortSignal,
  onSnapshot: (snapshot: ChatStreamSnapshot) => void,
) {
  const query = new URLSearchParams({ poll_seconds: "3", limit: "20" });
  if (afterId) {
    query.set("after_id", afterId);
  }

  try {
    const response = await fetch(
      getApiUrl(`/chat/channels/${encodeURIComponent(channelId)}/stream?${query}`),
      {
        headers: createApiHeaders(),
        signal,
      },
    );
    const reader = response.body?.getReader();
    if (!response.ok || !reader) {
      return;
    }
    const decoder = new TextDecoder();
    let buffer = "";
    while (!signal.aborted) {
      const { done, value } = await reader.read();
      if (done) {
        break;
      }
      buffer += decoder.decode(value, { stream: true });
      const frames = buffer.split("\n\n");
      buffer = frames.pop() ?? "";
      frames.forEach((frame) => consumeFrame(frame, onSnapshot));
    }
  } catch {
    // Query polling remains the fallback when the realtime stream drops.
  }
}

function consumeFrame(frame: string, onSnapshot: (snapshot: ChatStreamSnapshot) => void) {
  const lines = frame.split(/\r?\n/);
  const event = lines.find((line) => line.startsWith("event:"))?.slice("event:".length).trim();
  const data = lines
    .filter((line) => line.startsWith("data:"))
    .map((line) => line.slice("data:".length).trim())
    .join("\n");
  if (event !== "chat" || !data) {
    return;
  }
  try {
    const parsed = parseChatStreamPayload(JSON.parse(data) as unknown);
    if (parsed) {
      onSnapshot(parsed);
    }
  } catch {
    // Ignore malformed frames; the next valid snapshot will reconcile state.
  }
}

function emptyMessagePage(): ChatMessagePage {
  return {
    messages: [],
    has_more: false,
    next_before_id: null,
  };
}

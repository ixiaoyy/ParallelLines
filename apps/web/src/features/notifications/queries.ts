import { useMutation, useQuery, useQueryClient } from "@tanstack/vue-query";
import { onBeforeUnmount, onMounted } from "vue";

import { createApiHeaders, getApiUrl, hasAccessToken } from "@/shared/api/client";
import { queryKeys } from "@/shared/api/queryKeys";

import { fetchNotifications, markNotificationsRead } from "./api";
import { createMockNotificationList } from "./mockNotifications";
import {
  markNotificationListRead,
  mergeNotificationLists,
  parseNotificationStreamPayload,
} from "./model";
import type { NotificationListResponse, NotificationReadResponse } from "./model";

export function useNotificationList() {
  return useQuery({
    queryKey: queryKeys.notifications,
    queryFn: async () => {
      if (!hasAccessToken()) {
        return createMockNotificationList();
      }

      try {
        return await fetchNotifications();
      } catch {
        return createMockNotificationList();
      }
    },
    staleTime: 15_000,
  });
}

export function useMarkNotificationsRead() {
  const queryClient = useQueryClient();

  return useMutation<
    NotificationReadResponse,
    Error,
    string[] | undefined,
    { previous?: NotificationListResponse }
  >({
    mutationFn: async (ids) => {
      if (!hasAccessToken()) {
        const previous = queryClient.getQueryData<NotificationListResponse>(queryKeys.notifications);
        const next = markNotificationListRead(previous, ids);
        return {
          updated_count: previousUnread(previous) - previousUnread(next),
          unread_count: next?.unread_count ?? 0,
        };
      }

      return markNotificationsRead(ids);
    },
    onMutate: async (ids) => {
      await queryClient.cancelQueries({ queryKey: queryKeys.notifications });
      const previous = queryClient.getQueryData<NotificationListResponse>(queryKeys.notifications);
      queryClient.setQueryData<NotificationListResponse>(
        queryKeys.notifications,
        markNotificationListRead(previous, ids),
      );
      return { previous };
    },
    onError: (_error, _ids, context) => {
      if (context?.previous) {
        queryClient.setQueryData(queryKeys.notifications, context.previous);
      }
    },
    onSettled: () => {
      if (hasAccessToken()) {
        void queryClient.invalidateQueries({ queryKey: queryKeys.notifications });
      }
    },
  });
}

export function useNotificationsStream() {
  const queryClient = useQueryClient();
  let controller: AbortController | null = null;

  onMounted(() => {
    if (!hasAccessToken() || typeof ReadableStream === "undefined") {
      return;
    }

    controller = new AbortController();
    void readNotificationStream(controller.signal, (snapshot) => {
      queryClient.setQueryData<NotificationListResponse>(queryKeys.notifications, (current) =>
        mergeNotificationLists(current, snapshot),
      );
    });
  });

  onBeforeUnmount(() => {
    controller?.abort();
    controller = null;
  });
}

async function readNotificationStream(
  signal: AbortSignal,
  onSnapshot: (snapshot: NotificationListResponse) => void,
) {
  try {
    const response = await fetch(getApiUrl("/notifications/stream?poll_seconds=5&limit=5"), {
      headers: createApiHeaders(),
      signal,
    });
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
  } catch (error) {
    if (!signal.aborted) {
      console.warn("notifications stream closed", error);
    }
  }
}

function consumeFrame(frame: string, onSnapshot: (snapshot: NotificationListResponse) => void) {
  const lines = frame.split(/\r?\n/);
  const event = lines.find((line) => line.startsWith("event:"))?.slice("event:".length).trim();
  const data = lines
    .filter((line) => line.startsWith("data:"))
    .map((line) => line.slice("data:".length).trim())
    .join("\n");

  if (event !== "notifications" || !data) {
    return;
  }

  try {
    const parsed = parseNotificationStreamPayload(JSON.parse(data) as unknown);
    if (parsed) {
      onSnapshot(parsed);
    }
  } catch {
    // Ignore malformed server-sent events; the next valid frame will refresh state.
  }
}

function previousUnread(value: NotificationListResponse | undefined): number {
  return value?.unread_count ?? 0;
}

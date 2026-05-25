import { apiGet, apiPost, apiPut } from "@/shared/api/client";

import type {
  ChatChannel,
  ChatChannelCreateRequest,
  ChatMessage,
  ChatMessageCreateRequest,
  ChatMessagePage,
  ChatPresence,
  ChatPresenceUpdateRequest,
} from "./model";

export function fetchChatChannels(): Promise<ChatChannel[]> {
  return apiGet<ChatChannel[]>("/chat/channels");
}

export function createChatChannel(payload: ChatChannelCreateRequest): Promise<ChatChannel> {
  return apiPost<ChatChannel, ChatChannelCreateRequest>("/chat/channels", payload);
}

export function fetchChatMessages(
  channelId: string,
  params: { beforeId?: string; afterId?: string; q?: string; limit?: number } = {},
): Promise<ChatMessagePage> {
  const query = new URLSearchParams();
  if (params.beforeId) query.set("before_id", params.beforeId);
  if (params.afterId) query.set("after_id", params.afterId);
  if (params.q) query.set("q", params.q);
  if (params.limit) query.set("limit", String(params.limit));
  const suffix = query.toString() ? `?${query}` : "";
  return apiGet<ChatMessagePage>(`/chat/channels/${encodeURIComponent(channelId)}/messages${suffix}`);
}

export function sendChatMessage(
  channelId: string,
  payload: ChatMessageCreateRequest,
): Promise<ChatMessage> {
  return apiPost<ChatMessage, ChatMessageCreateRequest>(
    `/chat/channels/${encodeURIComponent(channelId)}/messages`,
    payload,
  );
}

export function fetchChatPresence(channelId: string): Promise<ChatPresence[]> {
  return apiGet<ChatPresence[]>(`/chat/channels/${encodeURIComponent(channelId)}/presence`);
}

export function updateChatPresence(
  channelId: string,
  payload: ChatPresenceUpdateRequest,
): Promise<ChatPresence> {
  return apiPut<ChatPresence, ChatPresenceUpdateRequest>(
    `/chat/channels/${encodeURIComponent(channelId)}/presence`,
    payload,
  );
}

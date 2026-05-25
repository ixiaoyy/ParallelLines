import type { components } from "@/shared/api/generated";

export type ChatChannel = components["schemas"]["ChatChannelResponse"];
export type ChatChannelCreateRequest = components["schemas"]["ChatChannelCreateRequest"];
export type ChatMessage = components["schemas"]["ChatMessageResponse"];
export type ChatMessageCreateRequest = components["schemas"]["ChatMessageCreateRequest"];
export type ChatMessagePage = components["schemas"]["ChatMessagePageResponse"];
export type ChatPresence = components["schemas"]["ChatPresenceResponse"];
export type ChatPresenceUpdateRequest = components["schemas"]["ChatPresenceUpdateRequest"];

export interface ChatStreamSnapshot {
  messages: ChatMessage[];
  presence: ChatPresence[];
}

export function channelTypeLabel(channel: ChatChannel): string {
  if (channel.channel_type === "board") {
    return channel.board_slug ? `版块 · ${channel.board_slug}` : "版块频道";
  }
  if (channel.channel_type === "direct") {
    return "直聊";
  }
  return "公共频道";
}

export function parseChatStreamPayload(value: unknown): ChatStreamSnapshot | null {
  if (!value || typeof value !== "object") {
    return null;
  }
  const payload = value as { messages?: unknown; presence?: unknown };
  if (!Array.isArray(payload.messages) || !Array.isArray(payload.presence)) {
    return null;
  }
  return {
    messages: payload.messages.filter(isChatMessage),
    presence: payload.presence.filter(isChatPresence),
  };
}

function isChatMessage(value: unknown): value is ChatMessage {
  if (!value || typeof value !== "object") {
    return false;
  }
  const message = value as Partial<ChatMessage>;
  return (
    typeof message.id === "string" &&
    typeof message.channel_id === "string" &&
    typeof message.raw_text === "string" &&
    typeof message.created_at === "string" &&
    Boolean(message.user)
  );
}

function isChatPresence(value: unknown): value is ChatPresence {
  if (!value || typeof value !== "object") {
    return false;
  }
  const presence = value as Partial<ChatPresence>;
  return (
    typeof presence.channel_id === "string" &&
    typeof presence.online === "boolean" &&
    typeof presence.typing === "boolean" &&
    typeof presence.last_seen_at === "string" &&
    Boolean(presence.user)
  );
}

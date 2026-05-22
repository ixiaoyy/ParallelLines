import { relativeTime } from "@/shared/lib/format";
import { topicDetailPath } from "@/shared/router/topicRoutes";

export type NotificationType =
  | "replied"
  | "mentioned"
  | "liked"
  | "topic_new_post"
  | "board_new_topic"
  | "user_new_topic"
  | "private_message"
  | "moderation";

export type NotificationLevel = "muted" | "normal" | "tracking" | "watching";

export interface NotificationResponse {
  id: string;
  type: NotificationType | (string & {});
  topic_id: string | null;
  post_id: string | null;
  actor_id: string | null;
  actor_name: string | null;
  data: Record<string, unknown>;
  read_at: string | null;
  created_at: string;
}

export interface NotificationListResponse {
  notifications: NotificationResponse[];
  unread_count: number;
}

export interface NotificationReadResponse {
  updated_count: number;
  unread_count: number;
}

export interface NotificationItemVM {
  id: string;
  type: NotificationResponse["type"];
  tone: "blue" | "green" | "amber" | "red" | "gray";
  unread: boolean;
  title: string;
  description: string;
  actorName: string | null;
  relativeCreatedAt: string;
  targetUrl: string;
}

const typeMeta: Record<
  NotificationType,
  { title: string; tone: NotificationItemVM["tone"]; description: string }
> = {
  replied: { title: "有人回复了你的主题", tone: "blue", description: "新回复" },
  mentioned: { title: "有人提到了你", tone: "green", description: "提及" },
  liked: { title: "有人赞同了你的楼层", tone: "amber", description: "赞同" },
  topic_new_post: { title: "关注主题有新楼层", tone: "blue", description: "新楼层" },
  board_new_topic: { title: "关注版块有新主题", tone: "green", description: "新主题" },
  user_new_topic: { title: "关注成员发布主题", tone: "blue", description: "成员动态" },
  private_message: { title: "收到新的私信", tone: "green", description: "私密主题" },
  moderation: { title: "版务提醒", tone: "red", description: "站务" },
};

export function toNotificationItem(notification: NotificationResponse): NotificationItemVM {
  const knownType = isKnownNotificationType(notification.type) ? notification.type : "moderation";
  const meta = typeMeta[knownType];
  const topicTitle = readString(notification.data.topic_title) ?? "未命名主题";
  const boardName = readString(notification.data.board_name);
  const actorName = notification.actor_name ?? readString(notification.data.actor_name);
  const postNumber = readNumber(notification.data.post_number);

  return {
    id: notification.id,
    type: notification.type,
    tone: notification.read_at ? "gray" : meta.tone,
    unread: notification.read_at === null,
    title: meta.title,
    description: buildDescription(meta.description, topicTitle, boardName, actorName, postNumber),
    actorName,
    relativeCreatedAt: relativeTime(notification.created_at),
    targetUrl: buildNotificationUrl(notification),
  };
}

export function mergeNotificationLists(
  current: NotificationListResponse | undefined,
  incoming: NotificationListResponse,
): NotificationListResponse {
  const merged = new Map<string, NotificationResponse>();

  incoming.notifications.forEach((notification) => merged.set(notification.id, notification));
  current?.notifications.forEach((notification) => {
    if (!merged.has(notification.id)) {
      merged.set(notification.id, notification);
    }
  });

  return {
    unread_count: incoming.unread_count,
    notifications: [...merged.values()].sort(
      (left, right) => Date.parse(right.created_at) - Date.parse(left.created_at),
    ),
  };
}

export function markNotificationListRead(
  current: NotificationListResponse | undefined,
  ids?: string[],
): NotificationListResponse | undefined {
  if (!current) {
    return current;
  }

  const targetIds = ids ? new Set(ids) : null;
  const now = new Date().toISOString();
  const notifications = current.notifications.map((notification) => {
    if (notification.read_at || (targetIds && !targetIds.has(notification.id))) {
      return notification;
    }

    return { ...notification, read_at: now };
  });

  return {
    notifications,
    unread_count: notifications.filter((notification) => notification.read_at === null).length,
  };
}

export function parseNotificationStreamPayload(value: unknown): NotificationListResponse | null {
  if (!isRecord(value)) {
    return null;
  }

  if (typeof value.unread_count !== "number" || !Array.isArray(value.notifications)) {
    return null;
  }

  const notifications = value.notifications.filter(isNotificationResponse);
  if (notifications.length !== value.notifications.length) {
    return null;
  }

  return {
    unread_count: value.unread_count,
    notifications,
  };
}

function isKnownNotificationType(value: string): value is NotificationType {
  return Object.hasOwn(typeMeta, value);
}

function isNotificationResponse(value: unknown): value is NotificationResponse {
  if (!isRecord(value)) {
    return false;
  }

  return (
    typeof value.id === "string" &&
    typeof value.type === "string" &&
    nullableString(value.topic_id) &&
    nullableString(value.post_id) &&
    nullableString(value.actor_id) &&
    nullableString(value.actor_name) &&
    isRecord(value.data) &&
    nullableString(value.read_at) &&
    typeof value.created_at === "string"
  );
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function nullableString(value: unknown): value is string | null {
  return value === null || typeof value === "string";
}

function readString(value: unknown): string | null {
  return typeof value === "string" && value.trim() ? value : null;
}

function readNumber(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function buildDescription(
  fallback: string,
  topicTitle: string,
  boardName: string | null,
  actorName: string | null,
  postNumber: number | null,
) {
  const subject = boardName ? `${boardName} · ${topicTitle}` : topicTitle;
  const actor = actorName ? `${actorName} · ` : "";
  const floor = postNumber ? `#${postNumber} · ` : "";

  return `${actor}${floor}${subject || fallback}`;
}

function buildNotificationUrl(notification: NotificationResponse): string {
  if (notification.type === "moderation" && readString(notification.data.reviewable_id)) {
    return "/moderation/reviewables";
  }

  if (notification.type === "private_message") {
    return notification.topic_id
      ? topicDetailPath({
          id: notification.topic_id,
          slug: readString(notification.data.topic_slug) ?? "private-message",
          hash: readNumber(notification.data.post_number)
            ? `post-${readNumber(notification.data.post_number)}`
            : null,
        })
      : "/messages";
  }

  const topicSlug = readString(notification.data.topic_slug);
  if (notification.topic_id && topicSlug) {
    const hash = readNumber(notification.data.post_number);
    return topicDetailPath({
      id: notification.topic_id,
      slug: topicSlug,
      hash: hash ? `post-${hash}` : null,
    });
  }

  const boardSlug = readString(notification.data.board_slug);
  if (boardSlug) {
    return `/b/${boardSlug}`;
  }

  return "/";
}

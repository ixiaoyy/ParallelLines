import type { NotificationListResponse, NotificationResponse } from "./model";

const now = Date.now();
const minutesAgo = (value: number) => new Date(now - 1000 * 60 * value).toISOString();

export const mockNotifications: NotificationResponse[] = [
  {
    id: "mock-notification-1",
    type: "mentioned",
    topic_id: "t-2",
    post_id: "t-2-p4",
    actor_id: "u-chen",
    actor_name: "Chen",
    data: {
      topic_title: "FastAPI 长任务：先上队列还是 Celery？",
      topic_slug: "fastapi-background-job-queue",
      post_number: 4,
    },
    read_at: null,
    created_at: minutesAgo(6),
  },
  {
    id: "mock-notification-2",
    type: "board_new_topic",
    topic_id: "t-10",
    post_id: "t-10-p1",
    actor_id: "u-helper",
    actor_name: "平行线小助手",
    data: {
      board_name: "支持与排障",
      board_slug: "support",
      topic_title: "升级到 v0.1 后迁移提示缺少 notification_cursor 字段",
      topic_slug: "upgrade-migration-missing-column",
      post_number: 1,
    },
    read_at: null,
    created_at: minutesAgo(18),
  },
  {
    id: "mock-notification-3",
    type: "liked",
    topic_id: "t-3",
    post_id: "t-3-p2",
    actor_id: "u-ada",
    actor_name: "Ada",
    data: {
      topic_title: "深色代码块太刺眼，有更稳的配色吗？",
      topic_slug: "calm-tech-forum-design",
      post_number: 2,
    },
    read_at: minutesAgo(45),
    created_at: minutesAgo(49),
  },
];

export function createMockNotificationList(): NotificationListResponse {
  return {
    notifications: mockNotifications,
    unread_count: mockNotifications.filter((notification) => notification.read_at === null).length,
  };
}

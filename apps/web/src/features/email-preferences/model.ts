export type DigestFrequency = "off" | "daily" | "weekly";

export interface EmailPreferenceResponse {
  email_enabled: boolean;
  notify_replied: boolean;
  notify_mentioned: boolean;
  notify_liked: boolean;
  notify_topic_new_post: boolean;
  notify_board_new_topic: boolean;
  digest_frequency: DigestFrequency | string;
  last_digest_sent_at: string | null;
  delivery_status: string;
  disabled_reason: string | null;
  quiet_hours_start: number | null;
  quiet_hours_end: number | null;
  updated_at: string;
}

export interface EmailPreferenceUpdateRequest {
  email_enabled?: boolean;
  notify_replied?: boolean;
  notify_mentioned?: boolean;
  notify_liked?: boolean;
  notify_topic_new_post?: boolean;
  notify_board_new_topic?: boolean;
  digest_frequency?: DigestFrequency;
  quiet_hours_start?: number | null;
  quiet_hours_end?: number | null;
}

export interface EmailToggleVM {
  key: keyof Pick<
    EmailPreferenceResponse,
    | "notify_replied"
    | "notify_mentioned"
    | "notify_liked"
    | "notify_topic_new_post"
    | "notify_board_new_topic"
  >;
  title: string;
  description: string;
  badge: string;
}

export const emailToggleItems: EmailToggleVM[] = [
  {
    key: "notify_replied",
    title: "被回复",
    description: "当有人回复你的主题或楼层时发送即时邮件。",
    badge: "高优先级",
  },
  {
    key: "notify_mentioned",
    title: "被提及",
    description: "当正文中 @ 你的用户名时发送即时邮件。",
    badge: "协作",
  },
  {
    key: "notify_liked",
    title: "被点赞",
    description: "有人赞同你的楼层时发送轻量提醒。",
    badge: "反馈",
  },
  {
    key: "notify_topic_new_post",
    title: "关注主题更新",
    description: "跟踪或关注的主题出现新楼层时发送邮件。",
    badge: "订阅",
  },
  {
    key: "notify_board_new_topic",
    title: "关注版块新主题",
    description: "关注版块有新主题时发送邮件。",
    badge: "版块",
  },
];

export function digestLabel(value: string): string {
  if (value === "weekly") {
    return "每周摘要";
  }

  if (value === "daily") {
    return "每日摘要";
  }

  return "关闭摘要";
}

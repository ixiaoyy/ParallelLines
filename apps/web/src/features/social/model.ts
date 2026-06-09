import type { TopicResponse } from "@/features/topics/model";

export type UserRelationshipKind = "follow" | "ignore" | "block";
export type UserRelationshipListKind = "following" | "followers";

export interface UserRelationshipState {
  target_user_id: string;
  target_username: string;
  following: boolean;
  ignored: boolean;
  blocked: boolean;
  followed_by: boolean;
}

export interface UserRelationshipUser {
  id: string;
  username: string;
  display_name: string | null;
  avatar_url: string | null;
  role: string;
  level: number;
  trust_level: number;
  trust_level_label: string;
  topic_count: number;
  post_count: number;
  followed_at: string;
}

export interface PrivateMessageParticipant {
  user_id: string;
  username: string;
  role: "owner" | "participant" | (string & {});
  last_read_post_number: number;
  muted: boolean;
}

export interface PrivateMessageTopic {
  topic: TopicResponse;
  participants: PrivateMessageParticipant[];
  unread: boolean;
}

export interface PrivateMessageCreateRequest {
  participant_usernames: string[];
  title: string;
  raw_md: string;
}

export function relationshipSummary(state: UserRelationshipState | null): string {
  if (!state) {
    return "登录后可以关注、忽略或屏蔽该成员。";
  }

  if (state.blocked) {
    return "已屏蔽该成员：不会收到对方通知，也不能互发私信。";
  }

  if (state.ignored) {
    return "已忽略该成员：动态流会减少来自对方的打扰。";
  }

  if (state.following) {
    return state.followed_by ? "你们正在互相关注。" : "已关注，对方发布新主题时会提醒你。";
  }

  if (state.followed_by) {
    return "对方已关注你，你也可以关注回来。";
  }

  return "关注后，对方发布新主题时会进入你的通知中心。";
}

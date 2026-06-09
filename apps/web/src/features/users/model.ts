import type { UserBadgeResponse } from "@/features/badges/model";
import type { UserRole, UserStatus } from "@/features/auth/model";

export interface UserProfile {
  id: string;
  username: string;
  avatar_url: string | null;
  display_name: string | null;
  bio: string | null;
  website_url: string | null;
  location: string | null;
  role: UserRole;
  level: number;
  trust_level: number;
  trust_level_label: string;
  points_balance: number;
  experience_total: number;
  experience_to_next_level: number;
  level_progress_percent: number;
  status: UserStatus;
  profile_visibility: "public" | "members" | "private" | string;
  show_activity: boolean;
  can_edit: boolean;
  created_at: string;
  topic_count: number;
  post_count: number;
  following_count: number;
  follower_count: number;
  badges: UserBadgeResponse[];
}

export interface UserProfileUpdateRequest {
  display_name?: string | null;
  bio?: string | null;
  website_url?: string | null;
  location?: string | null;
  profile_visibility?: "public" | "members" | "private";
  show_activity?: boolean;
  interface_theme?: "system" | "light" | "colorful";
  locale?: "zh-CN" | "en-US";
}

export interface UserDirectoryEntry {
  id: string;
  username: string;
  display_name: string | null;
  avatar_url: string | null;
  role: UserRole;
  level: number;
  trust_level: number;
  trust_level_label: string;
  points_balance: number;
  topic_count: number;
  post_count: number;
  last_seen_at: string | null;
  created_at: string;
}

export type UserDirectorySort = "active" | "level" | "contribution";

export interface UserActivityItem {
  id: string;
  type: "post" | "liked_topic" | "liked_post" | "bookmarked_topic" | "bookmarked_post";
  created_at: string;
  topic_id: string;
  topic_title: string;
  topic_slug: string;
  post_number: number | null;
  excerpt: string;
}

export type UserActivityType = "posts" | "likes" | "bookmarks";

export function profileDisplayName(profile: Pick<UserProfile, "display_name" | "username">): string {
  return profile.display_name?.trim() || profile.username;
}

export function profileVisibilityLabel(value: string): string {
  const labels: Record<string, string> = {
    members: "登录用户可见",
    private: "仅自己可见",
    public: "公开",
  };
  return labels[value] ?? value;
}

export function activityTypeLabel(value: UserActivityItem["type"]): string {
  const labels: Record<UserActivityItem["type"], string> = {
    bookmarked_post: "收藏回复",
    bookmarked_topic: "收藏主题",
    liked_post: "点赞回复",
    liked_topic: "点赞主题",
    post: "发布回复",
  };
  return labels[value];
}

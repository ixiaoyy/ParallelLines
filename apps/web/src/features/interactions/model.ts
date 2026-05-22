import type { NotificationLevel } from "@/features/notifications/model";

export interface InteractionStateResponse {
  target_type: "post" | "topic";
  target_id: string;
  active: boolean;
  count: number;
}

export interface BoardFollowResponse {
  board_id: string;
  board_slug: string;
  following: boolean;
  role: string | null;
  notification_level: NotificationLevel | null;
  follower_count: number;
}

export type FlagTargetType = "topic" | "post";
export type FlagReason = "spam" | "harassment" | "off_topic" | "private_info" | "other";
export type FlagStatus = "pending" | "resolved" | "rejected";
export type UserModerationStatus = "active" | "silenced" | "suspended";

export interface FlagCreateRequest {
  target_type: FlagTargetType;
  target_id: string;
  reason: FlagReason;
  detail?: string | null;
}

export interface FlagStatusUpdateRequest {
  status: FlagStatus;
  resolution_note?: string | null;
}

export interface HideContentRequest {
  note?: string | null;
}

export interface UserStatusUpdateRequest {
  status: UserModerationStatus;
  note?: string | null;
}

export interface ModerationTargetResponse {
  target_type: FlagTargetType;
  target_id: string;
  topic_id: string | null;
  topic_slug: string | null;
  post_number: number | null;
  board_id: string;
  board_slug: string;
  board_name: string;
  author_id: string;
  author_name: string;
  title: string;
  excerpt: string;
  hidden: boolean;
}

export interface FlagResponse {
  id: string;
  target_type: FlagTargetType;
  target_id: string;
  board_id: string;
  reporter_id: string;
  reporter_name: string;
  reason: FlagReason;
  detail: string | null;
  status: FlagStatus;
  resolution_note: string | null;
  resolved_by_id: string | null;
  resolved_at: string | null;
  created_at: string;
  updated_at: string;
  target: ModerationTargetResponse;
}

export interface ModerationActionResponse {
  target_type: FlagTargetType;
  target_id: string;
  hidden: boolean;
  status?: string | null;
}

export interface UserStatusResponse {
  user_id: string;
  username: string;
  status: UserModerationStatus;
}

export interface AuditLogResponse {
  id: string;
  actor_id: string | null;
  actor_name: string | null;
  action: string;
  target_type: string;
  target_id: string;
  board_id: string | null;
  data: Record<string, unknown>;
  created_at: string;
}

export function flagReasonLabel(reason: FlagReason): string {
  const labels: Record<FlagReason, string> = {
    spam: "垃圾/刷屏",
    harassment: "骚扰攻击",
    off_topic: "偏离主题",
    private_info: "隐私泄露",
    other: "其他问题",
  };
  return labels[reason];
}

export function flagStatusLabel(status: FlagStatus): string {
  const labels: Record<FlagStatus, string> = {
    pending: "待处理",
    resolved: "已处理",
    rejected: "已驳回",
  };
  return labels[status];
}

export function auditActionLabel(action: string): string {
  const labels: Record<string, string> = {
    flag_created: "创建举报",
    flag_status_changed: "更新举报状态",
    topic_hidden: "隐藏主题",
    topic_restored: "恢复主题",
    post_hidden: "隐藏楼层",
    post_restored: "恢复楼层",
    user_status_changed: "调整用户状态",
  };
  return labels[action] ?? action;
}

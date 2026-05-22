export type FlagTargetType = "topic" | "post";
export type FlagReason = "spam" | "harassment" | "off_topic" | "private_info" | "other";
export type FlagStatus = "pending" | "resolved" | "rejected";
export type UserModerationStatus = "active" | "silenced" | "suspended";
export type ReviewableType =
  | "flag"
  | "queued_topic"
  | "queued_post"
  | "queued_edit"
  | "appeal"
  | "system";
export type ReviewableStatus =
  | "pending"
  | "claimed"
  | "approved"
  | "rejected"
  | "hidden"
  | "deleted"
  | "silenced"
  | "escalated"
  | "appealed";
export type ReviewableDecisionAction =
  | "approve"
  | "reject"
  | "hide"
  | "delete"
  | "silence"
  | "escalate";

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

export interface ReviewableDecisionRequest {
  action: ReviewableDecisionAction;
  note?: string | null;
}

export interface ReviewableAppealRequest {
  reason: string;
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

export interface ReviewableEventResponse {
  id: string;
  actor_id: string | null;
  actor_name: string | null;
  event: string;
  from_status: string | null;
  to_status: string | null;
  note: string | null;
  data: Record<string, unknown>;
  created_at: string;
}

export interface ReviewableResponse {
  id: string;
  type: ReviewableType | (string & {});
  status: ReviewableStatus | (string & {});
  priority: number;
  source: string;
  source_summary: string;
  target_type: string | null;
  target_id: string | null;
  board_id: string | null;
  board_name: string | null;
  topic_id: string | null;
  post_id: string | null;
  flag_id: string | null;
  created_by_id: string | null;
  created_by_name: string | null;
  target_user_id: string | null;
  target_user_name: string | null;
  assigned_to_id: string | null;
  assigned_to_name: string | null;
  assigned_at: string | null;
  resolved_by_id: string | null;
  resolved_by_name: string | null;
  resolved_at: string | null;
  appeal_available: boolean;
  data: Record<string, unknown>;
  events: ReviewableEventResponse[];
  created_at: string;
  updated_at: string;
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
    reviewable_created: "创建审核项",
    reviewable_claimed: "认领审核项",
    reviewable_released: "释放审核项",
    reviewable_decided: "处理审核项",
    reviewable_appealed: "提交申诉",
    created: "创建",
    claimed: "认领",
    released: "释放",
    decided: "处理",
    appealed: "申诉",
  };
  return labels[action] ?? action;
}

export function reviewableStatusLabel(status: string): string {
  const labels: Record<ReviewableStatus, string> = {
    pending: "待处理",
    claimed: "已认领",
    approved: "已通过",
    rejected: "已拒绝",
    hidden: "已隐藏",
    deleted: "已删除",
    silenced: "已禁言",
    escalated: "已升级",
    appealed: "申诉中",
  };
  return labels[status as ReviewableStatus] ?? status;
}

export function reviewableTypeLabel(type: string): string {
  const labels: Record<ReviewableType, string> = {
    flag: "用户举报",
    queued_topic: "待审主题",
    queued_post: "待审回复",
    queued_edit: "待审编辑",
    appeal: "申诉",
    system: "系统规则",
  };
  return labels[type as ReviewableType] ?? type;
}

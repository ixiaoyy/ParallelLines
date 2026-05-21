export type SiteSettingValue =
  | string
  | number
  | boolean
  | null
  | Record<string, unknown>
  | unknown[];

export interface SiteSettingResponse {
  id: string;
  key: string;
  value: SiteSettingValue;
  data_type: "string" | "boolean" | "integer" | "json" | string;
  category: string;
  description: string;
  public: boolean;
  updated_by_id: string | null;
  updated_by_name: string | null;
  created_at: string;
  updated_at: string;
}

export interface PublicSiteSettingsResponse {
  settings: Record<string, SiteSettingValue>;
  updated_at: string | null;
}

export interface SiteSettingUpdateRequest {
  value: SiteSettingValue;
}

export interface AdminUserResponse {
  id: string;
  username: string;
  email: string;
  avatar_url: string | null;
  role: "user" | "moderator" | "admin" | string;
  level: number;
  status: "active" | "silenced" | "suspended" | "deleted" | string;
  two_factor_enabled: boolean;
  created_at: string;
  updated_at: string;
  last_seen_at: string | null;
  topic_count: number;
  post_count: number;
}

export interface AdminUserUpdateRequest {
  role?: "user" | "moderator" | "admin";
  status?: "active" | "silenced" | "suspended" | "deleted";
  level?: number;
}

export interface AdminUsersParams {
  query?: string;
  role?: string;
  status?: string;
  limit?: number;
}

export interface AdminServiceStatusResponse {
  name: string;
  status: "ok" | "degraded" | "unknown";
  detail: string;
}

export interface AdminStatsResponse {
  users: number;
  boards: number;
  topics: number;
  posts: number;
  pending_flags: number;
  audit_logs: number;
  spam_actions: number;
}

export interface AdminEmailLogResponse {
  to_email: string;
  subject: string;
  kind: string;
  sent_at: string;
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

export interface AdminSystemOverviewResponse {
  version: string;
  environment: string;
  services: AdminServiceStatusResponse[];
  stats: AdminStatsResponse;
  queue: Record<string, unknown>;
  recent_audit_logs: AuditLogResponse[];
  recent_email_logs: AdminEmailLogResponse[];
  recent_errors: Record<string, unknown>[];
}

export function publicSettingString(
  response: PublicSiteSettingsResponse | undefined,
  key: string,
  fallback: string,
): string {
  const value = response?.settings[key];
  return typeof value === "string" && value.trim() ? value : fallback;
}

export function settingCategoryLabel(category: string): string {
  const labels: Record<string, string> = {
    access: "访问控制",
    brand: "品牌",
    uploads: "上传",
  };
  return labels[category] ?? category;
}

export function adminRoleLabel(role: string): string {
  const labels: Record<string, string> = {
    admin: "管理员",
    moderator: "版主",
    user: "用户",
  };
  return labels[role] ?? role;
}

export function adminStatusLabel(status: string): string {
  const labels: Record<string, string> = {
    active: "正常",
    deleted: "已删除",
    silenced: "禁言",
    suspended: "停用",
  };
  return labels[status] ?? status;
}

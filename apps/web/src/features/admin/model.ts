import type { UserBadgeResponse } from "@/features/badges/model";
import {
  builtinSiteText,
  currentLocale,
  type AppLocale,
} from "@/shared/i18n/locale";

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
  trust_level: number;
  trust_level_label: string;
  points_balance: number;
  experience_total: number;
  experience_to_next_level: number;
  level_progress_percent: number;
  status: "active" | "silenced" | "suspended" | "deleted" | string;
  two_factor_enabled: boolean;
  created_at: string;
  updated_at: string;
  last_seen_at: string | null;
  topic_count: number;
  post_count: number;
  badges: UserBadgeResponse[];
}

export interface AdminUserUpdateRequest {
  role?: "user" | "moderator" | "admin";
  status?: "active" | "silenced" | "suspended" | "deleted";
  level?: number;
  points_delta?: number;
  experience_delta?: number;
  adjustment_reason?: string | null;
}

export interface AdminUsersParams {
  query?: string;
  role?: string;
  status?: string;
  limit?: number;
}

export interface ApiKeyResponse {
  id: string;
  name: string;
  token_prefix: string;
  scopes: string[];
  key_type: string;
  owner_user_id: string | null;
  created_by_id: string | null;
  last_used_at: string | null;
  expires_at: string | null;
  disabled_at: string | null;
  note: string | null;
  created_at: string;
  updated_at: string;
}

export interface ApiKeyCreateRequest {
  name: string;
  scopes: string[];
  owner_user_id?: string | null;
  expires_at?: string | null;
  note?: string | null;
}

export interface ApiKeyCreateResponse {
  api_key: ApiKeyResponse;
  token: string;
}

export interface WebhookEndpointResponse {
  id: string;
  name: string;
  url: string;
  events: string[];
  active: boolean;
  created_by_id: string | null;
  disabled_at: string | null;
  disabled_by_id: string | null;
  note: string | null;
  created_at: string;
  updated_at: string;
}

export interface WebhookEndpointCreateRequest {
  name: string;
  url: string;
  events: string[];
  note?: string | null;
}

export interface WebhookEndpointCreateResponse {
  webhook: WebhookEndpointResponse;
  secret: string;
}

export interface WebhookDeliveryResponse {
  id: string;
  endpoint_id: string;
  endpoint_name: string | null;
  event_type: string;
  status: string;
  attempt_count: number;
  max_attempts: number;
  next_attempt_at: string | null;
  last_status_code: number | null;
  last_error: string | null;
  delivered_at: string | null;
  response_body_excerpt: string | null;
  created_at: string;
  updated_at: string;
}

export const API_KEY_SCOPE_OPTIONS = [
  "read",
  "topics:read",
  "topics:write",
  "webhooks:read",
  "webhooks:write",
  "admin:read",
];

export const WEBHOOK_EVENT_OPTIONS = [
  "topic.created",
  "post.created",
  "user.created",
  "user.verified",
  "moderation.flag_created",
];

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

export interface AdminQueueOverview {
  queued: number;
  running: number;
  dead: number;
  worker: string;
  poll_seconds: number;
  batch_size: number;
  retry_delay_seconds: number;
  hot_rank_interval_seconds: number;
  upload_cleanup_interval_seconds: number;
  session_cleanup_interval_seconds: number;
  counts?: Record<string, number>;
}

export interface AdminSystemOverviewResponse {
  version: string;
  environment: string;
  services: AdminServiceStatusResponse[];
  stats: AdminStatsResponse;
  queue: AdminQueueOverview;
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

export function publicSettingRecord(
  response: PublicSiteSettingsResponse | undefined,
  key: string,
): Record<string, string> {
  const value = response?.settings[key];
  if (!value || Array.isArray(value) || typeof value !== "object") {
    return {};
  }

  return Object.entries(value).reduce<Record<string, string>>((acc, [entryKey, entryValue]) => {
    if (typeof entryValue === "string" && entryValue.trim()) {
      acc[entryKey] = entryValue;
    }
    return acc;
  }, {});
}

export function siteText(
  response: PublicSiteSettingsResponse | undefined,
  key: string,
  fallback: string,
  locale: AppLocale = currentLocale.value,
): string {
  const overrides = publicSettingRecord(response, "site_text_overrides");
  return (
    overrides[`${locale}.${key}`] ??
    overrides[key] ??
    builtinSiteText(key, fallback, locale)
  );
}

export function settingCategoryLabel(category: string): string {
  const labels: Record<string, string> = {
    access: "访问控制",
    brand: "品牌",
    email: "邮件模板",
    text: "站点文案",
    theme: "主题",
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

import { getApiUrl } from "@/shared/api/client";
import type { UserPublic } from "@/features/auth/model";

import { CIRCLE_CLIENT_ID, isRecord, isUnifiedState } from "./protocol";
import type { UnifiedState } from "./protocol";

export interface UnifiedAccess extends UnifiedState {
  authenticated: true;
  subject: string;
  auth_epoch: string;
  access_token: string;
  token_type: "bearer";
  expires_in: number;
  session_id: string;
  user: UserPublic;
}
export interface UnifiedLogout extends UnifiedState {
  ok: true;
  return_url: string | null;
}

export class UnifiedApiError extends Error {
  constructor(public code: string, message: string, public status: number) { super(message); }
}

function isUserPublic(value: unknown): value is UserPublic {
  if (!isRecord(value)) return false;
  const strings = ["id", "username", "email", "trust_level_label", "profile_visibility", "interface_theme", "locale", "created_at"];
  const nullable = ["avatar_url", "display_name", "bio", "website_url", "location"];
  const numbers = ["level", "trust_level", "points_balance", "experience_total", "experience_to_next_level", "level_progress_percent"];
  return strings.every(key => typeof value[key] === "string")
    && nullable.every(key => value[key] === null || typeof value[key] === "string")
    && numbers.every(key => typeof value[key] === "number" && Number.isFinite(value[key]))
    && typeof value.role === "string" && ["user", "moderator", "admin"].includes(value.role) && value.status === "active"
    && typeof value.two_factor_enabled === "boolean" && typeof value.show_activity === "boolean";
}

export function accessResponse(value: unknown): UnifiedAccess {
  if (!isUnifiedState(value) || !isRecord(value) || value.authenticated !== true
    || !isUserPublic(value.user) || value.user.id !== value.subject || value.token_type !== "bearer"
    || typeof value.access_token !== "string" || value.access_token.length > 8192 || !/^[A-Za-z0-9_.-]+$/.test(value.access_token)
    || typeof value.session_id !== "string" || !value.session_id || value.session_id.length > 128
    || typeof value.expires_in !== "number" || !Number.isInteger(value.expires_in) || value.expires_in <= 0 || value.expires_in > 300) {
    throw new UnifiedApiError("invalid_unified_response", "统一登录响应无效，请重试。", 0);
  }
  return { authenticated: true, subject: value.user.id, auth_epoch: String(value.auth_epoch),
    access_token: value.access_token, token_type: "bearer", expires_in: value.expires_in,
    session_id: value.session_id, user: value.user };
}

/** 统一认证不走普通401自动重放链，避免过期旧令牌把换号或退出请求重放到另一个账号。 */
async function request(path: string, payload?: object, bearer?: string): Promise<unknown> {
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), 10_000);
  try {
    const headers = new Headers({ Accept: "application/json" });
    if (payload) headers.set("Content-Type", "application/json");
    if (bearer) headers.set("Authorization", "Bearer " + bearer);
    const response = await fetch(getApiUrl("/auth/" + path), {
      method: payload ? "POST" : "GET", credentials: "include", cache: "no-store", redirect: "error",
      headers, body: payload ? JSON.stringify(payload) : undefined, signal: controller.signal,
    });
    const reader = response.body?.getReader();
    if (!reader) throw new UnifiedApiError("invalid_unified_response", "统一登录响应无效。", response.status);
    const decoder = new TextDecoder();
    let size = 0;
    let text = "";
    try {
      while (true) {
        const part = await reader.read();
        if (part.done) break;
        size += part.value.byteLength;
        if (size > 65536) {
          await reader.cancel();
          throw new UnifiedApiError("invalid_unified_response", "统一登录响应超出限制。", response.status);
        }
        text += decoder.decode(part.value, { stream: true });
      }
      text += decoder.decode();
    } finally { reader.releaseLock(); }
    let envelope: unknown;
    try { envelope = JSON.parse(text); } catch { throw new UnifiedApiError("invalid_unified_response", "统一登录响应无效，请重试。", response.status); }
    if (!response.ok) {
      const error = isRecord(envelope) && isRecord(envelope.error) ? envelope.error : null;
      throw new UnifiedApiError(typeof error?.code === "string" ? error.code : "unified_auth_failed",
        response.status === 401 ? "主站会话已失效，请重新登录。" : "统一登录暂不可用，请重试。", response.status);
    }
    if (!isRecord(envelope) || !Object.hasOwn(envelope, "data")) throw new UnifiedApiError("invalid_unified_response", "统一登录响应无效，请重试。", 0);
    return envelope.data;
  } catch (error) {
    if (error instanceof UnifiedApiError) throw error;
    throw new UnifiedApiError("unified_auth_unavailable", "无法连接主站统一登录，请重试。", 0);
  } finally { window.clearTimeout(timer); }
}

export async function fetchUnifiedState(): Promise<UnifiedState> {
  const value = await request("unified/state");
  if (!isUnifiedState(value)) throw new UnifiedApiError("invalid_unified_response", "统一登录状态无效。", 0);
  return { authenticated: value.authenticated, subject: value.subject, auth_epoch: value.auth_epoch };
}

export async function bootstrapUnified(replace = false, bearer?: string): Promise<UnifiedAccess> {
  return accessResponse(await request("unified/bootstrap", { replace }, bearer));
}

export async function authorizeCircle(payload: { redirect_uri: string; state: string; code_challenge: string }): Promise<string> {
  const value = await request("unified/authorize", { client_id: CIRCLE_CLIENT_ID, code_challenge_method: "S256", ...payload });
  if (!isRecord(value) || typeof value.redirect_url !== "string") throw new UnifiedApiError("invalid_unified_response", "登录回调无效。", 0);
  return value.redirect_url;
}

export async function exchangeCircle(payload: { redirect_uri: string; code: string; code_verifier: string }): Promise<UnifiedAccess> {
  return accessResponse(await request("unified/exchange", { client_id: CIRCLE_CLIENT_ID, ...payload }));
}

export async function createUnifiedLogoutTicket(returnUri: string, bearer: string): Promise<string> {
  const value = await request("unified/logout-ticket", { return_uri: returnUri }, bearer);
  if (!isRecord(value) || typeof value.logout_url !== "string" || value.expires_in !== 60) throw new UnifiedApiError("invalid_unified_response", "统一退出请求无效。", 0);
  return value.logout_url;
}

export async function finishUnifiedLogout(ticket: string): Promise<UnifiedLogout> {
  const value = await request("unified/logout", { ticket });
  if (!isUnifiedState(value) || !isRecord(value) || value.ok !== true
    || (value.return_url !== null && typeof value.return_url !== "string")) throw new UnifiedApiError("invalid_unified_response", "统一退出响应无效。", 0);
  return { authenticated: value.authenticated, subject: value.subject, auth_epoch: value.auth_epoch,
    ok: true, return_url: value.return_url };
}

/** 仅主站旧会话迁移使用，刷新令牌不离开其原有主域和原生刷新接口。 */
export async function refreshLegacyMainAccess(refreshToken: string): Promise<string> {
  const value = await request("refresh", { refresh_token: refreshToken });
  if (!isRecord(value) || typeof value.access_token !== "string" || !value.access_token || value.token_type !== "bearer") {
    throw new UnifiedApiError("invalid_unified_response", "主站会话刷新响应无效。", 0);
  }
  return value.access_token;
}

export async function approveUnifiedChat(interactionId: string): Promise<unknown> {
  return request("unified/chat-approve", { interaction_id: interactionId });
}

import { SITE_LINKS } from "@/shared/site/links";

export const UNIFIED_AUTH_ENABLED = import.meta.env.VITE_UNIFIED_AUTH_ENABLED === "true";
export const UNIFIED_MESSAGE_TYPE = "pl:unified-session";
export const UNIFIED_REFRESH_TYPE = "pl:unified-session:refresh";
export const UNIFIED_VERSION = 1;
export const CIRCLE_CLIENT_ID = "parallellines-circle";
export const CALLBACK_PATH = "/auth/unified/callback";
export const STATUS_PATH = "/auth/unified/state";
export const FLOW_STORAGE_KEY = "parallellines.unified-flow.v1";
const FLOW_TTL_MS = 15 * 60_000;

export type StatusClient = "circle" | "chat" | "newapi";
export interface UnifiedState {
  authenticated: boolean;
  subject: string | null;
  auth_epoch: string | null;
}
export interface UnifiedStatusMessage extends UnifiedState {
  type: typeof UNIFIED_MESSAGE_TYPE;
  version: typeof UNIFIED_VERSION;
  request_id: string;
  available: boolean;
}
export interface CircleTransaction {
  state: string;
  verifier: string;
  returnTo: string;
  createdAt: number;
  mode: "redirect" | "silent";
}

export class UnifiedProtocolError extends Error {
  constructor(public code: string, message: string) { super(message); }
}

export function isRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

/** 读取固定主站来源；仅显式开发配置允许回环 HTTP，不接受任意外站作为登录权威。 */
export function mainAuthOrigin(): string {
  const raw = import.meta.env.VITE_UNIFIED_MAIN_ORIGIN || SITE_LINKS.games;
  let url: URL;
  try { url = new URL(raw); } catch { throw new UnifiedProtocolError("invalid_main_origin", "统一登录地址配置无效。"); }
  const local = ["localhost", "127.0.0.1", "[::1]"].includes(url.hostname);
  if (url.username || url.password || url.search || url.hash || url.pathname !== "/"
    || (!local && url.origin !== new URL(SITE_LINKS.games).origin)
    || (url.protocol !== "https:" && !(local && url.protocol === "http:"))) {
    throw new UnifiedProtocolError("invalid_main_origin", "统一登录地址配置无效。");
  }
  return url.origin;
}

/** 状态页只向登记站点回信；工具没有账号功能，不为游客额外创建账号会话。 */
export function statusClientOrigin(client: StatusClient): string {
  const configured = client === "circle" ? import.meta.env.VITE_UNIFIED_CIRCLE_ORIGIN
    : client === "chat" ? import.meta.env.VITE_UNIFIED_CHAT_ORIGIN : import.meta.env.VITE_UNIFIED_NEWAPI_ORIGIN;
  const fallback = client === "circle" ? SITE_LINKS.forum : client === "chat" ? SITE_LINKS.chat : "https://api.pingxingxian.space/";
  const url = new URL(configured || fallback);
  const local = ["localhost", "127.0.0.1", "[::1]"].includes(url.hostname);
  if (url.username || url.password || url.search || url.hash || url.pathname !== "/"
    || (!local && url.origin !== new URL(fallback).origin)
    || (url.protocol !== "https:" && !(local && url.protocol === "http:"))) {
    throw new UnifiedProtocolError("invalid_client_origin", "统一登录回调配置无效。");
  }
  return url.origin;
}

export function isStatusClient(value: unknown): value is StatusClient {
  return value === "circle" || value === "chat" || value === "newapi";
}

export function isUnifiedState(value: unknown): value is UnifiedState {
  if (!isRecord(value) || typeof value.authenticated !== "boolean") return false;
  return value.authenticated
    ? typeof value.subject === "string" && value.subject.length > 0 && value.subject.length <= 128
      && typeof value.auth_epoch === "string" && /^[A-Za-z0-9_-]{32,128}$/.test(value.auth_epoch)
    : value.subject === null && value.auth_epoch === null;
}

/** 调用方还必须核 event.origin、event.source 和本次 request_id，不能只凭消息内容认人。 */
export function isUnifiedStatusMessage(value: unknown, requestId: string): value is UnifiedStatusMessage {
  return isUnifiedState(value) && isRecord(value) && value.type === UNIFIED_MESSAGE_TYPE
    && value.version === UNIFIED_VERSION && value.request_id === requestId && typeof value.available === "boolean";
}

/** 只保留当前站普通页面回跳，拒绝外站、协议页及登录自身，避免授权循环和开放重定向。 */
export function localReturnPath(value: unknown, origin: string, fallback = "/"): string {
  if (typeof value !== "string" || value.length > 2048 || !value.startsWith("/")
    || value.startsWith("//") || /[\\\u0000-\u001f\u007f]/.test(value)) return fallback;
  try {
    let decoded = value.split(/[?#]/)[0];
    for (let index = 0; index < 4; index += 1) {
      if (decoded.startsWith("//") || /[\\\u0000-\u001f\u007f]/.test(decoded)
        || /%2f|%5c/i.test(decoded)
        || decoded.split("/").some(part => part === "." || part === "..")) return fallback;
      const next = decodeURIComponent(decoded);
      if (next === decoded) break;
      if (index === 3) return fallback;
      decoded = next;
    }
    const url = new URL(value, origin);
    const pathname = new URL(decoded, origin).pathname;
    if (url.origin !== origin || url.username || url.password || pathname === "/auth"
      || pathname.startsWith("/auth/") || pathname === "/api" || pathname.startsWith("/api/")) return fallback;
    return url.pathname + url.search + url.hash;
  } catch { return fallback; }
}

export function randomRequestId(): string {
  return Array.from(crypto.getRandomValues(new Uint8Array(16)), byte => byte.toString(16).padStart(2, "0")).join("");
}

function base64url(bytes: Uint8Array): string {
  return btoa(String.fromCharCode(...bytes)).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

/** 每次导航独立产生 PKCE 和 state；存储不可用就明确失败，不把 verifier 放进 URL。 */
export async function beginCircleTransaction(returnTo: unknown, origin: string, storage: Storage, mode: "redirect" | "silent" = "redirect"): Promise<{
  transaction: CircleTransaction; challenge: string;
}> {
  const verifier = base64url(crypto.getRandomValues(new Uint8Array(32)));
  const challenge = base64url(new Uint8Array(await crypto.subtle.digest("SHA-256", new TextEncoder().encode(verifier))));
  const transaction = { state: randomRequestId(), verifier, returnTo: localReturnPath(returnTo, origin), createdAt: Date.now(), mode };
  try { storage.setItem(FLOW_STORAGE_KEY, JSON.stringify(transaction)); }
  catch { throw new UnifiedProtocolError("flow_storage_unavailable", "浏览器无法保存安全登录状态，请允许会话存储后重试。"); }
  return { transaction, challenge };
}

/** 仅兑换本标签保存、未过期且 state 匹配的一次流程；不采信地址栏中的回跳地址。 */
export function readCircleTransaction(state: unknown, storage: Storage, now = Date.now()): CircleTransaction {
  let value: unknown;
  try { value = JSON.parse(storage.getItem(FLOW_STORAGE_KEY) || "null"); }
  catch { throw new UnifiedProtocolError("invalid_flow", "登录状态无法读取，请重新从圈子登录。"); }
  if (!isRecord(value) || value.state !== state || typeof value.state !== "string"
    || !/^[0-9a-f]{32}$/.test(value.state) || typeof value.verifier !== "string"
    || !/^[A-Za-z0-9_-]{43,128}$/.test(value.verifier) || typeof value.returnTo !== "string"
    || typeof value.createdAt !== "number" || !Number.isFinite(value.createdAt)
    || (value.mode !== "redirect" && value.mode !== "silent")
    || value.createdAt > now || now - value.createdAt > FLOW_TTL_MS) {
    throw new UnifiedProtocolError("invalid_flow", "登录状态已失效或不匹配，请重新从圈子登录。");
  }
  return { state: value.state, verifier: value.verifier, returnTo: value.returnTo, createdAt: value.createdAt, mode: value.mode };
}

export function clearCircleTransaction(storage: Storage): void {
  try { storage.removeItem(FLOW_STORAGE_KEY); }
  catch { throw new UnifiedProtocolError("flow_storage_unavailable", "浏览器无法清理登录状态，请刷新后重试。"); }
}

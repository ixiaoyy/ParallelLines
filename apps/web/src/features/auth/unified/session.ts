import { readonly, shallowRef } from "vue";

import { clearAuthTokens, getAccessToken, getRefreshToken, registerSessionAccessRefresher,
  setApiIdentityContext, setSessionAccessToken, suspendSessionAccess } from "@/shared/api/client";
import { queryClient } from "@/shared/api/queryClient";
import { queryKeys } from "@/shared/api/queryKeys";
import { IS_FORUM_SITE } from "@/shared/site/links";
import { resetQueryCacheForAuthChange } from "../sessionCache";
import { accessResponse, bootstrapUnified, createUnifiedLogoutTicket, fetchUnifiedState, refreshLegacyMainAccess, UnifiedApiError } from "./api";
import type { UnifiedAccess } from "./api";
import { beginCircleTransaction, CALLBACK_PATH, CIRCLE_CLIENT_ID, isRecord, isUnifiedStatusMessage,
  mainAuthOrigin, randomRequestId, STATUS_PATH, UNIFIED_AUTH_ENABLED,
  UNIFIED_REFRESH_TYPE, UNIFIED_VERSION } from "./protocol";
import type { UnifiedState } from "./protocol";

const CHANGE_KEY = "parallellines.unified-change.v1";
const CHANGE_EVENT = "pl:unified-auth-change";
const CHANNEL_NAME = "parallellines.unified-auth.v1";
export const ACCESS_RESULT_TYPE = "pl:unified-access-result";
interface SessionMeta { subject: string; auth_epoch: string; expiresAt: number }
const availability = shallowRef<"pending" | "anonymous" | "authenticated" | "unavailable">("pending");
export const unifiedAvailability = readonly(availability);
let current: SessionMeta | null = null;
let initialized = false;
let primaryPromise: Promise<UnifiedAccess | null> | null = null;
let primaryAccess: UnifiedAccess | null = null;
let legacyAccess: string | null = null;
let legacyRefresh: string | null = null;
let pendingLoginProof: string | null = null;
let statusFrame: HTMLIFrameElement | null = null;
let statusRequest = "";
let lastStatusAt = 0;
let silentPromise: Promise<UnifiedAccess> | null = null;
let silentGeneration = -1;
let cancelSilent: (() => void) | null = null;
let stopBrowser: (() => void) | null = null;
let authorityGeneration = 0;
let transitionRevision = 0;
let observedEpoch: string | null | undefined;

/** 只通知主域同源状态页重新读取权威状态，不在广播中发送账号资料或凭据。 */
export function notifyUnifiedChange(): void {
  window.dispatchEvent(new Event(CHANGE_EVENT));
  try { localStorage.setItem(CHANGE_KEY, randomRequestId()); } catch { /* 同窗口事件仍可用。 */ }
  if (typeof BroadcastChannel !== "undefined") {
    const channel = new BroadcastChannel(CHANNEL_NAME);
    channel.postMessage({ type: CHANGE_EVENT });
    channel.close();
  }
}

/** 可通信的主域窗口及时同步；不设置持续轮询，组件销毁后撤销全部监听。 */
export function listenUnifiedChanges(callback: () => void): () => void {
  const storage = (event: StorageEvent) => { if (event.key === CHANGE_KEY) callback(); };
  const channel = typeof BroadcastChannel !== "undefined" ? new BroadcastChannel(CHANNEL_NAME) : null;
  channel?.addEventListener("message", callback);
  window.addEventListener(CHANGE_EVENT, callback);
  window.addEventListener("storage", storage);
  return () => { channel?.close(); window.removeEventListener(CHANGE_EVENT, callback); window.removeEventListener("storage", storage); };
}

/** 先切换响应消费身份再清旧缓存；相同会话短 token 续发不清空正在阅读的页面数据。 */
export async function applyUnifiedAccess(access: UnifiedAccess): Promise<void> {
  const revision = ++transitionRevision;
  const changed = current?.subject !== access.subject || current.auth_epoch !== access.auth_epoch;
  setApiIdentityContext(access.auth_epoch);
  setSessionAccessToken(access.access_token);
  current = { subject: access.subject, auth_epoch: access.auth_epoch, expiresAt: Date.now() + access.expires_in * 1000 };
  primaryAccess = access;
  legacyAccess = null;
  legacyRefresh = null;
  availability.value = "authenticated";
  if (changed) await resetQueryCacheForAuthChange(queryClient, access.user, () => revision === transitionRevision);
  else queryClient.setQueryData(queryKeys.currentUser, access.user);
}

export async function clearUnifiedAccess(): Promise<void> {
  const revision = ++transitionRevision;
  const hadIdentity = current !== null || getAccessToken() !== null || queryClient.getQueryData(queryKeys.currentUser) != null;
  setApiIdentityContext(null);
  clearAuthTokens();
  current = null;
  primaryAccess = null;
  legacyAccess = null;
  legacyRefresh = null;
  availability.value = "anonymous";
  if (hadIdentity) await resetQueryCacheForAuthChange(queryClient, null, () => revision === transitionRevision);
}

/** 仅主站可迁移自己的旧 token；Circle 的旧刷新令牌绝不传给主域。 */
export async function ensurePrimarySession(): Promise<UnifiedAccess | null> {
  if (primaryPromise) return primaryPromise;
  const generation = authorityGeneration;
  const apply = async (access: UnifiedAccess): Promise<UnifiedAccess | null> => {
    if (generation !== authorityGeneration) return primaryAccess;
    await applyUnifiedAccess(access);
    return access;
  };
  primaryPromise = (async () => {
    const state = await fetchUnifiedState();
    if (state.authenticated) {
      const access = await bootstrapUnified();
      return apply(access);
    }
    const refresh = legacyRefresh || getRefreshToken();
    if (refresh) {
      const bearer = legacyAccess || getAccessToken();
      // 已有access先迁移；仅401允许续原主域refresh一次，网络故障不降级成匿名。
      if (bearer) {
        try {
          const applied = await apply(await bootstrapUnified(false, bearer));
          if (generation === authorityGeneration) notifyUnifiedChange();
          return applied;
        } catch (error) {
          if (!(error instanceof UnifiedApiError) || error.status !== 401) throw error;
        }
      }
      try {
        const access = await bootstrapUnified(false, await refreshLegacyMainAccess(refresh));
        const applied = await apply(access);
        if (generation === authorityGeneration) notifyUnifiedChange();
        return applied;
      } catch (error) {
        if (!(error instanceof UnifiedApiError) || error.status !== 401) throw error;
      }
    }
    if (generation === authorityGeneration) await clearUnifiedAccess();
    return null;
  })().catch(error => { if (generation === authorityGeneration) availability.value = "unavailable"; throw error; }).finally(() => { primaryPromise = null; });
  return primaryPromise;
}

/** 用户真实完成密码/MFA/邮箱登录后才允许替换主域会话，失败不拿旧账号冒充成功。 */
export async function completePrimaryLogin(bearer: string): Promise<void> {
  authorityGeneration += 1;
  pendingLoginProof = bearer;
  await clearUnifiedAccess();
  try {
    const access = await bootstrapUnified(true, bearer);
    await applyUnifiedAccess(access);
    pendingLoginProof = null;
    notifyUnifiedChange();
  } catch (error) {
    availability.value = "unavailable";
    notifyUnifiedChange();
    throw error;
  }
}

export async function retryPrimaryLogin(): Promise<UnifiedAccess | null> {
  if (pendingLoginProof) { await completePrimaryLogin(pendingLoginProof); return primaryAccess; }
  return ensurePrimarySession();
}

export function circleAuthorizeUrl(state: string, challenge: string, silent: boolean): string {
  const destination = new URL("/auth/unified", mainAuthOrigin());
  destination.search = new URLSearchParams({ client_id: CIRCLE_CLIENT_ID, redirect_uri: window.location.origin + CALLBACK_PATH,
    state, code_challenge: challenge, code_challenge_method: "S256", ...(silent ? { silent: "1" } : {}) }).toString();
  return destination.href;
}

/** 明确受限操作才作顶层登录导航，公开匿名页面不因此变成登录墙。 */
export async function beginCircleLogin(returnTo: unknown): Promise<void> {
  const { transaction, challenge } = await beginCircleTransaction(returnTo, window.location.origin, sessionStorage);
  window.location.assign(circleAuthorizeUrl(transaction.state, challenge, false));
}

/** 使用独立隐藏授权帧续短 token；只接收自己帧、Circle来源和本次state的回信。 */
export async function silentCircleAccess(): Promise<UnifiedAccess> {
  if (silentPromise && silentGeneration !== authorityGeneration) {
    const generation = authorityGeneration;
    // 等旧帧结束再建立新state，不能把旧账号的在途兑换复用到刚确认的新身份。
    try { await silentPromise; } catch { /* 原调用方处理旧流程失败；新身份必须单独接续。 */ }
    if (generation !== authorityGeneration) throw new UnifiedApiError("identity_changed", "账号已切换，请重试。", 409);
  }
  if (silentPromise) return silentPromise;
  silentGeneration = authorityGeneration;
  const generation = silentGeneration;
  silentPromise = (async () => {
    const { transaction, challenge } = await beginCircleTransaction(window.location.pathname + window.location.search + window.location.hash,
      window.location.origin, sessionStorage, "silent");
    if (generation !== authorityGeneration) throw new UnifiedApiError("identity_changed", "账号已切换，请重试。", 409);
    return new Promise<UnifiedAccess>((resolve, reject) => {
      const frame = document.createElement("iframe");
      frame.hidden = true;
      frame.title = "同步主站登录";
      frame.referrerPolicy = "no-referrer";
      const finish = (access: UnifiedAccess | null, error?: Error) => {
        window.clearTimeout(timer); window.removeEventListener("message", receive); frame.remove();
        cancelSilent = null;
        if (access) resolve(access); else reject(error || new UnifiedApiError("unified_login_required", "请先登录主站。", 401));
      };
      const receive = (event: MessageEvent<unknown>) => {
        if (event.origin !== window.location.origin || event.source !== frame.contentWindow || !isRecord(event.data)
          || event.data.type !== ACCESS_RESULT_TYPE || event.data.version !== 1 || event.data.state !== transaction.state) return;
        if (event.data.access) {
          try { finish(accessResponse(event.data.access)); }
          catch (error) { finish(null, error instanceof Error ? error : new Error("invalid_access")); }
        } else {
          const code = event.data.error === "login_required" ? "login_required" : "unified_auth_unavailable";
          finish(null, new UnifiedApiError(code, "主站登录接续未完成，请重试。", code === "login_required" ? 401 : 0));
        }
      };
      const timer = window.setTimeout(() => finish(null, new UnifiedApiError("unified_auth_timeout", "统一登录同步超时，请重试。", 0)), 15_000);
      cancelSilent = () => finish(null, new UnifiedApiError("unified_auth_cancelled", "登录已取消。", 0));
      window.addEventListener("message", receive);
      frame.src = circleAuthorizeUrl(transaction.state, challenge, true);
      document.body.append(frame);
    });
  })().finally(() => { silentPromise = null; });
  return silentPromise;
}

function askStatus(): void {
  if (!statusFrame || Date.now() - lastStatusAt < 1000) return;
  lastStatusAt = Date.now();
  statusFrame.contentWindow?.postMessage({ type: UNIFIED_REFRESH_TYPE, version: UNIFIED_VERSION, request_id: statusRequest }, mainAuthOrigin());
}

/** 应用仅创建一个状态桥和一个短续发器，销毁时释放帧/监听；没有全局登录重定向。 */
export function startUnifiedBrowserSession(): () => void {
  if (!UNIFIED_AUTH_ENABLED || window.location.pathname.startsWith("/auth/unified")) return () => {};
  if (initialized) return () => {};
  initialized = true;
  const previousAccess = getAccessToken();
  legacyAccess = IS_FORUM_SITE ? null : previousAccess;
  legacyRefresh = IS_FORUM_SITE ? null : getRefreshToken();
  if (!current || !getAccessToken()) { suspendSessionAccess(); setApiIdentityContext(null); }
  const refresh = registerSessionAccessRefresher(async () => {
    const epoch = current?.auth_epoch;
    const generation = authorityGeneration;
    try {
      const access = IS_FORUM_SITE ? await silentCircleAccess() : await ensurePrimarySession();
      if (generation !== authorityGeneration) return null;
      if (!access) { await clearUnifiedAccess(); return null; }
      await applyUnifiedAccess(access);
      return epoch === access.auth_epoch ? access.access_token : null;
    } catch (error) {
      if (generation !== authorityGeneration) return null;
      // 确认登录失效才清当前身份；断连不等于退出，旧请求仍由响应隔离边界拒绝。
      if (error instanceof UnifiedApiError && error.status === 401) { await clearUnifiedAccess(); return null; }
      availability.value = "unavailable";
      throw error;
    }
  });
  let statusTimer: number | undefined;
  const receive = async (event: MessageEvent<unknown>) => {
    if (!statusFrame || event.origin !== mainAuthOrigin() || event.source !== statusFrame.contentWindow
      || !isUnifiedStatusMessage(event.data, statusRequest)) return;
    window.clearTimeout(statusTimer);
    const state = event.data;
    if (!state.available) { availability.value = "unavailable"; return; }
    if (observedEpoch !== state.auth_epoch) { observedEpoch = state.auth_epoch; authorityGeneration += 1; }
    const generation = authorityGeneration;
    if (!state.authenticated) { await clearUnifiedAccess(); return; }
    try {
      if (current?.auth_epoch === state.auth_epoch && current.subject === state.subject && getAccessToken()
        && current.expiresAt > Date.now() + 10_000) { availability.value = "authenticated"; return; }
      // 新标签必须由本次PKCE接续认领身份，不拼接跨标签分开写入的磁盘token和元数据。
      if (current && current.auth_epoch !== state.auth_epoch) await clearUnifiedAccess();
      const access = await silentCircleAccess();
      if (generation === authorityGeneration) await applyUnifiedAccess(access);
    } catch (error) {
      if (generation !== authorityGeneration) return;
      if (error instanceof UnifiedApiError && error.status === 401) await clearUnifiedAccess();
      else availability.value = "unavailable";
    }
  };
  let cancelChanges = () => {};
  let syncMain = () => {};
  if (IS_FORUM_SITE) {
    statusRequest = randomRequestId();
    statusFrame = document.createElement("iframe");
    statusFrame.hidden = true; statusFrame.title = "主站登录状态"; statusFrame.referrerPolicy = "no-referrer";
    window.addEventListener("message", receive);
    statusFrame.src = mainAuthOrigin() + STATUS_PATH + "?client=circle&request_id=" + statusRequest;
    statusTimer = window.setTimeout(() => { availability.value = "unavailable"; }, 8000);
    document.body.append(statusFrame);
  } else {
    let running = false;
    let dirty = false;
    let disposed = false;
    // 另一标签的通知先废弃旧在途读取，再排队复核；不能仅复用旧promise而吃掉这次换号。
    const drain = async () => {
      running = true;
      do {
        dirty = false;
        const previousRequest = primaryPromise;
        if (previousRequest) { try { await previousRequest; } catch { /* 随后单独读取本次权威状态。 */ } }
        if (disposed) break;
        try { await ensurePrimarySession(); } catch { /* ensurePrimarySession已保留不可用状态。 */ }
      } while (dirty && !disposed);
      running = false;
    };
    syncMain = () => { authorityGeneration += 1; dirty = true; if (!running && !disposed) void drain(); };
    const unlisten = listenUnifiedChanges(syncMain);
    cancelChanges = () => { disposed = true; unlisten(); };
    syncMain();
  }
  const focus = () => { if (IS_FORUM_SITE) askStatus(); else syncMain(); };
  window.addEventListener("focus", focus);
  stopBrowser = () => { refresh(); cancelChanges(); statusFrame?.remove(); statusFrame = null;
    authorityGeneration += 1; observedEpoch = undefined;
    cancelSilent?.();
    window.clearTimeout(statusTimer);
    window.removeEventListener("message", receive); window.removeEventListener("focus", focus); initialized = false; stopBrowser = null; };
  return stopBrowser;
}

/** 受保护路由只承认中央身份；未登录时由路由层发起显式登录，不用旧Circle独立刷新。 */
export async function ensureUnifiedForProtectedRoute(): Promise<boolean> {
  if (!UNIFIED_AUTH_ENABLED) return getAccessToken() !== null;
  startUnifiedBrowserSession();
  if (!IS_FORUM_SITE) return (await ensurePrimarySession()) !== null;
  const generation = authorityGeneration;
  try {
    const access = await silentCircleAccess();
    if (observedEpoch !== undefined && access.auth_epoch !== observedEpoch) {
      throw new UnifiedApiError("identity_changed", "账号已切换，请重试。", 409);
    }
    await applyUnifiedAccess(access); return true;
  }
  catch (error) {
    if (error instanceof UnifiedApiError && error.status === 401) {
      if (generation === authorityGeneration) await clearUnifiedAccess();
      return false;
    }
    throw error;
  }
}

export async function beginUnifiedLogout(): Promise<void> {
  const token = getAccessToken();
  if (!token) throw new UnifiedApiError("unified_login_required", "此站会话已失效，请先同步主站登录。", 401);
  authorityGeneration += 1;
  const destination = new URL(await createUnifiedLogoutTicket(window.location.origin + "/", token));
  if (destination.origin !== mainAuthOrigin() || destination.pathname !== "/auth/unified/logout"
    || destination.username || destination.password || destination.hash || !/^[A-Za-z0-9_-]{32,128}$/.test(destination.searchParams.get("ticket") || "")) {
    throw new UnifiedApiError("invalid_unified_response", "统一退出地址无效。", 0);
  }
  window.location.assign(destination.href);
}

export function currentUnifiedState(): UnifiedState {
  return current ? { authenticated: true, subject: current.subject, auth_epoch: current.auth_epoch }
    : { authenticated: false, subject: null, auth_epoch: null };
}

export function stopUnifiedBrowserSession(): void { stopBrowser?.(); }

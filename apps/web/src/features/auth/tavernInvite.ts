import { readonly, shallowRef } from "vue";

export const TAVERN_INVITE_PATH = "/tavern/invite";
const STORAGE_KEY = "parallellines.tavern-invite-flow.v1";
const LEGACY_STORAGE_KEY = "parallellines.tavern-invite.v1";
const FLOW_PATTERN = /^[A-Za-z0-9_-]{22}$/;
const captureVersion = shallowRef(0);
let captureFailed = false;
export const tavernInviteCaptureVersion = readonly(captureVersion);

/** 主站只保存酒馆发出的无入场权流程标记；无效片段清除上一次流程。 */
export function captureTavernInvite(hash: string): void {
  const flow = hash.slice(1);
  try {
    window.sessionStorage.removeItem(LEGACY_STORAGE_KEY);
    if (FLOW_PATTERN.test(flow)) window.sessionStorage.setItem(STORAGE_KEY, flow);
    else window.sessionStorage.removeItem(STORAGE_KEY);
    captureFailed = false;
  } catch {
    // 写不进去时即使旧值仍可读，也不能误用旧流程。
    captureFailed = true;
  } finally {
    captureVersion.value += 1;
  }
}

/** 返回当前标签的合法流程标记；不读取旧版暂存值。 */
export function loadTavernInviteFlow(): string | null {
  if (captureFailed) throw new Error("tavern_invite_storage_unavailable");
  window.sessionStorage.removeItem(LEGACY_STORAGE_KEY);
  const flow = window.sessionStorage.getItem(STORAGE_KEY);
  return flow && FLOW_PATTERN.test(flow) ? flow : null;
}

/** 交接未完成又需要重新登录时，只把当前流程标记保留在同一标签。 */
export function restoreTavernInviteFlow(flow: string): void {
  window.sessionStorage.setItem(STORAGE_KEY, flow);
}

/** 返回酒馆前清掉当前主站标签内的流程标记。 */
export function clearTavernInviteFlow(): void {
  window.sessionStorage.removeItem(STORAGE_KEY);
}

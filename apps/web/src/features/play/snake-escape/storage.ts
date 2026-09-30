import { LEVEL_COUNT } from "./rules";

const STORAGE_KEY = "parallellines.snake-escape.progress.v1";
export interface Progress { version: 1; highestUnlocked: number }
const emptyProgress = (): Progress => ({ version: 1, highestUnlocked: 1 });

/** 只接受当前版本和合法关卡，损坏或旧版本记录不会跳过关卡。 */
export function parseProgress(raw: string | null): Progress {
  if (raw === null) return emptyProgress();
  try {
    const parsed: unknown = JSON.parse(raw);
    if (typeof parsed !== "object" || parsed === null || !("version" in parsed) || !("highestUnlocked" in parsed)) return emptyProgress();
    if (parsed.version !== 1 || typeof parsed.highestUnlocked !== "number"
      || !Number.isInteger(parsed.highestUnlocked) || parsed.highestUnlocked < 1 || parsed.highestUnlocked > LEVEL_COUNT) return emptyProgress();
    return { version: 1, highestUnlocked: parsed.highestUnlocked };
  } catch {
    // 本地进度损坏仅从第一关恢复，游戏不依赖持久化才能进行。
    return emptyProgress();
  }
}

/** 读取浏览器进度；无浏览器或存储被禁用时使用本次会话的起始进度。 */
export function loadProgress(): Progress {
  if (typeof window === "undefined") return emptyProgress();
  try { return parseProgress(window.localStorage.getItem(STORAGE_KEY)); }
  catch { return emptyProgress(); }
}

/** 通关后最多解锁下一关，并保留之前已解锁的更高关卡。 */
export function unlockNext(progress: Progress, completed: number): Progress {
  if (!Number.isInteger(completed) || completed < 1 || completed > progress.highestUnlocked) return progress;
  return { version: 1, highestUnlocked: Math.min(LEVEL_COUNT, Math.max(progress.highestUnlocked, completed + 1)) };
}

/** 保存已验证的解锁进度，浏览器禁用存储时仍保留内存中的会话进度。 */
export function saveProgress(progress: Progress): void {
  if (typeof window === "undefined") return;
  try { window.localStorage.setItem(STORAGE_KEY, JSON.stringify(progress)); }
  catch { /* 浏览器隐私设置可禁用存储；本局与已解锁关卡仍由组件内存持有。 */ }
}

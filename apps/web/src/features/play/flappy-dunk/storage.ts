const BEST_KEY = "parallellines.flappy-dunk.best.v1";
let reportedStorageFailure = false;

/** 校验本地最高分，只接收安全范围内的非负整数，坏值作为未有记录处理。 */
export function parseDunkBest(raw: string | null): number {
  if (raw === null || !/^\d{1,7}$/.test(raw)) return 0;
  const value = Number(raw);
  return Number.isSafeInteger(value) && value >= 0 && value <= 9_999_999 ? value : 0;
}

/** 存储不可用时仅诊断一次，保留本局内存分数，避免每次得分重复输出。 */
function reportFailure(error: unknown): void {
  if (reportedStorageFailure) return;
  reportedStorageFailure = true;
  console.warn("[flappy-dunk] best-score-storage-unavailable", error instanceof Error ? error.name : "unknown");
}

/** 读取经过校验的本机最高分；非浏览器环境及被禁用的存储返回 0。 */
export function readDunkBest(): number {
  if (typeof window === "undefined") return 0;
  try { return parseDunkBest(window.localStorage.getItem(BEST_KEY)); }
  catch (error) { reportFailure(error); return 0; }
}

/** 仅持久化合法的新最高分，保留其他标签页已经保存的更高记录。 */
export function saveDunkBest(score: number): number {
  const validated = parseDunkBest(String(score));
  if (typeof window === "undefined") return validated;
  try {
    const best = Math.max(validated, parseDunkBest(window.localStorage.getItem(BEST_KEY)));
    window.localStorage.setItem(BEST_KEY, String(best));
    return best;
  } catch (error) { reportFailure(error); return validated; }
}

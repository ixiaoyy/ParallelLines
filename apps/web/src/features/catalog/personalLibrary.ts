export const PERSONAL_LIBRARY_KEY = "parallellines.catalog-library.v1";
export const WANTED_LIMIT = 500;
export const RECENT_LIMIT = 50;

export interface PersonalLibrary {
  version: 1;
  wantedIds: string[];
  recent: Array<{ projectId: string; lastOpenedAt: number }>;
}

let reportedStorageFailure = false;

/** 校验本机清单并去重；空存储返回空清单，未知版本或坏数据抛错以保留原记录。 */
function decodeLibrary(raw: string | null): PersonalLibrary {
  if (raw === null) return { version: 1, wantedIds: [], recent: [] };
  // 限制本地异常大值的解析开销；正常清单只含最多 550 个标识和时间。
  if (raw.length > 250_000) throw new RangeError("personal-library-size");
  const value: unknown = JSON.parse(raw);
  if (!value || typeof value !== "object"
    || !("version" in value) || value.version !== 1
    || !("wantedIds" in value) || !Array.isArray(value.wantedIds)
    || !("recent" in value) || !Array.isArray(value.recent)
    || value.wantedIds.length > WANTED_LIMIT || value.recent.length > RECENT_LIMIT) {
    throw new TypeError("personal-library-format");
  }

  // 标识保留原字符串，去重只作用于个人清单，不按名称或数值合并不同项目。
  const wantedIds = new Set<string>();
  for (const id of value.wantedIds) {
    if (typeof id !== "string" || !id.trim()) throw new TypeError("personal-library-id");
    wantedIds.add(id);
  }
  // 同一游戏出现多条最近记录时取最后打开时间，不凭当前目录删掉暂缺项目。
  const recentTimes = new Map<string, number>();
  for (const candidate of value.recent) {
    const entry: unknown = candidate;
    if (!entry || typeof entry !== "object"
      || !("projectId" in entry) || typeof entry.projectId !== "string" || !entry.projectId.trim()
      || !("lastOpenedAt" in entry) || typeof entry.lastOpenedAt !== "number"
      || !Number.isSafeInteger(entry.lastOpenedAt) || entry.lastOpenedAt < 0
      || entry.lastOpenedAt > 8_640_000_000_000_000) {
      throw new TypeError("personal-library-recent");
    }
    recentTimes.set(entry.projectId, Math.max(recentTimes.get(entry.projectId) ?? 0, entry.lastOpenedAt));
  }
  return {
    version: 1,
    wantedIds: [...wantedIds],
    recent: [...recentTimes].map(([projectId, lastOpenedAt]) => ({ projectId, lastOpenedAt }))
      .sort((left, right) => right.lastOpenedAt - left.lastOpenedAt),
  };
}

/** 存储异常仅诊断一次，不记录用户清单内容；页面通过返回值提示本次只能保留内存状态。 */
function reportStorageFailure(operation: "read" | "write", error: unknown): void {
  if (reportedStorageFailure) return;
  reportedStorageFailure = true;
  console.warn("catalog_personal_library_storage_failed", {
    operation,
    reason: error instanceof Error ? error.name : "unknown",
  });
}

/** 读取当前浏览器清单；失败返回空的内存清单并禁止本次页面覆盖原存储。 */
export function readPersonalLibrary(): { library: PersonalLibrary; canPersist: boolean } {
  if (typeof window !== "undefined") {
    try {
      return { library: decodeLibrary(window.localStorage.getItem(PERSONAL_LIBRARY_KEY)), canPersist: true };
    } catch (error) {
      reportStorageFailure("read", error);
    }
  }
  return { library: { version: 1, wantedIds: [], recent: [] }, canPersist: false };
}

/** 保存完整清单并返回是否成功；再次校验原值，避免覆盖其他标签页留下的未知版本或坏数据。 */
export function savePersonalLibrary(library: PersonalLibrary): boolean {
  if (typeof window === "undefined") return false;
  try {
    const storage = window.localStorage;
    decodeLibrary(storage.getItem(PERSONAL_LIBRARY_KEY));
    const validated = decodeLibrary(JSON.stringify(library));
    storage.setItem(PERSONAL_LIBRARY_KEY, JSON.stringify(validated));
    return true;
  } catch (error) {
    reportStorageFailure("write", error);
    return false;
  }
}

/** 按字符串项目 ID 切换想玩状态并返回新快照；达到上限时拒绝新增，但仍可移出。 */
export function toggleWantedProject(library: PersonalLibrary, projectId: string): PersonalLibrary | null {
  // 已收藏项目始终允许移出，达到上限后也不能阻断整理清单。
  if (library.wantedIds.includes(projectId)) {
    return { ...library, wantedIds: library.wantedIds.filter((id) => id !== projectId) };
  }
  if (library.wantedIds.length >= WANTED_LIMIT) return null;
  return { ...library, wantedIds: [...library.wantedIds, projectId] };
}

/** 记录一次链接打开，按传入毫秒时间更新最近记录；只保留最新 50 项，不表示实际游玩。 */
export function recordRecentProject(library: PersonalLibrary, projectId: string, now = Date.now()): PersonalLibrary {
  return {
    ...library,
    recent: [{ projectId, lastOpenedAt: now }, ...library.recent.filter((entry) => entry.projectId !== projectId)]
      .sort((left, right) => right.lastOpenedAt - left.lastOpenedAt)
      .slice(0, RECENT_LIMIT),
  };
}

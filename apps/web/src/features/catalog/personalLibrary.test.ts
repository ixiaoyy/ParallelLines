import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  PERSONAL_LIBRARY_KEY,
  RECENT_LIMIT,
  WANTED_LIMIT,
  readPersonalLibrary,
  recordRecentProject,
  savePersonalLibrary,
  toggleWantedProject,
  type PersonalLibrary,
} from "./personalLibrary";

const emptyLibrary: PersonalLibrary = { version: 1, wantedIds: [], recent: [] };

/** 为每例提供独立的浏览器存储，可检查实际写入内容及失败边界。 */
function memoryStorage() {
  const values = new Map<string, string>();
  return {
    values,
    getItem: vi.fn((key: string) => values.get(key) ?? null),
    setItem: vi.fn((key: string, value: string) => { values.set(key, value); }),
  };
}

let storage = memoryStorage();

beforeEach(() => {
  storage = memoryStorage();
  vi.stubGlobal("window", { localStorage: storage });
  vi.spyOn(console, "warn").mockImplementation(() => undefined);
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("个人游戏清单的本地持久化", () => {
  it("未保存时返回空清单，不提前写入存储", () => {
    expect(readPersonalLibrary()).toEqual({ library: emptyLibrary, canPersist: true });
    expect(storage.setItem).not.toHaveBeenCalled();
  });

  it("去重并保留字符串标识、最新打开时间以及暂时下架的项目", () => {
    storage.values.set(PERSONAL_LIBRARY_KEY, JSON.stringify({
      version: 1,
      wantedIds: ["001", "unlisted-project", "001"],
      recent: [
        { projectId: "001", lastOpenedAt: 1000 },
        { projectId: "unlisted-project", lastOpenedAt: 4000 },
        { projectId: "001", lastOpenedAt: 3000 },
      ],
    }));
    const result = readPersonalLibrary();
    expect(result).toEqual({
      canPersist: true,
      library: {
        version: 1,
        wantedIds: ["001", "unlisted-project"],
        recent: [
          { projectId: "unlisted-project", lastOpenedAt: 4000 },
          { projectId: "001", lastOpenedAt: 3000 },
        ],
      },
    });
    expect(savePersonalLibrary(result.library)).toBe(true);
    expect(JSON.parse(storage.values.get(PERSONAL_LIBRARY_KEY)!)).toEqual(result.library);
  });

  it.each([
    "not-json",
    "null",
    JSON.stringify({ version: 2, wantedIds: ["901"], recent: [] }),
    JSON.stringify({ version: 1, wantedIds: [901], recent: [] }),
    JSON.stringify({ version: 1, wantedIds: [""], recent: [] }),
    JSON.stringify({ version: 1, wantedIds: [], recent: [{ projectId: "901", lastOpenedAt: -1 }] }),
    JSON.stringify({ version: 1, wantedIds: [], recent: [{ projectId: "901", lastOpenedAt: "1000" }] }),
  ])("无法恢复的原始快照不会被读取或后续保存自动覆盖：%s", (raw) => {
    storage.values.set(PERSONAL_LIBRARY_KEY, raw);
    expect(readPersonalLibrary()).toEqual({ library: emptyLibrary, canPersist: false });
    expect(savePersonalLibrary({ ...emptyLibrary, wantedIds: ["902"] })).toBe(false);
    expect(storage.values.get(PERSONAL_LIBRARY_KEY)).toBe(raw);
    expect(storage.setItem).not.toHaveBeenCalled();
  });

  it("读取存储被禁用时返回明确失败，仍可操作页面内存清单", () => {
    storage.getItem.mockImplementation(() => { throw new Error("storage denied"); });
    const result = readPersonalLibrary();
    expect(result).toEqual({ library: emptyLibrary, canPersist: false });
    expect(toggleWantedProject(result.library, "901")?.wantedIds).toEqual(["901"]);
    expect(recordRecentProject(result.library, "901", 2000).recent)
      .toEqual([{ projectId: "901", lastOpenedAt: 2000 }]);
  });

  it("超出约定容量的快照保留原值，避免静默截断用户记录", () => {
    const raw = JSON.stringify({
      ...emptyLibrary,
      wantedIds: Array.from({ length: WANTED_LIMIT + 1 }, (_, index) => String(index)),
    });
    storage.values.set(PERSONAL_LIBRARY_KEY, raw);
    expect(readPersonalLibrary().canPersist).toBe(false);
    expect(savePersonalLibrary(emptyLibrary)).toBe(false);
    expect(storage.values.get(PERSONAL_LIBRARY_KEY)).toBe(raw);
  });

  it("写入失败返回 false，并保留原快照", () => {
    const original = JSON.stringify(emptyLibrary);
    storage.values.set(PERSONAL_LIBRARY_KEY, original);
    storage.setItem.mockImplementation(() => { throw new Error("quota exceeded"); });
    expect(savePersonalLibrary({ ...emptyLibrary, wantedIds: ["901"] })).toBe(false);
    expect(storage.values.get(PERSONAL_LIBRARY_KEY)).toBe(original);
  });
});

describe("想玩与最近打开的边界", () => {
  it("同一毫秒新打开的项目置顶，刷新读取仍保持顺序", () => {
    const first = recordRecentProject(emptyLibrary, "901", 2000);
    const second = recordRecentProject(first, "902", 2000);
    expect(second.recent.map((entry) => entry.projectId)).toEqual(["902", "901"]);
    expect(savePersonalLibrary(second)).toBe(true);
    expect(readPersonalLibrary().library.recent.map((entry) => entry.projectId)).toEqual(["902", "901"]);
  });

  it("想玩操作可撤销且不改动输入或最近打开", () => {
    const original: PersonalLibrary = {
      version: 1,
      wantedIds: ["901"],
      recent: [{ projectId: "902", lastOpenedAt: 1000 }],
    };
    const added = toggleWantedProject(original, "902");
    expect(added?.wantedIds).toEqual(expect.arrayContaining(["901", "902"]));
    expect(added?.wantedIds).toHaveLength(2);
    expect(toggleWantedProject(added!, "902")).toEqual(original);
    expect(original.wantedIds).toEqual(["901"]);
    expect(added?.recent).toEqual(original.recent);
  });

  it("想玩满 500 项拒绝新增，移出后可以重新加入", () => {
    expect(WANTED_LIMIT).toBe(500);
    const full: PersonalLibrary = {
      ...emptyLibrary,
      wantedIds: Array.from({ length: WANTED_LIMIT }, (_, index) => `game-${index}`),
    };
    expect(toggleWantedProject(full, "new-game")).toBeNull();
    expect(full.wantedIds).toHaveLength(WANTED_LIMIT);
    const removed = toggleWantedProject(full, "game-1");
    expect(removed?.wantedIds).toHaveLength(WANTED_LIMIT - 1);
    expect(toggleWantedProject(removed!, "new-game")?.wantedIds).toContain("new-game");
  });

  it("最近打开重复更新置顶、最多 50 项，不改变想玩", () => {
    expect(RECENT_LIMIT).toBe(50);
    const original: PersonalLibrary = {
      version: 1,
      wantedIds: ["unlisted-project"],
      recent: Array.from({ length: RECENT_LIMIT }, (_, index) => ({
        projectId: `game-${index}`, lastOpenedAt: 1000 - index,
      })),
    };
    const reopened = recordRecentProject(original, "game-49", 2000);
    expect(reopened.recent).toHaveLength(RECENT_LIMIT);
    expect(reopened.recent[0]).toEqual({ projectId: "game-49", lastOpenedAt: 2000 });
    expect(reopened.recent.filter((entry) => entry.projectId === "game-49")).toHaveLength(1);
    const added = recordRecentProject(reopened, "new-game", 3000);
    expect(added.recent[0]).toEqual({ projectId: "new-game", lastOpenedAt: 3000 });
    expect(added.recent).toHaveLength(RECENT_LIMIT);
    expect(added.recent.some((entry) => entry.projectId === "game-48")).toBe(false);
    expect(added.wantedIds).toEqual(["unlisted-project"]);
    expect(original.recent[0]?.lastOpenedAt).toBe(1000);
  });
});

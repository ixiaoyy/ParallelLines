import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { SpaceJournalCreatePayload, SpaceJournalItem, SpaceLedgerCreatePayload, SpaceLedgerItem, SpaceSetting } from "./model";

const client = vi.hoisted(() => {
  class ApiError extends Error {
    constructor(public code: string, message: string, public details: Record<string, unknown> = {}, public status = 0) {
      super(message);
    }
  }
  return { ApiError, apiRequest: vi.fn(), getAccessToken: vi.fn<() => string | null>(), hasAccessToken: vi.fn() };
});
vi.mock("@/shared/api/client", () => client);

const KEY = "parallellines.space.local_v1";
const NOW = "2026-11-17T04:00:00.000Z";
const PAYLOAD: SpaceJournalCreatePayload = {
  entry_date: "2026-11-17", title: "本人手账", content: "只用于隔离测试的输入",
  mood: "calm", weather: "cloudy", location: "", visibility: "private", card_theme: "paper",
  tags: ["记录"], media_urls: [], checklist: [], unlock_at: "2026-12-01",
};

/** 每例使用独立的内存值，精确检查原始快照及实际写入次数。 */
function memoryStorage() {
  const values = new Map<string, string>();
  return {
    values,
    getItem: vi.fn((key: string) => values.get(key) ?? null),
    setItem: vi.fn((key: string, value: string) => { values.set(key, value); }),
  };
}

/** 构造完整旧记录；固定测试 ID 与金额不进入运行时默认数据。 */
function journal(id = "local-journal-real-1"): SpaceJournalItem {
  return {
    ...PAYLOAD, id, user_id: "local", title: PAYLOAD.title!, location: "", is_pinned: false,
    likes_count: 0, ledger_snapshot: null, created_at: NOW, updated_at: NOW, is_locked: true,
  };
}

function ledger(id = "local-ledger-real-1"): SpaceLedgerItem {
  return {
    id, user_id: "local", entry_date: "2026-11-17", kind: "expense", amount_cents: 1234,
    category: "dining", note: "测试餐费", payment_method: "wechat", created_at: NOW, updated_at: NOW,
  };
}

function store(): { settings: SpaceSetting; journals: SpaceJournalItem[]; ledgers: SpaceLedgerItem[] } {
  return {
    settings: { user_id: "local", space_title: "原空间", space_subtitle: "原签名", cover_preset: "paper", monthly_budget_cents: 300000 },
    journals: [journal()], ledgers: [ledger()],
  };
}

let storage = memoryStorage();
let api: typeof import("./api");

beforeEach(async () => {
  vi.resetModules();
  vi.clearAllMocks();
  vi.useFakeTimers({ toFake: ["Date"] });
  vi.setSystemTime(new Date(NOW));
  storage = memoryStorage();
  vi.stubGlobal("window", { localStorage: storage });
  client.getAccessToken.mockReturnValue(null);
  client.hasAccessToken.mockReturnValue(false);
  api = await import("./api");
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe("本机保存的真实失败边界", () => {
  it("全新存储返回空记录和零预算，不提前填充或写入", async () => {
    const workspace = await api.fetchMySpaceWorkspace("2026-11");
    expect(workspace.settings.monthly_budget_cents).toBe(0);
    expect(workspace.journals).toEqual([]);
    expect(workspace.ledger_entries).toEqual([]);
    expect(api.getPendingLocalSpaceSummary().totalCount).toBe(0);
    expect(storage.setItem).not.toHaveBeenCalled();
  });

  it.each(["", "not-json", "null", "[]", '{"version":2}', '{"journals":{}}', '{"journals":[null]}', '{"ledgers":[{"id":"real"}]}'])
  ("坏数据不退空，也不覆盖原值：%s", async (raw) => {
    storage.values.set(KEY, raw);
    await expect(api.fetchMySpaceWorkspace()).rejects.toMatchObject({ reason: "invalid" });
    await expect(api.createSpaceJournal(PAYLOAD)).rejects.toMatchObject({ reason: "invalid" });
    expect(() => api.getPendingLocalSpaceSummary()).toThrow(api.SpaceLocalStorageError);
    expect(storage.values.get(KEY)).toBe(raw);
    expect(storage.setItem).not.toHaveBeenCalled();
  });

  it("读取权限失败抛明确错误，不转成空空间或新写入", async () => {
    storage.getItem.mockImplementation(() => { throw new Error("denied"); });
    await expect(api.createSpaceJournal(PAYLOAD)).rejects.toMatchObject({ reason: "read" });
    expect(storage.setItem).not.toHaveBeenCalled();
  });

  it("写入失败时创建、编辑和删除均拒绝成功，原始快照不变", async () => {
    const original = JSON.stringify(store());
    storage.values.set(KEY, original);
    storage.setItem.mockImplementation(() => { throw new Error("quota"); });
    await expect(api.createSpaceJournal(PAYLOAD)).rejects.toMatchObject({ reason: "write" });
    await expect(api.updateSpaceJournal(journal().id, { content: "编辑内容" })).rejects.toMatchObject({ reason: "write" });
    await expect(api.deleteSpaceJournal(journal().id)).rejects.toMatchObject({ reason: "write" });
    await expect(api.deleteSpaceLedgerEntry(ledger().id)).rejects.toMatchObject({ reason: "write" });
    expect(storage.values.get(KEY)).toBe(original);
  });

  it("只排除既有固定旧示例ID；真实同名记录、3000预算及扩展字段完整保留", async () => {
    const original = store();
    const raw = { ...original, extra_root: { preserved: true }, settings: { ...original.settings, extra_setting: "保留" }, journals: [
      { ...journal(), title: "2026-11 月度生活账单小结", extra_record: [1, 2] },
      { id: "local-journal-welcome" },
    ] };
    storage.values.set(KEY, JSON.stringify(raw));
    await api.updateMySpaceSettings({ ...original.settings, space_title: "只改名称" });
    const saved = JSON.parse(storage.values.get(KEY)!);
    expect(saved.extra_root).toEqual(raw.extra_root);
    expect(saved.settings).toMatchObject({ monthly_budget_cents: 300000, extra_setting: "保留", space_title: "只改名称" });
    expect(saved.journals).toEqual([raw.journals[0]]);
    expect(saved.ledgers).toEqual(original.ledgers);
  });

  it("编辑只改请求字段并正确保留或取消拆封日期", async () => {
    const original = store();
    storage.values.set(KEY, JSON.stringify(original));
    const updated = await api.updateSpaceJournal(journal().id, { content: "新正文" });
    expect(updated).toMatchObject({ content: "新正文", mood: "calm", weather: "cloudy", unlock_at: "2026-12-01", is_locked: true });
    const unlocked = await api.updateSpaceJournal(journal().id, { unlock_at: null });
    expect(unlocked).toMatchObject({ unlock_at: null, is_locked: false });
    expect(JSON.parse(storage.values.get(KEY)!).ledgers).toEqual(original.ledgers);
  });
});

describe("云端保存30秒边界", () => {
  const settingsPayload: Omit<SpaceSetting, "user_id"> = {
    space_title: "本人空间", space_subtitle: "", cover_preset: "paper", monthly_budget_cents: 0,
  };
  const ledgerPayload: SpaceLedgerCreatePayload = {
    entry_date: "2026-11-17", kind: "expense", amount_cents: 1234,
    category: "dining", note: "测试餐费", payment_method: "wechat",
  };
  const cases = [
    { label: "新建手账", path: "/space/journals", method: "POST", payload: PAYLOAD, result: journal("cloud-1"), save: () => api.createSpaceJournal(PAYLOAD) },
    { label: "编辑手账", path: "/space/journals/cloud-1", method: "PATCH", payload: { content: "修改正文" }, result: { ...journal("cloud-1"), content: "修改正文" }, save: () => api.updateSpaceJournal("cloud-1", { content: "修改正文" }) },
    { label: "记账", path: "/space/ledger", method: "POST", payload: ledgerPayload, result: ledger("cloud-2"), save: () => api.createSpaceLedgerEntry(ledgerPayload) },
    { label: "空间设置", path: "/space/settings", method: "PUT", payload: settingsPayload, result: { ...settingsPayload, user_id: "cloud-user" }, save: () => api.updateMySpaceSettings(settingsPayload) },
  ];

  beforeEach(() => {
    client.hasAccessToken.mockReturnValue(true);
    vi.useFakeTimers();
  });

  it.each(cases)("$label 正常成功结果原样返回，并清理总时限", async (entry) => {
    client.apiRequest.mockResolvedValue(entry.result);
    expect(await entry.save()).toBe(entry.result);
    expect(client.apiRequest).toHaveBeenCalledTimes(1);
    const [path, init] = client.apiRequest.mock.calls[0]!;
    expect(path).toBe(entry.path);
    expect(init.method).toBe(entry.method);
    expect(JSON.parse(init.body)).toEqual(entry.payload);
    expect(init.signal).toBeInstanceOf(AbortSignal);
    await vi.advanceTimersByTimeAsync(30_001);
    expect(init.signal.aborted).toBe(false);
    expect(storage.setItem).not.toHaveBeenCalled();
  });

  it.each(cases)("$label 挂起30秒时结果明确未确认，不自动重发", async (entry) => {
    // 请求替身故意不响应 AbortSignal，覆盖共享鉴权刷新未接收此信号时的总等待边界。
    client.apiRequest.mockImplementation(() => new Promise(() => {}));
    const pending = entry.save();
    const assertion = expect(pending).rejects.toMatchObject({
      code: "space_save_outcome_unconfirmed", status: 0,
      message: expect.stringContaining("保留当前输入，先核对云端记录"),
    });
    await vi.advanceTimersByTimeAsync(30_000);
    await assertion;
    expect(client.apiRequest).toHaveBeenCalledTimes(1);
    expect(client.apiRequest.mock.calls[0]![1].signal.aborted).toBe(true);
    expect(storage.setItem).not.toHaveBeenCalled();
  });
});

describe("本机到云端同步的确认与恢复", () => {
  beforeEach(() => {
    client.getAccessToken.mockReturnValue("test-only-token");
    client.hasAccessToken.mockReturnValue(true);
    client.apiRequest.mockResolvedValue({});
  });

  it("每条确认后立刻保存剩余队列，4xx中断后重试不重发已成功记录", async () => {
    const original = { ...store(), journals: [journal("local-real-a"), journal("local-real-b")] };
    storage.values.set(KEY, JSON.stringify(original));
    client.apiRequest.mockResolvedValueOnce({}).mockRejectedValueOnce(new client.ApiError("invalid", "请修正记录", {}, 422));
    await expect(api.syncLocalSpaceToCloud()).rejects.toMatchObject({ journalsSynced: 1, ledgersSynced: 0, pendingJournalCount: 1, pendingLedgerCount: 1, needsCloudReview: false });
    const saved = JSON.parse(storage.values.get(KEY)!);
    expect(saved.journals).toEqual([original.journals[1]]);
    expect(saved.ledgers).toEqual(original.ledgers);
    const firstPayload = JSON.parse(client.apiRequest.mock.calls[0]![1]!.body);
    expect(firstPayload.unlock_at).toBe("2026-12-01");
    expect(firstPayload.visibility).toBe("private");
    client.apiRequest.mockResolvedValue({});
    expect(await api.syncLocalSpaceToCloud()).toEqual({ journalsSynced: 1, ledgersSynced: 1 });
    expect(client.apiRequest).toHaveBeenCalledTimes(4);
    expect(JSON.parse(storage.values.get(KEY)!)).toEqual({ ...original, journals: [], ledgers: [] });
  });

  it("云端成功但写进度失败时保留本机原记录，并阻止当前页直接再次发送", async () => {
    const original = JSON.stringify(store());
    storage.values.set(KEY, original);
    storage.setItem.mockImplementation(() => { throw new Error("quota"); });
    await expect(api.syncLocalSpaceToCloud()).rejects.toMatchObject({ journalsSynced: 1, pendingJournalCount: 1, needsCloudReview: true });
    await expect(api.syncLocalSpaceToCloud()).rejects.toMatchObject({ needsCloudReview: true });
    expect(client.apiRequest).toHaveBeenCalledTimes(1);
    expect(storage.values.get(KEY)).toBe(original);
  });

  it.each([new TypeError("network"), new client.ApiError("server_error", "服务器异常", {}, 500)])
  ("不确定的网络或服务端结果不被当作安全重试：%s", async (error) => {
    const original = JSON.stringify(store());
    storage.values.set(KEY, original);
    client.apiRequest.mockRejectedValue(error);
    await expect(api.syncLocalSpaceToCloud()).rejects.toMatchObject({ journalsSynced: 0, needsCloudReview: true });
    await expect(api.syncLocalSpaceToCloud()).rejects.toMatchObject({ needsCloudReview: true });
    expect(client.apiRequest).toHaveBeenCalledTimes(1);
    expect(storage.values.get(KEY)).toBe(original);
  });

  it("请求30秒未完成会中止并要求核对云端，不自动重新POST", async () => {
    vi.useFakeTimers();
    storage.values.set(KEY, JSON.stringify(store()));
    client.apiRequest.mockImplementation((_path: string, init: RequestInit) => new Promise((_resolve, reject) => {
      init.signal!.addEventListener("abort", () => reject(new DOMException("aborted", "AbortError")));
    }));
    const pending = api.syncLocalSpaceToCloud();
    const assertion = expect(pending).rejects.toMatchObject({ needsCloudReview: true });
    await vi.advanceTimersByTimeAsync(30_000);
    await assertion;
    expect(client.apiRequest).toHaveBeenCalledTimes(1);
  });

  it("单批在换号或令牌更新后暂停，不把剩余记录发给新账号", async () => {
    const original = store();
    storage.values.set(KEY, JSON.stringify(original));
    client.apiRequest.mockImplementationOnce(() => {
      client.getAccessToken.mockReturnValue("different-test-token");
      return Promise.resolve({});
    });
    await expect(api.syncLocalSpaceToCloud()).rejects.toMatchObject({ journalsSynced: 1, ledgersSynced: 0, needsCloudReview: true });
    expect(client.apiRequest).toHaveBeenCalledTimes(1);
    expect(JSON.parse(storage.values.get(KEY)!).ledgers).toEqual(original.ledgers);
  });

  it.each(["journal", "ledger"])("未知旧状态不被默认替换或删除：%s", async (kind) => {
    const original = store();
    if (kind === "journal") original.journals[0]!.mood = "custom-old-mood";
    else {
      original.journals = [];
      original.ledgers[0]!.category = "custom-old-category";
    }
    const raw = JSON.stringify(original);
    storage.values.set(KEY, raw);
    await expect(api.syncLocalSpaceToCloud()).rejects.toMatchObject({ needsCloudReview: false });
    expect(client.apiRequest).not.toHaveBeenCalled();
    expect(storage.values.get(KEY)).toBe(raw);
  });

  it("旧blob配图阻止该条同步，不能静默去图后移除本机原记录", async () => {
    const original = store();
    original.journals[0]!.media_urls = ["/uploads/101/content", "blob:local-preview-only"];
    const raw = JSON.stringify(original);
    storage.values.set(KEY, raw);
    await expect(api.syncLocalSpaceToCloud()).rejects.toMatchObject({ needsCloudReview: false, pendingJournalCount: 1 });
    await expect(api.syncLocalSpaceToCloud()).rejects.toThrow("重新上传配图");
    expect(client.apiRequest).not.toHaveBeenCalled();
    expect(storage.values.get(KEY)).toBe(raw);
  });

  it("同步过程中被修改的原记录不能被已发出的旧版本移除", async () => {
    const original = store();
    storage.values.set(KEY, JSON.stringify(original));
    const edited = { ...journal(), content: "同步期间修改", updated_at: "2026-11-17T04:01:00.000Z" };
    client.apiRequest.mockImplementationOnce(() => {
      storage.values.set(KEY, JSON.stringify({ ...original, journals: [edited] }));
      return Promise.resolve({});
    });
    await expect(api.syncLocalSpaceToCloud()).rejects.toMatchObject({ journalsSynced: 1, needsCloudReview: true });
    expect(JSON.parse(storage.values.get(KEY)!).journals).toEqual([edited]);
    expect(client.apiRequest).toHaveBeenCalledTimes(1);
  });

  it("同步期间新增的本机记录和预算设置不会被旧快照覆盖", async () => {
    const original = store();
    storage.values.set(KEY, JSON.stringify(original));
    const added = journal("local-real-added");
    client.apiRequest.mockImplementationOnce(() => {
      storage.values.set(KEY, JSON.stringify({ ...original, settings: { ...original.settings, monthly_budget_cents: 123456 }, journals: [...original.journals, added] }));
      return Promise.resolve({});
    });
    expect(await api.syncLocalSpaceToCloud()).toEqual({ journalsSynced: 1, ledgersSynced: 1 });
    const saved = JSON.parse(storage.values.get(KEY)!);
    expect(saved.journals).toEqual([added]);
    expect(saved.settings.monthly_budget_cents).toBe(123456);
  });

  it("同页重复发起同步不会并发提交同一队列", async () => {
    storage.values.set(KEY, JSON.stringify({ ...store(), ledgers: [] }));
    let complete!: () => void;
    client.apiRequest.mockImplementationOnce(() => new Promise<void>((resolve) => { complete = resolve; }));
    const first = api.syncLocalSpaceToCloud();
    await expect(api.syncLocalSpaceToCloud()).rejects.toThrow("正在同步");
    complete();
    expect(await first).toEqual({ journalsSynced: 1, ledgersSynced: 0 });
    expect(client.apiRequest).toHaveBeenCalledTimes(1);
  });
});

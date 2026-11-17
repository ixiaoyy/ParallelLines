import { uiText } from "@/shared/i18n/locale";
import { ApiError, apiRequest, getAccessToken, hasAccessToken } from "@/shared/api/client";

import {
  currentMonthString,
  JOURNAL_CARD_THEMES,
  JOURNAL_MOODS,
  JOURNAL_WEATHERS,
  LEDGER_CATEGORIES,
  LEDGER_PAYMENT_METHODS,
  todayDateString,
  type SpaceJournalCreatePayload,
  type SpaceJournalItem,
  type SpaceJournalUpdatePayload,
  type SpaceLedgerCategoryBreakdown,
  type SpaceLedgerCreatePayload,
  type SpaceLedgerItem,
  type SpaceLedgerMonthlySummary,
  type SpaceMyWorkspace,
  type SpacePublicProfile,
  type SpaceReactionKind,
  type SpaceSetting,
} from "./model";

const LOCAL_STORAGE_KEY = "parallellines.space.local_v1";
const LEGACY_SEED_JOURNAL_IDS = new Set([
  "local-journal-1",
  "local-journal-2",
  "local-journal-welcome",
]);
const LEGACY_SEED_LEDGER_IDS = new Set([
  "local-ledger-1",
  "local-ledger-2",
  "local-ledger-3",
  "local-ledger-demo-1",
]);

interface LocalSpaceStore {
  [key: string]: unknown;
  settings: SpaceSetting;
  journals: SpaceJournalItem[];
  ledgers: SpaceLedgerItem[];
}

/** 本机记录读取、格式或写入失败；调用方应保留输入并直接展示 message。 */
export class SpaceLocalStorageError extends Error {
  constructor(public readonly reason: "read" | "invalid" | "write", message: string) {
    super(message);
    this.name = "SpaceLocalStorageError";
  }
}

/** 同步中断时返回已确认完成及待处理数量；needsCloudReview 表示不能直接重发。 */
export class SpaceLocalSyncError extends Error {
  constructor(
    message: string,
    public readonly journalsSynced: number,
    public readonly ledgersSynced: number,
    public readonly pendingJournalCount: number,
    public readonly pendingLedgerCount: number,
    public readonly needsCloudReview: boolean,
  ) {
    super(message);
    this.name = "SpaceLocalSyncError";
  }
}

type StoredLocalSpace = {
  [key: string]: unknown;
  settings?: Partial<SpaceSetting>;
  journals?: SpaceJournalItem[];
  ledgers?: SpaceLedgerItem[];
};

let syncingLocalSpace = false;
let uncertainSyncProgress: SpaceLocalSyncError | null = null;

/** JSON 对象边界；数组和 null 不能当作存储快照或记录。 */
function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

/** 从现有选项表确认请求枚举；旧记录的未知值保留在本机，不擅自替换成默认值。 */
function isOptionKey<Key extends string>(value: string, options: ReadonlyArray<{ key: Key }>): value is Key {
  return options.some((option) => option.key === value);
}

/** 校验持久化记录实际使用的字段；未知扩展字段保留，不按内容或金额删除记录。 */
function isLocalJournal(value: unknown): value is SpaceJournalItem {
  if (!isRecord(value)) return false;
  const stringFields = ["id", "user_id", "entry_date", "title", "content", "mood", "weather", "location", "visibility", "card_theme", "created_at", "updated_at"];
  return stringFields.every((key) => typeof value[key] === "string")
    && typeof value.is_pinned === "boolean"
    && typeof value.likes_count === "number" && Number.isFinite(value.likes_count)
    && Array.isArray(value.tags) && value.tags.every((tag) => typeof tag === "string")
    && Array.isArray(value.media_urls) && value.media_urls.every((url) => typeof url === "string")
    && Array.isArray(value.checklist) && value.checklist.every((item) => isRecord(item)
      && typeof item.id === "string" && typeof item.text === "string" && typeof item.done === "boolean")
    && (value.ledger_snapshot === undefined || value.ledger_snapshot === null || isRecord(value.ledger_snapshot))
    && (value.reactions === undefined || (isRecord(value.reactions)
      && Object.values(value.reactions).every((count) => typeof count === "number" && Number.isFinite(count))))
    && (value.unlock_at === undefined || value.unlock_at === null || typeof value.unlock_at === "string")
    && (value.is_locked === undefined || typeof value.is_locked === "boolean");
}

/** 记账原值必须能安全读取和汇总；校验失败时保留整个原始存储，不丢弃单条记录。 */
function isLocalLedger(value: unknown): value is SpaceLedgerItem {
  if (!isRecord(value)) return false;
  return ["id", "user_id", "entry_date", "kind", "category", "note", "payment_method", "created_at", "updated_at"]
    .every((key) => typeof value[key] === "string")
    && typeof value.amount_cents === "number" && Number.isSafeInteger(value.amount_cents)
    && value.amount_cents > 0;
}

/** 接受旧快照缺省的区段，拒绝错类型区段；后续写入保留未知字段。 */
function isStoredLocalSpace(value: unknown): value is StoredLocalSpace {
  if (!isRecord(value)) return false;
  if (value.version !== undefined && value.version !== 1) return false;
  if (value.settings !== undefined) {
    if (!isRecord(value.settings)) return false;
    const setting = value.settings;
    if (!["user_id", "space_title", "space_subtitle", "cover_preset", "current_status"]
      .every((key) => setting[key] === undefined || typeof setting[key] === "string")) return false;
    if (setting.monthly_budget_cents !== undefined
      && (typeof setting.monthly_budget_cents !== "number" || !Number.isSafeInteger(setting.monthly_budget_cents)
        || setting.monthly_budget_cents < 0)) return false;
  }
  return (value.journals === undefined || (Array.isArray(value.journals) && value.journals.every(isLocalJournal)))
    && (value.ledgers === undefined || (Array.isArray(value.ledgers) && value.ledgers.every(isLocalLedger)));
}

function buildDefaultLocalStore(): LocalSpaceStore {
  return {
    settings: {
      user_id: "local",
      space_title: "",
      space_subtitle: "",
      cover_preset: "aurora",
      // 未主动设置预算时保持 0，不用示例金额填充个人账本。
      monthly_budget_cents: 0,
    },
    journals: [],
    ledgers: [],
  };
}

function readLocalStore(): LocalSpaceStore {
  if (typeof window === "undefined") {
    return buildDefaultLocalStore();
  }
  let raw: string | null;
  try {
    raw = window.localStorage.getItem(LOCAL_STORAGE_KEY);
  } catch {
    throw new SpaceLocalStorageError("read", uiText("无法读取本机记录，请检查浏览器存储权限后重试；原数据未改动"));
  }
  if (raw === null) return buildDefaultLocalStore();
  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch {
    throw new SpaceLocalStorageError("invalid", uiText("本机记录格式异常，已停止写入以保护原数据；请先备份并检查原记录"));
  }
  if (!isRecord(parsed)) {
    throw new SpaceLocalStorageError("invalid", uiText("本机记录格式异常，已停止写入以保护原数据；请先备份并检查原记录"));
  }
  // 旧示例仅按既有固定 ID 排除；其余坏记录阻止写入，不能被当空数据覆盖。
  const snapshot: Record<string, unknown> = { ...parsed };
  if (Array.isArray(snapshot.journals)) {
    snapshot.journals = snapshot.journals.filter((item) => !isRecord(item)
      || typeof item.id !== "string" || !LEGACY_SEED_JOURNAL_IDS.has(item.id));
  }
  if (Array.isArray(snapshot.ledgers)) {
    snapshot.ledgers = snapshot.ledgers.filter((item) => !isRecord(item)
      || typeof item.id !== "string" || !LEGACY_SEED_LEDGER_IDS.has(item.id));
  }
  if (!isStoredLocalSpace(snapshot)) {
    throw new SpaceLocalStorageError("invalid", uiText("本机记录格式异常，已停止写入以保护原数据；请先备份并检查原记录"));
  }
  const fallback = buildDefaultLocalStore();
  return {
    ...snapshot,
    settings: { ...fallback.settings, ...snapshot.settings },
    journals: snapshot.journals ?? [],
    ledgers: snapshot.ledgers ?? [],
  };
}

function writeLocalStore(store: LocalSpaceStore): void {
  if (typeof window === "undefined") {
    throw new SpaceLocalStorageError("write", uiText("当前环境不能保存到本机，请保留内容后在浏览器中重试"));
  }
  try {
    window.localStorage.setItem(LOCAL_STORAGE_KEY, JSON.stringify(store));
  } catch {
    throw new SpaceLocalStorageError("write", uiText("未能保存到本机，请保留当前内容并检查浏览器存储空间或权限后重试"));
  }
}

export function computeMonthlySummaryFromLedgers(
  ledgers: SpaceLedgerItem[],
  month: string,
  monthlyBudgetCents: number,
): SpaceLedgerMonthlySummary {
  const prefix = `${month}-`;
  const monthItems = ledgers.filter((item) => item.entry_date.startsWith(prefix));
  let totalExpense = 0;
  let totalIncome = 0;
  const catTotals = new Map<string, { amount: number; count: number }>();

  for (const item of monthItems) {
    if (item.kind === "income") {
      totalIncome += item.amount_cents;
    } else {
      totalExpense += item.amount_cents;
      const prev = catTotals.get(item.category) ?? { amount: 0, count: 0 };
      prev.amount += item.amount_cents;
      prev.count += 1;
      catTotals.set(item.category, prev);
    }
  }

  const breakdown: SpaceLedgerCategoryBreakdown[] = Array.from(catTotals.entries())
    .sort((a, b) => b[1].amount - a[1].amount)
    .map(([category, info]) => ({
      category,
      amount_cents: info.amount,
      count: info.count,
      ratio_percent:
        totalExpense > 0 ? Math.max(1, Math.round((info.amount * 100) / totalExpense)) : 0,
    }));

  return {
    month,
    total_expense_cents: totalExpense,
    total_income_cents: totalIncome,
    monthly_budget_cents: monthlyBudgetCents,
    entry_count: monthItems.length,
    category_breakdown: breakdown,
  };
}

function buildWorkspaceFromLocal(month: string): SpaceMyWorkspace {
  const store = readLocalStore();
  const sortedJournals = [...store.journals].sort((a, b) => {
    if (a.is_pinned !== b.is_pinned) return a.is_pinned ? -1 : 1;
    if (a.entry_date !== b.entry_date) return b.entry_date.localeCompare(a.entry_date);
    return b.created_at.localeCompare(a.created_at);
  });
  const sortedLedgers = [...store.ledgers].sort((a, b) => {
    if (a.entry_date !== b.entry_date) return b.entry_date.localeCompare(a.entry_date);
    return b.created_at.localeCompare(a.created_at);
  });
  return {
    settings: store.settings,
    journals: sortedJournals,
    ledger_entries: sortedLedgers,
    ledger_summary: computeMonthlySummaryFromLedgers(
      sortedLedgers,
      month,
      store.settings.monthly_budget_cents,
    ),
  };
}

export interface LocalSpacePendingSummary {
  journalCount: number;
  ledgerCount: number;
  totalCount: number;
}

export function getPendingLocalSpaceSummary(): LocalSpacePendingSummary {
  if (typeof window === "undefined") {
    return { journalCount: 0, ledgerCount: 0, totalCount: 0 };
  }
  const store = readLocalStore();
  return {
    journalCount: store.journals.length,
    ledgerCount: store.ledgers.length,
    totalCount: store.journals.length + store.ledgers.length,
  };
}

/** 个人记录保存最多等待 30 秒；超时结果未确认，调用方保留输入并先核对云端，不自动重试。 */
async function requestSpaceSave<Result>(
  path: string,
  payload: SpaceJournalCreatePayload | SpaceJournalUpdatePayload | SpaceLedgerCreatePayload | Omit<SpaceSetting, "user_id">,
  method: "POST" | "PUT" | "PATCH" = "POST",
): Promise<Result> {
  const controller = new AbortController();
  let timeout: ReturnType<typeof setTimeout>;
  const deadline = new Promise<never>((_resolve, reject) => {
    timeout = setTimeout(() => {
      reject(new ApiError("space_save_outcome_unconfirmed", uiText("保存结果尚未确认，请保留当前输入，先核对云端记录，确认未保存后再重试，避免重复保存"), {}, 0));
      controller.abort();
    }, 30_000);
  });
  try {
    // 同时约束鉴权刷新的总等待时间；共享请求内部的刷新不一定接收此信号。
    return await Promise.race([deadline, apiRequest<Result>(path, {
      method, body: JSON.stringify(payload), signal: controller.signal,
    })]);
  } finally {
    clearTimeout(timeout!);
  }
}

/** 单条云端确认成功后更新最新本机快照；保留同步期间新增的记录和装扮设置。 */
function checkpointLocalSyncEntry(
  kind: "journals" | "ledgers",
  item: SpaceJournalItem | SpaceLedgerItem,
): LocalSpacePendingSummary {
  const latest = readLocalStore();
  const current = latest[kind].find((entry) => entry.id === item.id);
  if (!current || current.updated_at !== item.updated_at) {
    throw new SpaceLocalStorageError("write", uiText("同步期间本机记录发生改动，已暂停；请先核对云端与本机记录"));
  }
  const next = kind === "journals"
    ? { ...latest, journals: latest.journals.filter((entry) => entry.id !== item.id) }
    : { ...latest, ledgers: latest.ledgers.filter((entry) => entry.id !== item.id) };
  writeLocalStore(next);
  return {
    journalCount: next.journals.length,
    ledgerCount: next.ledgers.length,
    totalCount: next.journals.length + next.ledgers.length,
  };
}

export async function syncLocalSpaceToCloud(): Promise<{
  journalsSynced: number;
  ledgersSynced: number;
}> {
  const syncToken = getAccessToken();
  if (!syncToken) {
    throw new Error(uiText("请先登录后再同步到云端"));
  }
  if (uncertainSyncProgress) throw uncertainSyncProgress;
  if (syncingLocalSpace) throw new Error(uiText("正在同步本机记录，请等待本次同步完成"));
  const store = readLocalStore();
  const pendingJournals = [...store.journals];
  const pendingLedgers = [...store.ledgers];

  let journalsSynced = 0;
  let ledgersSynced = 0;
  let savedPending: LocalSpacePendingSummary = {
    journalCount: pendingJournals.length,
    ledgerCount: pendingLedgers.length,
    totalCount: pendingJournals.length + pendingLedgers.length,
  };
  let awaitingLocalCheckpoint = false;
  syncingLocalSpace = true;

  try {
    // 固定本批登录边界；换号或令牌更新后暂停，不能让后续记录进入另一个账号。
    for (const item of pendingJournals) {
      if (getAccessToken() !== syncToken) throw new ApiError("identity_changed", uiText("登录状态已变更，请重新核对同步目标账号"), {}, 409);
      if (!(item.mood === "" || isOptionKey(item.mood, JOURNAL_MOODS))
        || !(item.weather === "" || isOptionKey(item.weather, JOURNAL_WEATHERS))
        || !isOptionKey(item.card_theme, JOURNAL_CARD_THEMES)
        || (item.visibility !== "public" && item.visibility !== "friends" && item.visibility !== "private")) {
        throw new ApiError("invalid_local_record", uiText("手账包含云端不支持的状态，请先编辑此记录；原记录仍保留在本机"), {}, 422);
      }
      // 旧本地预览图不具备云端可用地址，不能丢掉图片后宣称整条同步成功。
      if (item.media_urls.some((url) => url.startsWith("blob:"))) {
        throw new ApiError("local_image_upload_required", uiText("手账含有仅当前浏览器可用的配图，请先重新上传配图再同步；原记录仍保留在本机"), {}, 422);
      }
      await requestSpaceSave<SpaceJournalItem>("/space/journals", {
        entry_date: item.entry_date,
        title: item.title,
        content: item.content,
        mood: item.mood,
        weather: item.weather,
        location: item.location,
        visibility: item.visibility,
        is_pinned: item.is_pinned,
        card_theme: item.card_theme,
        tags: item.tags,
        media_urls: item.media_urls,
        checklist: item.checklist,
        ledger_snapshot: item.ledger_snapshot ?? undefined,
        unlock_at: item.unlock_at ?? null,
      });
      journalsSynced += 1;
      awaitingLocalCheckpoint = true;
      savedPending = checkpointLocalSyncEntry("journals", item);
      awaitingLocalCheckpoint = false;
    }

    for (const item of pendingLedgers) {
      if (getAccessToken() !== syncToken) throw new ApiError("identity_changed", uiText("登录状态已变更，请重新核对同步目标账号"), {}, 409);
      if ((item.kind !== "expense" && item.kind !== "income")
        || !isOptionKey(item.category, LEDGER_CATEGORIES)
        || !isOptionKey(item.payment_method, LEDGER_PAYMENT_METHODS)) {
        throw new ApiError("invalid_local_record", uiText("账单包含云端不支持的分类或支付方式，请先核对；原记录仍保留在本机"), {}, 422);
      }
      await requestSpaceSave<SpaceLedgerItem>("/space/ledger", {
        entry_date: item.entry_date,
        kind: item.kind,
        amount_cents: item.amount_cents,
        category: item.category,
        note: item.note,
        payment_method: item.payment_method,
      });
      ledgersSynced += 1;
      awaitingLocalCheckpoint = true;
      savedPending = checkpointLocalSyncEntry("ledgers", item);
      awaitingLocalCheckpoint = false;
    }
    return { journalsSynced, ledgersSynced };
  } catch (error) {
    // 网络、服务端异常或写进度失败时可能已有云端副作用，停止自动重发并保留原记录。
    const needsCloudReview = awaitingLocalCheckpoint || !(error instanceof ApiError)
      || error.status === 0 || error.status >= 500 || error.code === "identity_changed";
    const progress = uiText("已确认同步 {journals} 篇手账、{ledgers} 笔账单；本机仍有 {pendingJournals} 篇手账、{pendingLedgers} 笔账单待处理。", { journals: journalsSynced, ledgers: ledgersSynced, pendingJournals: savedPending.journalCount, pendingLedgers: savedPending.ledgerCount });
    const reason = needsCloudReview
      ? uiText("本次结果或本机同步进度未能确认，请先核对云端和本机记录，不要直接重试；刷新页面也不能消除重复风险。")
      : uiText("同步已停止，未完成记录仍保留在本机。{reason}", { reason: error instanceof Error ? uiText(error.message) : uiText("请检查后重试") });
    const failure = new SpaceLocalSyncError(
      progress + reason, journalsSynced, ledgersSynced,
      savedPending.journalCount, savedPending.ledgerCount, needsCloudReview,
    );
    if (needsCloudReview) uncertainSyncProgress = failure;
    throw failure;
  } finally {
    syncingLocalSpace = false;
  }
}

export async function fetchMySpaceWorkspace(month = currentMonthString()): Promise<SpaceMyWorkspace> {
  if (!hasAccessToken()) {
    return buildWorkspaceFromLocal(month);
  }
  const query = month ? `?month=${encodeURIComponent(month)}` : "";
  return apiRequest<SpaceMyWorkspace>(`/space/me${query}`);
}

export async function updateMySpaceSettings(
  payload: Omit<SpaceSetting, "user_id">,
): Promise<SpaceSetting> {
  if (hasAccessToken()) {
    return requestSpaceSave<SpaceSetting>("/space/settings", payload, "PUT");
  }
  const store = readLocalStore();
  store.settings = {
    ...store.settings,
    ...payload,
  };
  writeLocalStore(store);
  return store.settings;
}

export async function createSpaceJournal(
  payload: SpaceJournalCreatePayload,
): Promise<SpaceJournalItem> {
  if (hasAccessToken()) {
    return requestSpaceSave<SpaceJournalItem>("/space/journals", payload);
  }

  const store = readLocalStore();
  const nowIso = new Date().toISOString();
  const created: SpaceJournalItem = {
    id: `local-journal-${Date.now()}`,
    user_id: "local",
    entry_date: payload.entry_date,
    title: payload.title?.trim() ?? "",
    content: payload.content.trim(),
    mood: payload.mood,
    weather: payload.weather,
    location: payload.location?.trim() ?? "",
    visibility: payload.visibility,
    is_pinned: Boolean(payload.is_pinned),
    card_theme: payload.card_theme,
    tags: payload.tags,
    media_urls: payload.media_urls,
    checklist: payload.checklist,
    ledger_snapshot: payload.ledger_snapshot ?? null,
    likes_count: 0,
    reactions: {},
    unlock_at: payload.unlock_at ?? null,
    is_locked: Boolean(payload.unlock_at && payload.unlock_at > todayDateString()),
    created_at: nowIso,
    updated_at: nowIso,
  };
  store.journals.unshift(created);
  writeLocalStore(store);
  return created;
}

export async function updateSpaceJournal(
  entryId: string,
  payload: SpaceJournalUpdatePayload,
): Promise<SpaceJournalItem> {
  if (hasAccessToken() && !entryId.startsWith("local-")) {
    return requestSpaceSave<SpaceJournalItem>(
      `/space/journals/${encodeURIComponent(entryId)}`,
      payload,
      "PATCH",
    );
  }

  const store = readLocalStore();
  const index = store.journals.findIndex((item) => item.id === entryId);
  if (index >= 0) {
    const existing = store.journals[index]!;
    const unlockAt = payload.unlock_at !== undefined ? payload.unlock_at : existing.unlock_at;
    const updated: SpaceJournalItem = {
      ...existing,
      ...payload,
      // 编辑拆封日期后同步本地展示状态，显式 null 仍表示取消定时。
      is_locked: Boolean(unlockAt && unlockAt > todayDateString()),
      updated_at: new Date().toISOString(),
    };
    store.journals[index] = updated;
    writeLocalStore(store);
    return updated;
  }
  throw new Error(uiText("未找到对应的手账记录"));
}

export async function deleteSpaceJournal(entryId: string): Promise<boolean> {
  if (hasAccessToken() && !entryId.startsWith("local-")) {
    return apiRequest<boolean>(`/space/journals/${encodeURIComponent(entryId)}`, {
      method: "DELETE",
    });
  }

  const store = readLocalStore();
  store.journals = store.journals.filter((item) => item.id !== entryId);
  writeLocalStore(store);
  return true;
}

export async function likeSpaceJournal(entryId: string): Promise<SpaceJournalItem> {
  if (!entryId.startsWith("local-")) {
    return apiRequest<SpaceJournalItem>(
      `/space/journals/${encodeURIComponent(entryId)}/like`,
      {
        method: "POST",
      },
    );
  }

  const store = readLocalStore();
  const found = store.journals.find((item) => item.id === entryId);
  if (found) {
    found.likes_count = (found.likes_count || 0) + 1;
    writeLocalStore(store);
    return { ...found };
  }
  throw new Error(uiText("点赞失败"));
}

export async function reactSpaceJournal(
  entryId: string,
  kind: SpaceReactionKind,
): Promise<SpaceJournalItem> {
  if (!entryId.startsWith("local-")) {
    return apiRequest<SpaceJournalItem>(
      `/space/journals/${encodeURIComponent(entryId)}/react`,
      {
        method: "POST",
        body: JSON.stringify({ kind }),
      },
    );
  }

  const store = readLocalStore();
  const found = store.journals.find((item) => item.id === entryId);
  if (found) {
    const reactions = { ...(found.reactions ?? {}) };
    reactions[kind] = (reactions[kind] ?? 0) + 1;
    found.reactions = reactions;
    found.likes_count = (found.likes_count || 0) + 1;
    writeLocalStore(store);
    return { ...found };
  }
  throw new Error(uiText("回应失败"));
}

export async function createSpaceLedgerEntry(
  payload: SpaceLedgerCreatePayload,
): Promise<SpaceLedgerItem> {
  if (hasAccessToken()) {
    return requestSpaceSave<SpaceLedgerItem>("/space/ledger", payload);
  }

  const store = readLocalStore();
  const nowIso = new Date().toISOString();
  const created: SpaceLedgerItem = {
    id: `local-ledger-${Date.now()}`,
    user_id: "local",
    entry_date: payload.entry_date,
    kind: payload.kind,
    amount_cents: payload.amount_cents,
    category: payload.category,
    note: payload.note.trim(),
    payment_method: payload.payment_method,
    created_at: nowIso,
    updated_at: nowIso,
  };
  store.ledgers.unshift(created);
  writeLocalStore(store);
  return created;
}

export async function deleteSpaceLedgerEntry(entryId: string): Promise<boolean> {
  if (hasAccessToken() && !entryId.startsWith("local-")) {
    return apiRequest<boolean>(`/space/ledger/${encodeURIComponent(entryId)}`, {
      method: "DELETE",
    });
  }

  const store = readLocalStore();
  store.ledgers = store.ledgers.filter((item) => item.id !== entryId);
  writeLocalStore(store);
  return true;
}

export async function fetchPublicSpaceFeed(limit = 30): Promise<SpaceJournalItem[]> {
  return apiRequest<SpaceJournalItem[]>(`/space/feed?limit=${limit}`);
}

export async function fetchPublicUserSpace(identifier: string): Promise<SpacePublicProfile> {
  try {
    return await apiRequest<SpacePublicProfile>(
      `/space/users/${encodeURIComponent(identifier)}`,
    );
  } catch {
    // 接口不可用时只返回空空间，绝不把本机手账展示到他人主页。
    return {
      user_id: identifier,
      username: identifier,
      display_name: null,
      avatar_url: null,
      bio: null,
      space_title: "",
      space_subtitle: "",
      cover_preset: "aurora",
      public_journal_count: 0,
      journals: [],
    };
  }
}

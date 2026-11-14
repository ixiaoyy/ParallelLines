import { apiRequest, hasAccessToken } from "@/shared/api/client";

import {
  currentMonthString,
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
  type SpaceSetting,
} from "./model";

const LOCAL_STORAGE_KEY = "parallellines.space.local_v1";

interface LocalSpaceStore {
  settings: SpaceSetting;
  journals: SpaceJournalItem[];
  ledgers: SpaceLedgerItem[];
}

function buildDefaultLocalStore(): LocalSpaceStore {
  const today = todayDateString();
  const nowIso = new Date().toISOString();
  return {
    settings: {
      user_id: "local",
      space_title: "平行线手账本",
      space_subtitle: "把日常的闪念、玩过的游戏与每一笔生活开支，装进属于自己的安静角落。",
      cover_preset: "aurora",
      monthly_budget_cents: 300000,
    },
    journals: [
      {
        id: "local-journal-1",
        user_id: "local",
        entry_date: today,
        title: "今日小记：把生活调成自己喜欢的频道",
        content:
          "在圈子里开辟了一块属于自己的手账角落。不管是随手记下刚通关的小游戏感想、读到的一段好句子，还是整理这个月的日常开销，都可以在这里安静沉淀。",
        mood: "inspired",
        weather: "sunny",
        location: "书桌前",
        visibility: "public",
        is_pinned: true,
        card_theme: "paper",
        tags: ["手账初体验", "日常灵感", "平行线"],
        media_urls: [],
        checklist: [
          { id: "c1", text: "写下第一篇心情日签", done: true },
          { id: "c2", text: "记录今天的一杯咖啡开销", done: true },
          { id: "c3", text: "晚上睡前阅读 30 分钟", done: false },
        ],
        ledger_snapshot: null,
        likes_count: 0,
        created_at: nowIso,
        updated_at: nowIso,
        author: {
          id: "local",
          username: "me",
          display_name: "我的手账本",
          avatar_url: null,
          level: 2,
        },
      },
      {
        id: "local-journal-2",
        user_id: "local",
        entry_date: today,
        title: "",
        content:
          "下午泡了一杯热拿铁，顺手整理了一下这周的小目标。发现把碎片想法写成带贴纸的卡片之后，焦虑感会明显少很多。",
        mood: "cozy",
        weather: "breezy",
        location: "窗边角落",
        visibility: "private",
        is_pinned: false,
        card_theme: "mint",
        tags: ["随手记", "充电时刻"],
        media_urls: [],
        checklist: [],
        ledger_snapshot: {
          single_entry: {
            kind: "expense",
            category: "coffee",
            amount_cents: 2600,
            note: "桂花燕麦拿铁",
          },
        },
        likes_count: 0,
        created_at: nowIso,
        updated_at: nowIso,
        author: {
          id: "local",
          username: "me",
          display_name: "我的手账本",
          avatar_url: null,
          level: 2,
        },
      },
    ],
    ledgers: [
      {
        id: "local-ledger-1",
        user_id: "local",
        entry_date: today,
        kind: "expense",
        amount_cents: 2600,
        category: "coffee",
        note: "下午茶：桂花燕麦拿铁",
        payment_method: "wechat",
        created_at: nowIso,
        updated_at: nowIso,
      },
      {
        id: "local-ledger-2",
        user_id: "local",
        entry_date: today,
        kind: "expense",
        amount_cents: 4200,
        category: "dining",
        note: "晚餐：日式猪排滑蛋饭",
        payment_method: "alipay",
        created_at: nowIso,
        updated_at: nowIso,
      },
      {
        id: "local-ledger-3",
        user_id: "local",
        entry_date: today,
        kind: "expense",
        amount_cents: 6800,
        category: "gaming",
        note: "独立解谜游戏与创意工坊支持",
        payment_method: "wechat",
        created_at: nowIso,
        updated_at: nowIso,
      },
    ],
  };
}

function readLocalStore(): LocalSpaceStore {
  if (typeof window === "undefined") {
    return buildDefaultLocalStore();
  }
  try {
    const raw = window.localStorage.getItem(LOCAL_STORAGE_KEY);
    if (!raw) {
      const seed = buildDefaultLocalStore();
      window.localStorage.setItem(LOCAL_STORAGE_KEY, JSON.stringify(seed));
      return seed;
    }
    const parsed = JSON.parse(raw) as Partial<LocalSpaceStore>;
    const fallback = buildDefaultLocalStore();
    return {
      settings: parsed.settings ?? fallback.settings,
      journals: Array.isArray(parsed.journals) ? parsed.journals : fallback.journals,
      ledgers: Array.isArray(parsed.ledgers) ? parsed.ledgers : fallback.ledgers,
    };
  } catch {
    return buildDefaultLocalStore();
  }
}

function writeLocalStore(store: LocalSpaceStore): void {
  if (typeof window === "undefined") {
    return;
  }
  try {
    window.localStorage.setItem(LOCAL_STORAGE_KEY, JSON.stringify(store));
  } catch {
    // Ignore storage quota errors.
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

export async function fetchMySpaceWorkspace(month = currentMonthString()): Promise<SpaceMyWorkspace> {
  if (!hasAccessToken()) {
    return buildWorkspaceFromLocal(month);
  }
  try {
    const query = month ? `?month=${encodeURIComponent(month)}` : "";
    const remote = await apiRequest<SpaceMyWorkspace>(`/space/me${query}`);
    // If remote has 0 journals and 0 ledgers, also sync local store settings so user has a smooth start.
    return remote;
  } catch {
    return buildWorkspaceFromLocal(month);
  }
}

export async function updateMySpaceSettings(
  payload: Omit<SpaceSetting, "user_id">,
): Promise<SpaceSetting> {
  const store = readLocalStore();
  store.settings = {
    ...store.settings,
    ...payload,
  };
  writeLocalStore(store);

  if (!hasAccessToken()) {
    return store.settings;
  }
  try {
    return await apiRequest<SpaceSetting>("/space/settings", {
      method: "PUT",
      body: JSON.stringify(payload),
    });
  } catch {
    return store.settings;
  }
}

export async function createSpaceJournal(
  payload: SpaceJournalCreatePayload,
): Promise<SpaceJournalItem> {
  if (hasAccessToken()) {
    try {
      return await apiRequest<SpaceJournalItem>("/space/journals", {
        method: "POST",
        body: JSON.stringify(payload),
      });
    } catch {
      // Fall through to local store so user never loses their writing.
    }
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
    try {
      return await apiRequest<SpaceJournalItem>(
        `/space/journals/${encodeURIComponent(entryId)}`,
        {
          method: "PATCH",
          body: JSON.stringify(payload),
        },
      );
    } catch {
      // Fall through to local update if applicable.
    }
  }

  const store = readLocalStore();
  const index = store.journals.findIndex((item) => item.id === entryId);
  if (index >= 0) {
    const existing = store.journals[index]!;
    const updated: SpaceJournalItem = {
      ...existing,
      ...payload,
      updated_at: new Date().toISOString(),
    };
    store.journals[index] = updated;
    writeLocalStore(store);
    return updated;
  }
  throw new Error("未找到对应的手账记录");
}

export async function deleteSpaceJournal(entryId: string): Promise<boolean> {
  if (hasAccessToken() && !entryId.startsWith("local-")) {
    try {
      return await apiRequest<boolean>(`/space/journals/${encodeURIComponent(entryId)}`, {
        method: "DELETE",
      });
    } catch {
      // Fall through to local removal.
    }
  }

  const store = readLocalStore();
  store.journals = store.journals.filter((item) => item.id !== entryId);
  writeLocalStore(store);
  return true;
}

export async function likeSpaceJournal(entryId: string): Promise<SpaceJournalItem> {
  if (!entryId.startsWith("local-")) {
    try {
      return await apiRequest<SpaceJournalItem>(
        `/space/journals/${encodeURIComponent(entryId)}/like`,
        {
          method: "POST",
        },
      );
    } catch {
      // Fall through to local increment.
    }
  }

  const store = readLocalStore();
  const found = store.journals.find((item) => item.id === entryId);
  if (found) {
    found.likes_count = (found.likes_count || 0) + 1;
    writeLocalStore(store);
    return { ...found };
  }
  throw new Error("点赞失败");
}

export async function createSpaceLedgerEntry(
  payload: SpaceLedgerCreatePayload,
): Promise<SpaceLedgerItem> {
  if (hasAccessToken()) {
    try {
      return await apiRequest<SpaceLedgerItem>("/space/ledger", {
        method: "POST",
        body: JSON.stringify(payload),
      });
    } catch {
      // Fall through to local persistence.
    }
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
    try {
      return await apiRequest<boolean>(`/space/ledger/${encodeURIComponent(entryId)}`, {
        method: "DELETE",
      });
    } catch {
      // Fall through to local deletion.
    }
  }

  const store = readLocalStore();
  store.ledgers = store.ledgers.filter((item) => item.id !== entryId);
  writeLocalStore(store);
  return true;
}

export async function fetchPublicSpaceFeed(limit = 30): Promise<SpaceJournalItem[]> {
  try {
    const remote = await apiRequest<SpaceJournalItem[]>(`/space/feed?limit=${limit}`);
    if (remote.length > 0) {
      return remote;
    }
  } catch {
    // Fallback to local public items when offline.
  }
  const store = readLocalStore();
  return store.journals.filter((item) => item.visibility === "public");
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
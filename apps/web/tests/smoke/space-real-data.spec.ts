import { expect, test, type Locator, type Page, type TestInfo } from "@playwright/test";

import type {
  SpaceJournalCreatePayload,
  SpaceJournalItem,
  SpaceJournalUpdatePayload,
  SpaceLedgerCreatePayload,
  SpaceLedgerItem,
  SpaceMyWorkspace,
  SpaceSetting,
} from "../../src/features/space/model";
import { USER } from "./fixtures/forum";

test.use({ serviceWorkers: "block" });

const NOW = "2026-11-17T04:00:00Z";
const STORAGE_KEY = "parallellines.space.local_v1";

interface LocalStore {
  settings: SpaceSetting;
  journals: SpaceJournalItem[];
  ledgers: SpaceLedgerItem[];
}

/** 仅构造回归输入，不连接数据库；故意保留月度小结标题，防止按标题误删真实记录。 */
function existingLocalStore(): LocalStore {
  return {
    settings: {
      user_id: "local", space_title: "我的真实空间", space_subtitle: "本人填写的签名",
      cover_preset: "paper", monthly_budget_cents: 300000,
    },
    journals: [{
      id: "local-journal-1794801600000", user_id: "local", entry_date: "2026-11-17",
      title: "2026-11 月度生活账单小结", content: "这条是我自己填写的真实记录，请保留。",
      mood: "calm", weather: "cloudy", location: "", visibility: "private",
      is_pinned: false, card_theme: "paper", tags: ["真实记录"], media_urls: [], checklist: [],
      ledger_snapshot: null, likes_count: 0, created_at: NOW, updated_at: NOW,
    }],
    ledgers: [
      {
        id: "local-ledger-1794888000001", user_id: "local", entry_date: "2026-11-17",
        kind: "expense", amount_cents: 1234, category: "dining", note: "本人记录午饭",
        payment_method: "wechat", created_at: NOW, updated_at: NOW,
      },
      {
        id: "local-ledger-1794888000002", user_id: "local", entry_date: "2026-11-17",
        kind: "income", amount_cents: 50000, category: "salary", note: "本人记录收入",
        payment_method: "card", created_at: NOW, updated_at: NOW,
      },
    ],
  };
}

/** 构造已存在且包含全部可选字段的本人记录，用于确认正文编辑不会抹去旧功能数据。 */
function richLocalStore(): LocalStore {
  const store = existingLocalStore();
  store.journals[0] = {
    ...store.journals[0]!, entry_date: "2026-11-16", title: "本人既有的完整手账",
    content: "已有正文，编辑时应完整预填。", mood: "inspired", weather: "breezy",
    location: "家中", visibility: "friends", is_pinned: true, card_theme: "grid",
    tags: ["原有标签", "保留字段"], media_urls: ["/fixture/space-image.svg"],
    checklist: [{ id: "original-check-1", text: "已完成的小目标", done: true }, { id: "original-check-2", text: "尚未完成的小目标", done: false }],
    unlock_at: "2026-11-16", is_locked: false,
    ledger_snapshot: { single_entry: { kind: "income", category: "salary", amount_cents: 12345, note: "本人记录的收入" } },
  };
  return store;
}

/** 将固定本地输入作为模拟云端响应；所有写入仍被浏览器 route 拦截。 */
function cloudWorkspace(store = existingLocalStore()): SpaceMyWorkspace {
  const expenses = store.ledgers.filter(item => item.kind === "expense");
  const totalExpense = expenses.reduce((sum, item) => sum + item.amount_cents, 0);
  const totalIncome = store.ledgers.filter(item => item.kind === "income").reduce((sum, item) => sum + item.amount_cents, 0);
  return {
    settings: { ...store.settings, user_id: USER.id },
    journals: store.journals.map(item => ({ ...item, id: item.id.replace("local-", "cloud-"), user_id: USER.id })),
    ledger_entries: store.ledgers.map(item => ({ ...item, id: item.id.replace("local-", "cloud-"), user_id: USER.id })),
    ledger_summary: { month: "2026-11", total_expense_cents: totalExpense, total_income_cents: totalIncome, monthly_budget_cents: store.settings.monthly_budget_cents, entry_count: store.ledgers.length,
      category_breakdown: totalExpense > 0 ? [{ category: "dining", amount_cents: totalExpense, count: expenses.length, ratio_percent: 100 }] : [] },
  };
}

/** 只阻断个人空间的 localStorage 写入；解除标记后仍使用同一原生存储实现重试。 */
async function blockLocalWrites(page: Page, blocked = true) {
  if (!blocked) {
    await page.evaluate(() => sessionStorage.removeItem("fixture.block-space-writes"));
    return;
  }
  await page.evaluate(key => {
    const original = Storage.prototype.setItem;
    Storage.prototype.setItem = function (storageKey, value) {
      if (storageKey === key && sessionStorage.getItem("fixture.block-space-writes")) {
        throw new DOMException("本地测试模拟个人空间存储不可写", "QuotaExceededError");
      }
      original.call(this, storageKey, value);
    };
    sessionStorage.setItem("fixture.block-space-writes", "1");
  }, STORAGE_KEY);
}

/** 拦截页面全部业务接口及站外资源；访客走真实本地存储，登录测试只操作内存响应。 */
async function fixture(page: Page, options: { local?: LocalStore; cloud?: SpaceMyWorkspace } = {}) {
  const state = {
    errors: [] as string[], unexpected: [] as string[],
    settingsWrites: [] as Omit<SpaceSetting, "user_id">[], cloud: options.cloud,
    journalWrites: [] as SpaceJournalCreatePayload[], journalPatches: [] as { id: string; payload: SpaceJournalUpdatePayload }[],
    ledgerWrites: [] as SpaceLedgerCreatePayload[], failJournalWrites: false,
  };
  await page.clock.setFixedTime(new Date(NOW));
  await page.addInitScript(({ key, local, authenticated }) => {
    localStorage.setItem("parallellines.locale", "zh-CN");
    if (local && !localStorage.getItem(key)) localStorage.setItem(key, JSON.stringify(local));
    if (authenticated) localStorage.setItem("parallellines.access_token", "fixture-only-not-a-real-token");
  }, { key: STORAGE_KEY, local: options.local, authenticated: Boolean(options.cloud) });
  page.on("pageerror", error => state.errors.push(error.message));
  const origin = new URL(process.env.PLAYWRIGHT_BASE_URL ?? "http://127.0.0.1:5173").origin;
  await page.route("**/*", async route => {
    const request = route.request();
    const url = new URL(request.url());
    if (url.origin === origin && url.pathname === "/fixture/space-image.svg") {
      return route.fulfill({ contentType: "image/svg+xml", body: '<svg xmlns="http://www.w3.org/2000/svg" width="240" height="120"><rect width="240" height="120" fill="#e2e8f0"/><text x="30" y="65" font-size="22">本人原有配图</text></svg>' });
    }
    if (!url.pathname.startsWith("/api/")) {
      if (url.origin === origin) return route.continue();
      state.unexpected.push(`External: ${url.origin}${url.pathname}`);
      return route.abort();
    }
    const path = url.pathname.replace(/^\/api\/v1/, "");
    const send = (data: unknown) => route.fulfill({ json: { data } });
    if (path === "/site/settings") return send({ settings: { site_title: "平行线" }, updated_at: null });
    if (path === "/site/visits") return send({ recorded: false });
    if (["/site/extensions", "/tags", "/boards"].includes(path)) return send([]);
    if (path === "/auth/oauth/providers") return send({ providers: [] });
    if (path === "/auth/me" && state.cloud) return send(USER);
    if (path === "/auth/fablespace/access") return send({ access_allowed: false, capabilities: [], access_level: null, expires_at: null, authorization_version: 0 });
    if (path === "/notifications") return send({ notifications: [], unread_count: 0 });
    if (path === "/notifications/stream") return route.fulfill({ status: 204, body: "" });
    if (path === "/space/me" && state.cloud) return send(state.cloud);
    if (path === "/space/feed") return send([]);
    if (path === "/space/settings" && request.method() === "PUT" && state.cloud) {
      const payload = request.postDataJSON() as Omit<SpaceSetting, "user_id">;
      state.settingsWrites.push(payload);
      state.cloud.settings = { ...state.cloud.settings, ...payload };
      state.cloud.ledger_summary.monthly_budget_cents = payload.monthly_budget_cents;
      return send(state.cloud.settings);
    }
    if (path === "/space/journals" && request.method() === "POST" && state.cloud) {
      const payload = request.postDataJSON() as SpaceJournalCreatePayload;
      state.journalWrites.push(payload);
      if (state.failJournalWrites) return route.fulfill({ status: 503, json: { error: { code: "service_unavailable", message: "本地模拟手账保存失败" } } });
      const entry: SpaceJournalItem = {
        ...existingLocalStore().journals[0]!, ...payload,
        id: `cloud-journal-${state.journalWrites.length}`, user_id: USER.id,
        title: payload.title ?? "", location: payload.location ?? "", is_pinned: payload.is_pinned ?? false,
        ledger_snapshot: payload.ledger_snapshot ?? null, unlock_at: payload.unlock_at ?? null,
        is_locked: false, created_at: NOW, updated_at: NOW,
      };
      state.cloud.journals.unshift(entry);
      return send(entry);
    }
    const journalId = path.match(/^\/space\/journals\/([^/]+)$/)?.[1];
    if (journalId && request.method() === "PATCH" && state.cloud) {
      const payload = request.postDataJSON() as SpaceJournalUpdatePayload;
      state.journalPatches.push({ id: journalId, payload });
      if (state.failJournalWrites) return route.fulfill({ status: 503, json: { error: { code: "service_unavailable", message: "本地模拟手账保存失败" } } });
      const index = state.cloud.journals.findIndex(item => item.id === journalId);
      if (index < 0) return route.fulfill({ status: 404, json: { error: { code: "not_found", message: "记录不存在" } } });
      const updated = { ...state.cloud.journals[index]!, ...payload, updated_at: NOW };
      state.cloud.journals[index] = updated;
      return send(updated);
    }
    if (path === "/space/ledger" && request.method() === "POST" && state.cloud) {
      const payload = request.postDataJSON() as SpaceLedgerCreatePayload;
      state.ledgerWrites.push(payload);
      const entry: SpaceLedgerItem = { ...payload, id: `cloud-ledger-${state.ledgerWrites.length}`, user_id: USER.id, created_at: NOW, updated_at: NOW };
      state.cloud.ledger_entries.unshift(entry);
      state.cloud.ledger_summary.entry_count += 1;
      if (entry.kind === "income") state.cloud.ledger_summary.total_income_cents += entry.amount_cents;
      else state.cloud.ledger_summary.total_expense_cents += entry.amount_cents;
      return send(entry);
    }
    state.unexpected.push(`${request.method()} ${path}`);
    return route.fulfill({ status: 501, json: { error: { code: "unmocked_api", message: path } } });
  });
  return state;
}

/** 通过真实设置入口打开预算输入框，不直接改 Vue 状态。 */
async function openSettings(page: Page) {
  await page.getByRole("button", { name: "空间装扮 / 预算" }).click();
  return page.locator(".space-settings-drawer input[type=number]");
}

/** 读取测试页面自己的本地数据，检查设置保存没有误删原始记录。 */
async function readLocal(page: Page): Promise<LocalStore | null> {
  return page.evaluate(key => JSON.parse(localStorage.getItem(key) ?? "null"), STORAGE_KEY);
}

/** 按本批三个断点检查实际容器宽度并留存状态截图；不改变页面业务状态。 */
async function captureResponsive(page: Page, target: Locator, testInfo: TestInfo, label: string) {
  for (const width of [1440, 390, 320]) {
    await page.setViewportSize({ width, height: 1000 });
    // 直接定位真实视口，不用长元素截图把 fixed 导航拼进表单中段。
    await target.evaluate(element => window.scrollTo(0, window.scrollY + element.getBoundingClientRect().top - 110));
    expect(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1), `${label} ${width}px 页面横溢`).toBe(false);
    await page.screenshot({ path: testInfo.outputPath(`${label}-${width}.png`) });
    if ((await target.boundingBox())!.height > 830) {
      await target.evaluate(element => window.scrollTo(0, window.scrollY + element.getBoundingClientRect().bottom - innerHeight + 130));
      await page.screenshot({ path: testInfo.outputPath(`${label}-end-${width}.png`) });
    }
  }
}

test("新访客保持空数据，未填预算不回填金额，桌面和手机只显示未设置", async ({ page }, testInfo) => {
  const state = await fixture(page);
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto("/space");
  await expect(page.locator(".space-hero__stats")).toContainText("0 篇手账");
  await expect(page.locator(".space-journal-card")).toHaveCount(0);
  await expect(page.locator(".space-mini-ledger")).toContainText("未设置");
  await expect(page.locator(".budget-progress-bar")).toHaveCount(0);
  const budget = await openSettings(page);
  await expect(budget).toHaveValue("");
  await page.locator(".space-settings-drawer input[type=text]").first().fill("我的空白空间");
  await page.getByRole("button", { name: "保存空间设置", exact: true }).click();
  await expect(page.getByRole("heading", { name: "我的空白空间", exact: true })).toBeVisible();
  expect(await readLocal(page)).toMatchObject({ settings: { monthly_budget_cents: 0 }, journals: [], ledgers: [] });
  await page.reload();
  await expect(await openSettings(page)).toHaveValue("");
  await page.getByRole("button", { name: /^收\s*起$/ }).click();
  await page.getByRole("navigation", { name: "个人空间模块切换" }).getByRole("button", { name: /随手记账/ }).click();
  await expect(page.getByRole("region", { name: "私人记账本" })).toContainText("未设置");
  const share = page.getByRole("button", { name: "预览月度小结", exact: true });
  await expect(share).toBeDisabled();
  expect((await readLocal(page))?.journals).toEqual([]);
  await expect(page.locator(".budget-progress-bar")).toHaveCount(0);
  for (const width of [1440, 390]) {
    await page.setViewportSize({ width, height: 1000 });
    await page.getByRole("region", { name: "私人记账本" }).scrollIntoViewIfNeeded();
    expect(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1)).toBe(false);
    await page.screenshot({ path: testInfo.outputPath(`empty-budget-${width}.png`), fullPage: true });
  }
  expect(state.errors).toEqual([]);
  expect(state.unexpected).toEqual([]);
});

test("真实预算和同名手账保留，小数预算不丢精度，月度卡只取实际收支", async ({ page }, testInfo) => {
  const original = existingLocalStore();
  const state = await fixture(page, { local: original });
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto("/space");
  await expect(page.locator(".space-journal-card")).toHaveCount(1);
  await expect(page.locator(".space-journal-card__content")).toHaveText(original.journals[0]!.content);
  await expect(await openSettings(page)).toHaveValue("3000");
  await page.locator(".space-settings-drawer input[type=number]").fill("1234.56");
  await page.getByRole("button", { name: "保存空间设置", exact: true }).click();
  await expect(page.locator(".space-settings-drawer")).toHaveCount(0);
  await expect(await openSettings(page)).toHaveValue("1234.56");
  const saved = await readLocal(page);
  expect(saved?.settings.monthly_budget_cents).toBe(123456);
  expect(saved?.journals).toEqual(original.journals);
  expect(saved?.ledgers).toEqual(original.ledgers);
  await page.getByRole("button", { name: /^收\s*起$/ }).click();
  await page.getByRole("navigation", { name: "个人空间模块切换" }).getByRole("button", { name: /随手记账/ }).click();
  await expect(page.locator(".ledger-entry-row")).toHaveCount(2);
  await expect(page.locator(".ledger-overview-card")).toContainText("¥12.34");
  await expect(page.locator(".ledger-overview-card")).toContainText("+¥500.00");
  await expect(page.locator(".ledger-overview-card")).toContainText("¥1222.22");
  await page.getByRole("button", { name: "预览月度小结", exact: true }).click();
  const preview = page.getByRole("dialog", { name: "预览月度小结" });
  await expect(preview.getByLabel("月度小结可见范围")).toHaveValue("private");
  await expect(preview.getByLabel("仅晒比例（隐藏金额）")).toBeChecked();
  await expect(page.locator(".space-journal-card")).toHaveCount(0);
  expect((await readLocal(page))!.journals).toEqual(original.journals);
  await preview.getByLabel("仅晒比例（隐藏金额）").uncheck();
  await preview.getByRole("button", { name: "保存为私密手账", exact: true }).click();
  await expect(page.locator(".space-journal-card")).toHaveCount(2);
  const records = (await readLocal(page))!.journals;
  const generated = records.find(item => item.id !== original.journals[0]!.id)!;
  expect(generated.content).toContain("2 笔");
  expect(generated.content).not.toMatch(/快乐|成长|生活方式|有节奏|稳健|咖啡续命/);
  expect(generated).toMatchObject({ mood: "", weather: "", location: "", visibility: "private" });
  expect(generated.ledger_snapshot).toMatchObject({ month: "2026-11", total_expense_cents: 1234, total_income_cents: 50000, entry_count: 2 });
  expect(records.find(item => item.id === original.journals[0]!.id)).toEqual(original.journals[0]);
  const generatedCard = page.locator(".space-journal-card").filter({ has: page.locator(".space-journal-card__monthly-bill") });
  await expect(generatedCard.locator(".space-sticker--mood, .space-sticker--weather")).toHaveCount(0);
  const originalCard = page.locator(".space-journal-card").filter({ hasText: original.journals[0]!.content });
  await expect(originalCard.locator(".space-sticker--mood b")).toHaveText("平静");
  await expect(originalCard.locator(".space-sticker--weather b")).toHaveText("多云");
  const calendarDay = page.locator(".calendar-cell").filter({ has: page.locator(".cell-num", { hasText: /^17$/ }) });
  await expect(calendarDay.locator(".cell-mood")).toHaveText("🍵");
  await expect(page.locator(".mood-bar-track i")).toHaveCount(1);
  await expect(page.locator(".mood-bar-track i")).toHaveAttribute("title", "🍵 平静 1 篇 (100%)");
  await page.locator(".space-journal-timeline").screenshot({ path: testInfo.outputPath("real-records-and-monthly-summary.png") });
  await calendarDay.click();
  const slice = page.getByRole("dialog", { name: "一日生活切片" });
  await expect(slice.locator(".slice-journal-item").filter({ hasText: generated.content }).locator(".slice-journal-meta span")).toHaveCount(0);
  expect(state.errors).toEqual([]);
  expect(state.unexpected).toEqual([]);
});

test("登录账户返回零预算时显示未设置，改空间名称仍向接口提交零预算", async ({ page }) => {
  const cloud: SpaceMyWorkspace = {
    settings: { user_id: USER.id, space_title: "", space_subtitle: "", cover_preset: "aurora", monthly_budget_cents: 0 },
    journals: [], ledger_entries: [],
    ledger_summary: { month: "2026-11", total_expense_cents: 0, total_income_cents: 0, monthly_budget_cents: 0, entry_count: 0, category_breakdown: [] },
  };
  const state = await fixture(page, { cloud });
  await page.goto("/space");
  await expect(page.locator(".space-mini-ledger")).toContainText("未设置");
  await expect(await openSettings(page)).toHaveValue("");
  await page.locator(".space-settings-drawer input[type=text]").first().fill("只修改云端空间名称");
  await page.getByRole("button", { name: "保存空间设置", exact: true }).click();
  await expect(page.getByRole("heading", { name: "只修改云端空间名称", exact: true })).toBeVisible();
  expect(state.settingsWrites).toHaveLength(1);
  expect(state.settingsWrites[0]).toMatchObject({ monthly_budget_cents: 0 });
  expect(state.cloud?.journals).toEqual([]);
  expect(state.cloud?.ledger_entries).toEqual([]);
  expect(state.errors).toEqual([]);
  expect(state.unexpected).toEqual([]);
});

test("非法预算不保存，真实单笔收入同步时不附加心情天气或支出文案", async ({ page }) => {
  const original = existingLocalStore();
  original.settings.monthly_budget_cents = 0;
  original.ledgers = [];
  const state = await fixture(page, { local: original });
  await page.goto("/space");
  const budget = await openSettings(page);
  for (const value of ["-1", "1000000.01"]) {
    await budget.fill(value);
    await page.getByRole("button", { name: "保存空间设置", exact: true }).click();
    await expect(page.locator("#space-budget-error")).toHaveText("请输入 0 至 1000000 元的预算，或留空不设置");
    await expect(budget).toHaveAttribute("aria-invalid", "true");
    expect(await readLocal(page)).toEqual(original);
  }
  await page.getByRole("button", { name: /^收\s*起$/ }).click();
  await page.getByRole("button", { name: "随手记一笔账" }).click();
  await page.getByRole("radiogroup", { name: "收支分类" }).getByRole("button", { name: "收入进账" }).click();
  await page.locator(".ledger-amount-box input").fill("25.68");
  await page.getByLabel("同时生成一张带账单胶囊的手账日签").check();
  await page.getByRole("button", { name: "记入账本", exact: true }).click();
  await expect(page.locator(".space-journal-card")).toHaveCount(2);
  const saved = (await readLocal(page))!;
  expect(saved.ledgers).toHaveLength(1);
  expect(saved.ledgers[0]).toMatchObject({ entry_date: "2026-11-17", kind: "income", amount_cents: 2568, category: "salary" });
  expect(saved.journals.find(item => item.id === original.journals[0]!.id)).toEqual(original.journals[0]);
  const generated = saved.journals.find(item => item.id !== original.journals[0]!.id)!;
  expect(generated).toMatchObject({ mood: "", weather: "", location: "", visibility: "private" });
  expect(generated.content).toContain("收入");
  expect(generated.content).not.toMatch(/开销|支出/);
  expect(generated.ledger_snapshot?.single_entry).toMatchObject({ kind: "income", category: "salary", amount_cents: 2568 });
  const generatedCard = page.locator(".space-journal-card").filter({ has: page.locator(".space-journal-card__ledger-pill") });
  await expect(generatedCard.locator(".space-sticker--mood, .space-sticker--weather")).toHaveCount(0);
  await expect(generatedCard).toContainText("+¥25.68");
  expect(state.errors).toEqual([]);
  expect(state.unexpected).toEqual([]);
});

test("常用编辑器默认私密且无预填心情，扩展功能可达，保存真实正文后卡片紧凑", async ({ page }, testInfo) => {
  const state = await fixture(page);
  await page.goto("/space");
  const editor = page.locator(".space-composer");
  const body = page.getByRole("textbox", { name: "手账正文", exact: true });
  await expect(body).toHaveValue("");
  await expect(page.getByLabel("手账可见性")).toHaveValue("private");
  await expect(editor.getByRole("button", { name: "添加图片", exact: true })).toBeVisible();
  await expect(editor.getByRole("button", { name: "保存手账", exact: true })).toBeVisible();
  await expect(editor.getByRole("button", { name: "更多选项", exact: true })).toHaveAttribute("aria-expanded", "false");
  await expect(page.locator("#journal-more-options")).toBeHidden();
  await editor.getByRole("button", { name: "更多选项", exact: true }).click();
  await expect(editor.locator(".mood-pill[aria-pressed=true], .weather-chip.active")).toHaveCount(0);
  await expect(editor.getByRole("button", { name: "不记录", exact: true })).toHaveAttribute("aria-pressed", "true");
  await expect(editor.getByRole("button", { name: "不记录天气", exact: true })).toHaveAttribute("aria-pressed", "true");
  await expect(editor.locator(".draft-tag")).toHaveCount(0);
  await expect(editor.getByLabel("标题（选填）")).toBeVisible();
  await expect(editor.getByLabel("添加标签")).toBeVisible();
  await expect(editor.getByLabel("手账日期")).toBeVisible();
  await expect(editor.getByLabel("时间胶囊拆封日期")).toBeVisible();
  await expect(editor.getByLabel("置顶手账")).toBeVisible();
  await expect(editor.locator(".theme-strip")).toBeVisible();
  await expect(editor.getByPlaceholder("添加打卡事项，回车添加")).toBeVisible();
  await editor.getByRole("button", { name: "收起选项", exact: true }).click();
  await body.fill("这是本人填写的日常记录，没有选择心情或天气。");
  await captureResponsive(page, editor, testInfo, "simple-composer");
  await editor.getByRole("button", { name: "保存手账", exact: true }).click();
  await expect(page.locator(".space-journal-card")).toHaveCount(1);
  const saved = (await readLocal(page))!.journals[0]!;
  expect(saved).toMatchObject({ content: "这是本人填写的日常记录，没有选择心情或天气。", mood: "", weather: "", visibility: "private", tags: [] });
  await expect(body).toHaveValue("");
  await expect(page.locator(".space-journal-card .space-sticker--mood, .space-journal-card .space-sticker--weather")).toHaveCount(0);
  await expect(page.locator(".space-card-more")).not.toHaveAttribute("open");
  await captureResponsive(page, page.locator(".space-journal-card"), testInfo, "compact-private-card");
  expect(state.errors).toEqual([]);
  expect(state.unexpected).toEqual([]);
});

test("正文编辑完整预填旧字段，仅PATCH正文，失败保留草稿，取消恢复未发布的新草稿", async ({ page }, testInfo) => {
  const cloud = cloudWorkspace(richLocalStore());
  const original = structuredClone(cloud.journals[0]!);
  const state = await fixture(page, { cloud });
  await page.goto("/space");
  const body = page.getByRole("textbox", { name: "手账正文", exact: true });
  await body.fill("尚未发布的新手账草稿");
  await page.locator(".space-journal-card").getByRole("button", { name: "编辑", exact: true }).click();
  await expect(body).toHaveValue(original.content);
  await expect(page.getByLabel("手账可见性")).toHaveValue("friends");
  await expect(page.locator(".composer-media-preview img")).toHaveAttribute("src", original.media_urls[0]!);
  await page.getByRole("button", { name: "更多选项", exact: true }).click();
  await expect(page.getByLabel("标题（选填）")).toHaveValue(original.title);
  await expect(page.getByLabel("地点或场景")).toHaveValue(original.location);
  await expect(page.getByLabel("手账日期")).toHaveValue(original.entry_date);
  await expect(page.getByLabel("时间胶囊拆封日期")).toHaveValue(original.unlock_at!);
  await expect(page.getByLabel("置顶手账")).toBeChecked();
  await expect(page.locator(".mood-pill[aria-pressed=true]")).toContainText("灵感");
  await expect(page.locator(".weather-chip[aria-pressed=true]")).toContainText("微风");
  await expect(page.locator(".theme-dot[aria-pressed=true]")).toHaveAttribute("title", "信纸：方格手账");
  await expect(page.locator(".draft-tag")).toHaveCount(2);
  await expect(page.getByLabel("已完成的小目标", { exact: true })).toBeChecked();
  await expect(page.getByLabel("尚未完成的小目标", { exact: true })).not.toBeChecked();
  await body.fill("只修改这段正文，其他资料保持不变。");
  state.failJournalWrites = true;
  await page.getByRole("button", { name: "保存修改", exact: true }).click();
  await expect(page.locator(".space-composer .space-form-error")).toContainText("当前草稿未清空");
  await expect(body).toHaveValue("只修改这段正文，其他资料保持不变。");
  expect(state.cloud!.journals[0]).toEqual(original);
  expect(state.journalPatches).toEqual([{ id: original.id, payload: { content: "只修改这段正文，其他资料保持不变。" } }]);
  await captureResponsive(page, page.locator(".space-composer"), testInfo, "editing-retained-draft");
  state.failJournalWrites = false;
  await page.getByRole("button", { name: "保存修改", exact: true }).click();
  await expect(page.locator(".composer-edit-notice")).toHaveCount(0);
  await expect(body).toHaveValue("尚未发布的新手账草稿");
  expect(state.journalPatches[1]).toEqual(state.journalPatches[0]);
  expect(state.cloud!.journals[0]).toEqual({ ...original, content: "只修改这段正文，其他资料保持不变。", updated_at: NOW });
  await page.locator(".space-journal-card").getByRole("button", { name: "编辑", exact: true }).click();
  await body.fill("这次编辑应取消，不写入任何记录。");
  await page.getByRole("button", { name: "取消编辑", exact: true }).click();
  await expect(body).toHaveValue("尚未发布的新手账草稿");
  expect(state.journalPatches).toHaveLength(2);
  expect(state.cloud!.journals[0]!.content).toBe("只修改这段正文，其他资料保持不变。");
  expect(state.errors).toEqual([]);
  expect(state.unexpected).toEqual([]);
});

test("月度小结先预览默认私密，取消不保存，公开比例卡请求不包含精确金额", async ({ page }, testInfo) => {
  const state = await fixture(page, { cloud: cloudWorkspace() });
  await page.goto("/space");
  await page.getByRole("navigation", { name: "个人空间模块切换" }).getByRole("button", { name: /随手记账/ }).click();
  const open = page.getByRole("button", { name: "预览月度小结", exact: true });
  await open.click();
  const preview = page.getByRole("dialog", { name: "预览月度小结" });
  await expect(preview.getByLabel("月度小结可见范围")).toHaveValue("private");
  await expect(preview.getByLabel("仅晒比例（隐藏金额）")).toBeChecked();
  await expect(preview).not.toContainText("12.34");
  await expect(preview).not.toContainText("500.00");
  expect(state.journalWrites).toEqual([]);
  await preview.getByRole("button", { name: /^取\s*消$/ }).click();
  await expect(preview).toHaveCount(0);
  expect(state.journalWrites).toEqual([]);
  await open.click();
  await preview.getByLabel("月度小结可见范围").selectOption("public");
  await expect(preview).toContainText("不包含精确金额");
  expect(state.journalWrites).toEqual([]);
  await captureResponsive(page, preview, testInfo, "monthly-public-confirmation");
  await preview.getByRole("button", { name: "确认公开发布", exact: true }).click();
  await expect(preview).toHaveCount(0);
  expect(state.journalWrites).toHaveLength(1);
  expect(state.journalWrites[0]).toMatchObject({ visibility: "public", mood: "", weather: "", ledger_snapshot: { month: "2026-11", entry_count: 2, hide_exact_amount: true, top_categories: [{ category: "dining", ratio_percent: 100 }] } });
  expect(JSON.stringify(state.journalWrites[0]!.ledger_snapshot)).not.toMatch(/"(?:amount_cents|total_expense_cents|total_income_cents)"/);
  const card = page.locator(".space-journal-card").filter({ has: page.locator(".space-journal-card__monthly-bill") });
  await expect(card).not.toContainText("12.34");
  await expect(card).not.toContainText("500.00");
  expect(state.errors).toEqual([]);
  expect(state.unexpected).toEqual([]);
});

test("本地写入失败不报告成功且不丢输入，解除故障后同一草稿可重试保存", async ({ page }) => {
  const state = await fixture(page);
  await page.goto("/space");
  const body = page.getByRole("textbox", { name: "手账正文", exact: true });
  await body.fill("本机存储失败时必须保留的真实输入。");
  await blockLocalWrites(page);
  await page.getByRole("button", { name: "保存手账", exact: true }).click();
  await expect(page.locator(".space-composer .space-form-error")).toBeVisible();
  await expect(body).toHaveValue("本机存储失败时必须保留的真实输入。");
  await expect(page.locator(".ant-message-success")).toHaveCount(0);
  await expect(page.locator(".space-journal-card")).toHaveCount(0);
  expect(await readLocal(page)).toBeNull();
  await blockLocalWrites(page, false);
  await page.getByRole("button", { name: "保存手账", exact: true }).click();
  await expect(page.locator(".space-journal-card")).toHaveCount(1);
  await expect(body).toHaveValue("");
  expect((await readLocal(page))!.journals).toHaveLength(1);
  expect((await readLocal(page))!.journals[0]).toMatchObject({ content: "本机存储失败时必须保留的真实输入。", visibility: "private", mood: "", weather: "" });
  expect(state.errors).toEqual([]);
  expect(state.unexpected).toEqual([]);
});

test("记账成功但卡片失败明确提示，只重试卡片不重复创建账目", async ({ page }) => {
  const store = existingLocalStore();
  store.journals = []; store.ledgers = [];
  const state = await fixture(page, { cloud: cloudWorkspace(store) });
  state.failJournalWrites = true;
  await page.goto("/space");
  await page.getByRole("button", { name: "随手记一笔账" }).click();
  await page.locator(".ledger-amount-box input").fill("19.99");
  await page.getByPlaceholder("一句话备注（例如：买独立游戏 / 桂花拿铁 / 稿费入账）").fill("本人填写的午饭账目");
  await page.getByLabel("同时生成一张带账单胶囊的手账日签").check();
  await page.getByRole("button", { name: "记入账本", exact: true }).click();
  await expect(page.locator(".space-composer .space-form-error")).toContainText("账目已保存，手账卡片尚未确认保存");
  expect(state.ledgerWrites).toHaveLength(1);
  expect(state.journalWrites).toHaveLength(1);
  expect(state.cloud!.ledger_entries[0]).toMatchObject({ kind: "expense", amount_cents: 1999, note: "本人填写的午饭账目" });
  await expect(page.getByRole("button", { name: "记入账本", exact: true })).toBeDisabled();
  state.failJournalWrites = false;
  await page.getByRole("button", { name: "只重试手账卡片", exact: true }).click();
  await expect(page.locator(".space-composer .space-form-error")).toHaveCount(0);
  expect(state.ledgerWrites).toHaveLength(1);
  expect(state.journalWrites).toHaveLength(2);
  expect(state.cloud!.ledger_entries).toHaveLength(1);
  expect(state.cloud!.journals).toHaveLength(1);
  expect(state.journalWrites[1]).toEqual(state.journalWrites[0]);
  expect(state.cloud!.journals[0]).toMatchObject({ visibility: "private", ledger_snapshot: { single_entry: { amount_cents: 1999, note: "本人填写的午饭账目" } } });
  expect(state.errors).toEqual([]);
  expect(state.unexpected).toEqual([]);
});

test("普通手账和卡片改公开都需确认，取消后不提交；隐藏单笔金额不显示零或NaN", async ({ page }) => {
  const store = existingLocalStore();
  store.journals[0]!.ledger_snapshot = { hide_exact_amount: true, single_entry: { kind: "expense", category: "dining", note: "按用户选择隐藏金额" } };
  const cloud = cloudWorkspace(store);
  cloud.journals.push({ ...cloud.journals[0]!, id: "cloud-locked-capsule", title: "", content: "", ledger_snapshot: null, unlock_at: "2026-12-01", is_locked: true });
  const state = await fixture(page, { cloud });
  const dialogs: string[] = [];
  page.on("dialog", async dialog => { dialogs.push(dialog.message()); await dialog.dismiss(); });
  await page.goto("/space");
  const card = page.locator(".space-journal-card").filter({ hasText: store.journals[0]!.content });
  await expect(page.locator(".space-journal-card").filter({ has: page.locator(".space-journal-card__capsule-seal") }).getByRole("button", { name: "编辑", exact: true })).toBeDisabled();
  await expect(card.locator(".space-journal-card__ledger-pill")).toContainText("金额已隐藏");
  await expect(card.locator(".space-journal-card__ledger-pill")).not.toContainText("¥0.00");
  await expect(card.locator(".space-journal-card__ledger-pill")).not.toContainText("NaN");
  await page.getByRole("textbox", { name: "手账正文", exact: true }).fill("公开前需要确认的本人正文。");
  await page.getByLabel("手账可见性").selectOption("public");
  await page.getByRole("button", { name: "保存并公开", exact: true }).click();
  expect(state.journalWrites).toEqual([]);
  await expect(page.getByRole("textbox", { name: "手账正文", exact: true })).toHaveValue("公开前需要确认的本人正文。");
  await card.locator("summary").click();
  await card.getByRole("button", { name: "设为公开", exact: true }).click();
  expect(state.journalPatches).toEqual([]);
  expect(dialogs).toHaveLength(2);
  expect(dialogs.every(message => message.includes("公开"))).toBe(true);
  expect(state.errors).toEqual([]);
  expect(state.unexpected).toEqual([]);
});

test("本地队列同步遇云端未确认结果保留记录，持续提示核对并禁直接重试", async ({ page }) => {
  const local = existingLocalStore();
  local.ledgers = [];
  const emptyCloud = existingLocalStore();
  emptyCloud.journals = []; emptyCloud.ledgers = [];
  const state = await fixture(page, { local, cloud: cloudWorkspace(emptyCloud) });
  state.failJournalWrites = true;
  await page.goto("/space");
  const sync = page.getByRole("button", { name: "同步到云端", exact: true });
  await expect(page.locator(".space-sync-banner")).toContainText("1 篇手账");
  await sync.click();
  const error = page.locator(".space-data-error").filter({ hasText: "不要直接重试" });
  await expect(error).toContainText("已确认同步 0 篇手账");
  await expect(error).toContainText("本机仍有 1 篇手账");
  await expect(error.getByRole("button", { name: "查看云端记录", exact: true })).toBeVisible();
  await expect(sync).toBeDisabled();
  expect(state.journalWrites).toHaveLength(1);
  expect(await readLocal(page)).toEqual(local);
  await error.getByRole("button", { name: "查看云端记录", exact: true }).click();
  await expect(error).toBeVisible();
  await expect(sync).toBeDisabled();
  expect(state.journalWrites).toHaveLength(1);
  expect(state.cloud!.journals).toEqual([]);
  expect(state.errors).toEqual([]);
  expect(state.unexpected).toEqual([]);
});

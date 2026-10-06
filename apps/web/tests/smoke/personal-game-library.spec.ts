import path from "node:path";

import { expect, test, type BrowserContext, type Locator, type Page } from "@playwright/test";

const storageKey = "parallellines.catalog-library.v1";
const storageWarning = "本地存储不可用，当前清单只在本次页面访问期间保留。";
const baseURL = process.env.PLAYWRIGHT_BASE_URL ?? "http://127.0.0.1:5173";

interface LibrarySnapshot {
  version: 1;
  wantedIds: string[];
  recent: Array<{ projectId: string; lastOpenedAt: number }>;
}

const games = [
  { id: "901", slug: "clock-out", name: "打工摸鱼", category: "puzzle", author: "测试作者甲", kind: "external" },
  { id: "902", slug: "merge-watermelon", name: "合成大西瓜", category: "casual", author: "测试作者乙", kind: "external" },
  { id: "903", slug: "snake-escape", name: "蛇蛇出洞", category: "puzzle", author: null, kind: "internal" },
];

/** 构造目录响应；扩展数量仅用于分页，不连接真实目录或数据库。 */
function catalogFixture(count = 3) {
  const entries = Array.from({ length: count }, (_, index) => {
    const fixture = games[index];
    return {
      id: fixture?.id ?? String(901 + index),
      slug: fixture?.slug ?? `test-game-${index}`,
      name: fixture?.name ?? `测试游戏${index + 1}`,
      category: fixture?.category ?? "puzzle",
      url: fixture?.kind === "internal" ? "/play/snake-escape" : `https://library-game.invalid/play/${901 + index}`,
      kind: fixture?.kind ?? "external",
      description: "个人清单验收数据",
      author_name: fixture?.author ?? (index > 2 ? "测试作者甲" : null),
      author_url: null,
      icon_url: null,
      created_at: new Date(Date.UTC(2026, 8, 30) - index * 86_400_000).toISOString(),
      average_score: null,
      rating_count: 0,
      rating_score_sum: 0,
      view_count: 0,
      my_score: null,
    };
  });
  return {
    categories: [
      { id: "1", slug: "puzzle", name: "解谜", icon_url: null, projects: entries.filter((game) => game.category === "puzzle") },
      { id: "2", slug: "casual", name: "休闲", icon_url: null, projects: entries.filter((game) => game.category === "casual") },
    ],
  };
}

/** 拦截全部 API、CDN 与游戏目标；本地页面保留真实前端代码及正式封面。 */
async function mockCatalog(context: BrowserContext, count = 3, failViews = false) {
  const opened: string[] = [];
  const ratings: Array<{ id: string; score: number }> = [];
  const unexpectedRequests: string[] = [];
  const fixture = catalogFixture(count);
  const localOrigin = new URL(baseURL).origin;
  await context.route("**/*", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const headers = { "access-control-allow-origin": "*" };
    if (url.pathname.includes("/static/web/")) {
      const key = url.pathname.split("/static/web/")[1];
      await route.fulfill({ path: path.resolve(process.cwd(), "../../static/web", key), headers });
      return;
    }
    if (url.hostname === "library-game.invalid" || (url.origin === localOrigin && url.pathname.startsWith("/play/"))) {
      await route.fulfill({ contentType: "text/html; charset=utf-8", body: "<!doctype html><meta charset='utf-8'><title>游戏打开验收</title><h1>已打开测试目标</h1>" });
      return;
    }
    if (url.pathname.startsWith("/api/v1/")) {
      const viewMatch = /\/catalog\/projects\/([^/]+)\/views$/.exec(url.pathname);
      const ratingMatch = /\/catalog\/projects\/([^/]+)\/ratings$/.exec(url.pathname);
      if (url.pathname === "/api/v1/catalog") {
        await route.fulfill({ json: { data: fixture }, headers });
      } else if (viewMatch) {
        const id = viewMatch[1]!;
        opened.push(id);
        await route.fulfill(failViews
          ? { status: 503, json: { error: { code: "TEST_UNAVAILABLE", message: "test" } }, headers }
          : { json: { data: { project_id: id, view_count: opened.filter((item) => item === id).length } }, headers });
      } else if (ratingMatch) {
        const score = (request.postDataJSON() as { score: number }).score;
        ratings.push({ id: ratingMatch[1]!, score });
        await route.fulfill({ json: { data: {
          project_id: ratingMatch[1], average_score: score, rating_count: 1, rating_score_sum: score, my_score: score,
        } }, headers });
      } else {
        await route.fulfill({ json: { data: url.pathname.endsWith("/settings/public") ? { settings: {} } : [] }, headers });
      }
      return;
    }
    if (url.origin !== localOrigin) {
      unexpectedRequests.push(request.url());
      await route.abort();
      return;
    }
    await route.continue();
  });
  return { opened, ratings, unexpectedRequests };
}

/** 初始化仅执行一次；刷新必须读取应用实际保存的内容。 */
async function seedLibrary(context: BrowserContext, snapshot: LibrarySnapshot | string) {
  await context.addInitScript(({ key, raw }) => {
    if (sessionStorage.getItem("library-test-seeded")) return;
    localStorage.setItem(key, raw);
    sessionStorage.setItem("library-test-seeded", "1");
  }, { key: storageKey, raw: typeof snapshot === "string" ? snapshot : JSON.stringify(snapshot) });
}

/** 读取持久化结果，避免以界面状态代替刷新恢复的证据。 */
async function savedLibrary(page: Page): Promise<LibrarySnapshot | null> {
  return page.evaluate((key) => JSON.parse(localStorage.getItem(key) ?? "null") as LibrarySnapshot | null, storageKey);
}

/** 按游戏标题定位所属卡片，避免与作者弹窗、榜单混淆。 */
function card(page: Page, name: string) {
  return page.locator("article.catalog-card").filter({ has: page.getByRole("heading", { name, exact: true }) });
}

/** 通过原生链接打开模拟目标；按钮种类决定鼠标或键盘入口。 */
async function openGame(page: Page, target: Locator, gesture: "left" | "middle" | "keyboard" = "left") {
  const opened = page.context().waitForEvent("page");
  if (gesture === "keyboard") {
    await target.focus();
    await target.press("Enter");
  } else {
    await target.click({ button: gesture });
  }
  const popup = await opened;
  await expect(popup.getByRole("heading", { name: "已打开测试目标" })).toBeVisible();
  await popup.close();
}

test("想玩可用键盘切换、刷新恢复，并保持评分和原生打开相互独立", async ({ page, context }) => {
  const requests = await mockCatalog(context);
  await page.goto("/");
  await expect(page.getByText("记录保存在当前浏览器，清理浏览器数据后会丢失。")).toBeVisible();
  const first = card(page, "打工摸鱼");
  await first.getByRole("button", { name: "加入想玩", exact: true }).focus();
  await page.keyboard.press("Space");
  await expect(first.getByRole("button", { name: "移出想玩", exact: true })).toHaveAttribute("aria-pressed", "true");
  expect(requests.opened).toEqual([]);
  expect(requests.ratings).toEqual([]);
  expect(context.pages()).toHaveLength(1);
  expect((await savedLibrary(page))?.wantedIds).toEqual(["901"]);
  await first.getByRole("button", { name: "查看打工摸鱼的评分", exact: true }).click();
  await first.getByRole("button", { name: "给打工摸鱼评3分", exact: true }).click();
  await expect(first.getByText("1 人评分", { exact: true })).toBeVisible();
  expect(requests.ratings).toEqual([{ id: "901", score: 3 }]);
  expect((await savedLibrary(page))?.recent).toEqual([]);
  await page.reload();
  await page.locator(".catalog-library-filters").getByRole("button", { name: "想玩清单", exact: true }).click();
  await expect(page.locator(".catalog-card")).toHaveCount(1);
  await expect(first.getByRole("button", { name: "移出想玩", exact: true })).toHaveAttribute("aria-pressed", "true");
  await first.getByRole("button", { name: "移出想玩", exact: true }).click();
  await expect(page.getByText("还没有加入想玩的游戏", { exact: true })).toBeVisible();
  expect((await savedLibrary(page))?.wantedIds).toEqual([]);
  expect(requests.unexpectedRequests).toEqual([]);
});

test("评分只展开一个面板，Escape 恢复入口焦点，外部点击不提交评分", async ({ page, context }) => {
  const requests = await mockCatalog(context);
  await page.goto("/");
  const first = card(page, "打工摸鱼");
  const second = card(page, "合成大西瓜");
  const firstTrigger = first.getByRole("button", { name: "查看打工摸鱼的评分", exact: true });
  const secondTrigger = second.getByRole("button", { name: "查看合成大西瓜的评分", exact: true });
  // 键盘进入评分后直接聚焦分值；关闭时回到当前游戏入口。
  await firstTrigger.focus();
  await firstTrigger.press("Enter");
  await expect(firstTrigger).toHaveAttribute("aria-expanded", "true");
  await expect(first.getByRole("button", { name: "给打工摸鱼评1分", exact: true })).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(firstTrigger).toBeFocused();
  await expect(page.locator(".catalog-card__rating-panel")).toHaveCount(0);
  // 改看另一款评分时收起旧面板，页面最多保留一个评分操作区。
  await firstTrigger.click();
  await secondTrigger.click();
  await expect(firstTrigger).toHaveAttribute("aria-expanded", "false");
  await expect(second.getByRole("group", { name: "合成大西瓜的评分", exact: true })).toBeVisible();
  await expect(page.locator(".catalog-card__rating-panel")).toHaveCount(1);
  await page.locator("#catalog-title").click();
  await expect(secondTrigger).toHaveAttribute("aria-expanded", "false");
  await expect(page.locator(".catalog-card__rating-panel")).toHaveCount(0);
  expect(requests.ratings).toEqual([]);
  expect(requests.opened).toEqual([]);
  expect(requests.unexpectedRequests).toEqual([]);
});

test("评分请求挂起或失败时 Escape 仍关闭面板并恢复入口焦点", async ({ page, context }) => {
  const requests = await mockCatalog(context);
  let releasePending = () => {};
  const pendingResponse = new Promise<void>((resolve) => { releasePending = resolve; });
  // 首次响应由测试显式放行，第二次直接失败；仅模拟当前评分接口，不写真实数据。
  await context.route("**/api/v1/catalog/projects/901/ratings", async (route) => {
    const score = (route.request().postDataJSON() as { score: number }).score;
    requests.ratings.push({ id: "901", score });
    if (requests.ratings.length === 1) await pendingResponse;
    await route.fulfill({ status: 503, json: { error: { code: "TEST_UNAVAILABLE", message: "test" } }, headers: { "access-control-allow-origin": "*" } });
  });
  await page.goto("/");
  const first = card(page, "打工摸鱼");
  const trigger = first.getByRole("button", { name: "查看打工摸鱼的评分", exact: true });
  const panel = first.getByRole("group", { name: "打工摸鱼的评分", exact: true });
  await trigger.click();
  try {
    await first.getByRole("button", { name: "给打工摸鱼评3分", exact: true }).click();
    await expect.poll(() => requests.ratings).toEqual([{ id: "901", score: 3 }]);
    await expect(panel).toBeFocused();
    await expect(first.getByRole("button", { name: "给打工摸鱼评3分", exact: true })).toBeDisabled();
    await page.keyboard.press("Escape");
    await expect(trigger).toBeFocused();
    await expect(page.locator(".catalog-card__rating-panel")).toHaveCount(0);
  } finally {
    releasePending();
  }
  await expect(first.getByRole("alert")).toHaveText("评分暂时不可用，请稍后重试。");
  // 失败不产生已评分结果；重新打开后仍可提交，失败时的焦点留在当前面板内。
  await trigger.click();
  await first.getByRole("button", { name: "给打工摸鱼评2分", exact: true }).click();
  await expect.poll(() => requests.ratings).toEqual([{ id: "901", score: 3 }, { id: "901", score: 2 }]);
  await expect(first.getByRole("alert")).toHaveText("评分暂时不可用，请稍后重试。");
  await expect(first.getByRole("button", { name: "给打工摸鱼评2分", exact: true })).toBeEnabled();
  await expect(panel).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(trigger).toBeFocused();
  await expect(page.locator(".catalog-card__rating-panel")).toHaveCount(0);
  expect(requests.opened).toEqual([]);
  expect((await savedLibrary(page))?.recent ?? []).toEqual([]);
});

test("排序下拉框沿用最新和热门顺序，网格列表切换保留排序与想玩记录", async ({ page, context }) => {
  const requests = await mockCatalog(context);
  const fixture = catalogFixture();
  // 公共浏览量不同但发布日期顺序不变，两个排序入口须得到各自的既有结果。
  for (const category of fixture.categories) {
    for (const game of category.projects) game.view_count = ({ "901": 2, "902": 10, "903": 20 } as Record<string, number>)[game.id]!;
  }
  await context.route("**/api/v1/catalog", (route) => route.fulfill({
    json: { data: fixture }, headers: { "access-control-allow-origin": "*" },
  }));
  await page.goto("/");
  const sort = page.getByRole("combobox", { name: "游戏排序", exact: true });
  await expect(sort).toHaveValue("latest");
  await expect(page.locator(".catalog-card h2")).toHaveText(["打工摸鱼", "合成大西瓜", "蛇蛇出洞"]);
  await sort.selectOption("hot");
  await expect(page.locator(".catalog-card h2")).toHaveText(["蛇蛇出洞", "合成大西瓜", "打工摸鱼"]);
  await card(page, "蛇蛇出洞").getByRole("button", { name: "加入想玩", exact: true }).click();
  await page.getByRole("button", { name: "列表显示", exact: true }).click();
  await expect(page.locator(".catalog-grid")).toHaveClass(/catalog-grid--list/);
  await expect(page.getByRole("button", { name: "列表显示", exact: true })).toHaveAttribute("aria-pressed", "true");
  await expect(sort).toHaveValue("hot");
  await expect(page.locator(".catalog-card h2")).toHaveText(["蛇蛇出洞", "合成大西瓜", "打工摸鱼"]);
  await expect(card(page, "蛇蛇出洞").getByRole("button", { name: "移出想玩", exact: true })).toHaveAttribute("aria-pressed", "true");
  await page.getByRole("button", { name: "网格显示", exact: true }).click();
  await expect(page.locator(".catalog-grid")).not.toHaveClass(/catalog-grid--list/);
  await expect(page.getByRole("button", { name: "网格显示", exact: true })).toHaveAttribute("aria-pressed", "true");
  await sort.selectOption("latest");
  await expect(page.locator(".catalog-card h2")).toHaveText(["打工摸鱼", "合成大西瓜", "蛇蛇出洞"]);
  expect((await savedLibrary(page))?.wantedIds).toEqual(["903"]);
  expect(requests.ratings).toEqual([]);
  expect(requests.opened).toEqual([]);
});

test("封面、标题、试玩及作者弹窗各记录一次打开，最近列表更新顺序并可刷新", async ({ page, context }) => {
  const requests = await mockCatalog(context);
  await page.goto("/");
  await openGame(page, card(page, "打工摸鱼").locator(".catalog-card__media-link"));
  await expect.poll(() => requests.opened).toEqual(["901"]);
  await expect(card(page, "打工摸鱼").locator(".catalog-card__views")).toHaveAttribute("aria-label", "1 次浏览");
  await openGame(page, card(page, "合成大西瓜").locator(".catalog-card__title-link"), "keyboard");
  await openGame(page, card(page, "蛇蛇出洞").locator(".catalog-card__open"), "middle");
  await card(page, "打工摸鱼").getByRole("button", { name: "查看测试作者甲的作品", exact: true }).click();
  await openGame(page, page.getByRole("dialog").getByRole("link", { name: "打工摸鱼", exact: true }));
  await expect(page.getByRole("dialog")).toBeVisible();
  await page.getByRole("button", { name: "关闭作者窗口", exact: true }).click();
  await expect.poll(() => requests.opened).toEqual(["901", "902", "903", "901"]);
  // 右键只打开菜单，不应写最近记录或增加公共打开量。
  await card(page, "打工摸鱼").locator(".catalog-card__media-link").click({ button: "right" });
  await page.keyboard.press("Escape");
  await page.locator(".catalog-library-filters").getByRole("button", { name: "最近打开", exact: true }).click();
  await expect(page.locator(".catalog-sort")).toHaveCount(0);
  await expect(page.locator(".catalog-card h2")).toHaveText(["打工摸鱼", "蛇蛇出洞", "合成大西瓜"]);
  expect((await savedLibrary(page))?.recent.map((item) => item.projectId)).toEqual(["901", "903", "902"]);
  expect(requests.opened).toEqual(["901", "902", "903", "901"]);
  await page.reload();
  await page.locator(".catalog-library-filters").getByRole("button", { name: "最近打开", exact: true }).click();
  await expect(page.locator(".catalog-card h2")).toHaveText(["打工摸鱼", "蛇蛇出洞", "合成大西瓜"]);
});

test("个人范围组合分类、搜索和作者条件，并重置分页但不改变公共榜单", async ({ page, context }) => {
  await mockCatalog(context, 30);
  await seedLibrary(context, { version: 1, wantedIds: Array.from({ length: 25 }, (_, index) => String(901 + index)), recent: [] });
  await page.goto("/");
  await expect(page.locator(".catalog-card")).toHaveCount(24);
  await page.getByRole("button", { name: "加载更多", exact: true }).click();
  await expect(page.locator(".catalog-card")).toHaveCount(30);
  await page.locator(".catalog-library-filters").getByRole("button", { name: "想玩清单", exact: true }).click();
  await expect(page.locator(".catalog-card")).toHaveCount(24);
  await expect(page.locator(".catalog-results")).toHaveText("25 个游戏");
  await page.getByRole("combobox", { name: "游戏分类", exact: true }).selectOption("casual");
  await expect(page.locator(".catalog-card h2")).toHaveText(["合成大西瓜"]);
  await page.getByRole("searchbox", { name: "搜索游戏名称", exact: true }).fill("蛇蛇");
  await page.getByRole("button", { name: "搜索", exact: true }).click();
  await expect(page.getByText("没有找到匹配的游戏", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "清除筛选", exact: true }).click();
  await expect(page.locator(".catalog-results")).toHaveText("25 个游戏");
  await page.locator(".catalog-view-tabs").getByRole("button", { name: "作者榜", exact: true }).click();
  await expect(page.locator(".catalog-author-count")).toHaveText("3 位作者");
  const author = page.locator(".catalog-podium__place").filter({ hasText: "测试作者甲" });
  await expect(author.locator(".catalog-podium__metric")).toHaveText("28 个作品");
  await author.getByRole("button", { name: "查看测试作者甲的作品", exact: true }).click();
  await expect(page.locator(".catalog-results")).toHaveText("28 个游戏");
  await page.locator(".catalog-library-filters").getByRole("button", { name: "想玩清单", exact: true }).click();
  await expect(page.locator(".catalog-results")).toHaveText("23 个游戏");
  await expect(page.locator(".catalog-author-selection")).toContainText("测试作者甲");
  await page.locator(".catalog-view-tabs").getByRole("button", { name: "贡献榜", exact: true }).click();
  await expect(page.locator(".catalog-podium__place").filter({ hasText: "测试作者甲" }).locator(".catalog-podium__metric"))
    .toHaveText("28 个作品");
});

test("空最近清单与未匹配记录正确展示，暂时下架条目仍保留", async ({ page, context }) => {
  await mockCatalog(context);
  await seedLibrary(context, { version: 1, wantedIds: ["temporarily-unlisted"], recent: [] });
  await page.goto("/");
  await page.locator(".catalog-library-filters").getByRole("button", { name: "最近打开", exact: true }).click();
  await expect(page.getByText("还没有打开过游戏", { exact: true })).toBeVisible();
  await page.locator(".catalog-library-filters").getByRole("button", { name: "想玩清单", exact: true }).click();
  await expect(page.locator(".catalog-card")).toHaveCount(0);
  await expect(page.getByText("没有找到匹配的游戏", { exact: true })).toBeVisible();
  expect((await savedLibrary(page))?.wantedIds).toEqual(["temporarily-unlisted"]);
  await page.locator(".catalog-library-filters").getByRole("button", { name: "全部游戏", exact: true }).click();
  await card(page, "打工摸鱼").getByRole("button", { name: "加入想玩", exact: true }).click();
  expect((await savedLibrary(page))?.wantedIds).toContain("temporarily-unlisted");
});

for (const raw of ["broken-json", JSON.stringify({ version: 99, wantedIds: ["901"], recent: [] })]) {
  test(`损坏或未知版本只影响持久化，仍可收藏与试玩且保留原数据：${raw}`, async ({ page, context }) => {
    const requests = await mockCatalog(context);
    await seedLibrary(context, raw);
    await page.goto("/");
    await expect(page.getByText(storageWarning, { exact: true })).toBeVisible();
    await card(page, "打工摸鱼").getByRole("button", { name: "加入想玩", exact: true }).click();
    await openGame(page, card(page, "打工摸鱼").locator(".catalog-card__open"));
    await expect.poll(() => requests.opened).toEqual(["901"]);
    await page.locator(".catalog-library-filters").getByRole("button", { name: "想玩清单", exact: true }).click();
    await expect(page.locator(".catalog-card h2")).toHaveText(["打工摸鱼"]);
    expect(await page.evaluate((key) => localStorage.getItem(key), storageKey)).toBe(raw);
    await page.locator(".catalog-library-filters").getByRole("button", { name: "最近打开", exact: true }).click();
    await expect(page.locator(".catalog-card h2")).toHaveText(["打工摸鱼"]);
  });
}

test("写入失败与打开接口失败分别保留内存清单及本地最近记录", async ({ page, context }) => {
  const requests = await mockCatalog(context, 3, true);
  await page.goto("/");
  await openGame(page, card(page, "打工摸鱼").locator(".catalog-card__open"));
  await expect.poll(async () => (await savedLibrary(page))?.recent.map((item) => item.projectId)).toEqual(["901"]);
  // 只阻止本功能存储键，避免改变站点鉴权或访客标识的既有行为。
  await page.evaluate((key) => {
    const original = Storage.prototype.setItem;
    Storage.prototype.setItem = function (name: string, value: string) {
      if (name === key) throw new DOMException("test quota", "QuotaExceededError");
      original.call(this, name, value);
    };
  }, storageKey);
  await card(page, "合成大西瓜").getByRole("button", { name: "加入想玩", exact: true }).click();
  await expect(page.getByText(storageWarning, { exact: true })).toBeVisible();
  await openGame(page, card(page, "合成大西瓜").locator(".catalog-card__open"));
  await expect.poll(() => requests.opened).toEqual(["901", "902"]);
  await page.locator(".catalog-library-filters").getByRole("button", { name: "最近打开", exact: true }).click();
  await expect(page.locator(".catalog-card h2")).toHaveText(["合成大西瓜", "打工摸鱼"]);
  expect((await savedLibrary(page))?.recent.map((item) => item.projectId)).toEqual(["901"]);
  await expect(card(page, "打工摸鱼").locator(".catalog-card__views")).toHaveAttribute("aria-label", "0 次浏览");
});

test("想玩满额提示后可移出再加入，不删除现存的未收录标识", async ({ page, context }) => {
  await mockCatalog(context);
  await seedLibrary(context, {
    version: 1, wantedIds: ["901", ...Array.from({ length: 499 }, (_, index) => `unlisted-${index}`)], recent: [],
  });
  await page.goto("/");
  await card(page, "合成大西瓜").getByRole("button", { name: "加入想玩", exact: true }).click();
  await expect(page.getByText("想玩清单最多保存 500 款游戏，请先移出部分游戏。", { exact: true })).toBeVisible();
  expect((await savedLibrary(page))?.wantedIds).toHaveLength(500);
  await card(page, "打工摸鱼").getByRole("button", { name: "移出想玩", exact: true }).click();
  await card(page, "合成大西瓜").getByRole("button", { name: "加入想玩", exact: true }).click();
  await expect(card(page, "合成大西瓜").getByRole("button", { name: "移出想玩", exact: true })).toHaveAttribute("aria-pressed", "true");
  expect((await savedLibrary(page))?.wantedIds).toContain("902");
  expect((await savedLibrary(page))?.wantedIds).toHaveLength(500);
});

for (const width of [320, 390, 940, 1280]) {
  test(`个人筛选与想玩按钮在 ${width}px 无横向溢出且可触摸操作`, async ({ page, context }, testInfo) => {
    await mockCatalog(context);
    await page.setViewportSize({ width, height: 1000 });
    await page.goto("/");
    await expect(page.locator(".catalog-card")).toHaveCount(3);
    const wanted = card(page, "打工摸鱼").getByRole("button", { name: "加入想玩", exact: true });
    const targets = [...await page.locator(".catalog-library-filters button").all(), wanted];
    for (const target of targets) {
      const bounds = await target.boundingBox();
      expect(bounds?.width).toBeGreaterThanOrEqual(44);
      expect(bounds?.height).toBeGreaterThanOrEqual(44);
    }
    await wanted.click();
    await expect(card(page, "打工摸鱼").getByRole("button", { name: "移出想玩", exact: true })).toHaveAttribute("aria-pressed", "true");
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    expect(overflow).toBeLessThanOrEqual(1);
    await page.screenshot({ path: testInfo.outputPath(`personal-library-${width}.png`), fullPage: true });
  });
}

test("首次评分成功后收起面板并恢复焦点，重新打开只读评分不重复提交", async ({ page, context }) => {
  const requests = await mockCatalog(context);
  await page.goto("/");
  const first = card(page, "打工摸鱼");
  const trigger = first.getByRole("button", { name: "查看打工摸鱼的评分", exact: true });
  const panel = first.getByRole("group", { name: "打工摸鱼的评分", exact: true });

  // 成功结果由既有评分响应更新真实查询缓存，关闭后应把键盘操作交回当前卡片。
  await trigger.focus();
  await trigger.press("Enter");
  const score = first.getByRole("button", { name: "给打工摸鱼评3分", exact: true });
  await score.focus();
  await score.press("Enter");
  await expect.poll(() => requests.ratings).toEqual([{ id: "901", score: 3 }]);
  await expect(first.getByText("1 人评分", { exact: true })).toBeVisible();
  await expect(page.locator(".catalog-card__rating-panel")).toHaveCount(0);
  await expect(trigger).toHaveAttribute("aria-expanded", "false");
  await expect(trigger).toBeFocused();

  // 已评分项目只展示首次分值；没有可操作分值时，键盘焦点留在只读面板上。
  await trigger.press("Enter");
  await expect(panel).toBeFocused();
  const readonlyScores = panel.getByRole("button", { name: "打工摸鱼已评3分，不能修改", exact: true });
  await expect(readonlyScores).toHaveCount(5);
  for (const readonlyScore of await readonlyScores.all()) await expect(readonlyScore).toBeDisabled();
  await panel.press("Enter");
  await page.keyboard.press("Escape");
  await expect(trigger).toBeFocused();
  await expect(page.locator(".catalog-card__rating-panel")).toHaveCount(0);
  expect(requests.ratings).toEqual([{ id: "901", score: 3 }]);
  expect(requests.opened).toEqual([]);
  expect((await savedLibrary(page))?.recent ?? []).toEqual([]);
  expect(requests.unexpectedRequests).toEqual([]);
});

test("开发预览保留开发进度入口且不开放评分，原生打开仍记录最近访问", async ({ page, context }) => {
  const requests = await mockCatalog(context);
  const fixture = catalogFixture();
  const category = fixture.categories[0]!;
  // 仅本用例追加开发预览，沿用模拟目标地址与拦截规则，不改其他用例的目录数据。
  category.projects.push({
    ...category.projects[0]!,
    id: "904", slug: "fablespace", name: "预览数据原名称", url: "https://library-game.invalid/play/904",
  });
  await context.route("**/api/v1/catalog", (route) => route.fulfill({
    json: { data: fixture }, headers: { "access-control-allow-origin": "*" },
  }));
  await page.goto("/");
  const preview = card(page, "朝花夕拾");
  await expect(preview.locator(".catalog-card__preview-note")).toHaveText("持续开发中");
  await expect(preview.locator(".catalog-card__rating-trigger")).toHaveCount(0);
  await expect(preview.locator(".catalog-card__rating-panel")).toHaveCount(0);
  const open = preview.locator(".catalog-card__open");
  await expect(open).toHaveText("开发进度");
  await expect(open).toHaveAttribute("href", "https://library-game.invalid/play/904");
  await expect(open).toHaveAttribute("target", "_blank");
  await openGame(page, open, "keyboard");
  await expect.poll(() => requests.opened).toEqual(["904"]);
  await expect.poll(async () => (await savedLibrary(page))?.recent.map((item) => item.projectId)).toEqual(["904"]);
  expect(requests.ratings).toEqual([]);
  expect(requests.unexpectedRequests).toEqual([]);
});

test("切换筛选或榜单关闭旧评分，顶部搜索返回游戏目录并聚焦输入框", async ({ page, context }) => {
  const requests = await mockCatalog(context);
  await page.goto("/");
  const trigger = card(page, "打工摸鱼").getByRole("button", { name: "查看打工摸鱼的评分", exact: true });
  const category = page.getByRole("combobox", { name: "游戏分类", exact: true });

  // 卡片被分类筛选隐藏后不能遗留评分面板，恢复全部分类也不能重新展开旧面板。
  await trigger.click();
  await expect(trigger).toHaveAttribute("aria-expanded", "true");
  await category.selectOption("casual");
  await expect(page.locator(".catalog-card h2")).toHaveText(["合成大西瓜"]);
  await expect(page.locator(".catalog-card__rating-panel")).toHaveCount(0);
  await category.selectOption("all");
  await expect(trigger).toHaveAttribute("aria-expanded", "false");

  // 榜单与目录共用导航；顶部搜索必须切回目录并把键盘焦点放到真实搜索输入框。
  await trigger.click();
  await page.locator(".catalog-view-tabs").getByRole("button", { name: "作者榜", exact: true }).click();
  await expect(page.getByRole("heading", { name: "作者榜", exact: true })).toBeVisible();
  await expect(page.locator(".catalog-card__rating-panel")).toHaveCount(0);
  await page.getByRole("button", { name: "搜索游戏", exact: true }).click();
  const search = page.getByRole("searchbox", { name: "搜索游戏名称", exact: true });
  await expect(search).toBeFocused();
  await expect(page.locator(".catalog-view-tabs").getByRole("button", { name: "游戏目录", exact: true }))
    .toHaveAttribute("aria-pressed", "true");
  await expect(trigger).toHaveAttribute("aria-expanded", "false");

  // 搜索同样关闭旧面板，筛选与导航本身都不提交评分或打开游戏。
  await trigger.click();
  await search.fill("合成");
  await page.getByRole("button", { name: "搜索", exact: true }).click();
  await expect(page.locator(".catalog-card h2")).toHaveText(["合成大西瓜"]);
  await expect(page.locator(".catalog-card__rating-panel")).toHaveCount(0);
  expect(requests.ratings).toEqual([]);
  expect(requests.opened).toEqual([]);
  expect(requests.unexpectedRequests).toEqual([]);
});

test("作者搜索保留原始名次，榜外结果不会变成领奖台冠军，无匹配保留空状态", async ({ page, context }) => {
  const requests = await mockCatalog(context);
  const fixture = catalogFixture(4);
  // 只给本用例的四组作者设置不同总心数，预期名次来自排序规则而非搜索后的数组位置。
  for (const category of fixture.categories) {
    for (const game of category.projects) {
      game.rating_score_sum = ({ "901": 40, "902": 30, "903": 20, "904": 10 } as Record<string, number>)[game.id]!;
      if (game.id === "904") game.author_name = "榜外测试作者";
    }
  }
  await context.route("**/api/v1/catalog", (route) => route.fulfill({
    json: { data: fixture }, headers: { "access-control-allow-origin": "*" },
  }));
  await page.goto("/");
  await page.locator(".catalog-view-tabs").getByRole("button", { name: "作者榜", exact: true }).click();
  await expect(page.locator('.catalog-podium__place[data-rank="1"] .catalog-podium__name')).toHaveText("测试作者甲");
  await expect(page.locator('.catalog-podium__place[data-rank="2"] .catalog-podium__name')).toHaveText("测试作者乙");
  await expect(page.locator('.catalog-podium__place[data-rank="3"] .catalog-podium__name')).toHaveText("原创");
  await expect(page.locator('.catalog-leaderboard__row[data-rank="4"] .catalog-leaderboard__identity strong'))
    .toHaveText("榜外测试作者");

  // 第二名被单独搜索时仍保留第二名的位置与有序列表值，不重新生成冠军。
  const search = page.getByRole("searchbox", { name: "搜索作者", exact: true });
  await search.fill("测试作者乙");
  await expect(page.locator(".catalog-podium__place")).toHaveCount(1);
  await expect(page.locator(".catalog-podium__place")).toHaveAttribute("data-rank", "2");
  await expect(page.locator(".catalog-podium__place")).toHaveAttribute("value", "2");
  await expect(page.locator(".catalog-podium__place--1")).toHaveCount(0);

  // 原第四名只属于其他作者列表；无结果仍显示原空状态，不生成占位领奖台。
  await search.fill("榜外测试作者");
  await expect(page.locator(".catalog-podium__place")).toHaveCount(0);
  await expect(page.locator(".catalog-leaderboard__row")).toHaveCount(1);
  await expect(page.locator(".catalog-leaderboard__row")).toHaveAttribute("data-rank", "4");
  await expect(page.locator(".catalog-leaderboard__row")).toHaveAttribute("value", "4");
  await search.fill("不存在的作者");
  await expect(page.locator(".catalog-leaderboard__empty")).toHaveText("没有找到匹配的作者。");
  await expect(page.locator(".catalog-leaderboard__empty")).toHaveAttribute("role", "status");
  await expect(page.locator(".catalog-podium__place, .catalog-leaderboard__row")).toHaveCount(0);
  expect(requests.ratings).toEqual([]);
  expect(requests.opened).toEqual([]);
  expect(requests.unexpectedRequests).toEqual([]);
});

test("贡献来源固定第一且只用开源装饰，查看作者作品恢复全部游戏范围", async ({ page, context }) => {
  const requests = await mockCatalog(context, 30);
  await seedLibrary(context, { version: 1, wantedIds: ["902"], recent: [] });
  await page.goto("/");
  await page.locator(".catalog-library-filters").getByRole("button", { name: "想玩清单", exact: true }).click();
  await expect(page.locator(".catalog-card h2")).toHaveText(["合成大西瓜"]);
  await page.locator(".catalog-view-tabs").getByRole("button", { name: "贡献榜", exact: true }).click();

  // 来源项不从个人范围或作者作品中推算排名，也不能把其他作者封面放进来源展示区。
  const source = page.locator('.catalog-podium__place[data-rank="1"]');
  await expect(source.locator(".catalog-podium__name")).toHaveText("martindelophy");
  await expect(source).toHaveAttribute("value", "1");
  await expect(source.locator(".catalog-podium__metric")).toHaveText("开源贡献");
  await expect(source.locator(".catalog-podium__source-art svg[data-icon='github']")).toBeVisible();
  await expect(source.locator(".catalog-podium__art > img")).toHaveCount(0);
  await expect(source.getByRole("button", { name: "查看martindelophy的作品", exact: true })).toHaveCount(0);
  for (const link of [source.locator(".catalog-podium__name"), source.locator(".catalog-leaderboard__open")]) {
    await expect(link).toHaveAttribute("href", "https://github.com/MartinDelophy/awesome-gpt-6-astra");
    await expect(link).toHaveAttribute("target", "_blank");
    await expect(link).toHaveAttribute("rel", "noopener noreferrer");
  }

  // 贡献榜查看作品也必须恢复公开作者的完整作品，不能继续受之前的个人想玩范围限制。
  const author = page.locator(".catalog-podium__place").filter({ hasText: "测试作者甲" });
  await expect(author).toHaveAttribute("data-rank", "2");
  await author.getByRole("button", { name: "查看测试作者甲的作品", exact: true }).click();
  await expect(page.locator(".catalog-library-filters").getByRole("button", { name: "全部游戏", exact: true }))
    .toHaveAttribute("aria-pressed", "true");
  await expect(page.locator(".catalog-results")).toHaveText("28 个游戏");
  await expect(page.locator(".catalog-author-selection")).toContainText("测试作者甲");
  expect((await savedLibrary(page))?.wantedIds).toEqual(["902"]);
  expect(requests.ratings).toEqual([]);
  expect(requests.opened).toEqual([]);
  expect(requests.unexpectedRequests).toEqual([]);
});

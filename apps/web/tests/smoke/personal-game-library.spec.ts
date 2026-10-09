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
        // 卡片已无评分入口；拦截意外写入并显式失败，不能连接真实评分接口。
        await route.fulfill({ status: 410, json: { error: { code: "TEST_RATING_REMOVED", message: "test" } }, headers });
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

test("想玩可用键盘切换、刷新恢复，并保持收藏与原生打开相互独立", async ({ page, context }) => {
  const requests = await mockCatalog(context);
  await page.goto("/");
  await expect(page.getByText("记录保存在当前浏览器，清理浏览器数据后会丢失。")).toBeVisible();
  const first = card(page, "打工摸鱼");
  await expect(first.locator(".catalog-card__author")).toHaveText("测试作者甲");
  await first.getByRole("button", { name: "加入想玩", exact: true }).focus();
  await page.keyboard.press("Space");
  await expect(first.getByRole("button", { name: "移出想玩", exact: true })).toHaveAttribute("aria-pressed", "true");
  expect(requests.opened).toEqual([]);
  expect(requests.ratings).toEqual([]);
  expect(context.pages()).toHaveLength(1);
  expect((await savedLibrary(page))?.wantedIds).toEqual(["901"]);
  expect((await savedLibrary(page))?.recent).toEqual([]);
  await page.reload();
  await page.locator(".catalog-library-filters").getByRole("button", { name: "想玩清单", exact: true }).click();
  await expect(page.locator(".catalog-card")).toHaveCount(1);
  await expect(first.getByRole("button", { name: "移出想玩", exact: true })).toHaveAttribute("aria-pressed", "true");
  await openGame(page, first.locator(".catalog-card__open"));
  await expect.poll(() => requests.opened).toEqual(["901"]);
  await expect(first.locator(".catalog-card__heat")).toHaveAttribute("aria-label", "热度 1");
  expect((await savedLibrary(page))?.wantedIds).toEqual(["901"]);
  expect((await savedLibrary(page))?.recent.map((item) => item.projectId)).toEqual(["901"]);
  await first.getByRole("button", { name: "移出想玩", exact: true }).click();
  await expect(page.getByText("还没有加入想玩的游戏", { exact: true })).toBeVisible();
  expect((await savedLibrary(page))?.wantedIds).toEqual([]);
  expect(requests.ratings).toEqual([]);
  expect(requests.unexpectedRequests).toEqual([]);
});

test("排序下拉框沿用最新和热门顺序，网格列表切换保留排序与想玩记录", async ({ page, context }) => {
  const requests = await mockCatalog(context);
  const fixture = catalogFixture();
  // 历史评分仍参与热度；排序沿用浏览量加评分总分五倍的既有规则。
  for (const category of fixture.categories) {
    for (const game of category.projects) {
      game.view_count = ({ "901": 2, "902": 10, "903": 20 } as Record<string, number>)[game.id]!;
      game.rating_score_sum = ({ "901": 6, "902": 1, "903": 0 } as Record<string, number>)[game.id]!;
    }
  }
  await context.route("**/api/v1/catalog", (route) => route.fulfill({
    json: { data: fixture }, headers: { "access-control-allow-origin": "*" },
  }));
  await page.goto("/");
  const sort = page.getByRole("combobox", { name: "游戏排序", exact: true });
  await expect(sort).toHaveValue("latest");
  await expect(page.locator(".catalog-card h2")).toHaveText(["打工摸鱼", "合成大西瓜", "蛇蛇出洞"]);
  await expect(card(page, "打工摸鱼").locator(".catalog-card__heat")).toHaveAttribute("aria-label", "热度 32");
  await expect(card(page, "合成大西瓜").locator(".catalog-card__heat")).toHaveAttribute("aria-label", "热度 15");
  await sort.selectOption("hot");
  await expect(page.locator(".catalog-card h2")).toHaveText(["打工摸鱼", "蛇蛇出洞", "合成大西瓜"]);
  await card(page, "蛇蛇出洞").getByRole("button", { name: "加入想玩", exact: true }).click();
  await page.getByRole("button", { name: "列表显示", exact: true }).click();
  await expect(page.locator(".catalog-grid")).toHaveClass(/catalog-grid--list/);
  await expect(page.getByRole("button", { name: "列表显示", exact: true })).toHaveAttribute("aria-pressed", "true");
  await expect(sort).toHaveValue("hot");
  await expect(page.locator(".catalog-card h2")).toHaveText(["打工摸鱼", "蛇蛇出洞", "合成大西瓜"]);
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
  await expect(card(page, "打工摸鱼").locator(".catalog-card__heat")).toHaveAttribute("aria-label", "热度 1");
  await openGame(page, card(page, "合成大西瓜").locator(".catalog-card__title-link"), "keyboard");
  await openGame(page, card(page, "蛇蛇出洞").locator(".catalog-card__open"), "middle");
  await card(page, "打工摸鱼").getByRole("button", { name: "查看测试作者甲的作品", exact: true }).click();
  await openGame(page, page.getByRole("dialog").getByRole("link", { name: "打工摸鱼", exact: true }));
  await expect(page.getByRole("dialog")).toBeVisible();
  await page.getByRole("button", { name: "关闭作者窗口", exact: true }).click();
  await expect.poll(() => requests.opened).toEqual(["901", "902", "903", "901"]);
  await expect(card(page, "打工摸鱼").locator(".catalog-card__heat")).toHaveAttribute("aria-label", "热度 2");
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
  await expect(card(page, "打工摸鱼").locator(".catalog-card__heat")).toHaveAttribute("aria-label", "热度 0");
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

test("开发预览保留开发进度入口，原生打开仍记录最近访问", async ({ page, context }) => {
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

test("分类筛选保留原顺序，顶部搜索从榜单返回游戏目录并聚焦输入框", async ({ page, context }) => {
  const requests = await mockCatalog(context);
  await page.goto("/");
  const category = page.getByRole("combobox", { name: "游戏分类", exact: true });

  await category.selectOption("casual");
  await expect(page.locator(".catalog-card h2")).toHaveText(["合成大西瓜"]);
  await category.selectOption("all");
  await expect(page.locator(".catalog-card h2")).toHaveText(["打工摸鱼", "合成大西瓜", "蛇蛇出洞"]);

  // 榜单与目录共用导航；顶部搜索必须切回目录并把键盘焦点放到真实搜索输入框。
  await page.locator(".catalog-view-tabs").getByRole("button", { name: "作者榜", exact: true }).click();
  await expect(page.getByRole("heading", { name: "作者榜", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "搜索游戏", exact: true }).click();
  const search = page.getByRole("searchbox", { name: "搜索游戏名称", exact: true });
  await expect(search).toBeFocused();
  await expect(page.locator(".catalog-view-tabs").getByRole("button", { name: "游戏目录", exact: true }))
    .toHaveAttribute("aria-pressed", "true");

  // 筛选与导航本身不应打开游戏或写入个人最近记录。
  await search.fill("合成");
  await page.getByRole("button", { name: "搜索", exact: true }).click();
  await expect(page.locator(".catalog-card h2")).toHaveText(["合成大西瓜"]);
  expect((await savedLibrary(page))?.recent ?? []).toEqual([]);
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

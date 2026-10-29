import { expect, test, type BrowserContext, type Page } from "@playwright/test";

const baseURL = process.env.PLAYWRIGHT_BASE_URL ?? "http://127.0.0.1:5199";
const writes: string[] = [];

async function readOnlyPreview(context: BrowserContext, catalog?: unknown): Promise<void> {
  await context.route("**/*", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    if (!["GET", "HEAD", "OPTIONS"].includes(request.method())) {
      writes.push(`${request.method()} ${url.pathname}`);
      await route.fulfill({ status: 409, json: { error: { code: "LOCAL_TOPICS_TEST_WRITE_BLOCKED" } } });
      return;
    }
    if (catalog && url.pathname === "/api/v1/catalog") {
      await route.fulfill({ json: catalog });
      return;
    }
    if (!["127.0.0.1", "localhost", "[::1]"].includes(url.hostname)) {
      await route.abort();
      return;
    }
    await route.continue();
  });
}

async function ids(page: Page): Promise<string[]> {
  return page.locator(".catalog-card").evaluateAll((cards) => cards.map((card) => card.getAttribute("data-project-id") ?? ""));
}

test.beforeEach(() => { writes.length = 0; });
test.afterEach(async ({ context }) => {
  expect(writes).toEqual([]);
  expect(context.pages()).toHaveLength(1);
});

test("original four tabs select gameplay topics, survive reload/back, and open real more-topics choices", async ({ page, context }) => {
  await readOnlyPreview(context);
  await page.goto(`${baseURL}/`);
  await expect(page.locator(".catalog-card").first()).toBeVisible();
  const tabs = page.getByRole("navigation", { name: "发现游戏", exact: true });
  await expect(tabs.getByRole("button")).toHaveText(["全部推荐", "经典游戏", "即玩即乐", "更多专题"]);
  await tabs.getByRole("button", { name: "经典游戏", exact: true }).click();
  await expect(page).toHaveURL(/\?topic=classic$/);
  await expect(page.locator(".catalog-card")).toHaveCount(16);
  expect(await ids(page)).toEqual(expect.arrayContaining(["4", "84", "96", "103", "109", "206", "219"]));
  expect(new URL(page.url()).searchParams.has("author")).toBe(false);
  expect(new URL(page.url()).searchParams.has("feed")).toBe(false);
  await page.reload();
  await expect(tabs.getByRole("button", { name: "经典游戏", exact: true })).toHaveAttribute("aria-pressed", "true");
  await expect(page.locator(".catalog-card")).toHaveCount(16);
  await tabs.getByRole("button", { name: "即玩即乐", exact: true }).click();
  await expect(page).toHaveURL(/\?topic=quick$/);
  await expect(page.locator(".catalog-card")).toHaveCount(13);
  expect(await ids(page)).toEqual(expect.arrayContaining(["2", "17", "75", "182", "189", "190"]));
  expect(await ids(page)).not.toContain("84");
  await page.goBack();
  await expect(page).toHaveURL(/\?topic=classic$/);
  await expect(page.locator(".catalog-card")).toHaveCount(16);
  await tabs.getByRole("button", { name: "更多专题", exact: true }).click();
  const dialog = page.getByRole("dialog", { name: "更多专题", exact: true });
  await expect(dialog).toBeVisible();
  await expect(dialog.locator(".catalog-topics__count")).toHaveText(["4 款游戏", "2 款游戏", "3 款游戏", "4 款游戏"]);
  await dialog.getByRole("button", { name: /棋盘对弈/ }).click();
  await expect(page).toHaveURL(/\?topic=board-duels$/);
  await expect(dialog).not.toBeVisible();
  await expect(page.locator(".catalog-card")).toHaveCount(4);
  expect((await ids(page)).sort()).toEqual(["103", "109", "84", "96"]);
});

test("unclassified or empty topic data stays empty and clear filters returns the real project", async ({ page, context }) => {
  const project = { id: "fixture-unclassified", slug: "unclassified", name: "未注明玩法的项目", url: "https://example.invalid/game", kind: "internal", author_name: "original", description: null, author_url: null, icon_url: null, created_at: "2026-10-29T00:00:00Z", average_score: null, rating_count: 0, rating_score_sum: 0, view_count: 999999, my_score: null, ai_rating: null };
  await readOnlyPreview(context, { data: { categories: [{ id: "fixture-category", slug: "casual", name: "休闲", icon_url: null, projects: [project] }] }, meta: {} });
  await page.goto(`${baseURL}/games?topic=classic`);
  await expect(page.getByRole("heading", { name: "经典游戏", exact: true })).toBeVisible();
  await expect(page.locator(".catalog-card")).toHaveCount(0);
  await expect(page.getByText("没有找到匹配的游戏", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "清除筛选", exact: true }).click();
  await expect(page).toHaveURL(/\/games$/);
  await expect(page.locator(".catalog-card")).toHaveCount(2);
  await page.getByRole("button", { name: "更多专题", exact: true }).click();
  const dialog = page.getByRole("dialog", { name: "更多专题", exact: true });
  await expect(dialog.locator(".catalog-topics__count")).toHaveText(["0 款游戏", "0 款游戏", "0 款游戏", "0 款游戏"]);
  await dialog.getByRole("button", { name: /棋盘对弈/ }).click();
  await expect(page.locator(".catalog-card")).toHaveCount(0);
  await expect(page.getByRole("button", { name: "清除筛选", exact: true })).toBeVisible();
});

test("topic and search combine while the existing site-source rail remains a separate filter", async ({ page, context }) => {
  await readOnlyPreview(context);
  await page.goto(`${baseURL}/games?topic=board-duels&q=Chess`);
  await expect(page.locator(".catalog-card")).toHaveCount(2);
  expect((await ids(page)).sort()).toEqual(["103", "84"]);
  await page.getByRole("navigation", { name: "游戏导航", exact: true }).getByRole("button", { name: "站内", exact: true }).click();
  await expect(page).toHaveURL(/\?author=original$/);
  await expect(page.locator(".catalog-card")).toHaveCount(5);
  await expect(page.getByRole("navigation", { name: "发现游戏", exact: true }).getByRole("button", { name: "经典游戏", exact: true })).toHaveAttribute("aria-pressed", "false");
});

import { existsSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { expect, test, type BrowserContext, type Locator, type Page, type Route } from "@playwright/test";

import type { CatalogCategoryResponse, CatalogProjectResponse } from "../../src/features/catalog/model";
import { catalogPublicFixture } from "./catalog-public-fixture";

const baseURL = process.env.PLAYWRIGHT_BASE_URL ?? "http://127.0.0.1:5184";
const storageKey = "parallellines.catalog-library.v1";
const staticRoot = path.resolve(fileURLToPath(new URL("../../../../static/web/", import.meta.url)));
const publicRoot = path.resolve(fileURLToPath(new URL("../../public/", import.meta.url)));
const wideCover = path.resolve(staticRoot, "catalog/2026-09-24-v1/covers/clock-out.webp");

test.use({ serviceWorkers: "block" });

/** 同时提供正式横封、正式竖封和晚到的上传封面，项目 ID 与响应顺序固定。 */
function fixture(): CatalogCategoryResponse[] {
  const project = (id: number, index: number): CatalogProjectResponse => ({
    id: String(id), slug: index === 0 ? "clock-out" : index === 1 ? "miami-flap" : `layout-project-${id}`,
    name: `布局验收游戏${id}`, url: `https://layout-game.invalid/play/${id}`, kind: "external",
    description: "仅用于本地布局回归", author_name: "布局测试作者", author_url: null,
    icon_url: index < 2 ? null : "/uploads/3000/content",
    created_at: new Date(Date.UTC(2026, 10, 10) - index * 1000).toISOString(),
    average_score: null, rating_count: 0, rating_score_sum: 0, view_count: 0, my_score: null,
  });
  return [
    { id: "1", slug: "casual", name: "休闲", icon_url: null, projects: Array.from({ length: 48 }, (_, index) => project(3001 + index, index)) },
    { id: "2", slug: "horror", name: "恐怖", icon_url: null, projects: Array.from({ length: 4 }, (_, index) => project(4001 + index, index + 2)) },
  ];
}

/** 分类请求可逐批放行；接口、图片和游戏目标均在本地拦截，不连接数据库或外站。 */
async function mockCatalog(context: BrowserContext, controlled = false) {
  const localOrigin = new URL(baseURL).origin;
  expect(["127.0.0.1", "localhost", "[::1]"].includes(new URL(baseURL).hostname)).toBe(true);
  const categories = fixture();
  const pending: Array<{ route: Route; url: URL; finish: () => void }> = [];
  const views: string[] = [];
  const navigations: string[] = [];
  const unexpected: string[] = [];
  await context.route("**/*", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const headers = { "access-control-allow-origin": "*" };
    if (url.hostname === "layout-game.invalid" && request.resourceType() === "document") {
      navigations.push(url.href);
      await route.fulfill({ contentType: "text/html; charset=utf-8", body: "<!doctype html><meta charset='utf-8'><h1>本地模拟游戏目标</h1>" });
      return;
    }
    if (url.pathname.startsWith("/static/web/")) {
      const key = url.pathname.slice("/static/web/".length);
      const source = [staticRoot, publicRoot].map((root) => ({ root, file: path.resolve(root, key) }))
        .find(({ root, file }) => file.startsWith(root + path.sep) && existsSync(file))?.file;
      expect(source, `本地图片缺失：${key}`).toBeDefined();
      await route.fulfill({ path: source!, headers });
      return;
    }
    if (/^\/(?:api\/v1\/)?uploads\/3000\/content$/.test(url.pathname)) {
      await route.fulfill({ path: wideCover, headers });
      return;
    }
    if (url.pathname.startsWith("/api/")) {
      const view = /\/catalog\/projects\/(\d+)\/views$/.exec(url.pathname);
      if (view && request.method() === "POST") {
        views.push(view[1]!);
        await route.fulfill({ json: { data: { project_id: view[1], view_count: views.length } }, headers });
      } else if (request.method() === "GET" && url.pathname === "/api/v1/site/settings") {
        await route.fulfill({ json: { data: { settings: {}, updated_at: null } }, headers });
      } else if (request.method() === "GET" && controlled && url.pathname === "/api/v1/catalog/categories/casual/projects") {
        await new Promise<void>((finish) => pending.push({ route, url, finish }));
      } else {
        const response = request.method() === "GET" ? catalogPublicFixture(url, categories) : undefined;
        if (response) await route.fulfill({ json: response, headers });
        else {
          unexpected.push(`${request.method()} ${url.href}`);
          await route.fulfill({ status: 409, json: { error: { code: "TEST_UNEXPECTED_REQUEST", message: "未声明的请求" } }, headers });
        }
      }
      return;
    }
    if (url.origin !== localOrigin || !["GET", "HEAD"].includes(request.method())) {
      unexpected.push(`${request.method()} ${url.href}`);
      await route.abort();
      return;
    }
    await route.continue();
  });
  return {
    pending, views, navigations, unexpected,
    /** 只处理已经暂停的一批；可模拟少量首批或同一游标失败，重试仍由真实页面触发。 */
    async respond(count?: number, fail = false) {
      await expect.poll(() => pending.length).toBeGreaterThan(0);
      const item = pending.shift()!;
      const cursor = item.url.searchParams.get("cursor");
      if (count !== undefined) item.url.searchParams.set("limit", String(count));
      await item.route.fulfill(fail
        ? { status: 503, json: { error: { code: "TEST_PAGE_UNAVAILABLE", message: "这批游戏加载失败，请重试。" } } }
        : { json: catalogPublicFixture(item.url, categories) });
      item.finish();
      return cursor;
    },
  };
}

/** 使用文档坐标排除浏览器滚动锚定的影响，比较目标栏高度和下一栏真实位置。 */
async function layout(page: Page) {
  return page.evaluate(() => {
    const section = document.querySelector('[data-category-section="casual"]')!.getBoundingClientRect();
    const rail = document.querySelector('[data-category-rail="casual"]')!.getBoundingClientRect();
    const viewport = document.querySelector('[data-category-rail="casual"] .catalog-category-rail__viewport')!.getBoundingClientRect();
    const next = document.querySelector('[data-category-section="horror"]')!.getBoundingClientRect();
    return { sectionHeight: section.height, railHeight: rail.height, viewportHeight: viewport.height, nextTop: next.top + scrollY };
  });
}

async function expectStable(page: Page, baseline: Awaited<ReturnType<typeof layout>>) {
  const actual = await layout(page);
  for (const key of Object.keys(baseline) as Array<keyof typeof baseline>) {
    expect(Math.abs(actual[key] - baseline[key]), `${key} 不随加载状态变化`).toBeLessThanOrEqual(1);
  }
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
}

/** 必须实际存在并解码图片，避免空集合使比例及可见性检查误通过。 */
async function decodeCovers(cards: Locator, count: number) {
  const images = cards.locator(".catalog-card__cover img");
  await expect(images).toHaveCount(count);
  for (const image of await images.all()) {
    await image.scrollIntoViewIfNeeded();
    await expect.poll(() => image.evaluate((node: HTMLImageElement) => node.complete && node.naturalWidth > 0 && node.naturalHeight > 0)).toBe(true);
    await image.evaluate((node: HTMLImageElement) => node.decode());
  }
}

/** 星星可见区域的四角必须位于封面的圆角内；透明点击区不作为可见图案测量。 */
async function expectStarInsideCover(card: Locator) {
  const geometry = await card.evaluate((node) => {
    const cover = node.querySelector<HTMLElement>(".catalog-card__cover")!;
    const button = node.querySelector<HTMLElement>(".catalog-card__wanted")!;
    const bounds = cover.getBoundingClientRect();
    const star = button.querySelector("svg")!.getBoundingClientRect();
    return { width: bounds.width, height: bounds.height, radius: Number.parseFloat(getComputedStyle(cover).borderTopRightRadius),
      points: [[star.left - bounds.left, star.top - bounds.top], [star.right - bounds.left, star.top - bounds.top],
        [star.left - bounds.left, star.bottom - bounds.top], [star.right - bounds.left, star.bottom - bounds.top]],
      overflowX: getComputedStyle(node).overflowX, overflowY: getComputedStyle(node).overflowY };
  });
  const radius = Math.min(geometry.radius, geometry.width / 2, geometry.height / 2);
  for (const [x, y] of geometry.points) {
    expect(x).toBeGreaterThanOrEqual(0);
    expect(x).toBeLessThanOrEqual(geometry.width);
    expect(y).toBeGreaterThanOrEqual(0);
    expect(y).toBeLessThanOrEqual(geometry.height);
    const centerX = Math.min(geometry.width - radius, Math.max(radius, x!));
    const centerY = Math.min(geometry.height - radius, Math.max(radius, y!));
    expect(Math.hypot(x! - centerX, y! - centerY)).toBeLessThanOrEqual(radius + .5);
  }
  expect(geometry.overflowX).toBe("visible");
  expect(geometry.overflowY).toBe("visible");
}

test("1440、390、320px 延迟首批、补页及失败重试不改变分类布局", async ({ page, context }, testInfo) => {
  test.setTimeout(90_000);
  const requests = await mockCatalog(context, true);
  await page.emulateMedia({ reducedMotion: "reduce" });
  for (const width of [1440, 390, 320]) {
    await page.setViewportSize({ width, height: 1000 });
    await page.goto("/games");
    const rail = page.locator('[data-category-rail="casual"]');
    await rail.scrollIntoViewIfNeeded();
    await page.evaluate(async () => { await document.fonts.ready; });
    await expect(rail).toHaveAttribute("data-load-state", "loading");
    await expect(rail.getByRole("status")).toContainText("正在加载休闲游戏");
    await expect(rail.locator(".catalog-card")).toHaveCount(0);
    const baseline = await layout(page);
    await requests.respond(3);
    await expect(rail.locator(".catalog-card")).toHaveCount(3);
    await expectStable(page, baseline);
    // 首批不足一屏时放行必要后续批，仍由真实覆盖算法决定请求数量。
    for (let step = 0; step < 3 && await rail.getAttribute("data-load-state") !== "ready"; step++) {
      await expect.poll(async () => requests.pending.length > 0 || await rail.getAttribute("data-load-state") === "ready").toBe(true);
      if (requests.pending.length) await requests.respond();
    }
    await expect(rail).toHaveAttribute("data-load-state", "ready");
    await expectStable(page, baseline);
    const initialIds = await rail.locator(".catalog-card").evaluateAll((nodes) => nodes.map((node) => node.getAttribute("data-project-id")));
    await rail.getByRole("button", { name: "下一组休闲游戏", exact: true }).click();
    await expect.poll(() => requests.pending.length).toBeGreaterThan(0);
    await expect(rail).toHaveAttribute("data-load-state", "loading-more");
    await expect(rail.getByRole("status")).toContainText("正在加载休闲游戏");
    await expectStable(page, baseline);
    await rail.screenshot({ path: testInfo.outputPath(`rail-loading-${width}.png`) });
    await requests.respond();
    await expect(rail).toHaveAttribute("data-load-state", "ready");
    await expectStable(page, baseline);
    const appendedIds = await rail.locator(".catalog-card").evaluateAll((nodes) => nodes.map((node) => node.getAttribute("data-project-id")));
    expect(appendedIds.slice(0, initialIds.length)).toEqual(initialIds);
    await rail.getByRole("button", { name: "下一组休闲游戏", exact: true }).click();
    const failedCursor = await requests.respond(undefined, true);
    await expect(rail).toHaveAttribute("data-load-state", "error");
    await expect(rail.getByRole("alert")).toBeVisible();
    const retry = rail.getByRole("button", { name: "重新加载休闲游戏", exact: true });
    // 圆角内的四角和中心都须命中重试按钮，不能被左右翻页箭头遮住。
    const retryArea = await retry.evaluate((button) => {
      const rect = button.getBoundingClientRect();
      const points = [[rect.left + 3, rect.top + 3], [rect.right - 3, rect.top + 3],
        [rect.left + 3, rect.bottom - 3], [rect.right - 3, rect.bottom - 3],
        [rect.left + rect.width / 2, rect.top + rect.height / 2]];
      return { width: rect.width, height: rect.height, hits: points.map(([x, y]) => {
        const hit = document.elementFromPoint(x!, y!);
        return hit === button || button.contains(hit);
      }) };
    });
    expect(retryArea.width).toBeGreaterThanOrEqual(44);
    expect(retryArea.height).toBeGreaterThanOrEqual(44);
    expect(retryArea.hits).toEqual([true, true, true, true, true]);
    await expectStable(page, baseline);
    await rail.screenshot({ path: testInfo.outputPath(`rail-error-${width}.png`) });
    await retry.click();
    await expect.poll(() => requests.pending.length).toBeGreaterThan(0);
    expect(requests.pending[0]!.url.searchParams.get("cursor")).toBe(failedCursor);
    await expectStable(page, baseline);
    await requests.respond();
    await expect(rail).toHaveAttribute("data-load-state", "ready");
    await expectStable(page, baseline);
    const finalIds = await rail.locator(".catalog-card").evaluateAll((nodes) => nodes.map((node) => node.getAttribute("data-project-id")));
    expect(finalIds.slice(0, appendedIds.length)).toEqual(appendedIds);
    const firstCards = rail.locator('.catalog-card[data-project-id="3001"], .catalog-card[data-project-id="3002"]');
    await decodeCovers(firstCards, 2);
    const ratios = await firstCards.evaluateAll((nodes) => nodes.map((node) => {
      const cover = node.querySelector(".catalog-card__cover")!.getBoundingClientRect();
      const image = node.querySelector<HTMLImageElement>("img")!;
      return Math.abs(cover.width / cover.height - image.naturalWidth / image.naturalHeight);
    }));
    expect(ratios.every((difference) => difference < .01)).toBe(true);
    await expectStable(page, baseline);
  }
  expect(requests.views).toEqual([]);
  expect(requests.navigations).toEqual([]);
  expect(requests.unexpected).toEqual([]);
});

test("横封、窄竖封与推荐大卡的收藏星星和键盘焦点均留在封面内", async ({ page, context }, testInfo) => {
  const requests = await mockCatalog(context);
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/games");
  const targets = [
    { name: "featured", card: page.locator('.catalog-group--featured .catalog-card[data-hero-slot="0"]') },
    { name: "landscape", card: page.locator('[data-category-rail="casual"] .catalog-card[data-project-id="3001"]') },
    { name: "portrait", card: page.locator('[data-category-rail="casual"] .catalog-card[data-project-id="3002"]') },
  ];
  for (const target of targets) {
    await decodeCovers(target.card, 1);
    await target.card.hover();
    const wanted = target.card.locator(".catalog-card__wanted");
    await expect(wanted).toHaveCSS("opacity", "1");
    await expectStarInsideCover(target.card);
    await target.card.locator(".catalog-card__open").focus();
    await page.keyboard.press("Tab");
    await expect(wanted).toBeFocused();
    const focus = await wanted.evaluate((node) => {
      const style = getComputedStyle(node);
      return { width: Number.parseFloat(style.outlineWidth), offset: Number.parseFloat(style.outlineOffset) };
    });
    expect(focus.width).toBeGreaterThan(0);
    expect(focus.offset).toBeLessThanOrEqual(-focus.width);
    await expectStarInsideCover(target.card);
    await target.card.screenshot({ path: testInfo.outputPath(`star-${target.name}-1440.png`) });
  }
  const instances = page.locator('.catalog-card[data-project-id="3001"] .catalog-card__wanted');
  await expect(instances).toHaveCount(2);
  await targets[1]!.card.hover();
  await targets[1]!.card.locator(".catalog-card__wanted").click();
  for (const wanted of await instances.all()) await expect(wanted).toHaveAttribute("aria-pressed", "true");
  expect(await page.evaluate((key) => JSON.parse(localStorage.getItem(key)!).wantedIds, storageKey)).toEqual(["3001"]);
  await targets[0]!.card.locator(".catalog-card__open").focus();
  await page.keyboard.press("Tab");
  await page.keyboard.press("Space");
  for (const wanted of await instances.all()) await expect(wanted).toHaveAttribute("aria-pressed", "false");
  expect(requests.views).toEqual([]);
  expect(requests.navigations).toEqual([]);
  expect(requests.unexpected).toEqual([]);
  expect(context.pages()).toHaveLength(1);
});

test.describe("390px 原生触摸", () => {
  test.use({ viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true, deviceScaleFactor: 1 });

  test("拖动取消长按，长按收藏不打开游戏，随后轻触仍只打开一次", async ({ page, context }, testInfo) => {
    const requests = await mockCatalog(context);
    await page.emulateMedia({ reducedMotion: "reduce" });
    await page.goto("/games");
    const card = page.locator('[data-category-rail="casual"] .catalog-card[data-project-id="3001"]');
    await decodeCovers(card, 1);
    await card.scrollIntoViewIfNeeded();
    const session = await context.newCDPSession(page);
    const cover = await card.locator(".catalog-card__cover").boundingBox();
    const point = { x: cover!.x + cover!.width / 2, y: cover!.y + cover!.height / 2 };
    const finger = { ...point, id: 1, radiusX: 2, radiusY: 2, force: 1 };
    await session.send("Input.dispatchTouchEvent", { type: "touchStart", touchPoints: [finger] });
    await session.send("Input.dispatchTouchEvent", { type: "touchMove", touchPoints: [{ ...finger, x: point.x + 25 }] });
    await page.waitForTimeout(650);
    await expect(card).not.toHaveClass(/catalog-card--touch-actions/);
    await session.send("Input.dispatchTouchEvent", { type: "touchEnd", touchPoints: [] });
    await card.scrollIntoViewIfNeeded();
    const current = await card.locator(".catalog-card__cover").boundingBox();
    await session.send("Input.dispatchTouchEvent", { type: "touchStart", touchPoints: [{ ...finger, x: current!.x + current!.width / 2, y: current!.y + current!.height / 2 }] });
    await expect(card).toHaveClass(/catalog-card--touch-actions/);
    await session.send("Input.dispatchTouchEvent", { type: "touchEnd", touchPoints: [] });
    const wanted = card.locator(".catalog-card__wanted");
    await expect(wanted).toHaveCSS("opacity", "1");
    await expectStarInsideCover(card);
    await card.screenshot({ path: testInfo.outputPath("star-touch-390.png") });
    await wanted.tap();
    await expect(wanted).toHaveAttribute("aria-pressed", "true");
    expect(requests.views).toEqual([]);
    expect(requests.navigations).toEqual([]);
    expect(context.pages()).toHaveLength(1);
    const popupPromise = context.waitForEvent("page");
    await card.locator(".catalog-card__open").tap();
    const popup = await popupPromise;
    await expect(popup.getByRole("heading", { name: "本地模拟游戏目标", exact: true })).toBeVisible();
    await expect.poll(() => requests.views).toEqual(["3001"]);
    expect(requests.navigations).toEqual(["https://layout-game.invalid/play/3001"]);
    expect(await page.evaluate((key) => JSON.parse(localStorage.getItem(key)!).wantedIds, storageKey)).toEqual(["3001"]);
    await popup.close();
    await session.detach();
    expect(requests.unexpected).toEqual([]);
  });
});

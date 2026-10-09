import path from "node:path";

import { expect, test } from "@playwright/test";

import type { CatalogProjectResponse, CatalogResponse } from "../../src/features/catalog/model";

const baseURL = process.env.PLAYWRIGHT_BASE_URL ?? "http://127.0.0.1:5173";
const libraryKey = "parallellines.catalog-library.v1";

// 固定确认的原创收录信息，目录与浏览统计均使用测试响应，不访问真实数据库。
const game = {
  id: "963", slug: "illusion-prototype", name: "回廊彼岸", url: "/games/illusion-prototype/index.html",
  kind: "internal", description: "转动机关，连接错位的道路，带着红帽旅人走向终点。",
  author_name: null, author_url: null, icon_url: null, created_at: "2026-10-09T00:00:00Z",
  average_score: null, rating_count: 0, rating_score_sum: 0, view_count: 0, my_score: null,
} satisfies CatalogProjectResponse;
const oldProject = {
  id: "901", slug: "snake-escape", name: "蛇蛇出洞", url: "/play/snake-escape",
  kind: "internal", description: "按顺序放走彩色小蛇，避开阻挡，在倒计时结束前清空棋盘。",
  author_name: null, author_url: null, icon_url: null, created_at: "2026-09-30T00:00:00Z",
  average_score: null, rating_count: 0, rating_score_sum: 0, view_count: 0, my_score: null,
} satisfies CatalogProjectResponse;
const fixture = {
  categories: [{ id: "1", slug: "puzzle", name: "解谜", icon_url: null, projects: [game, oldProject] }],
} satisfies CatalogResponse;
const gameLinks = [".catalog-card__media-link", ".catalog-card__title-link", ".catalog-card__open"] as const;

for (const viewport of [
  { name: "desktop", width: 1280, height: 900 },
  { name: "mobile", width: 390, height: 844 },
]) {
  test.describe(viewport.name, () => {
    test.use({ viewport: { width: viewport.width, height: viewport.height } });

    test("回廊彼岸按原创解谜收录，正式封面与四种打开入口保持正确", async ({ page, context }, testInfo) => {
      const opened: string[] = [];
      const unexpectedRequests: string[] = [];
      const errors: string[] = [];
      const loadedCovers = new Set<string>();
      const localOrigin = new URL(baseURL).origin;
      page.on("pageerror", (error) => errors.push(error.message));
      context.on("page", (popup) => popup.on("pageerror", (error) => errors.push(error.message)));

      // CDN 回读本地正式素材；只允许同源静态游戏，所有 API 写请求均在这里拦截。
      await context.route("**/*", async (route) => {
        const request = route.request();
        const url = new URL(request.url());
        const headers = {
          "access-control-allow-origin": "*",
          "access-control-allow-methods": "GET, POST, OPTIONS",
          "access-control-allow-headers": "content-type, authorization",
        };
        if (url.pathname.startsWith("/static/web/")) {
          const key = url.pathname.slice("/static/web/".length);
          loadedCovers.add(key);
          await route.fulfill({ path: path.resolve(process.cwd(), "../../static/web", key), headers });
          return;
        }
        if (url.pathname.startsWith("/api/v1/")) {
          if (request.method() === "OPTIONS") {
            await route.fulfill({ status: 204, headers });
            return;
          }
          const viewMatch = /\/catalog\/projects\/([^/]+)\/views$/.exec(url.pathname);
          if (url.pathname === "/api/v1/catalog") {
            await route.fulfill({ json: { data: fixture }, headers });
          } else if (viewMatch) {
            expect(request.method()).toBe("POST");
            expect(request.postDataJSON()).toEqual({});
            expect(viewMatch[1]).toBe(game.id);
            opened.push(viewMatch[1]!);
            await route.fulfill({ json: { data: { project_id: game.id, view_count: opened.length } }, headers });
          } else {
            if (request.method() !== "GET") unexpectedRequests.push(request.url());
            await route.fulfill({
              json: { data: url.pathname.endsWith("/settings/public") ? { settings: {} } : [] }, headers,
            });
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

      await page.goto("/");
      const cards = page.locator("article.catalog-card");
      const card = cards.filter({ has: page.getByRole("heading", { name: game.name, exact: true }) });
      const oldCard = cards.filter({ has: page.getByRole("heading", { name: oldProject.name, exact: true }) });
      await expect(cards).toHaveCount(2);
      await expect(card.locator(".catalog-card__author")).toHaveText("作者：原创");
      await expect(card.locator(".catalog-card__author")).toHaveAttribute("title", "作者：原创");

      // 名称搜索和解谜筛选只改变可见目录，不能提前记录浏览或改变旧游戏归属。
      const search = page.getByRole("searchbox", { name: "搜索游戏名称", exact: true });
      await search.fill(game.name);
      await page.getByRole("button", { name: "搜索", exact: true }).click();
      await expect(cards).toHaveCount(1);
      await expect(card).toBeVisible();
      await search.fill("");
      await page.getByRole("button", { name: "搜索", exact: true }).click();
      const category = page.getByRole("combobox", { name: "游戏分类", exact: true });
      await expect(category.locator('option[value="puzzle"]')).toHaveText("解谜");
      await category.selectOption("puzzle");
      await expect(cards).toHaveCount(2);
      await expect(card).toBeVisible();
      await expect(oldCard).toBeVisible();

      // 网格和列表均使用实机 WebP，核对真实尺寸、裁切、旧版封面以及视口边界。
      for (const layout of ["grid", "list"] as const) {
        const layoutButton = page.getByRole("button", {
          name: layout === "grid" ? "网格显示" : "列表显示", exact: true,
        });
        await layoutButton.click();
        await expect(layoutButton).toHaveAttribute("aria-pressed", "true");
        if (layout === "list") {
          await expect(page.locator(".catalog-grid")).toHaveClass(/catalog-grid--list/);
        } else {
          await expect(page.locator(".catalog-grid")).not.toHaveClass(/catalog-grid--list/);
        }
        const cover = card.locator(".catalog-card__media-link img");
        await cover.scrollIntoViewIfNeeded();
        await expect(cover).toHaveAttribute("src", /\/2026-10-09-v4\/covers\/illusion-prototype\.webp$/);
        await expect.poll(() => cover.evaluate((img) => ({
          width: (img as HTMLImageElement).naturalWidth, height: (img as HTMLImageElement).naturalHeight,
        }))).toEqual({ width: 960, height: 452 });
        expect(await cover.evaluate((img) => getComputedStyle(img).objectFit)).toBe("cover");
        const mediaBounds = await card.locator(".catalog-card__media").boundingBox();
        const coverBounds = await cover.boundingBox();
        expect(mediaBounds).not.toBeNull();
        expect(coverBounds).not.toBeNull();
        expect(coverBounds!.width).toBeGreaterThan(0);
        expect(coverBounds!.height).toBeGreaterThan(0);
        expect(coverBounds!.width).toBeCloseTo(mediaBounds!.width, 1);
        expect(coverBounds!.height).toBeCloseTo(mediaBounds!.height, 1);
        for (const selector of gameLinks) {
          await expect(card.locator(selector)).toHaveAttribute("href", game.url);
          await expect(card.locator(selector)).toHaveAttribute("target", "_blank");
          await expect(card.locator(selector)).toHaveAttribute("rel", "noopener noreferrer");
        }
        const bounds = await card.boundingBox();
        expect(bounds).not.toBeNull();
        expect(bounds!.x).toBeGreaterThanOrEqual(0);
        expect(bounds!.x + bounds!.width).toBeLessThanOrEqual(viewport.width);
        await card.screenshot({ path: testInfo.outputPath(`illusion-prototype-${layout}-${viewport.name}.png`) });
        const oldCover = oldCard.locator(".catalog-card__media-link img");
        await oldCover.scrollIntoViewIfNeeded();
        await expect(oldCover).toHaveAttribute("src", /\/2026-09-30-v1\/covers\/snake-escape\.webp$/);
        await expect.poll(() => oldCover.evaluate((img) => ({
          width: (img as HTMLImageElement).naturalWidth, height: (img as HTMLImageElement).naturalHeight,
        }))).toEqual({ width: 960, height: 452 });
        await expect(page.locator(".catalog-card__cover-fallback")).toHaveCount(0);
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
        await page.evaluate(() => window.scrollTo(0, 0));
        await page.screenshot({ path: testInfo.outputPath(`illusion-prototype-page-${layout}-${viewport.name}.png`), fullPage: true });
      }
      expect(loadedCovers.has("catalog/2026-10-09-v4/covers/illusion-prototype.webp")).toBe(true);
      expect(opened).toEqual([]);

      // 三个原生链接和街机 Enter 均打开同一独立页；每次只记一次浏览，最近记录按游戏去重。
      await page.getByRole("button", { name: "网格显示", exact: true }).click();
      for (const [index, entry] of [...gameLinks, "arcade-enter"].entries()) {
        const pendingPopup = context.waitForEvent("page");
        if (entry === "arcade-enter") {
          await card.focus();
          await expect(card).toHaveClass(/is-selected/);
          await card.press("Enter");
        } else {
          await card.locator(entry).click();
        }
        const popup = await pendingPopup;
        await expect(popup).toHaveURL(new URL(game.url, baseURL).href);
        await expect(popup).toHaveTitle("回廊彼岸 · 第一关");
        await expect(popup.getByRole("main", { name: "回廊彼岸第一关", exact: true })).toBeVisible();
        await expect(popup.locator("#scene")).toBeVisible();
        await expect.poll(() => opened.length).toBe(index + 1);
        await expect(card.locator(".catalog-card__views")).toHaveAttribute("aria-label", `${index + 1} 次浏览`);
        await expect.poll(() => page.evaluate((key) => {
          const snapshot = JSON.parse(localStorage.getItem(key) ?? "null") as {
            recent: Array<{ projectId: string; lastOpenedAt: number }>;
          } | null;
          return snapshot?.recent.map((item) => item.projectId);
        }, libraryKey)).toEqual([game.id]);
        await popup.close();
      }
      expect(opened).toEqual([game.id, game.id, game.id, game.id]);
      await page.locator(".catalog-library-filters").getByRole("button", { name: "最近打开", exact: true }).click();
      await expect(cards).toHaveCount(1);
      await expect(card).toBeVisible();
      expect(unexpectedRequests).toEqual([]);
      expect(errors).toEqual([]);
    });
  });
}

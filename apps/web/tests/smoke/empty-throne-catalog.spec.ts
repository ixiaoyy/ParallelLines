import path from "node:path";

import { expect, test } from "@playwright/test";

import type { CatalogProjectResponse, CatalogResponse } from "../../src/features/catalog/model";

const baseURL = process.env.PLAYWRIGHT_BASE_URL ?? "http://127.0.0.1:5173";
const diagnostics = path.resolve(process.cwd(), "../../.trellis/tasks/10-19-add-empty-throne/diagnostics");

// 固定本次收录资料，浏览器只读取本地页面、接口响应和正式素材。
const game = {
  id: "964", slug: "empty-throne", name: "空王座 · 白鹭王国的冒险", url: "https://muselabs.co/empty-throne",
  kind: "external", description: "选择战士、法师或牧师，探索白鹭王国的六章故事，通过战斗、调查与推理揭开王座背后的阴谋，支持中英日三语配音。",
  author_name: "_westfall", author_url: "https://linux.do/u/_westfall/summary",
  icon_url: null, created_at: "2026-10-19T00:00:00Z", average_score: null,
  rating_count: 0, rating_score_sum: 0, view_count: 0, my_score: null,
} satisfies CatalogProjectResponse;
const oldGame = {
  id: "901", slug: "snake-escape", name: "蛇蛇出洞", url: "/play/snake-escape",
  kind: "internal", description: "按顺序放走彩色小蛇，避开阻挡，在倒计时结束前清空棋盘。",
  author_name: null, author_url: null, icon_url: null, created_at: "2026-09-30T00:00:00Z",
  average_score: null, rating_count: 0, rating_score_sum: 0, view_count: 0, my_score: null,
} satisfies CatalogProjectResponse;
const fixture = {
  categories: [
    { id: "1", slug: "rpg", name: "角色扮演", icon_url: null, projects: [game] },
    { id: "2", slug: "puzzle", name: "解谜", icon_url: null, projects: [oldGame] },
  ],
} satisfies CatalogResponse;
const gameLinks = [".catalog-card__media-link", ".catalog-card__title-link", ".catalog-card__open"] as const;

for (const viewport of [
  { name: "desktop", width: 1280, height: 900 },
  { name: "mobile", width: 390, height: 844 },
]) {
  test.describe(viewport.name, () => {
    test.use({ viewport: { width: viewport.width, height: viewport.height } });

    test("空王座的分类、作者、正式封面及三个外链入口正确", async ({ page, context }) => {
      const errors: string[] = [];
      const externalRequests: string[] = [];
      const loadedCovers = new Set<string>();
      const localOrigin = new URL(baseURL).origin;
      page.on("pageerror", (error) => errors.push(error.message));
      context.on("page", (popup) => popup.on("pageerror", (error) => errors.push(error.message)));

      // 接口固定响应，CDN 从本地素材返回，游戏入口返回隔离文档以避免外部副作用。
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
          if (url.pathname === "/api/v1/catalog") {
            await route.fulfill({ json: { data: fixture }, headers });
          } else if (url.pathname === `/api/v1/catalog/projects/${game.id}/views`) {
            await route.fulfill({ json: { data: { project_id: game.id, view_count: 1 } }, headers });
          } else {
            await route.fulfill({
              json: { data: url.pathname.endsWith("/settings/public") ? { settings: {} } : [] }, headers,
            });
          }
          return;
        }
        if (request.resourceType() === "document" && url.href === game.url) {
          await route.fulfill({
            contentType: "text/html; charset=utf-8",
            body: "<!doctype html><meta charset='utf-8'><title>外链打开验收</title><h1>已打开本地验收目标</h1>",
          });
          return;
        }
        if (url.origin !== localOrigin) {
          externalRequests.push(request.url());
          await route.abort();
          return;
        }
        await route.continue();
      });

      await page.goto("/");
      await expect(page.locator("article.catalog-card")).toHaveCount(2);
      const card = page.locator("article.catalog-card").filter({
        has: page.getByRole("heading", { name: game.name, exact: true }),
      });
      const category = page.getByRole("combobox", { name: "游戏分类", exact: true });

      // 角色扮演分类只显示新游戏，旧分类和全部分类继续保留原游戏。
      await expect(category.locator('option[value="rpg"]')).toHaveText("角色扮演");
      await category.selectOption("rpg");
      await expect(page.locator("article.catalog-card")).toHaveCount(1);
      await expect(card).toBeVisible();
      await category.selectOption("puzzle");
      await expect(page.locator("article.catalog-card")).toHaveCount(1);
      await expect(page.getByRole("heading", { name: oldGame.name, exact: true })).toBeVisible();
      await category.selectOption("all");
      await expect(page.locator("article.catalog-card")).toHaveCount(2);

      // 两种布局必须读取正式 WebP，图片完整覆盖媒体框且页面无横向溢出。
      for (const layout of ["grid", "list"] as const) {
        const layoutButton = page.getByRole("button", {
          name: layout === "grid" ? "网格显示" : "列表显示", exact: true,
        });
        await layoutButton.click();
        await expect(layoutButton).toHaveAttribute("aria-pressed", "true");
        const cover = card.locator(".catalog-card__media-link img");
        await cover.scrollIntoViewIfNeeded();
        await expect(cover).toHaveAttribute("src", /\/2026-10-19-v1\/covers\/empty-throne\.webp$/);
        await expect.poll(() => cover.evaluate((img) => (img as HTMLImageElement).naturalWidth)).toBeGreaterThan(0);
        await expect.poll(() => cover.evaluate((img) => (img as HTMLImageElement).naturalHeight)).toBeGreaterThan(0);
        expect(await cover.evaluate((img) => getComputedStyle(img).objectFit)).toBe("cover");
        const mediaBounds = await card.locator(layout === "grid" ? ".catalog-card__screen" : ".catalog-card__media").boundingBox();
        const coverBounds = await cover.boundingBox();
        expect(mediaBounds).not.toBeNull();
        expect(coverBounds).not.toBeNull();
        expect(coverBounds!.width).toBeGreaterThan(0);
        expect(coverBounds!.height).toBeGreaterThan(0);
        expect(coverBounds!.x).toBeCloseTo(mediaBounds!.x, 1);
        expect(coverBounds!.y).toBeCloseTo(mediaBounds!.y, 1);
        expect(coverBounds!.width).toBeCloseTo(mediaBounds!.width, 1);
        expect(coverBounds!.height).toBeCloseTo(mediaBounds!.height, 1);

        for (const selector of gameLinks) {
          const link = card.locator(selector);
          await expect(link).toHaveAttribute("href", game.url);
          await expect(link).toHaveAttribute("target", "_blank");
          await expect(link).toHaveAttribute("rel", "noopener noreferrer");
        }
        const author = card.getByRole("link", { name: `查看${game.author_name}的作者链接`, exact: true });
        await expect(author).toHaveText(game.author_name);
        await expect(author).toHaveAttribute("href", game.author_url);
        await expect(author).toHaveAttribute("target", "_blank");
        await expect(author).toHaveAttribute("rel", "noopener noreferrer");
        const bounds = await card.boundingBox();
        expect(bounds).not.toBeNull();
        expect(bounds!.x).toBeGreaterThanOrEqual(0);
        expect(bounds!.x + bounds!.width).toBeLessThanOrEqual(viewport.width);
        await card.screenshot({ path: path.join(diagnostics, `empty-throne-${layout}-${viewport.name}.png`) });

        // 旧游戏仍使用原版本封面，不受本次映射新增影响。
        const oldCover = page.locator("article.catalog-card").filter({
          has: page.getByRole("heading", { name: oldGame.name, exact: true }),
        }).locator(".catalog-card__media-link img");
        await oldCover.scrollIntoViewIfNeeded();
        await expect(oldCover).toHaveAttribute("src", /\/2026-09-30-v1\/covers\/snake-escape\.webp$/);
        await expect.poll(() => oldCover.evaluate((img) => (img as HTMLImageElement).naturalWidth)).toBeGreaterThan(0);
        await expect(page.locator(".catalog-card__cover-fallback")).toHaveCount(0);
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
        await page.evaluate(() => window.scrollTo(0, 0));
        await page.screenshot({ path: path.join(diagnostics, `empty-throne-page-${layout}-${viewport.name}.png`), fullPage: true });
      }

      // 封面、标题和开始游戏均实际打开已确认的原 HTTPS 地址。
      await page.getByRole("button", { name: "网格显示", exact: true }).click();
      for (const selector of gameLinks) {
        const pendingPopup = context.waitForEvent("page");
        await card.locator(selector).click();
        const popup = await pendingPopup;
        await expect(popup).toHaveURL(game.url);
        await expect(popup.getByRole("heading", { name: "已打开本地验收目标" })).toBeVisible();
        await popup.close();
      }
      expect(loadedCovers.has("catalog/2026-10-19-v1/covers/empty-throne.webp")).toBe(true);
      expect(externalRequests).toEqual([]);
      expect(errors).toEqual([]);
    });
  });
}

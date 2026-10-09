import path from "node:path";

import { expect, test } from "@playwright/test";

import type { CatalogProjectResponse, CatalogResponse } from "../../src/features/catalog/model";

const baseURL = process.env.PLAYWRIGHT_BASE_URL ?? "http://127.0.0.1:5173";

// 固定已确认的收录资料，验收真实目录组件时不连接数据库或游戏服务器。
const game = {
  id: "962", slug: "shinobi-chronicles", name: "忍界纪行", url: "https://shinobi-chronicles.hellolittledong.chatgpt.site/",
  kind: "external", description: "火影题材的 3D 同人角色扮演游戏，从战国时期的边境营地出发，完成年代任务、修炼忍术和天赋，并通过跳跃、攀附与瞬身探索忍界。",
  author_name: "max_reboots", author_url: "https://linux.do/u/max_reboots/summary",
  icon_url: null, created_at: "2026-10-09T00:00:00Z", average_score: null,
  rating_count: 0, rating_score_sum: 0, view_count: 0, my_score: null,
} satisfies CatalogProjectResponse;
const previousGame = {
  id: "961", slug: "nanbeidou", name: "NANBEIDOU", url: "https://opea.de5.net/rpg",
  kind: "external", description: "像素风回合制卡牌冒险，组建队伍探索异世界，在剧情中解锁角色；也可选择混战或地主模式，结合手牌、装备和角色技能对战。",
  author_name: "sehsapneb", author_url: "https://linux.do/u/sehsapneb/summary",
  icon_url: null, created_at: "2026-10-09T00:00:00Z", average_score: null,
  rating_count: 0, rating_score_sum: 0, view_count: 0, my_score: null,
} satisfies CatalogProjectResponse;
// 同时保留前批收录及旧原创游戏，确保新分类筛选和封面映射不影响已有目录。
const oldProject = {
  id: "901", slug: "snake-escape", name: "蛇蛇出洞", url: "/play/snake-escape",
  kind: "internal", description: "按顺序放走彩色小蛇，避开阻挡，在倒计时结束前清空棋盘。",
  author_name: null, author_url: null, icon_url: null, created_at: "2026-09-30T00:00:00Z",
  average_score: null, rating_count: 0, rating_score_sum: 0, view_count: 0, my_score: null,
} satisfies CatalogProjectResponse;
const fixture = {
  categories: [
    { id: "1", slug: "cards", name: "卡牌", icon_url: null, projects: [previousGame] },
    { id: "2", slug: "puzzle", name: "解谜", icon_url: null, projects: [oldProject] },
    { id: "3", slug: "rpg", name: "角色扮演", icon_url: null, projects: [game] },
  ],
} satisfies CatalogResponse;
const gameLinks = [".catalog-card__media-link", ".catalog-card__title-link", ".catalog-card__open"] as const;

for (const viewport of [
  { name: "desktop", width: 1280, height: 900 },
  { name: "mobile", width: 390, height: 844 },
]) {
  test.describe(viewport.name, () => {
    test.use({ viewport: { width: viewport.width, height: viewport.height } });

    test("忍界纪行的角色扮演分类、正式封面、作者和三种打开入口保持正确", async ({ page, context }, testInfo) => {
      const errors: string[] = [];
      const opened: string[] = [];
      const externalRequests: string[] = [];
      const loadedCovers = new Set<string>();
      const localOrigin = new URL(baseURL).origin;
      page.on("pageerror", (error) => errors.push(error.message));
      context.on("page", (popup) => popup.on("pageerror", (error) => errors.push(error.message)));

      // API 使用固定响应，CDN 回读本地正式素材，游戏弹窗只显示本地验收文档。
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
            // 只有游戏入口点击记一次浏览，使用响应累计值核对真实卡片状态更新。
            expect(request.method()).toBe("POST");
            expect(request.postDataJSON()).toEqual({});
            expect(viewMatch[1]).toBe(game.id);
            opened.push(viewMatch[1]!);
            await route.fulfill({
              json: { data: { project_id: game.id, view_count: opened.length } }, headers,
            });
          } else {
            await route.fulfill({
              json: { data: url.pathname.endsWith("/settings/public") ? { settings: {} } : [] }, headers,
            });
          }
          return;
        }
        if (request.resourceType() === "document" && url.href === new URL(game.url).href) {
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
      await expect(page.locator("article.catalog-card")).toHaveCount(3);
      const card = page.locator("article.catalog-card").filter({
        has: page.getByRole("heading", { name: game.name, exact: true }),
      });
      const categorySelect = page.getByRole("combobox", { name: "游戏分类", exact: true });

      // 角色扮演筛选保留本游戏，卡牌和解谜分类仍显示原游戏，筛选操作不产生浏览统计。
      await expect(categorySelect.locator('option[value="rpg"]')).toHaveText("角色扮演");
      await categorySelect.selectOption("rpg");
      await expect(page.locator("article.catalog-card")).toHaveCount(1);
      await expect(card).toBeVisible();
      await expect(categorySelect.locator('option[value="cards"]')).toHaveText("卡牌");
      await categorySelect.selectOption("cards");
      await expect(page.locator("article.catalog-card")).toHaveCount(1);
      await expect(page.getByRole("heading", { name: previousGame.name, exact: true })).toBeVisible();
      await expect(card).toHaveCount(0);
      await categorySelect.selectOption("puzzle");
      await expect(page.locator("article.catalog-card")).toHaveCount(1);
      await expect(page.getByRole("heading", { name: oldProject.name, exact: true })).toBeVisible();
      await expect(card).toHaveCount(0);
      await categorySelect.selectOption("all");
      await expect(page.locator("article.catalog-card")).toHaveCount(3);

      // 网格和列表都渲染实际 WebP，核对图片裁切与视口边界并保存可复查截图。
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
        await expect(cover).toHaveAttribute("src", /\/2026-10-09-v3\/covers\/shinobi-chronicles\.webp$/);
        await expect.poll(() => cover.evaluate((img) => (img as HTMLImageElement).naturalWidth)).toBe(960);
        await expect.poll(() => cover.evaluate((img) => (img as HTMLImageElement).naturalHeight)).toBe(540);
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
        await card.screenshot({ path: testInfo.outputPath(`shinobi-chronicles-${layout}-${viewport.name}.png`) });

        // 前批游戏继续使用原版本封面，新游戏不能回退到分类占位图。
        const oldCover = page.locator("article.catalog-card").filter({
          has: page.getByRole("heading", { name: oldProject.name, exact: true }),
        }).locator(".catalog-card__media-link img");
        await oldCover.scrollIntoViewIfNeeded();
        await expect(oldCover).toHaveAttribute("src", /\/2026-09-30-v1\/covers\/snake-escape\.webp$/);
        await expect.poll(() => oldCover.evaluate((img) => ({
          width: (img as HTMLImageElement).naturalWidth,
          height: (img as HTMLImageElement).naturalHeight,
        }))).toEqual({ width: 960, height: 452 });
        const previousCover = page.locator("article.catalog-card").filter({
          has: page.getByRole("heading", { name: previousGame.name, exact: true }),
        }).locator(".catalog-card__media-link img");
        await previousCover.scrollIntoViewIfNeeded();
        await expect(previousCover).toHaveAttribute("src", /\/2026-10-09-v2\/covers\/nanbeidou\.webp$/);
        await expect.poll(() => previousCover.evaluate((img) => ({
          width: (img as HTMLImageElement).naturalWidth,
          height: (img as HTMLImageElement).naturalHeight,
        }))).toEqual({ width: 960, height: 454 });
        await expect(page.locator(".catalog-card__cover-fallback")).toHaveCount(0);
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
        await page.evaluate(() => window.scrollTo(0, 0));
        await page.screenshot({ path: testInfo.outputPath(`shinobi-chronicles-page-${layout}-${viewport.name}.png`), fullPage: true });
      }
      expect(loadedCovers.has("catalog/2026-10-09-v3/covers/shinobi-chronicles.webp")).toBe(true);
      expect(opened).toEqual([]);

      // 封面、标题和开始游戏各打开一个新页，每次只发送一次浏览记录请求。
      await page.getByRole("button", { name: "网格显示", exact: true }).click();
      for (const [index, selector] of gameLinks.entries()) {
        const pendingPopup = context.waitForEvent("page");
        await card.locator(selector).click();
        const popup = await pendingPopup;
        await expect(popup).toHaveURL(new URL(game.url).href);
        await expect(popup.getByRole("heading", { name: "已打开本地验收目标" })).toBeVisible();
        await expect.poll(() => opened.length).toBe(index + 1);
        await expect(card.locator(".catalog-card__heat")).toHaveAttribute("aria-label", `热度 ${index + 1}`);
        await popup.close();
      }
      expect(opened).toEqual([game.id, game.id, game.id]);
      expect(externalRequests).toEqual([]);
      expect(errors).toEqual([]);
    });
  });
}

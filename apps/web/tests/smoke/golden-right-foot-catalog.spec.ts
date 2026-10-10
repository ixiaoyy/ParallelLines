import path from "node:path";

import { expect, test } from "@playwright/test";

import type { CatalogProjectResponse, CatalogResponse } from "../../src/features/catalog/model";

const baseURL = process.env.PLAYWRIGHT_BASE_URL ?? "http://127.0.0.1:5173";
const storageKey = "parallellines.catalog-library.v1";
const diagnostics = path.resolve(process.cwd(), "../../.trellis/tasks/10-10-add-golden-right-foot/diagnostics");

// 固定已确认的收录资料；原 HTTP 地址必须保留，验收不连接数据库或游戏服务器。
const game = {
  id: "963", slug: "1589n-golden-right-foot", name: "1589 N · 黄金右脚", url: "http://sxyongweb.cn/Brake/index.html",
  kind: "external", description: "第一人称驾驶小游戏，在日落海岸公路上控制刹车力度，保持 1000–1589 N 完成超车，避免追尾或踏板断裂。",
  author_name: "qeeshui", author_url: "https://linux.do/u/qeeshui/summary",
  icon_url: null, created_at: "2026-10-10T00:00:00Z", average_score: null,
  rating_count: 0, rating_score_sum: 0, view_count: 0, my_score: null,
} satisfies CatalogProjectResponse;
const previousGame = {
  id: "962", slug: "shinobi-chronicles", name: "忍界纪行", url: "https://shinobi-chronicles.hellolittledong.chatgpt.site/",
  kind: "external", description: "火影题材的 3D 同人角色扮演游戏，从战国时期的边境营地出发，完成年代任务、修炼忍术和天赋，并通过跳跃、攀附与瞬身探索忍界。",
  author_name: "max_reboots", author_url: "https://linux.do/u/max_reboots/summary",
  icon_url: null, created_at: "2026-10-09T00:00:00Z", average_score: null,
  rating_count: 0, rating_score_sum: 0, view_count: 0, my_score: null,
} satisfies CatalogProjectResponse;
// 保留前批外链及旧原创游戏，核对竞速筛选和新封面映射对既有目录的兼容。
const oldProject = {
  id: "901", slug: "snake-escape", name: "蛇蛇出洞", url: "/play/snake-escape",
  kind: "internal", description: "按顺序放走彩色小蛇，避开阻挡，在倒计时结束前清空棋盘。",
  author_name: null, author_url: null, icon_url: null, created_at: "2026-09-30T00:00:00Z",
  average_score: null, rating_count: 0, rating_score_sum: 0, view_count: 0, my_score: null,
} satisfies CatalogProjectResponse;
const fixture = {
  categories: [
    { id: "1", slug: "racing", name: "竞速", icon_url: null, projects: [game] },
    { id: "2", slug: "puzzle", name: "解谜", icon_url: null, projects: [oldProject] },
    { id: "3", slug: "rpg", name: "角色扮演", icon_url: null, projects: [previousGame] },
  ],
} satisfies CatalogResponse;
const gameLinks = [".catalog-card__media-link", ".catalog-card__title-link", ".catalog-card__open"] as const;

for (const viewport of [
  { name: "desktop", width: 1280, height: 900 },
  { name: "mobile", width: 390, height: 844 },
]) {
  test.describe(viewport.name, () => {
    test.use({ viewport: { width: viewport.width, height: viewport.height } });

    test("黄金右脚的竞速分类、正式封面、作者、HTTP 入口与最近打开保持正确", async ({ page, context }) => {
      const errors: string[] = [];
      const opened: string[] = [];
      const externalRequests: string[] = [];
      const loadedCovers = new Set<string>();
      const localOrigin = new URL(baseURL).origin;
      page.on("pageerror", (error) => errors.push(error.message));
      context.on("page", (popup) => popup.on("pageerror", (error) => errors.push(error.message)));

      // API 使用固定响应，CDN 读取本地正式素材，外链弹窗只返回隔离验收文档。
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
            // 每次点击游戏入口只记一次浏览，响应累计值驱动真实卡片的热度更新。
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
      await expect(page.locator("article.catalog-card")).toHaveCount(3);
      const card = page.locator("article.catalog-card").filter({
        has: page.getByRole("heading", { name: game.name, exact: true }),
      });
      const categorySelect = page.getByRole("combobox", { name: "游戏分类", exact: true });

      // 竞速仅显示本游戏；切换其他分类仍显示旧游戏，筛选本身不产生浏览统计。
      await expect(categorySelect.locator('option[value="racing"]')).toHaveText("竞速");
      await categorySelect.selectOption("racing");
      await expect(page.locator("article.catalog-card")).toHaveCount(1);
      await expect(card).toBeVisible();
      await categorySelect.selectOption("rpg");
      await expect(page.locator("article.catalog-card")).toHaveCount(1);
      await expect(page.getByRole("heading", { name: previousGame.name, exact: true })).toBeVisible();
      await expect(card).toHaveCount(0);
      await categorySelect.selectOption("puzzle");
      await expect(page.locator("article.catalog-card")).toHaveCount(1);
      await expect(page.getByRole("heading", { name: oldProject.name, exact: true })).toBeVisible();
      await expect(card).toHaveCount(0);
      await categorySelect.selectOption("all");
      await expect(page.locator("article.catalog-card")).toHaveCount(3);

      // 两种布局均加载真实 WebP，图片覆盖媒体区域且卡片不超出手机或桌面视口。
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
        await expect(cover).toHaveAttribute("src", /\/2026-10-10-v1\/covers\/1589n-golden-right-foot\.webp$/);
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
        await card.screenshot({ path: path.join(diagnostics, `golden-right-foot-${layout}-${viewport.name}.png`) });

        // 前批外链和旧原创游戏继续读取原版本素材，不回退到分类占位图。
        for (const [project, expectedPath] of [
          [previousGame, /\/2026-10-09-v3\/covers\/shinobi-chronicles\.webp$/],
          [oldProject, /\/2026-09-30-v1\/covers\/snake-escape\.webp$/],
        ] as const) {
          const oldCover = page.locator("article.catalog-card").filter({
            has: page.getByRole("heading", { name: project.name, exact: true }),
          }).locator(".catalog-card__media-link img");
          await oldCover.scrollIntoViewIfNeeded();
          await expect(oldCover).toHaveAttribute("src", expectedPath);
          await expect.poll(() => oldCover.evaluate((img) => (img as HTMLImageElement).naturalWidth)).toBeGreaterThan(0);
          await expect.poll(() => oldCover.evaluate((img) => (img as HTMLImageElement).naturalHeight)).toBeGreaterThan(0);
        }
        await expect(page.locator(".catalog-card__cover-fallback")).toHaveCount(0);
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
        await page.evaluate(() => window.scrollTo(0, 0));
        await page.screenshot({ path: path.join(diagnostics, `golden-right-foot-page-${layout}-${viewport.name}.png`), fullPage: true });
      }
      expect(loadedCovers.has("catalog/2026-10-10-v1/covers/1589n-golden-right-foot.webp")).toBe(true);
      expect(opened).toEqual([]);

      // 封面、标题和开始游戏均打开原 HTTP 地址；重复打开只保留一条最近记录。
      await page.getByRole("button", { name: "网格显示", exact: true }).click();
      for (const [index, selector] of gameLinks.entries()) {
        const pendingPopup = context.waitForEvent("page");
        await card.locator(selector).click();
        const popup = await pendingPopup;
        await expect(popup).toHaveURL(game.url);
        await expect(popup.getByRole("heading", { name: "已打开本地验收目标" })).toBeVisible();
        await expect.poll(() => opened.length).toBe(index + 1);
        await expect(card.locator(".catalog-card__heat")).toHaveAttribute("aria-label", `热度 ${index + 1}`);
        await popup.close();
      }
      const stored: unknown = await page.evaluate((key) => JSON.parse(localStorage.getItem(key) ?? "null"), storageKey);
      expect(stored).toEqual({
        version: 1, wantedIds: [], recent: [{ projectId: game.id, lastOpenedAt: expect.any(Number) }],
      });
      await page.locator(".catalog-library-filters").getByRole("button", { name: "最近打开", exact: true }).click();
      await expect(page.locator("article.catalog-card")).toHaveCount(1);
      await expect(card).toBeVisible();

      // 刷新必须从真实本地存储恢复最近打开，筛选和恢复都不能增加浏览量请求。
      await page.reload();
      await page.locator(".catalog-library-filters").getByRole("button", { name: "最近打开", exact: true }).click();
      await expect(page.locator("article.catalog-card")).toHaveCount(1);
      await expect(card).toBeVisible();
      expect(opened).toEqual([game.id, game.id, game.id]);
      expect(externalRequests).toEqual([]);
      expect(errors).toEqual([]);
    });
  });
}

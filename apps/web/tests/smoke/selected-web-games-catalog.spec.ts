import path from "node:path";

import { expect, test } from "@playwright/test";

import type { CatalogProjectResponse, CatalogResponse } from "../../src/features/catalog/model";

const baseURL = process.env.PLAYWRIGHT_BASE_URL ?? "http://127.0.0.1:5173";
const staticRoot = path.resolve(process.cwd(), "../../static/web");

// 固定本批已确认的署名和外链；目录验收只使用本地响应，不连接数据库或真实游戏服务器。
const games = [
  {
    id: "9901", slug: "gd-spectrum", category: "puzzle", name: "Spectrum",
    url: "https://gd.games/mrmeeseeks/spectrum", author_name: "Calastrovsk",
    author_url: "https://gd.games/Calastrovsk",
    coverSize: { width: 320, height: 180 },
  },
  {
    id: "9902", slug: "gd-fungi-run", category: "stages", name: "Fungi Run",
    url: "https://gd.games/shehan/fungirun", author_name: "SHEHAN",
    author_url: "https://gd.games/SHEHAN",
    coverSize: { width: 1920, height: 1080 },
  },
  {
    id: "9903", slug: "gd-super-chicken-td", category: "tower-defense", name: "Super Chicken TD",
    url: "https://gd.games/texugozap/super-chicken-td", author_name: "texugozap / Rafa38gh",
    author_url: "https://gd.games/texugozap/super-chicken-td",
    coverSize: { width: 1920, height: 1080 },
  },
  {
    id: "9904", slug: "gd-golf-adventures-2", category: "casual", name: "Golf Adventures! 2",
    url: "https://gd.games/zachjukamashi/golf-adventures-2", author_name: "ZachjuKamashi / lhphr",
    author_url: "https://gd.games/zachjukamashi/golf-adventures-2",
    coverSize: { width: 1920, height: 1080 },
  },
] as const;

const categories = [
  { id: "1", slug: "puzzle", name: "解谜" },
  { id: "2", slug: "stages", name: "闯关" },
  { id: "3", slug: "tower-defense", name: "塔防" },
  { id: "4", slug: "casual", name: "休闲" },
];

const projects = games.map((game, index) => ({
  id: game.id, slug: game.slug, name: game.name, url: game.url,
  kind: "external" as const, description: null,
  author_name: game.author_name, author_url: game.author_url, icon_url: null,
  created_at: `2026-11-03T00:0${4 - index}:00Z`, average_score: null,
  rating_count: 0, rating_score_sum: 0, view_count: 0, my_score: null,
})) satisfies CatalogProjectResponse[];

// 两款既有作品让推荐区保持真实六卡结构，同时核对旧封面不被本批映射替换。
const oldProjects = [
  { id: "901", slug: "snake-escape", name: "蛇蛇出洞", url: "/play/snake-escape", category: "puzzle" },
  { id: "902", slug: "flappy-dunk", name: "弹跳灌篮", url: "/play/flappy-dunk", category: "casual" },
].map((game) => ({
  ...game, kind: "internal" as const, description: null,
  author_name: null, author_url: null, icon_url: null,
  created_at: "2026-09-30T00:00:00Z", average_score: null,
  rating_count: 0, rating_score_sum: 0, view_count: 0, my_score: null,
}));

const fixture = {
  categories: categories.map((category) => ({
    ...category, icon_url: null,
    projects: [
      ...projects.filter((project) => games.some((game) => game.id === project.id && game.category === category.slug)),
      ...oldProjects.filter((project) => project.category === category.slug),
    ],
  })),
} satisfies CatalogResponse;

for (const viewport of [
  { name: "desktop", width: 1280, height: 900 },
  { name: "mobile", width: 390, height: 844 },
]) {
  test.describe(viewport.name, () => {
    test.use({ viewport: { width: viewport.width, height: viewport.height }, serviceWorkers: "block" });

    test("四款 Web 游戏的分类、署名、正式封面和外链入口完整，旧封面保持不变", async ({ page, context }, testInfo) => {
      const errors: string[] = [];
      const opened: string[] = [];
      const unexpected: string[] = [];
      const loadedCovers = new Set<string>();
      const localOrigin = new URL(baseURL).origin;
      const gameTargets = new Set(games.map((game) => new URL(game.url).href));
      page.on("pageerror", (error) => errors.push(error.message));

      // CDN 图片回读本地正式 WebP；所有外链弹窗和 API 写请求均由本测试响应。
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
          await route.fulfill({ path: path.resolve(staticRoot, key), contentType: "image/webp", headers });
          return;
        }
        if (url.pathname.startsWith("/api/v1/")) {
          if (request.method() === "OPTIONS") {
            await route.fulfill({ status: 204, headers });
            return;
          }
          const view = /\/catalog\/projects\/([^/]+)\/views$/.exec(url.pathname);
          if (url.pathname === "/api/v1/catalog") {
            expect(request.method()).toBe("GET");
            await route.fulfill({ json: { data: fixture }, headers });
          } else if (view) {
            expect(request.method()).toBe("POST");
            expect(request.postDataJSON()).toEqual({});
            const id = view[1]!;
            expect(games.some((game) => game.id === id)).toBe(true);
            opened.push(id);
            await route.fulfill({ json: { data: {
              project_id: id, view_count: opened.filter((openedId) => openedId === id).length,
            } }, headers });
          } else {
            if (request.method() !== "GET") unexpected.push(`${request.method()} ${request.url()}`);
            await route.fulfill({ json: { data: url.pathname.endsWith("/settings/public") ? { settings: {} } : [] }, headers });
          }
          return;
        }
        if (request.resourceType() === "document" && gameTargets.has(url.href)) {
          await route.fulfill({
            contentType: "text/html; charset=utf-8",
            body: "<!doctype html><meta charset='utf-8'><title>外链入口验收</title><h1>本地外链验收目标</h1>",
          });
          return;
        }
        if (url.origin !== localOrigin) {
          unexpected.push(`${request.method()} ${request.url()}`);
          await route.abort();
          return;
        }
        await route.continue();
      });

      await page.goto("/");
      await expect(page.locator(".catalog-group--featured .catalog-card")).toHaveCount(6);
      const categorySelect = page.getByRole("combobox", { name: "游戏分类", exact: true });
      for (const category of categories) {
        await expect(categorySelect.locator(`option[value="${category.slug}"]`)).toHaveText(category.name);
        await categorySelect.selectOption(category.slug);
        const expected = fixture.categories.find((item) => item.slug === category.slug)!.projects;
        await expect(page.locator("article.catalog-card")).toHaveCount(expected.length);
        for (const project of expected) {
          await expect(page.getByRole("heading", { name: project.name, exact: true })).toBeVisible();
        }
      }
      await categorySelect.selectOption("all");
      expect(opened).toEqual([]);

      // 按当前推荐区、分类区和列表的真实结构检查裁切；不沿用旧版一款只渲染一卡的假设。
      for (const layout of ["grid", "list"] as const) {
        const layoutButton = page.getByRole("button", { name: layout === "grid" ? "网格显示" : "列表显示", exact: true });
        await layoutButton.click();
        await expect(layoutButton).toHaveAttribute("aria-pressed", "true");
        for (const game of games) {
          const cards = page.locator(`article.catalog-card[data-project-id="${game.id}"]`);
          await expect(cards).toHaveCount(layout === "grid" ? 2 : 1);
          for (const [index, card] of (await cards.all()).entries()) {
            const cover = card.locator(".catalog-card__media img");
            await card.scrollIntoViewIfNeeded();
            await expect(cover).toHaveAttribute("src", new RegExp(`/catalog/2026-11-03-v1/covers/${game.slug}\\.webp$`));
            await expect.poll(() => cover.evaluate((img) => ({
              width: (img as HTMLImageElement).naturalWidth, height: (img as HTMLImageElement).naturalHeight,
            }))).toEqual(game.coverSize);
            expect(await cover.evaluate((img) => getComputedStyle(img).objectFit)).toBe("cover");
            const mediaBounds = await card.locator(".catalog-card__media").boundingBox();
            const imageBounds = await cover.boundingBox();
            expect(imageBounds).not.toBeNull();
            expect(mediaBounds).not.toBeNull();
            expect(imageBounds!.x).toBeCloseTo(mediaBounds!.x, 1);
            expect(imageBounds!.y).toBeCloseTo(mediaBounds!.y, 1);
            expect(imageBounds!.width).toBeCloseTo(mediaBounds!.width, 1);
            expect(imageBounds!.height).toBeCloseTo(mediaBounds!.height, 1);
            for (const selector of [".catalog-card__media-link", ".catalog-card__title-link", ".catalog-card__open"]) {
              const link = card.locator(selector);
              await expect(link).toHaveAttribute("href", game.url);
              await expect(link).toHaveAttribute("target", "_blank");
              await expect(link).toHaveAttribute("rel", "noopener noreferrer");
            }
            const author = card.getByRole("link", { name: `查看${game.author_name}的作者链接`, exact: true });
            await expect(author).toHaveText(game.author_name);
            await expect(author).toHaveAttribute("href", new URL(game.author_url).href);
            await expect(author).toHaveAttribute("target", "_blank");
            await expect(author).toHaveAttribute("rel", "noopener noreferrer");
            const bounds = await card.boundingBox();
            expect(bounds).not.toBeNull();
            expect(bounds!.x).toBeGreaterThanOrEqual(0);
            expect(bounds!.x + bounds!.width).toBeLessThanOrEqual(viewport.width + 1);
            await card.screenshot({ path: testInfo.outputPath(`${game.slug}-${layout}-${index}-${viewport.name}.png`) });
          }
        }
        const oldCover = page.locator('article.catalog-card[data-project-id="901"]').first().locator(".catalog-card__media img");
        await oldCover.scrollIntoViewIfNeeded();
        await expect(oldCover).toHaveAttribute("src", /\/2026-09-30-v1\/covers\/snake-escape\.webp$/);
        await expect.poll(() => oldCover.evaluate((img) => ({
          width: (img as HTMLImageElement).naturalWidth, height: (img as HTMLImageElement).naturalHeight,
        }))).toEqual({ width: 960, height: 452 });
        await expect(page.locator(".catalog-card__cover-fallback")).toHaveCount(0);
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
        await page.evaluate(() => window.scrollTo(0, 0));
        await page.screenshot({ path: testInfo.outputPath(`selected-web-games-${layout}-${viewport.name}.png`), fullPage: true });
      }
      for (const game of games) {
        expect(loadedCovers.has(`catalog/2026-11-03-v1/covers/${game.slug}.webp`)).toBe(true);
      }
      expect(opened).toEqual([]);

      // 原生新标签＋一次打开统计只证明入口接线，不代表外部游戏已实际可玩。
      for (const game of games) {
        const card = page.locator(`article.catalog-card[data-project-id="${game.id}"]`).first();
        const popupPromise = context.waitForEvent("page");
        await card.locator(".catalog-card__open").click();
        const popup = await popupPromise;
        await expect(popup).toHaveURL(new URL(game.url).href);
        await expect(popup.getByRole("heading", { name: "本地外链验收目标" })).toBeVisible();
        await expect.poll(() => opened.filter((id) => id === game.id).length).toBe(1);
        await expect(card.locator(".catalog-card__heat")).toHaveAttribute("aria-label", "热度 1");
        await popup.close();
      }
      expect(opened).toEqual(games.map((game) => game.id));
      expect(unexpected).toEqual([]);
      expect(errors).toEqual([]);
    });
  });
}


import path from "node:path";

import { expect, test } from "@playwright/test";

import type { CatalogProjectResponse, CatalogResponse } from "../../src/features/catalog/model";

const baseURL = process.env.PLAYWRIGHT_BASE_URL ?? "http://127.0.0.1:5173";

// 固定已确认的三款收录资料，目录验收不连接数据库或外部游戏服务器。
const games = [
  {
    id: "951", slug: "entropy-blade", category: "action", name: "熵刃 · ENTROPY BLADE",
    url: "https://game.inc.re/entropy-blade/", author_name: "mumuhaha487",
    author_url: "https://linux.do/u/mumuhaha487/summary",
    description: "像素风横版动作肉鸽，包含三名角色、武技连段与秘技，四个场景各有专属敌人与首领，支持键盘、手柄和手机触屏。",
  },
  {
    id: "952", slug: "nexus", category: "exploration", name: "NEXUS",
    url: "https://traveritas.github.io/nexus/", author_name: "traveritas",
    author_url: "https://linux.do/u/traveritas/summary",
    description: "第一人称探索游戏，从家中出发，通过门、杯子与床穿行于不同世界，使用罗盘查看地图，在日记中记录足迹。",
  },
  {
    id: "953", slug: "emberfall", category: "action", name: "EmberFall",
    url: "https://ef.usbsb.sbs/", author_name: "doveusa",
    author_url: "https://linux.do/u/doveusa/summary",
    description: "暗黑像素风生存动作游戏，选择近战、远程或法术猎人，通过走位、冲刺和装备构筑抵御三十波敌潮，随后可继续无尽狩猎，支持键鼠与手机触屏。",
  },
] as const;

const categories = [
  { id: "1", slug: "action", name: "动作" },
  { id: "2", slug: "exploration", name: "探索" },
  { id: "3", slug: "puzzle", name: "解谜" },
];
const projects = games.map((game) => ({
  id: game.id, slug: game.slug, name: game.name, url: game.url,
  kind: "external" as const, description: game.description,
  author_name: game.author_name, author_url: game.author_url, icon_url: null,
  created_at: "2026-10-09T00:00:00Z", average_score: null,
  rating_count: 0, rating_score_sum: 0, view_count: 0, my_score: null,
})) satisfies CatalogProjectResponse[];
// 保留旧原创游戏及其原版本封面，核对新增映射不影响已有目录。
const oldProject: CatalogProjectResponse = {
  id: "901", slug: "snake-escape", name: "蛇蛇出洞", url: "/play/snake-escape",
  kind: "internal", description: "按顺序放走彩色小蛇，避开阻挡，在倒计时结束前清空棋盘。",
  author_name: null, author_url: null, icon_url: null, created_at: "2026-09-30T00:00:00Z",
  average_score: null, rating_count: 0, rating_score_sum: 0, view_count: 0, my_score: null,
};
const fixture = {
  categories: categories.map((category) => ({
    ...category,
    icon_url: null,
    projects: [
      ...projects.filter((project) => games.some((game) => game.id === project.id && game.category === category.slug)),
      ...(category.slug === "puzzle" ? [oldProject] : []),
    ],
  })),
} satisfies CatalogResponse;
const gameLinks = [".catalog-card__media-link", ".catalog-card__title-link", ".catalog-card__open"] as const;

for (const viewport of [
  { name: "desktop", width: 1280, height: 900 },
  { name: "mobile", width: 390, height: 844 },
]) {
  test.describe(viewport.name, () => {
    test.use({ viewport: { width: viewport.width, height: viewport.height } });

    test("三款游戏的分类、作者、正式封面和打开统计在网格及列表中保持正确", async ({ page, context }, testInfo) => {
      const errors: string[] = [];
      const opened: string[] = [];
      const externalRequests: string[] = [];
      const loadedCovers = new Set<string>();
      const localOrigin = new URL(baseURL).origin;
      const gameTargets = new Set(games.map((game) => new URL(game.url).href));
      page.on("pageerror", (error) => errors.push(error.message));
      context.on("page", (popup) => popup.on("pageerror", (error) => errors.push(error.message)));

      // API 固定响应，CDN 请求回读本地正式素材；外链弹窗也使用本地文档。
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
            // 入口点击沿用一次空对象 POST；夹具累计量验证卡片真实浏览量更新。
            expect(request.method()).toBe("POST");
            expect(request.postDataJSON()).toEqual({});
            const id = viewMatch[1]!;
            expect(games.some((game) => game.id === id)).toBe(true);
            opened.push(id);
            const viewCount = opened.filter((openedId) => openedId === id).length;
            await route.fulfill({ json: { data: { project_id: id, view_count: viewCount } }, headers });
          } else {
            await route.fulfill({ json: { data: url.pathname.endsWith("/settings/public") ? { settings: {} } : [] }, headers });
          }
          return;
        }
        if (request.resourceType() === "document" && gameTargets.has(url.href)) {
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
      await expect(page.locator("article.catalog-card")).toHaveCount(games.length + 1);

      // 分类选项使用现有目录分类；筛选只改变展示，不记录游戏打开。
      const categorySelect = page.getByRole("combobox", { name: "游戏分类", exact: true });
      for (const category of categories) {
        await expect(categorySelect.locator(`option[value="${category.slug}"]`)).toHaveText(category.name);
        await categorySelect.selectOption(category.slug);
        const names = category.slug === "puzzle"
          ? [oldProject.name]
          : games.filter((game) => game.category === category.slug).map((game) => game.name);
        await expect(page.locator("article.catalog-card")).toHaveCount(names.length);
        for (const name of names) {
          await expect(page.getByRole("heading", { name, exact: true })).toBeVisible();
        }
      }
      await categorySelect.selectOption("all");
      await expect(page.locator("article.catalog-card")).toHaveCount(games.length + 1);

      // 两种布局读取相同封面，检查真实尺寸、图片裁切和卡片在视口内的边界。
      for (const layout of ["grid", "list"] as const) {
        const layoutName = layout === "grid" ? "网格显示" : "列表显示";
        const layoutButton = page.getByRole("button", { name: layoutName, exact: true });
        await layoutButton.click();
        await expect(layoutButton).toHaveAttribute("aria-pressed", "true");
        if (layout === "list") {
          await expect(page.locator(".catalog-grid")).toHaveClass(/catalog-grid--list/);
        } else {
          await expect(page.locator(".catalog-grid")).not.toHaveClass(/catalog-grid--list/);
        }
        for (const game of games) {
          const card = page.locator("article.catalog-card").filter({
            has: page.getByRole("heading", { name: game.name, exact: true }),
          });
          const cover = card.locator(".catalog-card__media-link img");
          await cover.scrollIntoViewIfNeeded();
          await expect(cover).toHaveAttribute("src", new RegExp(`/2026-10-09-v1/covers/${game.slug}\\.webp$`));
          await expect.poll(() => cover.evaluate((img) => (img as HTMLImageElement).naturalWidth)).toBe(960);
          await expect.poll(() => cover.evaluate((img) => (img as HTMLImageElement).naturalHeight)).toBeGreaterThan(320);
          expect(await cover.evaluate((img) => getComputedStyle(img).objectFit)).toBe("cover");
          const mediaBounds = await card.locator(".catalog-card__media").boundingBox();
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
          await expect(author).toHaveAttribute("href", new URL(game.author_url).href);
          await expect(author).toHaveAttribute("target", "_blank");
          await expect(author).toHaveAttribute("rel", "noopener noreferrer");
          const bounds = await card.boundingBox();
          expect(bounds).not.toBeNull();
          expect(bounds!.x).toBeGreaterThanOrEqual(0);
          expect(bounds!.x + bounds!.width).toBeLessThanOrEqual(viewport.width);
          await card.screenshot({ path: testInfo.outputPath(`${game.slug}-${layout}-${viewport.name}.png`) });
        }

        // 旧封面保持原地址与原尺寸，两种布局都不能回退到文字或分类占位图。
        const oldCover = page.locator("article.catalog-card").filter({
          has: page.getByRole("heading", { name: oldProject.name, exact: true }),
        }).locator(".catalog-card__media-link img");
        await oldCover.scrollIntoViewIfNeeded();
        await expect(oldCover).toHaveAttribute("src", /\/2026-09-30-v1\/covers\/snake-escape\.webp$/);
        await expect.poll(() => oldCover.evaluate((img) => ({
          width: (img as HTMLImageElement).naturalWidth,
          height: (img as HTMLImageElement).naturalHeight,
        }))).toEqual({ width: 960, height: 452 });
        await expect(page.locator(".catalog-card__cover-fallback")).toHaveCount(0);
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
        await page.evaluate(() => window.scrollTo(0, 0));
        await page.screenshot({ path: testInfo.outputPath(`three-games-${layout}-${viewport.name}.png`), fullPage: true });
      }
      for (const game of games) {
        expect(loadedCovers.has(`catalog/2026-10-09-v1/covers/${game.slug}.webp`)).toBe(true);
      }
      expect(opened).toEqual([]);

      // 每款游戏的封面、标题和开始游戏入口各打开一次，累计浏览量必须与请求一一对应。
      await page.getByRole("button", { name: "网格显示", exact: true }).click();
      for (const game of games) {
        const card = page.locator("article.catalog-card").filter({
          has: page.getByRole("heading", { name: game.name, exact: true }),
        });
        for (const [index, selector] of gameLinks.entries()) {
          const pendingPopup = context.waitForEvent("page");
          await card.locator(selector).click();
          const popup = await pendingPopup;
          await expect(popup).toHaveURL(new URL(game.url).href);
          await expect(popup.getByRole("heading", { name: "已打开本地验收目标" })).toBeVisible();
          await expect.poll(() => opened.filter((id) => id === game.id).length).toBe(index + 1);
          await expect(card.locator(".catalog-card__views")).toHaveAttribute("aria-label", `${index + 1} 次浏览`);
          await popup.close();
        }
      }
      expect(opened).toEqual(games.flatMap((game) => gameLinks.map(() => game.id)));
      expect(externalRequests).toEqual([]);
      expect(errors).toEqual([]);
    });
  });
}

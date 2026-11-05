import { existsSync } from "node:fs";
import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";

import { expect, test, type Locator } from "@playwright/test";

import { CATALOG_COVER_ASPECTS_BY_PATH } from "../../src/features/catalog/coverAspectManifest";
import type { CatalogProjectResponse, CatalogResponse } from "../../src/features/catalog/model";
import { catalogPublicFixture } from "./catalog-public-fixture";

const baseURL = process.env.PLAYWRIGHT_BASE_URL ?? "http://127.0.0.1:5173";
const staticRoot = path.resolve(process.cwd(), "../../static/web");
const publicRoot = path.resolve(process.cwd(), "public");
const version = "2026-11-05-v3";
// 本批正式图的最终实测尺寸；ZType 保留更小的原生 JPEG，不强制重复转码。
const coverSizes: Record<string, { width: number; height: number }> = {
  "yorg-io": { width: 1280, height: 442 },
  "shapez-demo": { width: 990, height: 800 },
  ztype: { width: 560, height: 372 },
};
const gameAuthors: Record<string, { name: string; url: string; display: string; collaborator: string }> = {
  "yorg-io": { name: "Tobias Springer / tobspr Games", url: "https://tobspr.io/", display: "Tobias Springer", collaborator: "tobspr Games" },
  "shapez-demo": { name: "Tobias Springer / tobspr Games", url: "https://tobspr.io/", display: "Tobias Springer", collaborator: "tobspr Games" },
  ztype: { name: "Dominic Szablewski / PhobosLab", url: "https://phoboslab.org/", display: "Dominic Szablewski", collaborator: "PhobosLab" },
};

// 固定本批已确认资料；新标签和打开统计均在隔离夹具内响应，不请求真实游戏或生产 API。
const games = [
  {
    id: "9931", slug: "yorg-io", category: "tower-defense", name: "YORG.io",
    url: "https://yorg.io/", coverFile: "yorg-io.webp",
  },
  {
    id: "9932", slug: "shapez-demo", category: "simulation", name: "shapez（网页试玩版）",
    url: "https://shapez.io/", coverFile: "shapez-demo.webp",
  },
  {
    id: "9933", slug: "ztype", category: "shooting", name: "ZType",
    url: "https://zty.pe/", coverFile: "ztype.jpg",
  },
] as const;

const categories = [
  { id: "1", slug: "tower-defense", name: "塔防" },
  { id: "2", slug: "simulation", name: "模拟经营" },
  { id: "3", slug: "shooting", name: "射击" },
  { id: "4", slug: "puzzle", name: "解谜" },
  { id: "5", slug: "casual", name: "休闲" },
];
const projects = games.map((game, index) => ({
  id: game.id, slug: game.slug, name: game.name, url: game.url, kind: "external" as const,
  description: null, author_name: gameAuthors[game.slug]?.name ?? null, author_url: gameAuthors[game.slug]?.url ?? null, icon_url: null,
  created_at: `2026-11-05T00:0${3 - index}:00Z`, average_score: null, rating_count: 0,
  rating_score_sum: 0, view_count: 0, my_score: null,
})) satisfies CatalogProjectResponse[];
const oldProjects = [
  { id: "901", slug: "snake-escape", name: "蛇蛇出洞", url: "/play/snake-escape", category: "puzzle", kind: "internal" as const },
  { id: "902", slug: "flappy-dunk", name: "弹跳灌篮", url: "/play/flappy-dunk", category: "casual", kind: "internal" as const },
  { id: "903", slug: "clock-out", name: "准点下班", url: "https://clockout-18.vercel.app/", category: "puzzle", kind: "external" as const },
].map((game) => ({
  ...game, description: null,
  author_name: null, author_url: null, icon_url: null, created_at: "2026-09-30T00:00:00Z",
  average_score: null, rating_count: 0, rating_score_sum: 0, view_count: 0, my_score: null,
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
const hiddenGames = [
  { id: "229", name: "Fungi Run" }, { id: "230", name: "Super Chicken TD" },
  { id: "231", name: "Golf Adventures! 2" }, { id: "232", name: "Helicopter SOS" },
  { id: "233", name: "Rocket Racers" }, { id: "74", name: "Mystery Town" },
  { id: "58", name: "Canteen Crashers" }, { id: "110", name: "MUST. MAKE. PAPERCLIPS." },
  { id: "130", name: "Dungeon of Astra" },
] as const;

/** 检查当前卡片真实图片元素、完整解码和覆盖裁切；宽高比来自同批正式封面清单。 */
async function inspectCover(card: Locator, slug: string): Promise<{ width: number; height: number }> {
  const cover = card.locator(".catalog-card__cover img");
  const coverPath = `/catalog/${version}/covers/${games.find((game) => game.slug === slug)!.coverFile}`;
  await card.scrollIntoViewIfNeeded();
  await expect(cover).toHaveAttribute("src", new RegExp(`${coverPath.replaceAll(".", "\\.")}$`));
  await expect.poll(() => cover.evaluate((image: HTMLImageElement) =>
    image.complete && image.naturalWidth > 0 && image.naturalHeight > 0)).toBe(true);
  const dimensions = await cover.evaluate(async (image: HTMLImageElement) => {
    await image.decode();
    return { width: image.naturalWidth, height: image.naturalHeight };
  });
  expect(dimensions).toEqual(coverSizes[slug]);
  expect(dimensions.width / dimensions.height).toBeCloseTo(CATALOG_COVER_ASPECTS_BY_PATH[coverPath]!, 8);
  expect(await cover.evaluate((image) => getComputedStyle(image).objectFit)).toBe("cover");
  expect(await cover.evaluate((image) => getComputedStyle(image).objectPosition)).toBe(slug === "ztype" ? "50% 100%" : "50% 50%");
  const imageBounds = await cover.boundingBox();
  const coverBounds = await card.locator(".catalog-card__cover").boundingBox();
  expect(imageBounds).not.toBeNull();
  expect(coverBounds).not.toBeNull();
  for (const key of ["x", "y", "width", "height"] as const) {
    expect(imageBounds![key]).toBeCloseTo(coverBounds![key], 1);
  }
  // 手机底部导航固定定位；截图前把卡片置于可视区中央，避免导航遮住检查对象。
  if ((card.page().viewportSize()?.width ?? 0) < 760) {
    await card.evaluate((element) => element.scrollIntoView({ block: "center", inline: "nearest", behavior: "instant" }));
  }
  return dimensions;
}

for (const viewport of [
  { name: "desktop", width: 1280, height: 900 },
  { name: "mobile", width: 390, height: 844 },
]) {
  test.describe(viewport.name, () => {
    test.use({ viewport: { width: viewport.width, height: viewport.height }, serviceWorkers: "block" });

    test("三款新增外链游戏的分页、正式封面、搜索、作者榜与打开入口完整", async ({ page, context }, testInfo) => {
      test.setTimeout(90_000);
      for (const game of games) {
        expect(coverSizes[game.slug], `${game.slug} 正式尺寸待确认`).toBeDefined();
        expect(gameAuthors[game.slug], `${game.slug} 作者资料待确认`).toBeDefined();
      }
      expect(["127.0.0.1", "localhost", "[::1]"].includes(new URL(baseURL).hostname)).toBe(true);
      const output = process.env.DIRECT_GAME_SITES_QA_DIR ?? testInfo.outputDir;
      await mkdir(output, { recursive: true });
      const errors: string[] = [];
      const unexpected: string[] = [];
      const opened: string[] = [];
      const fullReads: string[] = [];
      const pageReads: string[] = [];
      const loadedCovers = new Set<string>();
      const dimensions: Record<string, { width: number; height: number }> = {};
      const localOrigin = new URL(baseURL).origin;
      const gameTargets = new Set(games.map((game) => new URL(game.url).href));
      page.on("pageerror", (error) => errors.push(error.message));
      await page.emulateMedia({ reducedMotion: "reduce" });

      // 公开分页仍通过现有分页夹具，只把实际静态请求映射到本地正式文件；不访问远端。
      await context.route("**/*", async (route) => {
        const request = route.request();
        const url = new URL(request.url());
        const headers = {
          "access-control-allow-origin": "*", "access-control-allow-methods": "GET, POST, OPTIONS",
          "access-control-allow-headers": "content-type, authorization",
        };
        if (url.pathname.startsWith("/static/web/")) {
          const key = url.pathname.slice("/static/web/".length);
          const source = [path.resolve(staticRoot, key), path.resolve(publicRoot, key)].find(existsSync);
          expect(source, `本地正式资源缺失：${key}`).toBeDefined();
          loadedCovers.add(key);
          await route.fulfill({ path: source!, headers });
          return;
        }
        if (url.pathname.startsWith("/api/v1/")) {
          if (request.method() === "OPTIONS") {
            await route.fulfill({ status: 204, headers });
            return;
          }
          const view = /\/catalog\/projects\/([^/]+)\/views$/.exec(url.pathname);
          const paged = catalogPublicFixture(url, fixture.categories);
          if (paged) {
            expect(request.method()).toBe("GET");
            if (url.pathname.includes("/categories/")) pageReads.push(url.pathname);
            await route.fulfill({ json: paged, headers });
          } else if (url.pathname === "/api/v1/catalog") {
            expect(request.method()).toBe("GET");
            fullReads.push(url.href);
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
            if (request.method() !== "GET") unexpected.push(`${request.method()} ${url.href}`);
            await route.fulfill({ json: { data: url.pathname.endsWith("/settings/public") ? { settings: {} } : [] }, headers });
          }
          return;
        }
        if (request.resourceType() === "document" && gameTargets.has(url.href)) {
          await route.fulfill({ contentType: "text/html; charset=utf-8",
            body: "<!doctype html><meta charset='utf-8'><title>外链入口验收</title><h1>本地外链验收目标</h1>" });
          return;
        }
        if (url.origin !== localOrigin || !["GET", "HEAD"].includes(request.method())) {
          unexpected.push(`${request.method()} ${url.href}`);
          await route.abort();
          return;
        }
        await route.continue();
      });

      await page.goto("/games");
      const featured = page.locator(".catalog-group--featured");
      await expect(featured.locator(".catalog-card")).toHaveCount(6);
      for (const game of games) {
        const card = featured.locator(`[data-project-id="${game.id}"]`);
        dimensions[game.slug] = await inspectCover(card, game.slug);
        await expect(card.getByRole("link", { name: `打开${game.name}`, exact: true })).toHaveAttribute("href", game.url);
        await card.screenshot({ path: path.join(output, `${game.slug}-hero-${viewport.name}.png`) });
      }
      for (const category of categories) {
        const section = page.locator(`[data-category-section="${category.slug}"]`);
        await section.scrollIntoViewIfNeeded();
        const expectedGames = games.filter((game) => game.category === category.slug);
        for (const game of expectedGames) {
          const card = section.locator(`[data-project-id="${game.id}"]`);
          await expect(card).toHaveCount(1);
          await inspectCover(card, game.slug);
          await card.screenshot({ path: path.join(output, `${game.slug}-category-${viewport.name}.png`) });
        }
      }
      expect(fullReads).toEqual([]);
      for (const category of categories) {
        expect(pageReads).toContain(`/api/v1/catalog/categories/${category.slug}/projects`);
      }
      expect(opened).toEqual([]);
      for (const hidden of hiddenGames) await expect(page.locator(`[data-project-id="${hidden.id}"]`)).toHaveCount(0);
      await page.evaluate(() => scrollTo({ top: 0, behavior: "instant" }));
      await page.screenshot({ path: path.join(output, `direct-game-sites-discovery-${viewport.name}.png`), fullPage: true });

      // 当前正式 UI 使用完整分类结果，无旧版网格/列表切换；筛选入口读取按需全量接口。
      await page.getByRole("button", { name: "最新", exact: true }).click();
      await expect(page.locator("article.catalog-card")).toHaveCount(6);
      const categorySelect = page.getByRole("combobox", { name: "游戏分类", exact: true });
      for (const category of categories) {
        await expect(categorySelect.locator(`option[value="${category.slug}"]`)).toHaveText(category.name);
        await categorySelect.selectOption(category.slug);
        const expectedProjects = fixture.categories.find((entry) => entry.slug === category.slug)!.projects;
        await expect(page.locator("article.catalog-card")).toHaveCount(expectedProjects.length);
        for (const game of games.filter((entry) => entry.category === category.slug)) {
          await inspectCover(page.locator(`[data-project-id="${game.id}"]`), game.slug);
        }
      }
      await categorySelect.selectOption("all");
      const oldCover = page.locator('[data-project-id="901"] .catalog-card__cover img');
      await oldCover.scrollIntoViewIfNeeded();
      await expect(oldCover).toHaveAttribute("src", /\/catalog\/2026-09-30-v1\/covers\/snake-escape\.webp$/);
      expect(await oldCover.evaluate((image) => getComputedStyle(image).objectPosition)).toBe("50% 50%");
      await expect.poll(() => oldCover.evaluate((image: HTMLImageElement) => image.complete && image.naturalWidth > 0)).toBe(true);
      await page.evaluate(() => scrollTo({ top: 0, behavior: "instant" }));
      await page.screenshot({ path: path.join(output, `direct-game-sites-results-${viewport.name}.png`), fullPage: true });

      const search = page.getByRole("searchbox", { name: "搜索游戏名称", exact: true });
      // 上批已下架九款不因本批新增静态封面或新游戏重现为搜索卡片。
      for (const hidden of hiddenGames) {
        await search.fill(hidden.name);
        await search.press("Enter");
        await expect(page.locator("article.catalog-card")).toHaveCount(0);
        await expect(page.getByText("没有找到匹配的游戏", { exact: true })).toBeVisible();
      }
      for (const game of games) {
        await search.fill(game.name);
        await search.press("Enter");
        const card = page.locator(`article.catalog-card[data-project-id="${game.id}"]`);
        await expect(page.locator("article.catalog-card")).toHaveCount(1);
        await expect(card.locator("h3")).toHaveText(game.name);
        if (game.slug === "shapez-demo") await expect(card.locator("h3")).toHaveText("shapez（网页试玩版）");
        await inspectCover(card, game.slug);
        const link = card.getByRole("link", { name: `打开${game.name}`, exact: true });
        await expect(link).toHaveAttribute("target", "_blank");
        await expect(link).toHaveAttribute("rel", "noopener noreferrer");
        const popupPromise = context.waitForEvent("page");
        await link.click();
        const popup = await popupPromise;
        await expect(popup).toHaveURL(new URL(game.url).href);
        await expect(popup.getByRole("heading", { name: "本地外链验收目标" })).toBeVisible();
        await expect.poll(() => opened.filter((id) => id === game.id).length).toBe(1);
        await expect(card.locator(".catalog-card__heat")).toHaveAttribute("aria-label", "综合热度 1");
        await popup.close();
      }

      // 卡片不展示作者链接，沿现有作者榜核对署名、作者 URL 及作品入口；合作署名仍可搜索。
      await page.getByRole("button", { name: "作者榜", exact: true }).click();
      const leaderboard = page.getByRole("region", { name: "作者榜", exact: true });
      await expect(leaderboard).toBeVisible();
      for (const game of games) {
        const profile = gameAuthors[game.slug]!;
        const author = leaderboard.getByRole("link", { name: profile.display, exact: true });
        await expect(author).toHaveAttribute("href", new URL(profile.url).href);
        await expect(author).toHaveAttribute("target", "_blank");
        await expect(author).toHaveAttribute("rel", "noopener noreferrer");
      }
      await page.screenshot({ path: path.join(output, `direct-game-sites-authors-${viewport.name}.png`), fullPage: true });
      const shared = gameAuthors["yorg-io"]!;
      expect(gameAuthors["shapez-demo"]!.url).toBe(shared.url);
      const sharedLink = leaderboard.getByRole("link", { name: shared.display, exact: true });
      await expect(sharedLink).toHaveCount(1);
      await expect(sharedLink.locator("xpath=ancestor::li[1]")).toContainText("2 个作品");
      await page.getByRole("searchbox", { name: "搜索作者", exact: true }).fill(shared.collaborator);
      await expect(sharedLink).toBeVisible();
      await expect(leaderboard.getByRole("link")).toHaveCount(1);
      await page.screenshot({ path: path.join(output, `direct-game-sites-shared-author-${viewport.name}.png`), fullPage: true });
      await leaderboard.getByRole("button", { name: `查看${shared.display}的作品`, exact: true }).click();
      await expect(page.locator("article.catalog-card")).toHaveCount(2);
      await expect(page.locator("article.catalog-card h3")).toHaveText(["YORG.io", "shapez（网页试玩版）"]);
      await page.getByRole("button", { name: "作者榜", exact: true }).click();
      await page.getByRole("searchbox", { name: "搜索作者", exact: true }).fill(gameAuthors.ztype!.collaborator);
      await expect(leaderboard.getByRole("link", { name: gameAuthors.ztype!.display, exact: true })).toHaveCount(1);
      await expect(leaderboard.getByRole("link")).toHaveCount(1);

      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
      for (const game of games) expect(loadedCovers.has(`catalog/${version}/covers/${game.coverFile}`)).toBe(true);
      expect(opened).toEqual(games.map((game) => game.id));
      expect(unexpected).toEqual([]);
      expect(errors).toEqual([]);
      await writeFile(path.join(output, `direct-game-sites-${viewport.name}-evidence.json`), JSON.stringify({
        viewport, dimensions, opened, fullReads, pageReads, hiddenGames, gameAuthors, unexpected, errors,
        boundary: "本地API/外链夹具与真实正式图片，不证明真实外站玩法或线上CDN。",
      }, null, 2));
    });
  });
}

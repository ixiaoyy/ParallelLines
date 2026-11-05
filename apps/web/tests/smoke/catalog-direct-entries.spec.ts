import { existsSync } from "node:fs";
import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";

import { expect, test, type Locator } from "@playwright/test";

import { CATALOG_COVER_ASPECTS_BY_PATH } from "../../src/features/catalog/coverAspectManifest";
import type { CatalogProjectResponse, CatalogResponse } from "../../src/features/catalog/model";
import { PERSONAL_LIBRARY_KEY, type PersonalLibrary } from "../../src/features/catalog/personalLibrary";
import { catalogPublicFixture } from "./catalog-public-fixture";

const baseURL = process.env.PLAYWRIGHT_BASE_URL ?? "http://127.0.0.1:5173";
const staticRoot = path.resolve(process.cwd(), "../../static/web");
const publicRoot = path.resolve(process.cwd(), "public");

// 固定本次三个公开直达目标与既有正式封面；不把作者作品页、版本路径或查询参数另行改写。
const games = [
  {
    id: "228", slug: "gd-spectrum", name: "Spectrum", category: "puzzle",
    url: "https://html-classic.itch.zone/html/7294044/Spectrum%201.1/index.html?v=1782787944",
    cover: "/catalog/2026-11-03-v1/covers/gd-spectrum.webp", size: { width: 320, height: 180 },
    author_name: "Calastrovsk", author_url: "https://gd.games/Calastrovsk",
  },
  {
    id: "234", slug: "itch-six-cats-under", name: "Six Cats Under", category: "puzzle",
    url: "https://html-classic.itch.zone/html/2267583/index.html",
    cover: "/catalog/2026-11-05-v1/covers/itch-six-cats-under.webp", size: { width: 630, height: 500 },
    author_name: "Team Bean Loop / Mosu", author_url: "https://teambeanloop.itch.io/six-cats-under",
  },
  {
    id: "235", slug: "itch-the-final-earth-2", name: "The Final Earth 2", category: "simulation",
    url: "https://html-classic.itch.zone/html/1995721-336862/index.html",
    cover: "/catalog/2026-11-05-v1/covers/itch-the-final-earth-2.webp", size: { width: 1200, height: 800 },
    author_name: "Florian van Strien", author_url: "https://flori9.itch.io",
  },
] as const;
const hiddenGames = [
  { id: "229", name: "Fungi Run" },
  { id: "230", name: "Super Chicken TD" },
  { id: "231", name: "Golf Adventures! 2" },
  { id: "232", name: "Helicopter SOS" },
  { id: "233", name: "Rocket Racers" },
  { id: "74", name: "Mystery Town" },
  { id: "58", name: "Canteen Crashers" },
  { id: "110", name: "MUST. MAKE. PAPERCLIPS." },
  { id: "130", name: "Dungeon of Astra" },
] as const;
const projects = games.map((game, index) => ({
  id: game.id, slug: game.slug, name: game.name, url: game.url, kind: "external" as const,
  description: null, author_name: game.author_name, author_url: game.author_url, icon_url: null,
  created_at: `2026-11-05T00:0${3 - index}:00Z`, average_score: 3,
  rating_count: 1, rating_score_sum: 3, view_count: 17 + index, my_score: null,
})) satisfies CatalogProjectResponse[];
const oldProjects = [
  { id: "901", slug: "snake-escape", name: "蛇蛇出洞", url: "/play/snake-escape", category: "puzzle" },
  { id: "902", slug: "flappy-dunk", name: "弹跳灌篮", url: "/play/flappy-dunk", category: "casual" },
  { id: "903", slug: "choppy-orc", name: "Choppy Orc", url: "https://eddynardo.com/games/choppy-orc/", category: "stages" },
].map((game) => ({
  ...game, kind: game.id === "903" ? "external" as const : "internal" as const,
  description: null, author_name: null, author_url: null, icon_url: null,
  created_at: "2026-09-30T00:00:00Z", average_score: null, rating_count: 0,
  rating_score_sum: 0, view_count: 0, my_score: null,
}));
const categories = [
  { id: "1", slug: "puzzle", name: "解谜" },
  { id: "2", slug: "simulation", name: "模拟经营" },
  { id: "3", slug: "casual", name: "休闲" },
  { id: "4", slug: "stages", name: "闯关" },
];
const fixture = {
  categories: categories.map((category) => ({
    ...category, icon_url: null,
    projects: [
      ...projects.filter((project) => games.some((game) => game.id === project.id && game.category === category.slug)),
      ...oldProjects.filter((project) => project.category === category.slug),
    ],
  })),
} satisfies CatalogResponse;

// 个人清单故意保留九个下架 ID；只有当前公开目录与清单的交集允许呈现可点击卡片。
const seededIds = [...hiddenGames.map((game) => game.id), ...games.map((game) => game.id), "901"];
const seed: PersonalLibrary = { version: 1, wantedIds: seededIds,
  recent: seededIds.map((projectId, index) => ({ projectId, lastOpenedAt: 1_790_000_000_000 - index * 1000 })) };
const hiddenIds = new Set<string>(hiddenGames.map((game) => game.id));

/** 原封面继续使用实测尺寸与比例；手机截图前居中，避开既有固定底部导航。 */
async function inspectCover(card: Locator, game: (typeof games)[number]) {
  const image = card.locator(".catalog-card__cover img");
  await card.evaluate((element) => element.scrollIntoView({ block: "center", inline: "nearest", behavior: "instant" }));
  await expect(image).toHaveAttribute("src", `https://img.pingxingxian.space/static/web${game.cover}`);
  await expect.poll(() => image.evaluate((element: HTMLImageElement) =>
    element.complete && element.naturalWidth > 0 && element.naturalHeight > 0)).toBe(true);
  const dimensions = await image.evaluate(async (element: HTMLImageElement) => {
    await element.decode();
    return { width: element.naturalWidth, height: element.naturalHeight };
  });
  expect(dimensions).toEqual(game.size);
  expect(dimensions.width / dimensions.height).toBeCloseTo(CATALOG_COVER_ASPECTS_BY_PATH[game.cover]!, 8);
  expect(await image.evaluate((element) => getComputedStyle(element).objectFit)).toBe("cover");
  const imageBox = await image.boundingBox();
  const coverBox = await card.locator(".catalog-card__cover").boundingBox();
  expect(imageBox).not.toBeNull();
  expect(coverBox).not.toBeNull();
  for (const key of ["x", "y", "width", "height"] as const) expect(imageBox![key]).toBeCloseTo(coverBox![key], 1);
  return dimensions;
}

for (const viewport of [{ name: "desktop", width: 1280, height: 900 }, { name: "mobile", width: 390, height: 844 }]) {
  test.describe(viewport.name, () => {
    test.use({ viewport: { width: viewport.width, height: viewport.height }, serviceWorkers: "block" });

    test("三款直达链接与旧封面保持，九款下架不从搜索或已存个人清单泄漏", async ({ page, context }, testInfo) => {
      test.setTimeout(90_000);
      const origin = new URL(baseURL).origin;
      expect(["127.0.0.1", "localhost", "[::1]"].includes(new URL(origin).hostname)).toBe(true);
      const output = process.env.DIRECT_ENTRIES_QA_DIR ?? testInfo.outputDir;
      await mkdir(output, { recursive: true });
      const errors: string[] = [];
      const unexpected: string[] = [];
      const opened: string[] = [];
      const pageReads: string[] = [];
      const fullReads: string[] = [];
      const gameTargets = new Set<string>(games.map((game) => game.url));
      const dimensions: Record<string, { width: number; height: number }> = {};
      page.on("pageerror", (error) => errors.push(error.message));
      await page.emulateMedia({ reducedMotion: "reduce" });
      await context.addInitScript(({ key, snapshot, localOrigin }) => {
        if (location.origin !== localOrigin || sessionStorage.getItem("direct-entries-seeded")) return;
        localStorage.setItem(key, JSON.stringify(snapshot));
        sessionStorage.setItem("direct-entries-seeded", "1");
      }, { key: PERSONAL_LIBRARY_KEY, snapshot: seed, localOrigin: origin });

      // 全部 API、CDN 和外链文档均为隔离夹具，不向真实 API 写浏览量或访问真实游戏。
      await context.route("**/*", async (route) => {
        const request = route.request();
        const url = new URL(request.url());
        const headers = { "access-control-allow-origin": "*", "access-control-allow-methods": "GET, POST, OPTIONS",
          "access-control-allow-headers": "content-type, authorization" };
        if (url.pathname.startsWith("/static/web/")) {
          const key = url.pathname.slice("/static/web/".length);
          const source = [path.resolve(staticRoot, key), path.resolve(publicRoot, key)].find(existsSync);
          expect(source, `本地正式资源缺失：${key}`).toBeDefined();
          await route.fulfill({ path: source!, headers });
          return;
        }
        if (url.pathname.startsWith("/api/v1/")) {
          if (request.method() === "OPTIONS") { await route.fulfill({ status: 204, headers }); return; }
          const paged = catalogPublicFixture(url, fixture.categories);
          const view = /\/catalog\/projects\/([^/]+)\/views$/.exec(url.pathname);
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
            const project = projects.find((entry) => entry.id === view[1]);
            expect(project).toBeDefined();
            opened.push(project!.id);
            await route.fulfill({ json: { data: { project_id: project!.id,
              view_count: project!.view_count + opened.filter((id) => id === project!.id).length } }, headers });
          } else {
            if (request.method() !== "GET") unexpected.push(`${request.method()} ${url.href}`);
            await route.fulfill({ json: { data: url.pathname.endsWith("/settings/public") ? { settings: {} } : [] }, headers });
          }
          return;
        }
        if (request.resourceType() === "document" && gameTargets.has(url.href)) {
          await route.fulfill({ contentType: "text/html; charset=utf-8",
            body: "<!doctype html><meta charset='utf-8'><title>直达入口夹具</title><h1>本地精确直达目标</h1>" });
          return;
        }
        if (url.origin !== origin || !["GET", "HEAD"].includes(request.method())) {
          unexpected.push(`${request.method()} ${url.href}`);
          await route.abort();
          return;
        }
        await route.continue();
      });

      await page.goto("/games");
      await expect(page.locator(".catalog-group--featured .catalog-card")).toHaveCount(6);
      for (const category of categories) {
        const section = page.locator(`[data-category-section="${category.slug}"]`);
        await section.scrollIntoViewIfNeeded();
        await expect.poll(() => section.locator(".catalog-card").count()).toBeGreaterThan(0);
      }
      expect(fullReads).toEqual([]);
      for (const category of categories) expect(pageReads).toContain(`/api/v1/catalog/categories/${category.slug}/projects`);
      for (const hidden of hiddenGames) await expect(page.locator(`[data-project-id="${hidden.id}"]`)).toHaveCount(0);

      const navigation = page.getByRole("navigation", { name: "游戏导航", exact: true });
      const expectedPersonalIds = [...games.map((game) => game.id), "901"].sort();
      for (const scope of [{ nav: "想玩", name: "wanted" }, { nav: "最近打开", name: "recent" }]) {
        await navigation.getByRole("button", { name: scope.nav, exact: true }).click();
        await expect(page.locator("article.catalog-card")).toHaveCount(4);
        expect((await page.locator("article.catalog-card").evaluateAll((cards) => cards.map((card) => card.getAttribute("data-project-id")))).sort()).toEqual(expectedPersonalIds);
        for (const hidden of hiddenGames) await expect(page.locator(`[data-project-id="${hidden.id}"]`)).toHaveCount(0);
        await expect.poll(() => page.evaluate((key) => JSON.parse(localStorage.getItem(key) ?? "null"), PERSONAL_LIBRARY_KEY)).toEqual(seed);
        await page.reload();
        await expect(page.locator("article.catalog-card")).toHaveCount(4);
        await page.screenshot({ path: path.join(output, `direct-entries-${scope.name}-${viewport.name}.png`), fullPage: true });
      }

      await navigation.getByRole("button", { name: "最新", exact: true }).click();
      const search = page.getByRole("searchbox", { name: "搜索游戏名称", exact: true });
      for (const hidden of hiddenGames) {
        await search.fill(hidden.name);
        await search.press("Enter");
        await expect(page.locator("article.catalog-card")).toHaveCount(0);
        await expect(page.getByText("没有找到匹配的游戏", { exact: true })).toBeVisible();
      }
      expect(opened).toEqual([]);
      await expect.poll(() => page.evaluate((key) => JSON.parse(localStorage.getItem(key) ?? "null"), PERSONAL_LIBRARY_KEY)).toEqual(seed);

      for (const game of games) {
        await search.fill(game.name);
        await search.press("Enter");
        const card = page.locator(`article.catalog-card[data-project-id="${game.id}"]`);
        await expect(page.locator("article.catalog-card")).toHaveCount(1);
        await expect(card.locator("h3")).toHaveText(game.name);
        const link = card.getByRole("link", { name: `打开${game.name}`, exact: true });
        await expect(link).toHaveAttribute("href", game.url);
        await expect(link).toHaveAttribute("target", "_blank");
        await expect(link).toHaveAttribute("rel", "noopener noreferrer");
        dimensions[game.slug] = await inspectCover(card, game);
        await card.screenshot({ path: path.join(output, `${game.slug}-direct-card-${viewport.name}.png`) });
        await page.screenshot({ path: path.join(output, `${game.slug}-direct-search-${viewport.name}.png`) });
        const popupPromise = context.waitForEvent("page");
        await link.click();
        const popup = await popupPromise;
        await expect(popup).toHaveURL(game.url);
        await expect(popup.getByRole("heading", { name: "本地精确直达目标" })).toBeVisible();
        await expect.poll(() => opened.filter((id) => id === game.id).length).toBe(1);
        const project = projects.find((entry) => entry.id === game.id)!;
        await expect(card.locator(".catalog-card__heat")).toHaveAttribute("aria-label", `综合热度 ${project.view_count + 1 + project.rating_score_sum * 5}`);
        await popup.close();
      }
      const saved = await page.evaluate((key) => JSON.parse(localStorage.getItem(key) ?? "null") as PersonalLibrary, PERSONAL_LIBRARY_KEY);
      expect(saved.wantedIds).toEqual(seed.wantedIds);
      expect(saved.recent.filter((entry) => hiddenIds.has(entry.projectId))).toEqual(seed.recent.filter((entry) => hiddenIds.has(entry.projectId)));
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
      expect(opened).toEqual(games.map((game) => game.id));
      expect(unexpected).toEqual([]);
      expect(errors).toEqual([]);
      await writeFile(path.join(output, `direct-entries-${viewport.name}-evidence.json`), JSON.stringify({ viewport,
        games: games.map(({ id, name, url, cover }) => ({ id, name, url, cover })), dimensions,
        hiddenGames, seed, saved, opened, pageReads, fullReads, unexpected, errors,
        boundary: "本地公开目录夹具与旧正式图；真实迁移、真实公开API过滤和外站运行不由此证明。",
      }, null, 2));
    });
  });
}

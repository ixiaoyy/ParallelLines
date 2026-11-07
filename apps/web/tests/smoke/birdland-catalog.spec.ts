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
const version = "2026-11-05-v4";
// 原始 JPEG 全部字节和元数据保持，卡片只按现有容器显示；许可只覆盖此张封面。
const cover = { file: "birdland.jpg", width: 900, height: 900, mime: "image/jpeg" };
const attribution = { path: "/licenses/catalog-covers.html", licenseUrl: "https://creativecommons.org/licenses/by/3.0/us/",
  sourceUrl: "https://ifdb.org/showimage?id=0%3A722", recordUrl: "https://ifdb.org/viewgame?coverart=&id=ap1651hvjldbuugj&ldesc=",
  modificationText: "图片未经修改，保留原始 JPEG 字节；目录卡片按容器显示。",
  scopeText: "此许可仅适用于上述封面，不覆盖游戏正文、游戏程序或 Izzy Marbella 的其他插画。" };
const game = {
  id: "9941", slug: "birdland", category: "romance", name: "BIRDLAND", url: "https://birdland.camp/",
  author_name: "Brendan Patrick Hennessy / Izzy Marbella", author_url: "https://bphennessy.itch.io/birdland",
} as const;
const project = {
  id: game.id, slug: game.slug, name: game.name, url: game.url, kind: "external" as const,
  description: null, author_name: game.author_name, author_url: game.author_url, icon_url: null,
  created_at: "2026-11-05T00:01:00Z", average_score: null, rating_count: 0,
  rating_score_sum: 0, view_count: 0, my_score: null,
} satisfies CatalogProjectResponse;
const oldProjects = [
  { id: "901", slug: "snake-escape", name: "蛇蛇出洞", url: "/play/snake-escape", category: "puzzle", kind: "internal" as const },
  { id: "902", slug: "flappy-dunk", name: "弹跳灌篮", url: "/play/flappy-dunk", category: "casual", kind: "internal" as const },
  { id: "903", slug: "clock-out", name: "准点下班", url: "https://clockout-18.vercel.app/", category: "puzzle", kind: "external" as const },
  { id: "904", slug: "ztype", name: "ZType", url: "https://zty.pe/", category: "shooting", kind: "external" as const },
  { id: "905", slug: "shapez-demo", name: "shapez（网页试玩版）", url: "https://shapez.io/", category: "simulation", kind: "external" as const },
].map((entry) => ({
  ...entry, description: null, author_name: null, author_url: null, icon_url: null,
  created_at: "2026-09-30T00:00:00Z", average_score: null, rating_count: 0,
  rating_score_sum: 0, view_count: 0, my_score: null,
}));
const categories = [
  { id: "1", slug: "romance", name: "恋爱" }, { id: "2", slug: "puzzle", name: "解谜" },
  { id: "3", slug: "casual", name: "休闲" }, { id: "4", slug: "shooting", name: "射击" },
  { id: "5", slug: "simulation", name: "模拟经营" },
];
const fixture = {
  categories: categories.map((category) => ({
    ...category, icon_url: null,
    projects: [...(category.slug === game.category ? [project] : []), ...oldProjects.filter((entry) => entry.category === category.slug)],
  })),
} satisfies CatalogResponse;
const hiddenGames = [
  { id: "229", name: "Fungi Run" }, { id: "230", name: "Super Chicken TD" },
  { id: "231", name: "Golf Adventures! 2" }, { id: "232", name: "Helicopter SOS" },
  { id: "233", name: "Rocket Racers" }, { id: "74", name: "Mystery Town" },
  { id: "58", name: "Canteen Crashers" }, { id: "110", name: "MUST. MAKE. PAPERCLIPS." },
  { id: "130", name: "Dungeon of Astra" },
] as const;

/** 正式封面须真实解码；不以占位、扩展名或仅自然宽度为零的 img 节点作为通过。 */
async function inspectCover(card: Locator) {
  const image = card.locator(".catalog-card__cover img");
  const coverPath = `/catalog/${version}/covers/${cover.file}`;
  await card.evaluate((element) => element.scrollIntoView({ block: "center", inline: "nearest", behavior: "instant" }));
  await expect(image).toHaveAttribute("src", `https://img.pingxingxian.space/static/web${coverPath}`);
  await expect.poll(() => image.evaluate((element: HTMLImageElement) =>
    element.complete && element.naturalWidth > 0 && element.naturalHeight > 0)).toBe(true);
  const size = await image.evaluate(async (element: HTMLImageElement) => {
    await element.decode();
    return { width: element.naturalWidth, height: element.naturalHeight };
  });
  expect(size).toEqual({ width: cover.width, height: cover.height });
  expect(size.width / size.height).toBeCloseTo(CATALOG_COVER_ASPECTS_BY_PATH[coverPath]!, 8);
  expect(await image.evaluate((element) => getComputedStyle(element).objectFit)).toBe("cover");
  const imageBox = await image.boundingBox();
  const coverBox = await card.locator(".catalog-card__cover").boundingBox();
  expect(imageBox).not.toBeNull();
  expect(coverBox).not.toBeNull();
  for (const key of ["x", "y", "width", "height"] as const) expect(imageBox![key]).toBeCloseTo(coverBox![key], 1);
  return size;
}

for (const viewport of [{ name: "desktop", width: 1280, height: 900 }, { name: "mobile", width: 390, height: 844 }]) {
  test.describe(viewport.name, () => {
    test.use({ viewport: { width: viewport.width, height: viewport.height }, serviceWorkers: "block" });

    test("BIRDLAND直达、恋爱分类、完整作者和仅封面许可的公开署名链路正确", async ({ page, context }, testInfo) => {
      test.setTimeout(90_000);
      expect(cover.file).not.toBe("");
      expect(cover.width).toBeGreaterThan(0);
      expect(attribution.sourceUrl).not.toBe("");
      expect(attribution.modificationText).not.toBe("");
      expect(attribution.scopeText).not.toBe("");
      const origin = new URL(baseURL).origin;
      expect(["127.0.0.1", "localhost", "[::1]"].includes(new URL(origin).hostname)).toBe(true);
      const output = process.env.BIRDLAND_QA_DIR ?? testInfo.outputDir;
      await mkdir(output, { recursive: true });
      const errors: string[] = [];
      const unexpected: string[] = [];
      const opened: string[] = [];
      const fullReads: string[] = [];
      const pageReads: string[] = [];
      let loadedFormalCover = false;
      let licenseStatus: number | undefined;
      context.on("response", (response) => {
        if (response.request().resourceType() === "document" && new URL(response.url()).pathname === attribution.path) licenseStatus = response.status();
      });
      page.on("pageerror", (error) => errors.push(error.message));
      context.on("page", (newPage) => newPage.on("pageerror", (error) => errors.push(error.message)));
      await page.emulateMedia({ reducedMotion: "reduce" });

      // 所有API、CDN和游戏弹窗都在本地隔离响应；许可HTML读取实际public文件，不伪造许可文本。
      await context.route("**/*", async (route) => {
        const request = route.request();
        const url = new URL(request.url());
        const headers = { "access-control-allow-origin": "*", "access-control-allow-methods": "GET, POST, OPTIONS",
          "access-control-allow-headers": "content-type, authorization" };
        if (url.pathname.startsWith("/static/web/")) {
          const key = url.pathname.slice("/static/web/".length);
          const source = [path.resolve(staticRoot, key), path.resolve(publicRoot, key)].find(existsSync);
          expect(source, `本地正式资源缺失：${key}`).toBeDefined();
          if (key === `catalog/${version}/covers/${cover.file}`) loadedFormalCover = true;
          await route.fulfill({ path: source!, headers });
          return;
        }
        if (url.pathname.startsWith("/api/v1/")) {
          if (request.method() === "OPTIONS") { await route.fulfill({ status: 204, headers }); return; }
          const paged = catalogPublicFixture(url, fixture.categories);
          if (paged) {
            expect(request.method()).toBe("GET");
            if (url.pathname.includes("/categories/")) pageReads.push(url.pathname);
            await route.fulfill({ json: paged, headers });
          } else if (url.pathname === "/api/v1/catalog") {
            expect(request.method()).toBe("GET");
            fullReads.push(url.href);
            await route.fulfill({ json: { data: fixture }, headers });
          } else if (url.pathname === `/api/v1/catalog/projects/${game.id}/views`) {
            expect(request.method()).toBe("POST");
            expect(request.postDataJSON()).toEqual({});
            opened.push(game.id);
            await route.fulfill({ json: { data: { project_id: game.id, view_count: opened.length } }, headers });
          } else {
            if (request.method() !== "GET") unexpected.push(`${request.method()} ${url.href}`);
            await route.fulfill({ json: { data: url.pathname.endsWith("/settings/public") ? { settings: {} } : [] }, headers });
          }
          return;
        }
        if (request.resourceType() === "document" && url.href === game.url) {
          await route.fulfill({ contentType: "text/html; charset=utf-8",
            body: "<!doctype html><meta charset='utf-8'><title>Birdland直达夹具</title><h1>本地BIRDLAND精确目标</h1>" });
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
      const hero = page.locator(`.catalog-group--featured [data-project-id="${game.id}"]`);
      await expect(page.locator(".catalog-group--featured .catalog-card")).toHaveCount(6);
      await inspectCover(hero);
      await hero.screenshot({ path: path.join(output, `birdland-hero-${viewport.name}.png`) });
      const romance = page.locator('[data-category-section="romance"]');
      await romance.scrollIntoViewIfNeeded();
      const romanceCard = romance.locator(`[data-project-id="${game.id}"]`);
      await expect(romanceCard).toHaveCount(1);
      await inspectCover(romanceCard);
      await romanceCard.screenshot({ path: path.join(output, `birdland-category-${viewport.name}.png`) });
      expect(fullReads).toEqual([]);
      expect(pageReads).toContain("/api/v1/catalog/categories/romance/projects");
      for (const hidden of hiddenGames) await expect(page.locator(`[data-project-id="${hidden.id}"]`)).toHaveCount(0);

      await page.getByRole("navigation", { name: "游戏导航", exact: true }).getByRole("button", { name: "最新", exact: true }).click();
      const category = page.getByRole("combobox", { name: "游戏分类", exact: true });
      await category.selectOption("romance");
      await expect(page.locator("article.catalog-card")).toHaveCount(1);
      await expect(page.locator("article.catalog-card h3")).toHaveText(game.name);
      await inspectCover(page.locator("article.catalog-card"));
      await category.selectOption("all");
      const oldCover = page.locator('[data-project-id="901"] .catalog-card__cover img');
      await oldCover.scrollIntoViewIfNeeded();
      await expect(oldCover).toHaveAttribute("src", /\/catalog\/2026-09-30-v1\/covers\/snake-escape\.webp$/);
      await expect.poll(() => oldCover.evaluate((element: HTMLImageElement) => element.complete && element.naturalWidth > 0)).toBe(true);
      const search = page.getByRole("searchbox", { name: "搜索游戏名称", exact: true });
      for (const hidden of hiddenGames) {
        await search.fill(hidden.name);
        await search.press("Enter");
        await expect(page.locator("article.catalog-card")).toHaveCount(0);
        await expect(page.getByText("没有找到匹配的游戏", { exact: true })).toBeVisible();
      }
      await search.fill(game.name);
      await search.press("Enter");
      await expect(page.locator("article.catalog-card")).toHaveCount(1);
      const card = page.locator(`article.catalog-card[data-project-id="${game.id}"]`);
      await expect(card.locator("h3")).toHaveText(game.name);
      await inspectCover(card);
      const link = card.getByRole("link", { name: "打开BIRDLAND", exact: true });
      await expect(link).toHaveAttribute("href", game.url);
      await expect(link).toHaveAttribute("target", "_blank");
      await expect(link).toHaveAttribute("rel", "noopener noreferrer");
      await page.mouse.move(0, 0);
      await card.screenshot({ path: path.join(output, `birdland-search-card-${viewport.name}.png`) });
      expect(opened).toEqual([]);
      const popupPromise = context.waitForEvent("page");
      await link.click();
      const popup = await popupPromise;
      await expect(popup).toHaveURL(game.url);
      await expect(popup.getByRole("heading", { name: "本地BIRDLAND精确目标" })).toBeVisible();
      await expect.poll(() => opened).toEqual([game.id]);
      await expect(card.locator(".catalog-card__heat, .catalog-card__category, .catalog-ai-rating")).toHaveCount(0);
      await popup.close();

      await page.getByRole("button", { name: "作者榜", exact: true }).click();
      const leaderboard = page.getByRole("region", { name: "作者榜", exact: true });
      const author = leaderboard.getByRole("link", { name: "Brendan Patrick Hennessy", exact: true });
      await expect(author).toHaveAttribute("href", game.author_url);
      await expect(author).toHaveAttribute("target", "_blank");
      await expect(author).toHaveAttribute("rel", "noopener noreferrer");
      await page.getByRole("searchbox", { name: "搜索作者", exact: true }).fill("Izzy Marbella");
      await expect(author).toBeVisible();
      await expect(leaderboard.getByRole("link")).toHaveCount(1);
      await page.screenshot({ path: path.join(output, `birdland-izzy-search-${viewport.name}.png`) });

      // 目录页脚不再展示署名入口；许可页仍直接打开实际 HTML，原站游戏链接与资料来源不可混用。
      await expect(page.locator(`.catalog-footer a[href="${attribution.path}"]`)).toHaveCount(0);
      const licensePage = await context.newPage();
      await licensePage.goto(new URL(attribution.path, origin).href);
      await expect(licensePage).toHaveURL(new URL(attribution.path, origin).href);
      await licensePage.waitForLoadState("domcontentloaded");
      expect(licenseStatus).toBe(200);
      await expect(licensePage.locator("body")).toContainText("BIRDLAND");
      await expect(licensePage.locator("body")).toContainText("Brendan Patrick Hennessy");
      await expect(licensePage.locator("body")).toContainText("CC BY 3.0 US");
      await expect(licensePage.locator("body")).toContainText(attribution.modificationText);
      await expect(licensePage.locator("body")).toContainText(attribution.scopeText);
      await expect(licensePage.locator(`a[href="${attribution.licenseUrl}"]`)).toHaveCount(1);
      await expect(licensePage.locator(`a[href="${attribution.sourceUrl}"]`)).toHaveCount(1);
      await expect(licensePage.locator(`a[href="${attribution.recordUrl}"]`)).toHaveCount(1);
      expect(await licensePage.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
      await licensePage.screenshot({ path: path.join(output, `birdland-cover-attribution-${viewport.name}.png`), fullPage: true });
      await licensePage.close();
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
      expect(loadedFormalCover).toBe(true);
      expect(opened).toEqual([game.id]);
      expect(unexpected).toEqual([]);
      expect(errors).toEqual([]);
      await writeFile(path.join(output, `birdland-${viewport.name}-evidence.json`), JSON.stringify({ viewport,
        game, cover, attribution, hiddenGames, opened, fullReads, pageReads, unexpected, errors,
        boundary: "本地目录/打开统计夹具和实际正式图/许可HTML；不代表原站剧情或线上CDN已验证。",
      }, null, 2));
    });
  });
}

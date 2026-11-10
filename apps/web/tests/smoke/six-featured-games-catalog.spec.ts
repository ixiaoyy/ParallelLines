import { existsSync } from "node:fs";
import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";

import { expect, test } from "@playwright/test";

import { CATALOG_COVER_ASPECTS_BY_PATH } from "../../src/features/catalog/coverAspectManifest";
import { catalogPublicFixture } from "./catalog-public-fixture";

const version = "2026-11-10-v1";
const staticRoot = path.resolve(process.cwd(), "../../static/web");
const publicRoot = path.resolve(process.cwd(), "public");
// 固定本批已批准的目录资料；测试ID仅用于隔离夹具，不写真实目录或外站。
const games = [
  { slug: "dragonsweeper", name: "Dragonsweeper", category: "puzzle", width: 480, height: 420, url: "https://html-classic.itch.zone/html/12786123/index.html" },
  { slug: "growmi", name: "Growmi", category: "puzzle", width: 480, height: 381, url: "https://html-classic.itch.zone/html/7612919/index.html" },
  { slug: "sort-the-court", name: "Sort the Court!", category: "simulation", width: 315, height: 250, url: "https://html-classic.itch.zone/html/347310/index.html" },
  { slug: "solitomb", name: "Solitomb", category: "cards", width: 256, height: 256, url: "https://html-classic.itch.zone/html/12290587/index.html" },
  { slug: "slipways-classic", name: "Slipways Classic", category: "rts", width: 480, height: 381, url: "https://html-classic.itch.zone/html/3076366/index.html" },
  { slug: "die-in-the-dungeon-classic", name: "Die in the Dungeon CLASSIC", category: "cards", width: 480, height: 364, url: "https://html-classic.itch.zone/html/7330268/Die%20in%20the%20Dungeon%201.6.2f%20%5BWEB%5D/index.html" },
].map((game, index) => ({ ...game, id: String(9901 + index) }));
const project = (game: typeof games[number]) => ({
  id: game.id, slug: game.slug, name: game.name, url: game.url, kind: "external", description: null,
  author_name: null, author_url: null, icon_url: null, created_at: "2026-11-10T10:00:00+08:00",
  average_score: null, rating_count: 0, rating_score_sum: 0, my_score: null, view_count: 0, ai_rating: null,
});
const old = { ...project(games[0]!), id: "98", slug: "astra-d29e74ac15e222629347", name: "DUST FRONT",
  url: "https://dust-front.mustafaakin.dev/", view_count: 3 };
const categories = ["puzzle", "rts", "cards", "simulation"].map((slug, index) => ({
  id: String(index + 1), slug, name: { puzzle: "解谜", rts: "策略", cards: "卡牌", simulation: "模拟经营" }[slug]!,
  icon_url: null, projects: [...games.filter((game) => game.category === slug).map(project), ...(slug === "rts" ? [old] : [])],
}));

for (const width of [1280, 390, 320]) {
  test(`six curated games: real covers, old catalog retention and isolated links at ${width}px`, async ({ page, context }, testInfo) => {
    test.setTimeout(90_000);
    await page.setViewportSize({ width, height: 900 });
    await page.emulateMedia({ reducedMotion: "reduce" });
    const output = process.env.SIX_FEATURED_GAMES_QA_DIR ?? testInfo.outputDir;
    await mkdir(output, { recursive: true });
    const localOrigin = new URL(testInfo.project.use.baseURL as string).origin;
    expect(["127.0.0.1", "localhost", "[::1]"].includes(new URL(localOrigin).hostname)).toBe(true);
    const opened: string[] = [];
    const unexpected: string[] = [];
    const errors: string[] = [];
    const dimensions: Record<string, { width: number; height: number }> = {};
    page.on("pageerror", (error) => errors.push(error.message));
    await context.route("**/*", async (route) => {
      const request = route.request();
      const url = new URL(request.url());
      if (url.pathname.startsWith("/static/web/")) {
        const key = url.pathname.slice("/static/web/".length);
        const source = [path.resolve(staticRoot, key), path.resolve(publicRoot, key)].find(existsSync);
        expect(source, `Missing actual asset ${key}`).toBeDefined();
        await route.fulfill({ path: source! });
      } else if (url.pathname.startsWith("/api/v1/")) {
        const paged = catalogPublicFixture(url, categories);
        const view = /\/catalog\/projects\/(\d+)\/views$/.exec(url.pathname);
        if (paged) await route.fulfill({ json: paged });
        else if (url.pathname === "/api/v1/catalog") await route.fulfill({ json: { data: { categories } } });
        else if (view && request.method() === "POST") {
          expect(games.some((game) => game.id === view[1])).toBe(true);
          opened.push(view[1]!);
          await route.fulfill({ json: { data: { project_id: view[1], view_count: 1 } } });
        } else if (request.method() === "GET") await route.fulfill({ json: { data: url.pathname.endsWith("/settings/public") ? { settings: {} } : [] } });
        else { unexpected.push(`${request.method()} ${url.href}`); await route.abort(); }
      } else if (request.isNavigationRequest() && games.some((game) => game.url === url.href)) {
        // 此响应只验证原生外链跳转，不冒充外站加载、游玩或联网匹配通过。
        await route.fulfill({ contentType: "text/html", body: "<!doctype html><title>Isolated link fixture</title>" });
      } else if (url.origin === localOrigin && ["GET", "HEAD"].includes(request.method())) await route.continue();
      else { unexpected.push(`${request.method()} ${url.href}`); await route.abort(); }
    });
    await page.goto("/games");
    const hero = page.locator(".catalog-group--featured");
    await expect(hero.locator(".catalog-card")).toHaveCount(6);
    await expect(hero.locator('[data-project-id="98"]')).toHaveCount(0);
    await expect(page.getByRole("button", { name: "下一组推荐游戏", exact: true })).toHaveCount(0);
    for (const game of games) {
      const card = hero.locator(`[data-project-id="${game.id}"]`);
      const image = card.locator(".catalog-card__cover img");
      await card.scrollIntoViewIfNeeded();
      await expect(image).toHaveAttribute("src", `/static/web/catalog/${version}/covers/${game.slug}.webp`);
      await expect.poll(() => image.evaluate((img: HTMLImageElement) => img.complete && img.naturalWidth > 0)).toBe(true);
      dimensions[game.slug] = await image.evaluate(async (img: HTMLImageElement) => {
        await img.decode(); return { width: img.naturalWidth, height: img.naturalHeight };
      });
      expect(dimensions[game.slug]).toEqual({ width: game.width, height: game.height });
      expect(game.width / game.height).toBeCloseTo(CATALOG_COVER_ASPECTS_BY_PATH[`/catalog/${version}/covers/${game.slug}.webp`]!, 8);
      await expect(card.getByRole("link", { name: `打开${game.name}`, exact: true })).toHaveAttribute("href", game.url);
      await expect(card).not.toContainText("AI评分");
      await card.screenshot({ path: path.join(output, `${game.slug}-${width}.png`) });
    }
    await page.evaluate(() => scrollTo(0, 0));
    await page.mouse.move(0, 0);
    await page.screenshot({ path: path.join(output, `curated-home-${width}.png`) });
    for (const game of games) {
      const link = hero.locator(`[data-project-id="${game.id}"]`).getByRole("link", { name: `打开${game.name}`, exact: true });
      const popup = page.waitForEvent("popup");
      await link.click();
      const destination = await popup;
      await expect(destination).toHaveURL(game.url);
      await destination.close();
    }
    await expect.poll(() => opened.length).toBe(6);
    expect([...opened].sort()).toEqual(games.map((game) => game.id).sort());
    await page.goto("/games?q=DUST%20FRONT");
    await expect(page.locator('.catalog-card[data-project-id="98"]')).toBeVisible();
    await page.goto("/licenses/catalog-covers.html");
    for (const game of games) await expect(page.locator(`section[aria-labelledby="${game.slug}-cover"]`)).toContainText(game.name);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
    expect(errors).toEqual([]);
    expect(unexpected).toEqual([]);
    await writeFile(path.join(output, `curated-games-${width}.json`), JSON.stringify({ width, dimensions, opened, errors, unexpected,
      boundary: "Isolated API and link fixtures with actual local covers. Not external gameplay or production acceptance." }, null, 2));
  });
}

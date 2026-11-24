import { existsSync } from "node:fs";
import path from "node:path";

import { expect, test } from "@playwright/test";

import { catalogPublicFixture } from "./catalog-public-fixture";

test.use({ locale: "zh-CN" });

const version = "2026-11-24-v1";
const games = [
  { slug: "polytrack", name: "PolyTrack", category: "racing", categoryName: "竞速", ext: "webp", width: 400, height: 300, url: "https://www.kodub.com/apps/polytrack" },
  { slug: "space-huggers", name: "Space Huggers", category: "shooting", categoryName: "射击", ext: "webp", width: 480, height: 360, url: "https://killedbyapixel.github.io/SpaceHuggers/" },
  { slug: "a-dark-room", name: "小黑屋（A Dark Room）", category: "rpg", categoryName: "角色扮演", ext: "svg", width: 480, height: 360, url: "https://adarkroom.doublespeakgames.com/?lang=zh_cn" },
  { slug: "evolution-of-trust", name: "信任的进化", category: "rts", categoryName: "策略", ext: "webp", width: 480, height: 360, url: "https://dccxi.com/trust/" },
].map((game, index) => ({ ...game, id: String(1141 + index) }));
const categories = games.map((game, index) => ({
  id: String(index + 1),
  slug: game.category,
  name: game.categoryName,
  projects: [{
    id: game.id, slug: game.slug, name: game.name, url: game.url, kind: "external",
    description: null, icon_url: null, author_name: null, author_url: null,
    created_at: "2026-11-24T12:00:00+08:00", ai_rating: null,
    average_score: null, rating_count: 0, rating_score_sum: 0, my_score: null, view_count: 0,
  }],
}));

for (const width of [1280, 390, 320]) {
  test(`browser games: category rail covers and direct links at ${width}px`, async ({ page, context }, info) => {
    await page.setViewportSize({ width, height: 900 });
    await page.emulateMedia({ reducedMotion: "reduce" });
    const base = new URL(info.project.use.baseURL as string);
    expect(["127.0.0.1", "localhost", "[::1]"]).toContain(base.hostname);
    const opened: string[] = [];
    const errors: string[] = [];
    page.on("pageerror", (error) => errors.push(error.message));
    await context.route("**/*", async (route) => {
      const req = route.request();
      const url = new URL(req.url());
      if (url.origin === base.origin && url.pathname.startsWith("/static/web/")) {
        const key = url.pathname.slice("/static/web/".length);
        const asset = [path.resolve("../../static/web", key), path.resolve("public", key)]
          .find(existsSync);
        expect(asset, `Missing local file: ${key}`).toBeDefined();
        await route.fulfill({ path: asset! });
      } else if (url.origin === base.origin && url.pathname.startsWith("/api/v1/")) {
        const fixture = catalogPublicFixture(url, categories);
        const view = /^\/api\/v1\/catalog\/projects\/(\d+)\/views$/.exec(url.pathname);
        if (fixture) await route.fulfill({ json: fixture });
        else if (url.pathname === "/api/v1/catalog") await route.fulfill({ json: { data: { categories } } });
        else if (view && req.method() === "POST") {
          opened.push(view[1]!);
          await route.fulfill({ json: { data: { project_id: view[1], view_count: 1 } } });
        } else if (req.method() === "GET") {
          await route.fulfill({ json: { data: url.pathname.endsWith("/settings/public") ? { settings: {} } : [] } });
        } else await route.abort();
      } else if (req.isNavigationRequest() && games.some((game) => game.url === url.href)) {
        // 只验证点击和原始外链，无实际第三方导航或真实统计写入。
        await route.fulfill({ contentType: "text/html", body: "<!doctype html><title>Isolated game entry</title>" });
      } else if (url.origin === base.origin && ["GET", "HEAD"].includes(req.method())) await route.continue();
      else await route.abort();
    });

    await page.goto("/games");
    for (const game of games) {
      const section = page.locator(`[data-category-section="${game.category}"]`);
      await expect(section.getByRole("heading", { name: game.categoryName })).toBeVisible();
      await section.scrollIntoViewIfNeeded();
      const card = section.locator(`[data-project-id="${game.id}"]`);
      await expect(card).toBeVisible();
      // 滚到正常浏览位置，避免截图撞上手机底部固定导航。
      await card.evaluate((node) => node.scrollIntoView({ block: "center", inline: "nearest" }));
      const image = card.locator(".catalog-card__cover img");
      await expect(image).toHaveAttribute("loading", "lazy");
      await expect(image).toHaveAttribute("src", `/static/web/catalog/${version}/covers/${game.slug}.${game.ext}`);
      const size = await image.evaluate(async (img: HTMLImageElement) => {
        await img.decode();
        return [img.naturalWidth, img.naturalHeight];
      });
      expect(size).toEqual([game.width, game.height]);
      if (width < 760) {
        const label = card.locator(".catalog-card__mobile-name");
        await expect(label).toHaveText(game.name);
        expect(await label.evaluate((node) => {
          const { left, top, width, height } = node.getBoundingClientRect();
          return node.contains(document.elementFromPoint(left + width / 2, top + height / 2));
        })).toBe(true);
      }
      await card.screenshot({ path: info.outputPath(`${game.slug}-${width}.png`) });
      const link = card.getByRole("link", { name: `打开${game.name}`, exact: true });
      await expect(link).toHaveAttribute("href", game.url);
      const popupPending = page.waitForEvent("popup");
      await link.click();
      const popup = await popupPending;
      await expect(popup).toHaveURL(game.url);
      await popup.close();
    }
    await expect.poll(() => opened).toEqual(games.map((game) => game.id));
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
    await page.goto("/licenses/catalog-covers.html");
    for (const game of games) {
      await expect(page.locator(`section[aria-labelledby="${game.slug}-cover"]`)).toContainText(game.name);
    }
    expect(errors).toEqual([]);
  });
}

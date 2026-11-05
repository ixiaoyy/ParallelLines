import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";

import { expect, test, type Page } from "@playwright/test";

import { catalogPublicFixture } from "./catalog-public-fixture";

const cdnPrefix = "https://img.pingxingxian.space/static/web/games/birdland/2026-11-05-v1/";
const gamePath = "/games/birdland/index.html";
const publicRoot = path.resolve(process.cwd(), "../../static/web/games/birdland/2026-11-05-v1");
const project = {
  id: "242", slug: "birdland", name: "BIRDLAND", url: gamePath, kind: "internal",
  description: "中文汉化文字互动剧情；包含粗口与成熟话题。",
  author_name: "Brendan Patrick Hennessy / Izzy Marbella", author_url: "https://bphennessy.com/",
  icon_url: null, created_at: "2026-11-05T00:01:00Z", average_score: null, rating_count: 0,
  rating_score_sum: 0, view_count: 123, my_score: null,
};
const categories = [{ id: "18", slug: "romance", name: "恋爱", icon_url: null, projects: [project] }];

/** 等待原有淡入和场景过渡真实完成，避免把动画中的黑屏或半透明画面当成视觉验收。 */
async function waitForPassage(page: Page) {
  await expect.poll(() => page.locator("#passage > :not(#preload)").evaluateAll((elements) =>
    elements.every((element) => Number(getComputedStyle(element).opacity) >= 0.999))).toBe(true);
  await page.waitForFunction(() => document.getAnimations().every((animation) => animation.playState !== "running"));
}

for (const viewport of [{ width: 1280, height: 900 }, { width: 390, height: 844 }, { width: 320, height: 740 }]) {
  test(`Birdland 汉化站内入口、真实 CDN、菜单与存档 ${viewport.width}px`, async ({ page, context }, testInfo) => {
    test.setTimeout(120_000);
    await page.setViewportSize(viewport);
    const output = process.env.BIRDLAND_QA_DIR ?? testInfo.outputDir;
    await mkdir(output, { recursive: true });
    const errors: string[] = [];
    const localImageRequests: string[] = [];
    const images = new Map<string, { status: number; mime: string; bytes: number; matchesLocal: boolean }>();
    const bodyChecks: Promise<void>[] = [];
    context.on("page", (created) => created.on("pageerror", (error) => errors.push(error.message)));
    page.on("pageerror", (error) => errors.push(error.message));
    context.on("request", (request) => {
      if (new URL(request.url()).pathname.startsWith("/games/birdland/img/")) localImageRequests.push(request.url());
    });
    context.on("response", (response) => {
      if (!response.url().startsWith(cdnPrefix)) return;
      const filename = response.url().slice(cdnPrefix.length);
      bodyChecks.push((async () => {
        const body = await response.body();
        images.set(filename, { status: response.status(), mime: response.headers()["content-type"] ?? "",
          bytes: body.length, matchesLocal: body.equals(await readFile(path.join(publicRoot, filename))) });
      })());
    });

    let game = page;
    let opened = 0;
    if (viewport.width === 1280) {
      // 仅目录 API 使用冻结夹具；卡片、游戏 HTML 和全部 CDN 图片均走真实本地/公开资源。
      await context.route("**/api/v1/**", async (route) => {
        const url = new URL(route.request().url());
        const fixture = catalogPublicFixture(url, categories);
        if (fixture) return route.fulfill({ json: fixture });
        if (url.pathname === "/api/v1/catalog") return route.fulfill({ json: { data: { categories } } });
        if (url.pathname === "/api/v1/catalog/projects/242/views") {
          expect(route.request().method()).toBe("POST");
          opened++;
          return route.fulfill({ json: { data: { project_id: "242", view_count: 123 + opened } } });
        }
        expect(route.request().method()).toBe("GET");
        return route.fulfill({ json: { data: url.pathname.endsWith("/settings/public") ? { settings: {} } : [] } });
      });
      await page.goto("/games");
      const search = page.getByRole("searchbox", { name: "搜索游戏名称", exact: true });
      await search.fill("BIRDLAND");
      await search.press("Enter");
      const card = page.locator('article.catalog-card[data-project-id="242"]');
      await expect(card).toHaveCount(1);
      const cover = card.locator(".catalog-card__cover img");
      await expect(cover).toHaveAttribute("src", /\/catalog\/2026-11-05-v4\/covers\/birdland\.jpg$/);
      await expect.poll(() => cover.evaluate((image: HTMLImageElement) => image.complete && image.naturalWidth > 0)).toBe(true);
      const link = card.getByRole("link", { name: "打开BIRDLAND", exact: true });
      await expect(link).toHaveAttribute("href", gamePath);
      await card.screenshot({ path: path.join(output, "catalog-internal-card.png") });
      const popup = context.waitForEvent("page");
      await link.click();
      game = await popup;
      await game.setViewportSize(viewport);
      await expect(game).toHaveURL(new URL(gamePath, page.url()).href);
      await expect.poll(() => opened).toBe(1);
    } else {
      await game.goto(gamePath);
    }
    await expect(game).toHaveTitle("BIRDLAND · 鸟之国度（中文汉化版）");
    await expect(game.locator('#menu a[data-passage="newgame"]')).toHaveText("开始游戏");
    await expect.poll(() => game.locator("#menu a").evaluateAll((elements) => elements.every((element) =>
      getComputedStyle(element).whiteSpace === "nowrap" && element.getBoundingClientRect().height >= 44))).toBe(true);
    await expect.poll(() => images.size, { timeout: 40_000 }).toBe(20);
    await Promise.all(bodyChecks);
    await writeFile(path.join(output, `cdn-browser-${viewport.width}.json`), JSON.stringify(Object.fromEntries(images), null, 2));
    await waitForPassage(game);
    await game.screenshot({ path: path.join(output, `title-${viewport.width}.png`), fullPage: true });
    for (const [filename, response] of images) {
      expect(response.status, filename).toBe(200);
      expect(response.mime, filename).toContain("image/webp");
      expect(response.matchesLocal, filename).toBe(true);
    }
    expect([...images.values()].reduce((sum, image) => sum + image.bytes, 0)).toBe(435272);
    await expect.poll(() => game.locator("#birdland img").evaluate((image: HTMLImageElement) => image.complete && image.naturalWidth > 0)).toBe(true);

    await game.locator('#menu a[data-passage="about"]').click();
    await expect(game.locator("#passage")).toContainText("Brendan Patrick Hennessy");
    await expect(game.locator("#passage")).toContainText("Izzy Marbella");
    await expect(game.locator(".characters img")).toHaveCount(19);
    await expect.poll(() => game.locator(".characters img").evaluateAll((elements) => elements.every((element) => (element as HTMLImageElement).complete && (element as HTMLImageElement).naturalWidth > 0))).toBe(true);
    await waitForPassage(game);
    await game.screenshot({ path: path.join(output, `about-${viewport.width}.png`), fullPage: true });
    await game.locator('.close a[data-passage="title"]').click();
    await game.locator('#menu a[data-passage="options"]').focus();
    await game.keyboard.press("Enter");
    await expect(game.locator("#passage")).toContainText("游戏设置");
    await game.locator("#undoswitchon").click();
    await expect(game.locator("#undoswitchoff")).toBeVisible();
    await game.locator("#undoswitchoff").click();
    await expect(game.locator("#undoswitchon")).toBeVisible();
    await game.locator("#moodswitchon").click();
    await expect(game.locator("#moodswitchoff")).toBeVisible();
    await game.locator("#moodswitchoff").click();
    await expect(game.locator("#moodswitchon")).toBeVisible();
    await game.locator('.close a[data-passage="title"]').click();
    await game.locator('#menu a[data-passage="chapters"]').click();
    await expect(game.locator("#passage")).toContainText("章节选择");
    await expect(game.locator('a[data-passage="west-start"]')).toHaveText("职位名称：警长");
    await game.locator('.close a[data-passage="title"]').click();
    await game.locator('#menu a[data-passage="newgame"]').click();
    await expect(game.locator(".intro").first()).toBeVisible();
    await game.locator('a[data-passage="intro1"]').click();
    await expect(game.locator("#passage")).toContainText("二十什么");
    await game.locator('a[data-passage="intro2"]').click();
    await game.locator('a[data-passage="intro-end"]').click();
    await expect(game.locator("#passage")).toContainText("警长");
    await expect(game.locator("body")).toHaveClass("dream");
    await expect.poll(() => game.locator(".delay1s").evaluateAll((elements) => elements.every((element) =>
      Number(getComputedStyle(element).opacity) >= 0.999))).toBe(true);
    await waitForPassage(game);
    const save = await game.evaluate(() => localStorage.getItem("birdlandautosave"));
    expect(save).not.toBeNull();
    expect(JSON.parse(save!).savedPassage).toBe("intro-end");
    await game.screenshot({ path: path.join(output, `story-${viewport.width}.png`), fullPage: true });
    if (viewport.width <= 360) {
      expect(await game.locator(".sidebox").evaluate((element) => getComputedStyle(element).cssFloat)).toBe("none");
    }
    expect(await game.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
    expect(await game.locator("#passage").evaluate((element) => parseFloat(getComputedStyle(element).fontSize))).toBeGreaterThanOrEqual(16);
    await game.reload();
    await expect(game.locator('#menu a[data-passage="continue"]')).toHaveText("继续游戏");
    await game.locator('#menu a[data-passage="continue"]').click();
    await expect(game.locator("#passage")).toContainText("警长");
    expect(await game.evaluate(() => localStorage.getItem("birdlandautosave"))).toBe(save);
    await game.goto(gamePath);
    await game.locator('#menu a[data-passage="newgame"]').click();
    await expect(game.locator(".intro").first()).toBeVisible();
    expect(await game.evaluate(() => localStorage.getItem("birdlandautosave"))).toBeNull();
    expect(localImageRequests).toEqual([]);
    expect(errors).toEqual([]);
    await writeFile(path.join(output, `game-${viewport.width}-evidence.json`), JSON.stringify({ viewport, cdnImages: images.size,
      localImageRequests, errors, saveRestore: true, restartClearedSave: true, catalogOpenCount: opened,
      boundary: "真实本地 HTML/页面 + 真实公开 CDN；仅目录 API 为冻结夹具，未连接真实业务库或部署应用。" }, null, 2));
  });
}

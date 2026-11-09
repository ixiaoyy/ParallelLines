import { existsSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { expect, test, type Locator, type Page } from "@playwright/test";

import type { CatalogResponse } from "../../src/features/catalog/model";

const baseURL = process.env.PLAYWRIGHT_BASE_URL ?? "http://127.0.0.1:5173";
const staticRoot = fileURLToPath(new URL("../../../../static/web/", import.meta.url));
const publicRoot = fileURLToPath(new URL("../../public/", import.meta.url));
const sourceUrl = "https://github.com/MartinDelophy/awesome-gpt-6-astra";
const longAuthor = "LongCreatorNameWithoutSpacesForAlignmentAcrossCardRows";
const zeroAuthor = "零评分且作品最多的后续作者";
const authorNames = ["短名作者", longAuthor, "站内", zeroAuthor];

test.use({ serviceWorkers: "block" });

/** 作品数与累计评分顺序相反；混合主页链接、纯名称和站内分组，不读取真实目录。 */
function catalogFixture(): CatalogResponse {
  const authors = [
    { name: authorNames[0]!, count: 1, score: 40, cover: "clock-out", url: null, internal: false },
    { name: longAuthor, count: 2, score: 30, cover: "merge-watermelon", url: "https://creators.invalid/long-creator", internal: false },
    { name: null, count: 3, score: 20, cover: "fruit-ninja", url: null, internal: true },
    { name: zeroAuthor, count: 4, score: 0, cover: "csgo-desert", url: null, internal: false },
  ];
  return { categories: [{
    id: "1", slug: "puzzle", name: "解谜", icon_url: null,
    projects: authors.flatMap((author, authorIndex) => Array.from({ length: author.count }, (_, index) => ({
      id: String(1001 + authorIndex * 10 + index),
      // 每位作者的首项沿真实封面映射取图；后续独立记录只扩展作品数。
      slug: index === 0 ? author.cover : `${author.cover}-leaderboard-${index + 1}`,
      name: `榜单验收游戏${authorIndex + 1}-${index + 1}`,
      url: `https://leaderboard-game.invalid/${authorIndex + 1}/${index + 1}`,
      kind: author.internal ? "internal" as const : "external" as const,
      description: "本地榜单回归夹具",
      author_name: author.name,
      author_url: author.url,
      icon_url: null,
      created_at: "2026-11-01T00:00:00Z",
      average_score: index === 0 && author.score > 0 ? 5 : null,
      rating_count: index === 0 ? author.score / 5 : 0,
      rating_score_sum: index === 0 ? author.score : 0,
      view_count: 0,
      my_score: null,
    }))),
  }] };
}

/** 全部 API 和外部目标均在浏览器拦截；只放行本机前端，并从仓库读取正式图片。 */
async function mockLeaderboard(page: Page) {
  const localOrigin = new URL(baseURL).origin;
  expect(["127.0.0.1", "localhost", "[::1]"].includes(new URL(baseURL).hostname)).toBe(true);
  const unexpected: string[] = [];
  const writes: string[] = [];
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.context().route("**/*", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const headers = {
      "access-control-allow-origin": "*", "access-control-allow-methods": "GET, OPTIONS",
      "access-control-allow-headers": "content-type, authorization",
    };
    if (url.pathname.startsWith("/static/web/")) {
      const key = url.pathname.slice("/static/web/".length);
      const source = [path.resolve(staticRoot, key), path.resolve(publicRoot, key)].find(existsSync);
      expect(source, `本地正式图片缺失：${key}`).toBeDefined();
      await route.fulfill({ path: source!, headers });
      return;
    }
    if (url.pathname.startsWith("/api/")) {
      if (request.method() === "OPTIONS") {
        await route.fulfill({ status: 204, headers });
      } else if (request.method() !== "GET") {
        writes.push(`${request.method()} ${url.href}`);
        await route.fulfill({ status: 405, json: { error: { code: "TEST_WRITE_BLOCKED", message: "榜单操作不得写入" } }, headers });
      } else if (url.pathname === "/api/v1/catalog") {
        await route.fulfill({ json: { data: catalogFixture() }, headers });
      } else if (url.pathname === "/api/v1/site/settings") {
        await route.fulfill({ json: { data: { settings: {}, updated_at: null } }, headers });
      } else {
        unexpected.push(`${request.method()} ${url.href}`);
        await route.fulfill({ status: 404, json: { error: { code: "TEST_UNEXPECTED_API", message: "未声明的 API" } }, headers });
      }
      return;
    }
    if (url.href === sourceUrl && request.resourceType() === "document") {
      await route.fulfill({ contentType: "text/html; charset=utf-8", body: "<!doctype html><meta charset='utf-8'><h1>本地开源清单目标</h1>" });
      return;
    }
    if (url.origin !== localOrigin || !["GET", "HEAD"].includes(request.method())) {
      unexpected.push(`${request.method()} ${url.href}`);
      await route.abort();
      return;
    }
    await route.continue();
  });
  return { unexpected, writes, errors };
}

/** 等待实际封面解码再截图，后续名次仍按其真实懒加载入口触发。 */
async function prepareCovers(leaderboard: Locator) {
  for (const cover of await leaderboard.locator(".catalog-podium__art > img, img.catalog-leaderboard__cover").all()) {
    await cover.scrollIntoViewIfNeeded();
    await expect.poll(() => cover.evaluate((image: HTMLImageElement) => image.complete && image.naturalWidth > 0 && image.naturalHeight > 0)).toBe(true);
    await cover.evaluate((image: HTMLImageElement) => image.decode());
  }
  await leaderboard.page().evaluate(() => window.scrollTo({ top: 0, behavior: "instant" }));
}

/** 除文档宽度外也核对内容边界，避免根节点裁切掩盖长名称或按钮溢出。 */
async function expectNoHorizontalOverflow(page: Page, leaderboard: Locator, width: number) {
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width + 1);
  const bounds = await leaderboard.locator(".catalog-podium__card, .catalog-podium__name, .catalog-podium__metric, .catalog-leaderboard__row, .catalog-leaderboard__identity, .catalog-leaderboard__metric, .catalog-leaderboard__open").evaluateAll((elements) => elements.map((element) => {
    const rect = element.getBoundingClientRect();
    return { left: rect.left, right: rect.right, overflow: element.scrollWidth - element.clientWidth };
  }));
  for (const bound of bounds) {
    expect(bound.left).toBeGreaterThanOrEqual(-1);
    expect(bound.right).toBeLessThanOrEqual(width + 1);
    expect(bound.overflow).toBeLessThanOrEqual(1);
  }
}

test("作者榜隐藏评分心数并保持真实排名，长短名称与按钮在各视口整齐对齐", async ({ page }, testInfo) => {
  test.setTimeout(90_000);
  const requests = await mockLeaderboard(page);
  await page.goto("/games?view=authors");
  const leaderboard = page.getByRole("region", { name: "作者榜", exact: true });
  const podium = leaderboard.locator(".catalog-podium__place");
  await expect(podium).toHaveCount(3);
  // 明确数量，不能让无封面时的空遍历冒充真实图片验收。
  await expect(podium.locator(".catalog-podium__art > img")).toHaveCount(3);
  await expect(leaderboard.locator("img.catalog-leaderboard__cover")).toHaveCount(1);
  await expect(podium.locator(".catalog-podium__name")).toHaveText(authorNames.slice(0, 3));
  await expect(podium.locator(".catalog-podium__metric")).toHaveText(["1 个作品", "2 个作品", "3 个作品"]);
  await expect(leaderboard.locator('.catalog-leaderboard__row[data-rank="4"] .catalog-leaderboard__metric')).toHaveText("4 个作品");
  await expect(podium.locator("a.catalog-podium__name")).toHaveCount(1);
  await expect(podium.locator("strong.catalog-podium__name")).toHaveCount(2);
  await expect(leaderboard.locator(".anticon-heart, svg[data-icon='heart']")).toHaveCount(0);
  await expect(leaderboard).not.toContainText(/\d+\s*心/);

  for (const width of [1440, 921, 641, 390, 320]) {
    await page.setViewportSize({ width, height: 980 });
    await prepareCovers(leaderboard);
    await expectNoHorizontalOverflow(page, leaderboard, width);
    const layout = await podium.evaluateAll((places) => places.map((place) => {
      const top = (selector: string) => place.querySelector(selector)!.getBoundingClientRect().top;
      const rect = place.getBoundingClientRect();
      return { rank: Number(place.getAttribute("data-rank")), left: rect.left, top: rect.top,
        name: top(".catalog-podium__name"), metric: top(".catalog-podium__metric"), button: top(".catalog-leaderboard__open") };
    }));
    if (width > 640) {
      // 桌面允许长名称换行，但姓名起点、作品数和底部操作仍各自共用水平线。
      for (const key of ["name", "metric", "button"] as const) {
        const positions = layout.map((entry) => entry[key]);
        expect(Math.max(...positions) - Math.min(...positions), `${width}px ${key} 对齐`).toBeLessThanOrEqual(1);
      }
      expect([...layout].sort((left, right) => left.left - right.left).map((entry) => entry.rank)).toEqual([2, 1, 3]);
    } else {
      expect([...layout].sort((left, right) => left.top - right.top).map((entry) => entry.rank)).toEqual([1, 2, 3]);
      expect(layout[1]!.top).toBeGreaterThan(layout[0]!.top);
      expect(layout[2]!.top).toBeGreaterThan(layout[1]!.top);
    }
    await page.screenshot({ path: testInfo.outputPath(`authors-${width}.png`), fullPage: true });
  }
  expect(requests).toEqual({ unexpected: [], writes: [], errors: [] });
});

test("作者搜索保留原名次和空态，隐藏评分后仍可查看完整作者作品", async ({ page }) => {
  const requests = await mockLeaderboard(page);
  await page.goto("/games?view=authors");
  const search = page.getByRole("searchbox", { name: "搜索作者", exact: true });
  await search.fill(longAuthor);
  const podium = page.locator(".catalog-podium__place");
  await expect(podium).toHaveCount(1);
  await expect(podium).toHaveAttribute("data-rank", "2");
  await expect(podium).toHaveAttribute("value", "2");
  await search.fill(zeroAuthor);
  await expect(podium).toHaveCount(0);
  await expect(page.locator(".catalog-leaderboard__row")).toHaveAttribute("data-rank", "4");
  await search.fill("不存在的作者");
  await expect(page.locator(".catalog-leaderboard__empty")).toHaveText("没有找到匹配的作者。");
  await expect(page.locator(".catalog-leaderboard__empty")).toHaveAttribute("role", "status");
  await search.fill(longAuthor);
  await page.getByRole("button", { name: `查看${longAuthor}的作品`, exact: true }).click();
  await expect.poll(() => new URL(page.url()).searchParams.get("author")).toBe("profile:https://creators.invalid/long-creator");
  await expect(page.locator(".catalog-author-selection")).toContainText(longAuthor);
  await expect(page.locator(".catalog-results")).toHaveText("2 个游戏");
  await expect(page.locator(".catalog-card")).toHaveCount(2);
  expect(requests).toEqual({ unexpected: [], writes: [], errors: [] });
});

test("贡献榜保持来源第一、GitHub 清单链接及作品入口", async ({ page }, testInfo) => {
  const requests = await mockLeaderboard(page);
  await page.goto("/games?view=contributors");
  const leaderboard = page.getByRole("region", { name: "贡献榜", exact: true });
  const source = leaderboard.locator('.catalog-podium__place[data-rank="1"]');
  await expect(source.locator(".catalog-podium__name")).toHaveText("martindelophy");
  await expect(source.locator(".catalog-podium__metric")).toHaveText("开源贡献");
  await expect(source.locator(".catalog-podium__source-art svg[data-icon='github']")).toBeVisible();
  await expect(source.locator(".catalog-podium__art > img")).toHaveCount(0);
  await expect(leaderboard.locator(".catalog-podium__art > img")).toHaveCount(2);
  await expect(leaderboard.locator("img.catalog-leaderboard__cover")).toHaveCount(2);
  for (const link of [source.locator(".catalog-podium__name"), source.locator(".catalog-leaderboard__open")]) {
    await expect(link).toHaveAttribute("href", sourceUrl);
    await expect(link).toHaveAttribute("target", "_blank");
    await expect(link).toHaveAttribute("rel", "noopener noreferrer");
  }
  await expect(leaderboard.locator('.catalog-podium__place[data-rank="2"] .catalog-podium__name')).toHaveText(zeroAuthor);
  for (const width of [1440, 320]) {
    await page.setViewportSize({ width, height: 980 });
    await prepareCovers(leaderboard);
    await expectNoHorizontalOverflow(page, leaderboard, width);
    await page.screenshot({ path: testInfo.outputPath(`contributors-${width}.png`), fullPage: true });
  }
  const popupPromise = page.waitForEvent("popup");
  await source.getByRole("link", { name: "查看清单", exact: true }).click();
  const popup = await popupPromise;
  await expect(popup.getByRole("heading", { name: "本地开源清单目标", exact: true })).toBeVisible();
  await popup.close();
  await leaderboard.getByRole("button", { name: `查看${zeroAuthor}的作品`, exact: true }).click();
  await expect(page.locator(".catalog-results")).toHaveText("4 个游戏");
  expect(requests).toEqual({ unexpected: [], writes: [], errors: [] });
});

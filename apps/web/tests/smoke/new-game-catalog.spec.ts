import path from "node:path";

import { expect, test } from "@playwright/test";

// 本地目录验收使用固定的两条 API 数据和本次正式图片，不访问共享数据库或 CDN。
const games = [
  { id: "901", slug: "snake-escape", name: "蛇蛇出洞", category: "puzzle", categoryName: "解谜" },
  { id: "902", slug: "flappy-dunk", name: "飞翼灌篮", category: "casual", categoryName: "休闲" },
];

test("新游戏目录读取正式封面，打开对应站内路由并记录打开次数", async ({ page, context }) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  const opened: string[] = [];
  await context.route("**/api/v1/catalog", (route) => route.fulfill({
    json: { data: { categories: games.map((game) => ({
      id: game.id, slug: game.category, name: game.categoryName, icon_url: null,
      projects: [{
        id: game.id, slug: game.slug, name: game.name, url: `/play/${game.slug}`, kind: "internal",
        description: "站内小游戏", author_name: null, author_url: null, icon_url: null,
        created_at: "2026-09-30T00:00:00Z", average_score: null, rating_count: 0,
        rating_score_sum: 0, view_count: 0, my_score: null,
      }],
    })) } },
  }));
  await context.route("**/api/v1/catalog/projects/*/views", (route) => {
    const id = new URL(route.request().url()).pathname.split("/").at(-2) ?? "";
    opened.push(id);
    return route.fulfill({ json: { data: { project_id: id, view_count: 1 } } });
  });
  await context.route("**/static/web/**", (route) => {
    const key = new URL(route.request().url()).pathname.split("/static/web/")[1];
    return route.fulfill({ path: path.resolve(process.cwd(), "../../static/web", key) });
  });
  await page.goto("/");

  for (const game of games) {
    const card = page.locator(".catalog-card").filter({ hasText: game.name });
    const cover = card.locator(".catalog-card__media-link img");
    await expect(cover).toHaveAttribute("src", new RegExp(`/2026-09-30-v1/covers/${game.slug}\\.webp$`));
    await expect.poll(() => cover.evaluate((img) => (img as HTMLImageElement).naturalWidth)).toBe(960);
    const pendingPopup = context.waitForEvent("page");
    await card.locator(".catalog-card__media-link").click();
    const popup = await pendingPopup;
    popup.on("pageerror", (error) => errors.push(error.message));
    await expect(popup).toHaveURL(new RegExp(`/play/${game.slug}$`));
    await expect(popup.getByRole("heading", { name: game.name, exact: true })).toBeVisible();
    await expect.poll(() => opened.includes(game.id)).toBe(true);
    await popup.close();
  }
  expect(errors).toEqual([]);
});

import path from "node:path";

import { expect, test } from "@playwright/test";

const baseURL = process.env.PLAYWRIGHT_BASE_URL ?? "http://127.0.0.1:5173";

// 本批确认资料作为固定目录响应；使用真实前端和本地正式封面，不连接项目数据库。
const games = [
  {
    id: "911", slug: "soulforge", name: "SOULFORGE 灵魂锻炉", category: "action",
    url: "https://soulforge.glasden.top/", author: "Glasden",
    authorUrl: "https://linux.do/u/glasden/summary",
    description: "像素风动作生存游戏，在裂隙中迎战成群敌人，通过装备合成、符文选择与锻炉强化构筑角色，挑战波次与首领。",
  },
  {
    id: "912", slug: "achroma", name: "Achroma", category: "action",
    url: "https://game.unsnow.online/ach/", author: "snowunseasonl",
    authorUrl: "https://linux.do/u/snowunseasonl/summary",
    description: "像素风地牢动作游戏，在灰白世界中探索房间、收集棱镜碎片，组合武器与元素强化，闪避弹幕并挑战首领，夺回失去的色彩。",
  },
  {
    id: "913", slug: "pelican-rider", name: "鹈鹕骑手", category: "racing",
    url: "https://luoxiaoman.com/pelican-rider/", author: "aqua33",
    authorUrl: "https://linux.do/u/aqua33/summary",
    description: "和一群鹈鹕骑车穿过海岸、花田、松林与港口小镇，吃鱼补充体力、躲避障碍，借助尾流与道具争先抵达终点。",
  },
  {
    id: "914", slug: "shousui", name: "守岁 · 猫与十二生肖", category: "rts",
    url: "https://shousui.vercel.app/", author: "donghuyulong",
    authorUrl: "https://linux.do/u/donghuyulong/summary",
    description: "以十二生肖与天轮为核心的回合制策略游戏，通过猫牌出击、拨动时针和生肖羁绊布阵，在除夕之夜与猫一起守岁。",
  },
  {
    id: "915", slug: "sketch-rts", name: "SKETCH RTS", category: "rts",
    url: "https://lexicalmathical.com/sketch-rts/", author: "Jeffry",
    authorUrl: "https://linux.do/u/jeffry/summary",
    description: "即时战略游戏，指挥农民采集金矿、建设基地与兵营，训练部队并运用不同兵种和法术展开战斗。",
  },
  {
    id: "916", slug: "bubble-tank", name: "泡泡坦克 Bubble Tanks", category: "shooting",
    url: "https://bubble-tank.zackwill.space/", author: "ZackWill",
    authorUrl: "https://linux.do/u/zackwill/summary",
    description: "操控泡泡坦克射击敌人，收集泡泡成长进化，在无尽的泡泡海中探索与战斗。",
  },
];

const categories = [
  { id: "1", slug: "action", name: "动作" },
  { id: "2", slug: "racing", name: "竞速" },
  { id: "3", slug: "rts", name: "策略" },
  { id: "4", slug: "shooting", name: "射击" },
  { id: "5", slug: "puzzle", name: "解谜" },
];
const projects = games.map((game) => ({
  id: game.id, slug: game.slug, name: game.name, category: game.category,
  url: game.url, kind: "external", description: game.description,
  author_name: game.author, author_url: game.authorUrl, icon_url: null,
  created_at: "2026-10-06T00:00:00Z", average_score: null,
  rating_count: 0, rating_score_sum: 0, view_count: 0, my_score: null,
}));
const fixture = {
  categories: categories.map((category) => ({
    ...category, icon_url: null,
    projects: category.slug === "puzzle" ? [{
      id: "901", slug: "snake-escape", name: "蛇蛇出洞", url: "/play/snake-escape",
      kind: "internal", description: "按顺序放走彩色小蛇，避开阻挡，在倒计时结束前清空棋盘。",
      author_name: null, author_url: null, icon_url: null, created_at: "2026-09-30T00:00:00Z",
      average_score: null, rating_count: 0, rating_score_sum: 0, view_count: 0, my_score: null,
    }] : projects.filter((game) => game.category === category.slug),
  })),
};

for (const viewport of [
  { name: "desktop", width: 1280, height: 900 },
  { name: "mobile", width: 390, height: 844 },
]) {
  test.describe(viewport.name, () => {
    test.use({ viewport: { width: viewport.width, height: viewport.height } });

    test("六款外部游戏显示正式封面、作者与正确打开地址，并保留旧封面", async ({ page, context }, testInfo) => {
      const errors: string[] = [];
      const opened: string[] = [];
      const externalRequests: string[] = [];
      page.on("pageerror", (error) => errors.push(error.message));
      const localOrigin = new URL(baseURL).origin;

      // 所有 API 都用安全固定响应；CDN 回读本地文件，外站弹窗文档也不发出真实请求。
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
            expect(request.method()).toBe("POST");
            const id = viewMatch[1]!;
            opened.push(id);
            await route.fulfill({ json: { data: { project_id: id, view_count: 1 } }, headers });
          } else {
            await route.fulfill({ json: {
              data: url.pathname.endsWith("/settings/public") ? { settings: {} } : [],
            }, headers });
          }
          return;
        }
        if (request.resourceType() === "document" && games.some((game) => game.url === url.href)) {
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
      await expect(page.locator("article.catalog-card")).toHaveCount(7);
      for (const game of games) {
        const card = page.locator("article.catalog-card").filter({
          has: page.getByRole("heading", { name: game.name, exact: true }),
        });
        const cover = card.locator(".catalog-card__media-link img");
        await cover.scrollIntoViewIfNeeded();
        await expect(cover).toHaveAttribute("src", new RegExp(`/2026-10-06-v1/covers/${game.slug}\\.webp$`));
        await expect.poll(() => cover.evaluate((img) => ({
          width: (img as HTMLImageElement).naturalWidth,
          height: (img as HTMLImageElement).naturalHeight,
        }))).toEqual({ width: 960, height: 452 });
        expect(await cover.evaluate((img) => getComputedStyle(img).objectFit)).toBe("cover");
        for (const selector of [".catalog-card__media-link", ".catalog-card__title-link", ".catalog-card__open"]) {
          const link = card.locator(selector);
          await expect(link).toHaveAttribute("href", game.url);
          await expect(link).toHaveAttribute("target", "_blank");
          await expect(link).toHaveAttribute("rel", "noopener noreferrer");
        }
        const author = card.getByRole("link", { name: `查看${game.author}的作者链接`, exact: true });
        await expect(author).toHaveText(game.author);
        await expect(author).toHaveAttribute("href", game.authorUrl);
        await expect(author).toHaveAttribute("target", "_blank");
        await expect(author).toHaveAttribute("rel", "noopener noreferrer");
        const bounds = await card.boundingBox();
        expect(bounds).not.toBeNull();
        expect(bounds!.x).toBeGreaterThanOrEqual(0);
        expect(bounds!.x + bounds!.width).toBeLessThanOrEqual(viewport.width);
      }

      // 旧版本封面地址与原尺寸必须继续可用，不能被本批映射替换。
      const oldCover = page.locator("article.catalog-card").filter({
        has: page.getByRole("heading", { name: "蛇蛇出洞", exact: true }),
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
      await page.screenshot({ path: testInfo.outputPath(`external-games-${viewport.name}.png`), fullPage: true });

      for (const game of games) {
        const card = page.locator("article.catalog-card").filter({
          has: page.getByRole("heading", { name: game.name, exact: true }),
        });
        const pendingPopup = context.waitForEvent("page");
        await card.locator(".catalog-card__media-link").click();
        const popup = await pendingPopup;
        await expect(popup).toHaveURL(game.url);
        await expect(popup.getByRole("heading", { name: "已打开本地验收目标" })).toBeVisible();
        await expect.poll(() => opened.filter((id) => id === game.id).length).toBe(1);
        await popup.close();
      }
      expect(opened).toEqual(games.map((game) => game.id));
      expect(externalRequests).toEqual([]);
      expect(errors).toEqual([]);
    });
  });
}

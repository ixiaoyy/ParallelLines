import path from "node:path";

import { expect, test } from "@playwright/test";

import type { CatalogProjectResponse, CatalogResponse } from "../../src/features/catalog/model";

const baseURL = process.env.PLAYWRIGHT_BASE_URL ?? "http://127.0.0.1:5173";

// 固定本批已确认的目录资料，测试运行不依赖本地任务文件或项目数据库。
const games = [
  {
    id: "931", slug: "hollowmark", category: "shooting", name: "HOLLOWMARK",
    url: "https://hollowmark.mindblown.ai/", author_name: "Mindblown", author_url: "https://mindblown.ai/",
    description: "第一人称探索工业地下世界，寻找门禁卡、管理弹药并迎战敌人。",
  },
  {
    id: "932", slug: "canyon-overdrive", category: "shooting", name: "Canyon Overdrive",
    url: "https://canyonoverdrive.ai-created.com/", author_name: "Marco van Hylckama Vlieg / AI & Design", author_url: "https://x.com/AIandDesign",
    description: "驾驶战机穿越霓虹峡谷，以机炮、导弹与滚转突破封锁。",
  },
  {
    id: "933", slug: "flight-1073", category: "stages", name: "Flight 1073",
    url: "https://flight1073.pages.dev/play/", author_name: "Guy Eshel", author_url: "https://x.com/GuyEshel_",
    description: "希伯来语航空恶搞小游戏，躲避餐车、完成限时任务并设法降落。",
  },
  {
    id: "934", slug: "foe-to-fleet", category: "shooting", name: "FOE TO FLEET",
    url: "https://foe-to-fleet.miya333.chatgpt.site", author_name: "miya", author_url: "https://x.com/miya00907380",
    description: "将击败的敌人收编为舰队，让伙伴协助攻防，撑过七波弹幕进攻。",
  },
  {
    id: "935", slug: "moxride", category: "action", name: "MoxRide",
    url: "https://www.moxride.com/", author_name: "Moxazza / Moxazza Games", author_url: "https://www.moxride.com/",
    description: "在彩色城市中下坡滑板，通过磨轨、腾空动作与连续技巧得分。",
  },
  {
    id: "936", slug: "midway-1942", category: "shooting", name: "中途岛海战·空中突击",
    url: "https://ihca.cn/midway/", author_name: "xilinnihao-afk / 一海千寻的AI实验室", author_url: "https://github.com/xilinnihao-afk",
    description: "与僚机迎战敌机并轰炸航母，掌握重力投弹落点，返回友舰补给。",
  },
  {
    id: "937", slug: "sandline", category: "shooting", name: "沙线行动 / SANDLINE",
    url: "https://ihca.cn/sandline/", author_name: "xilinnihao-afk / 一海千寻的AI实验室", author_url: "https://github.com/xilinnihao-afk",
    description: "与 AI 队友进行单机 3 对 3 战术交战，运用掩体、枪械与手雷争夺爆破目标。",
  },
  {
    id: "938", slug: "surge-for-oinja", category: "action", name: "SURGE for Oinja",
    url: "https://oinja-game.vercel.app/", author_name: "Olivia", author_url: "https://github.com/Olivia295",
    description: "自动攻击的第三人称生存游戏，组合电气技能和支援机械，修复设施并挑战首领。",
  },
  {
    id: "939", slug: "jellyblob", category: "action", name: "JellyBlob.win",
    url: "https://jellyblob.win/", author_name: "kvickan", author_url: "https://buymeacoffee.com/kvickan",
    description: "多人果冻竞技场，收集水滴、用尾迹围堵对手并跳跃避险。",
  },
  {
    id: "940", slug: "astra-2048-eddy", category: "puzzle", name: "Astra 2048",
    url: "https://jianfan.app/2048/gpt/", author_name: "Eddy", author_url: "https://x.com/ieddysun",
    description: "滑动合并相同数字并挑战 2048，收录作者模型对比中的 Astra 版本。",
  },
  {
    id: "941", slug: "the-fourth-knock", category: "puzzle", name: "The Fourth Knock",
    url: "https://nikhilsatishdesai.github.io/the-fourth-knock/play/", author_name: "Nikhil Desai", author_url: "https://x.com/NikhilDesai_007",
    description: "探索 Cedar House、询问人物并组合线索，解开 2.5D 密室凶案。",
  },
  {
    id: "942", slug: "saber-descent", category: "action", name: "Saber / Descent",
    url: "https://vheissu.github.io/saber-battle/", author_name: "Dwayne", author_url: "https://x.com/CtrlAltDwayne",
    description: "持能量剑探索五层地牢，以连击、格挡和冲刺击败守卫并前进。",
  },
  {
    id: "943", slug: "sulli-run", category: "stages", name: "Sulli RUN",
    url: "https://sulli-game.vercel.app/", author_name: "Morteza", author_url: "https://x.com/Mortezabihzadeh",
    description: "操控 3D 大猩猩在霓虹城市跑酷，换道、跳跃和滑行躲避障碍得分。",
  },
] as const;

const categories = [
  { id: "1", slug: "action", name: "动作" },
  { id: "2", slug: "shooting", name: "射击" },
  { id: "3", slug: "puzzle", name: "解谜" },
  { id: "4", slug: "stages", name: "闯关" },
];
const projects = games.map((game) => ({
  id: game.id, slug: game.slug, name: game.name, url: game.url,
  kind: "external" as const, description: game.description,
  author_name: game.author_name, author_url: game.author_url, icon_url: null,
  created_at: "2026-10-08T00:00:00Z", average_score: null,
  rating_count: 0, rating_score_sum: 0, view_count: 0, my_score: null,
})) satisfies CatalogProjectResponse[];
// 同一夹具保留旧原创游戏，核对本批映射没有覆盖既有封面。
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

    test("十三款更新显示正式封面、作者及外链，打开记录不影响旧封面", async ({ page, context }, testInfo) => {
      const errors: string[] = [];
      const opened: string[] = [];
      const externalRequests: string[] = [];
      const loadedCovers = new Set<string>();
      const localOrigin = new URL(baseURL).origin;
      const gameTargets = new Set(games.map((game) => new URL(game.url).href));
      page.on("pageerror", (error) => errors.push(error.message));
      context.on("page", (popup) => popup.on("pageerror", (error) => errors.push(error.message)));

      // API 使用固定响应，CDN 图片回读本地正式素材；其他外站请求全部隔离。
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
            // 每次游戏入口点击只发送一次空对象 POST，并使用夹具累计量更新卡片。
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
        // 弹窗保留真实外链地址，但内容由本地响应模拟，不访问游戏服务器。
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
      for (const game of games) {
        const card = page.locator("article.catalog-card").filter({
          has: page.getByRole("heading", { name: game.name, exact: true }),
        });
        const cover = card.locator(".catalog-card__media-link img");
        await cover.scrollIntoViewIfNeeded();
        await expect(cover).toHaveAttribute("src", new RegExp(`/2026-10-08-v1/covers/${game.slug}\\.webp$`));
        await expect.poll(() => cover.evaluate((img) => ({
          width: (img as HTMLImageElement).naturalWidth,
          height: (img as HTMLImageElement).naturalHeight,
        }))).toEqual({ width: 960, height: 452 });
        expect(await cover.evaluate((img) => getComputedStyle(img).objectFit)).toBe("cover");
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
      }

      // 旧封面继续使用原版本与原尺寸，新游戏不能回退到文字或分类占位图。
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
      for (const game of games) {
        expect(loadedCovers.has(`catalog/2026-10-08-v1/covers/${game.slug}.webp`)).toBe(true);
      }
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
      await page.evaluate(() => window.scrollTo(0, 0));
      await page.screenshot({ path: testInfo.outputPath(`astra-updates-${viewport.name}.png`), fullPage: true });

      // 封面、标题和开始游戏三个入口各记录一次打开，不能重复统计或阻止弹窗。
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

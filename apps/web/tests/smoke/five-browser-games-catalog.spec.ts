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
const version = "2026-11-05-v5";
// 根代理锁定的最终480px内署名缩略图；按实际文件核尺寸和裁切，不借上游评分造本站评分。
const covers: Record<string, { file: string; width: number; height: number; mime: string }> = {
  "her-tears-were-my-light": { file: "her-tears-were-my-light.webp", width: 480, height: 155, mime: "image/webp" },
  farmhand: { file: "farmhand.webp", width: 480, height: 400, mime: "image/webp" },
  "exhibit-of-sorrows": { file: "exhibit-of-sorrows.webp", width: 394, height: 342, mime: "image/webp" },
  "known-unknowns": { file: "known-unknowns.webp", width: 400, height: 480, mime: "image/webp" },
  "crosscode-demo": { file: "crosscode-demo.webp", width: 356, height: 480, mime: "image/webp" },
};
const gameAuthors: Record<string, { name: string; url: string; display: string; collaborator: string }> = {
  "her-tears-were-my-light": { name: "NomnomNami / Emmit / LydianChord", url: "https://nomnomnami.itch.io/", display: "NomnomNami", collaborator: "LydianChord" },
  farmhand: { name: "Jeremy Kahn / Farmhand contributors", url: "https://jeremyckahn.itch.io/", display: "Jeremy Kahn", collaborator: "Farmhand contributors" },
  "exhibit-of-sorrows": { name: "Maxim Tsai (adayofjoy) / Theresa Kao", url: "https://adayofjoy.itch.io/", display: "Maxim Tsai (adayofjoy)", collaborator: "Theresa Kao" },
  "known-unknowns": { name: "Brendan Patrick Hennessy / Izzy Marbella", url: "https://bphennessy.com/", display: "Brendan Patrick Hennessy", collaborator: "Izzy Marbella" },
  "crosscode-demo": { name: "Radical Fish Games", url: "https://www.radicalfishgames.com/", display: "Radical Fish Games", collaborator: "Radical Fish Games" },
};

// 固定本批已确认资料；新标签和打开统计均在隔离夹具内响应，不请求真实游戏或生产 API。
const games = [
  {
    id: "9951", slug: "her-tears-were-my-light", category: "romance", name: "她的眼泪曾是我的光芒（Her Tears Were My Light）",
    url: "https://html-classic.itch.zone/html/18220499/index.html?v=1783279519", licenseTitle: /Her Tears|她的眼泪/,
  },
  {
    id: "9952", slug: "farmhand", category: "farming", name: "Farmhand",
    url: "https://jeremyckahn.github.io/farmhand/", licenseTitle: /Farmhand/,
  },
  {
    id: "9953", slug: "exhibit-of-sorrows", category: "horror", name: "Exhibit of Sorrows",
    url: "https://html-classic.itch.zone/html/14611877/index.html", licenseTitle: /Exhibit of Sorrows/,
  },
  {
    id: "9954", slug: "known-unknowns", category: "romance", name: "Known Unknowns",
    url: "https://known.zone/one", licenseTitle: /Known Unknowns/,
  },
  {
    id: "9955", slug: "crosscode-demo", category: "rpg", name: "CrossCode（网页试玩版）",
    url: "https://www.cross-code.com/en/start", licenseTitle: /CrossCode/,
  },
] as const;

const categories = [
  { id: "1", slug: "romance", name: "恋爱" },
  { id: "2", slug: "farming", name: "种田" },
  { id: "3", slug: "horror", name: "恐怖" },
  { id: "4", slug: "rpg", name: "角色扮演" },
];
const projects = games.map((game, index) => ({
  id: game.id, slug: game.slug, name: game.name, url: game.url, kind: "external" as const,
  description: null, author_name: gameAuthors[game.slug]?.name ?? null, author_url: gameAuthors[game.slug]?.url ?? null, icon_url: null,
  created_at: `2026-11-05T00:0${5 - index}:00Z`, average_score: null, rating_count: 0,
  rating_score_sum: 0, view_count: 0, my_score: null, ai_rating: null,
})) satisfies CatalogProjectResponse[];
const oldProjects = [
  { id: "242", slug: "birdland", name: "BIRDLAND", url: "https://birdland.camp/", category: "romance", kind: "external" as const,
    description: null, author_name: "Brendan Patrick Hennessy / Izzy Marbella", author_url: "https://bphennessy.com/",
    icon_url: null, created_at: "2026-09-30T00:00:00Z", average_score: 3, rating_count: 1,
    rating_score_sum: 3, view_count: 7, my_score: null, ai_rating: null },
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
  const coverPath = `/catalog/${version}/covers/${covers[slug]!.file}`;
  await card.scrollIntoViewIfNeeded();
  await expect(cover).toHaveAttribute("src", new RegExp(`${coverPath.replaceAll(".", "\\.")}$`));
  await expect.poll(() => cover.evaluate((image: HTMLImageElement) =>
    image.complete && image.naturalWidth > 0 && image.naturalHeight > 0)).toBe(true);
  const dimensions = await cover.evaluate(async (image: HTMLImageElement) => {
    await image.decode();
    return { width: image.naturalWidth, height: image.naturalHeight };
  });
  expect(dimensions).toEqual({ width: covers[slug]!.width, height: covers[slug]!.height });
  expect(dimensions.width / dimensions.height).toBeCloseTo(CATALOG_COVER_ASPECTS_BY_PATH[coverPath]!, 8);
  // 分类横排统一完整显示原图；搜索网格仍裁切，CrossCode 保留其精确素材顶部定位。
  const inRail = await card.evaluate((element) => Boolean(element.closest("[data-category-rail]")));
  expect(await cover.evaluate((image) => getComputedStyle(image).objectFit), `${slug} fit`).toBe(inRail ? "contain" : "cover");
  const expectedPosition = slug === "crosscode-demo" ? "50% 0%" : "50% 50%";
  expect(await cover.evaluate((image) => getComputedStyle(image).objectPosition), `${slug} position`).toBe(expectedPosition);
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

    test("五款新增直达游戏的分页、正式封面、搜索、作者榜与打开入口完整", async ({ page, context }, testInfo) => {
      test.setTimeout(90_000);
      for (const game of games) {
        expect(covers[game.slug], `${game.slug} 正式尺寸待确认`).toBeDefined();
        expect(gameAuthors[game.slug], `${game.slug} 作者资料待确认`).toBeDefined();
      }
      expect(["127.0.0.1", "localhost", "[::1]"].includes(new URL(baseURL).hostname)).toBe(true);
      const output = process.env.FIVE_BROWSER_GAMES_QA_DIR ?? testInfo.outputDir;
      await mkdir(output, { recursive: true });
      const errors: string[] = [];
      const unexpected: string[] = [];
      const opened: string[] = [];
      const fullReads: string[] = [];
      const pageReads: string[] = [];
      const loadedCovers = new Set<string>();
      const dimensions: Record<string, { width: number; height: number }> = {};
      let licenseStatus: number | undefined;
      const licensePath = "/licenses/catalog-covers.html";
      const localOrigin = new URL(baseURL).origin;
      const gameTargets = new Set(games.map((game) => new URL(game.url).href));
      page.on("pageerror", (error) => errors.push(error.message));
      context.on("page", (newPage) => newPage.on("pageerror", (error) => errors.push(error.message)));
      context.on("response", (response) => {
        if (response.request().resourceType() === "document" && new URL(response.url()).pathname === licensePath) licenseStatus = response.status();
      });
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
      // 此批旧游戏不在当前编辑精选池内；保留六个空槽，不能从旧目录补推荐。
      await expect(featured.locator(".catalog-card")).toHaveCount(0);
      await expect(featured.locator(".catalog-hero-slot-empty")).toHaveCount(6);
      await expect(featured.getByText("暂无符合该推荐主题的游戏", { exact: true })).toBeVisible();
      for (const category of categories) {
        const section = page.locator(`[data-category-section="${category.slug}"]`);
        await section.scrollIntoViewIfNeeded();
        const expectedGames = games.filter((game) => game.category === category.slug);
        for (const game of expectedGames) {
          const card = section.locator(`[data-project-id="${game.id}"]`);
          await expect(card).toHaveCount(1);
          dimensions[game.slug] = await inspectCover(card, game.slug);
          await expect(card.getByRole("link", { name: `打开${game.name}`, exact: true })).toHaveAttribute("href", game.url);
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
      await page.screenshot({ path: path.join(output, `five-browser-games-discovery-${viewport.name}.png`), fullPage: true });

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
      const oldCover = page.locator('[data-project-id="242"] .catalog-card__cover img');
      await oldCover.scrollIntoViewIfNeeded();
      await expect(oldCover).toHaveAttribute("src", /\/catalog\/2026-11-05-v4\/covers\/birdland\.jpg$/);
      expect(await oldCover.evaluate((image) => getComputedStyle(image).objectPosition)).toBe("50% 50%");
      await expect.poll(() => oldCover.evaluate((image: HTMLImageElement) => image.complete && image.naturalWidth > 0)).toBe(true);
      await expect(page.locator('[data-project-id="242"] .catalog-card__heat, [data-project-id="242"] .catalog-card__category, [data-project-id="242"] .catalog-ai-rating')).toHaveCount(0);
      await page.evaluate(() => scrollTo({ top: 0, behavior: "instant" }));
      await page.screenshot({ path: path.join(output, `five-browser-games-results-${viewport.name}.png`), fullPage: true });

      const search = page.getByRole("searchbox", { name: "搜索游戏名称", exact: true });
      // 上批已下架九款不因本批新增静态封面或新游戏重现为搜索卡片。
      for (const hidden of hiddenGames) {
        await search.fill(hidden.name);
        await search.press("Enter");
        await expect(page.locator("article.catalog-card")).toHaveCount(0);
        await expect(page.getByText("没有找到匹配的游戏", { exact: true })).toBeVisible();
      }
      // 同一公开中文+英文展示名都可检索，不另建别名或只检索英文原名。
      for (const query of ["她的眼泪曾是我的光芒", "her tears were my light"]) {
        await search.fill(query);
        await search.press("Enter");
        await expect(page.locator("article.catalog-card")).toHaveCount(1);
        await expect(page.locator('article.catalog-card[data-project-id="9951"] h3')).toHaveText(games[0].name);
      }
      for (const game of games) {
        await search.fill(game.name);
        await search.press("Enter");
        const card = page.locator(`article.catalog-card[data-project-id="${game.id}"]`);
        await expect(page.locator("article.catalog-card")).toHaveCount(1);
        await expect(card.locator("h3")).toHaveText(game.name);
        if (game.slug === "crosscode-demo") await expect(card.locator("h3")).toHaveText("CrossCode（网页试玩版）");
        await inspectCover(card, game.slug);
        await expect(card.locator(".catalog-card__heat, .catalog-card__category, .catalog-ai-rating")).toHaveCount(0);
        const link = card.getByRole("link", { name: `打开${game.name}`, exact: true });
        await expect(link).toHaveAttribute("href", game.url);
        await expect(link).toHaveAttribute("target", "_blank");
        await expect(link).toHaveAttribute("rel", "noopener noreferrer");
        await page.mouse.move(0, 0);
        await card.screenshot({ path: path.join(output, `${game.slug}-search-card-${viewport.name}.png`) });
        const popupPromise = context.waitForEvent("page");
        await link.click();
        const popup = await popupPromise;
        await expect(popup).toHaveURL(new URL(game.url).href);
        await expect(popup.getByRole("heading", { name: "本地外链验收目标" })).toBeVisible();
        await expect.poll(() => opened.filter((id) => id === game.id).length).toBe(1);
        await expect(card.locator(".catalog-card__heat, .catalog-card__category, .catalog-ai-rating")).toHaveCount(0);
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
      await page.screenshot({ path: path.join(output, `five-browser-games-authors-${viewport.name}.png`), fullPage: true });
      const shared = gameAuthors["known-unknowns"]!;
      expect(oldProjects[0]!.author_url).toBe(shared.url);
      const sharedLink = leaderboard.getByRole("link", { name: shared.display, exact: true });
      await expect(sharedLink).toHaveCount(1);
      await expect(sharedLink.locator("xpath=ancestor::li[1]")).toContainText("2 个作品");
      await page.getByRole("searchbox", { name: "搜索作者", exact: true }).fill(shared.collaborator);
      await expect(sharedLink).toBeVisible();
      await expect(leaderboard.getByRole("link")).toHaveCount(1);
      await page.screenshot({ path: path.join(output, `five-browser-games-shared-author-${viewport.name}.png`), fullPage: true });
      await leaderboard.getByRole("button", { name: `查看${shared.display}的作品`, exact: true }).click();
      await expect(page.locator("article.catalog-card")).toHaveCount(2);
      await expect(page.locator("article.catalog-card h3")).toHaveText(["Known Unknowns", "BIRDLAND"]);
      await page.getByRole("button", { name: "作者榜", exact: true }).click();
      await page.getByRole("searchbox", { name: "搜索作者", exact: true }).fill("Emmit");
      await expect(leaderboard.getByRole("link", { name: "NomnomNami", exact: true })).toHaveCount(1);
      await expect(leaderboard.getByRole("link")).toHaveCount(1);
      await page.getByRole("searchbox", { name: "搜索作者", exact: true }).fill("LydianChord");
      await expect(leaderboard.getByRole("link", { name: "NomnomNami", exact: true })).toHaveCount(1);

      // 目录页不再放署名入口；署名页本身仍可直接打开，逐作核来源和不同许可范围。
      await expect(page.locator(`.catalog-footer a[href="${licensePath}"]`)).toHaveCount(0);
      const licensePage = await context.newPage();
      await licensePage.goto(new URL(licensePath, localOrigin).href);
      await licensePage.waitForLoadState("domcontentloaded");
      expect(licenseStatus).toBe(200);
      // 只核本批五项与原 BIRDLAND 署名仍完整，后续新增独立署名不应破坏旧收录回归。
      const priorNotices = [...games.map((game) => game.slug), "birdland"]
        .map((slug) => `main section[aria-labelledby="${slug}-cover"]`).join(",");
      await expect(licensePage.locator(priorNotices)).toHaveCount(6);
      for (const game of games) {
        const section = licensePage.locator(`section[aria-labelledby="${game.slug}-cover"]`);
        await expect(section.getByRole("heading", { name: game.licenseTitle })).toHaveCount(1);
        await expect(section.locator("a")).not.toHaveCount(0);
      }
      const namiNotice = licensePage.locator('section[aria-labelledby="her-tears-were-my-light-cover"]');
      for (const credit of ["NomnomNami", "Emmit", "LydianChord"]) await expect(namiNotice).toContainText(credit);
      await expect(namiNotice).toContainText("1920×620");
      await expect(namiNotice).toContainText("480×155");
      const farmNotice = licensePage.locator('section[aria-labelledby="farmhand-cover"]');
      await expect(farmNotice).toContainText("Jeremy Kahn");
      await expect(farmNotice).toContainText("非商业");
      await expect(farmNotice.locator('a[href="https://creativecommons.org/licenses/by-nc-sa/4.0/"]')).toHaveCount(1);
      const exhibitNotice = licensePage.locator('section[aria-labelledby="exhibit-of-sorrows-cover"]');
      for (const credit of ["Maxim Tsai", "Theresa Kao", "第 0 帧"]) await expect(exhibitNotice).toContainText(credit);
      await expect(exhibitNotice.locator('a[href="https://creativecommons.org/licenses/by/4.0/"]')).toHaveCount(1);
      await expect(exhibitNotice).toContainText("不将游戏代码的 Unlicense 当作图片许可");
      const crossNotice = licensePage.locator('section[aria-labelledby="crosscode-demo-cover"]');
      for (const text of ["Radical Fish Games", "0.7.1 beta", "(880,250)", "356×480", "不宣称开放 CC"]) await expect(crossNotice).toContainText(text);
      await expect(crossNotice.locator('a[href="https://www.cross-code.com/en/start"]')).toHaveCount(1);
      await expect(crossNotice.locator('a[href^="https://creativecommons.org/"]')).toHaveCount(0);
      const knownNotice = licensePage.locator('section[aria-labelledby="known-unknowns-cover"]');
      for (const credit of ["Brendan Patrick Hennessy", "Izzy Marbella", "400×480"]) await expect(knownNotice).toContainText(credit);
      await expect(knownNotice.locator('a[href="https://known.zone/img/nadia1.png"]')).toHaveCount(1);
      const birdlandNotice = licensePage.locator('section[aria-labelledby="birdland-cover"]');
      await expect(birdlandNotice).toContainText("Brendan Patrick Hennessy");
      await expect(birdlandNotice.locator('a[href="https://creativecommons.org/licenses/by/3.0/us/"]')).toHaveCount(1);
      const notices = await licensePage.locator("main section").allTextContents();
      expect(await licensePage.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
      await licensePage.screenshot({ path: path.join(output, `five-browser-games-cover-notices-${viewport.name}.png`), fullPage: true });
      await licensePage.close();

      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
      for (const game of games) expect(loadedCovers.has(`catalog/${version}/covers/${covers[game.slug]!.file}`)).toBe(true);
      expect(opened).toEqual(games.map((game) => game.id));
      expect(unexpected).toEqual([]);
      expect(errors).toEqual([]);
      await writeFile(path.join(output, `five-browser-games-${viewport.name}-evidence.json`), JSON.stringify({
        viewport, covers, dimensions, opened, fullReads, pageReads, hiddenGames, gameAuthors, notices, unexpected, errors,
        boundary: "本地API/外链夹具与真实正式图片，不证明真实外站玩法或线上CDN。",
      }, null, 2));
    });
  });
}

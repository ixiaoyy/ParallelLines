import { expect, test, type BrowserContext, type Page } from "@playwright/test";

const baseURL = process.env.PLAYWRIGHT_BASE_URL ?? "http://127.0.0.1:5173";
const longName = "很长的游戏名称 / A Very Long Arcade Game Name That Must Stay On One Line";
const longAuthor = "Marco van Hylckama Vlieg / AI & Design / 很长的作者名称";

/** 所有目录、打开统计、评分与游戏目标均由测试响应，禁止向真实服务发送写请求。 */
async function mockArcade(context: BrowserContext, count = 9) {
  const opens: string[] = [];
  const ratings: number[] = [];
  const unexpected: string[] = [];
  const localOrigin = new URL(baseURL).origin;
  const projects = Array.from({ length: count }, (_, index) => ({
    id: String(1001 + index), slug: `arcade-fixture-${index}`,
    name: index === 0 ? longName : `测试游戏${index + 1}`,
    url: index === 2 ? "/play/arcade-fixture" : `https://arcade-game.invalid/${1001 + index}`,
    kind: index === 2 ? "internal" : "external",
    description: null, author_name: index === 0 ? longAuthor : "测试作者",
    author_url: index === 0 ? "https://arcade-author.invalid/" : null,
    icon_url: "/uploads/arcade-fixture/content",
    created_at: new Date(Date.UTC(2026, 9, 1) - index * 86_400_000).toISOString(),
    average_score: null, rating_count: 0, rating_score_sum: 0,
    view_count: index === count - 1 ? 100 : 0, my_score: null,
  }));
  await context.route("**/*", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const headers = { "access-control-allow-origin": "*" };
    if (url.hostname === "arcade-game.invalid" || url.pathname === "/play/arcade-fixture") {
      await route.fulfill({ contentType: "text/html", body: "<!doctype html><h1>Mock game opened</h1>" });
    } else if (url.pathname.endsWith("/uploads/arcade-fixture/content")) {
      await route.fulfill({ headers, contentType: "image/svg+xml", body: '<svg xmlns="http://www.w3.org/2000/svg" width="320" height="120"><rect width="320" height="120" fill="#156bad"/></svg>' });
    } else if (url.pathname.startsWith("/api/v1/")) {
      const view = /\/catalog\/projects\/([^/]+)\/views$/.exec(url.pathname);
      const rating = /\/catalog\/projects\/([^/]+)\/ratings$/.exec(url.pathname);
      if (url.pathname === "/api/v1/catalog") {
        await route.fulfill({ headers, json: { data: { categories: [
          { id: "1", slug: "puzzle", name: "解谜", icon_url: null, projects: projects.filter((_, index) => index % 2 === 0) },
          { id: "2", slug: "casual", name: "休闲", icon_url: null, projects: projects.filter((_, index) => index % 2 !== 0) },
        ] } } });
      } else if (view) {
        opens.push(view[1]!);
        await route.fulfill({ headers, json: { data: { project_id: view[1], view_count: opens.filter((id) => id === view[1]).length } } });
      } else if (rating) {
        const { score } = request.postDataJSON() as { score: number };
        ratings.push(score);
        await route.fulfill({ headers, json: { data: { project_id: rating[1], average_score: score, rating_count: 1, rating_score_sum: score, my_score: score } } });
      } else {
        if (request.method() !== "GET" && request.method() !== "OPTIONS") unexpected.push(request.url());
        await route.fulfill({ headers, json: { data: url.pathname.endsWith("/settings/public") ? { settings: {} } : [] } });
      }
    } else if (url.origin !== localOrigin) {
      unexpected.push(request.url());
      await route.abort();
    } else {
      await route.continue();
    }
  });
  return { opens, ratings, unexpected, projects };
}

/** 选择状态必须对应真实可见卡片；新版选中样式不依赖街机贴图。 */
async function expectSelected(page: Page, id: string) {
  const selected = page.locator(".catalog-card.is-selected");
  await expect(selected).toHaveCount(1);
  await expect(selected).toHaveAttribute("data-project-id", id);
  await expect(selected).toBeVisible();
}

/** 所有清单范围入口都用实际拥有状态的工具栏，避免与顶部或侧栏快捷入口重名。 */
function libraryButton(page: Page, name: string) {
  return page.locator(".catalog-library-filters").getByRole("button", { name, exact: true });
}

function projectCard(page: Page, id: string) {
  // 首页允许同一游戏在推荐和分类重复出现；一般操作选首个实例，专门用例另查展示键。
  return page.locator(`.catalog-card[data-project-id="${id}"]`).first();
}

async function projectIds(page: Page) {
  return page.locator(".catalog-card").evaluateAll((cards) => cards.map((card) => card.getAttribute("data-project-id")));
}

/** 模拟目标的原生打开必须只产生一个新标签；不拦截点击或伪造浏览记录。 */
async function openTarget(page: Page, selector: string, gesture: "left" | "middle" | "keyboard" = "left") {
  const target = page.locator(selector).first();
  const popupPromise = page.context().waitForEvent("page");
  if (gesture === "keyboard") {
    await target.focus();
    await target.press("Enter");
  } else {
    await target.click({ button: gesture });
  }
  const popup = await popupPromise;
  await expect(popup.getByRole("heading", { name: "Mock game opened" })).toBeVisible();
  await popup.close();
  await expect(target).toBeFocused();
}

test("长标题作者保留省略与全文，推荐和分类预览在各断点可见且无溢出", async ({ page, context }) => {
  const requests = await mockArcade(context);
  await page.goto("/");
  await expect(page.locator(".catalog-group--featured .catalog-card")).toHaveCount(6);
  await expect(projectCard(page, "1001").locator(".catalog-card__title-link")).toHaveAttribute("title", longName);
  await expect(projectCard(page, "1001").locator(".catalog-card__author")).toHaveAttribute("title", longAuthor);
  for (const [width, columns] of [[320, 2], [390, 2], [600, 2], [760, 2], [800, 3], [960, 3], [1000, 3], [1280, 5], [1536, 5], [1920, 6]] as const) {
    await page.setViewportSize({ width, height: 1000 });
    await expect(page.locator(".catalog-card")).toHaveCount(6 + Math.min(5, columns) + Math.min(4, columns));
    const layout = await page.locator(".catalog-card").evaluateAll((cards) => ({
      visible: cards.every((card) => {
        const rect = card.getBoundingClientRect();
        return rect.width > 0 && rect.height > 0 && getComputedStyle(card).visibility !== "hidden";
      }),
      ids: cards.map((card) => card.getAttribute("data-project-id")),
      overflow: document.documentElement.scrollWidth > innerWidth + 1,
    }));
    expect(layout.visible, `所有渲染的真实预览在 ${width}px 都须可见`).toBe(true);
    expect(layout.ids.length).toBe(6 + Math.min(5, columns) + Math.min(4, columns));
    expect(layout.ids.every((id) => requests.projects.some((project) => project.id === id))).toBe(true);
    expect(layout.overflow, `${width}px 页面不能横向溢出`).toBe(false);
  }
  // 截断在受约束的桌面宽度验证；1920px 的推荐大卡允许完整显示作者。
  await page.setViewportSize({ width: 1280, height: 1000 });
  const truncation = await projectCard(page, "1001").evaluate((card) =>
    [card.querySelector(".catalog-card__title-link")!, card.querySelector(".catalog-card__author a")!]
      .map((element) => ({ whiteSpace: getComputedStyle(element).whiteSpace, overflow: getComputedStyle(element).textOverflow, clipped: element.scrollWidth > element.clientWidth })),
  );
  expect(truncation.every((style) => style.whiteSpace === "nowrap" && style.overflow === "ellipsis" && style.clipped)).toBe(true);
  for (const viewport of [{ width: 390, height: 844 }, { width: 960, height: 1000 }]) {
    const touch = await context.browser()!.newContext({ viewport, hasTouch: true, isMobile: viewport.width < 600 });
    try {
      await mockArcade(touch);
      const touchPage = await touch.newPage();
      await touchPage.goto(baseURL);
      await expect(touchPage.locator(".catalog-group--featured .catalog-card")).toHaveCount(6);
      for (const selector of [".catalog-card__title-link", ".catalog-card__author a", ".catalog-card__author button", ".catalog-card__wanted", ".catalog-card__open", ".catalog-layout-toggle button", ".catalog-account"]) {
        for (const target of await touchPage.locator(selector).all()) {
          await expect(target).toBeVisible();
          const box = await target.boundingBox();
          expect(box!.width, `${viewport.width}px ${selector} 触控宽度`).toBeGreaterThanOrEqual(44);
          expect(box!.height, `${viewport.width}px ${selector} 触控高度`).toBeGreaterThanOrEqual(44);
        }
      }
      await expect(touchPage.getByRole("button", { name: "投稿游戏", exact: true })).toBeVisible();
    } finally {
      await touch.close();
    }
  }
  expect(requests.unexpected).toEqual([]);
});

test("推荐拼图按真实几何双向移动，大卡到小卡可原路返回，Enter 复用打开链路", async ({ page, context }) => {
  const requests = await mockArcade(context);
  await page.setViewportSize({ width: 1280, height: 1000 });
  await page.goto("/");
  const featured = page.locator(".catalog-group--featured .catalog-card");
  await expect(featured).toHaveCount(6);
  const firstBox = await projectCard(page, "1001").boundingBox();
  const secondBox = await projectCard(page, "1002").boundingBox();
  expect(firstBox!.height).toBeGreaterThan(secondBox!.height * 1.8);
  expect(secondBox!.x).toBeGreaterThan(firstBox!.x + firstBox!.width - 1);
  await expectSelected(page, "1001");
  await page.keyboard.press("d");
  await expectSelected(page, "1002");
  await page.keyboard.press("a");
  await expectSelected(page, "1001");
  await page.keyboard.press("d");
  await page.keyboard.press("s");
  await expectSelected(page, "1004");
  await page.keyboard.press("w");
  await expectSelected(page, "1002");
  const popupPromise = context.waitForEvent("page");
  await page.keyboard.press("Enter");
  const popup = await popupPromise;
  await expect(popup.getByRole("heading", { name: "Mock game opened" })).toBeVisible();
  await popup.close();
  await expect.poll(() => requests.opens).toEqual(["1002"]);
  const recent = await page.evaluate(() => JSON.parse(localStorage.getItem("parallellines.catalog-library.v1")!).recent);
  expect(recent.map((item: { projectId: string }) => item.projectId)).toEqual(["1002"]);
  await expectSelected(page, "1002");
  expect(requests.ratings).toEqual([]);
  expect(requests.unexpected).toEqual([]);
});

test("收藏和原生打开留下的焦点仍可用 WASD 接续，导航不产生额外收藏或打开", async ({ page, context }) => {
  const requests = await mockArcade(context);
  await page.setViewportSize({ width: 1280, height: 1000 });
  await page.goto("/");
  const second = projectCard(page, "1002");
  const third = projectCard(page, "1003");
  await second.locator(".catalog-card__wanted").click();
  await expectSelected(page, "1002");
  await expect(second.locator(".catalog-card__wanted")).toHaveAttribute("aria-pressed", "true");
  await page.keyboard.press("d");
  await expectSelected(page, "1003");
  await page.keyboard.press("s");
  await expectSelected(page, "1005");
  await page.keyboard.press("w");
  await expectSelected(page, "1003");
  await page.keyboard.press("a");
  await expectSelected(page, "1002");
  await expect(second.locator(".catalog-card__wanted")).toHaveAttribute("aria-pressed", "true");
  await expect(third.locator(".catalog-card__wanted")).toHaveAttribute("aria-pressed", "false");
  expect(requests.opens).toEqual([]);
  for (const selector of [".catalog-card__media-link", ".catalog-card__title-link", ".catalog-card__open"]) {
    await openTarget(page, `.catalog-card[data-project-id="1003"] ${selector}`);
    await expectSelected(page, "1003");
    await page.keyboard.press("a");
    await expectSelected(page, "1002");
  }
  await expect.poll(() => requests.opens).toEqual(["1003", "1003", "1003"]);
  expect(requests.ratings).toEqual([]);
  expect(requests.unexpected).toEqual([]);
});

test("连续分页保持所有真实记录唯一可达，加载按钮焦点和 Enter 不启动游戏", async ({ page, context }) => {
  const requests = await mockArcade(context, 73);
  await page.setViewportSize({ width: 1280, height: 1000 });
  await page.goto("/");
  // 首页是各类独立预览；平铺列表仍验证原24条分页与跨批次键盘。
  await page.getByRole("button", { name: "列表显示", exact: true }).click();
  const cards = page.locator(".catalog-card");
  const loadMore = page.getByRole("button", { name: "加载更多", exact: true });
  await expect(cards).toHaveCount(24);
  expect(new Set(await projectIds(page)).size).toBe(24);
  await projectCard(page, "1024").focus();
  await loadMore.click();
  await expect(cards).toHaveCount(48);
  await expect(loadMore).toBeFocused();
  await expectSelected(page, "1024");
  await page.keyboard.press("s");
  await expectSelected(page, "1025");
  await page.keyboard.press("w");
  await expectSelected(page, "1024");
  await projectCard(page, "1048").focus();
  await loadMore.focus();
  await page.keyboard.press("Enter");
  await expect(cards).toHaveCount(72);
  await expect(loadMore).toBeFocused();
  await expectSelected(page, "1048");
  expect(requests.opens).toEqual([]);
  await page.keyboard.press("s");
  await expectSelected(page, "1049");
  await projectCard(page, "1072").focus();
  await loadMore.click();
  await expect(cards).toHaveCount(73);
  await expect(loadMore).toHaveCount(0);
  expect(await projectIds(page)).toEqual(Array.from({ length: 73 }, (_, index) => String(1001 + index)));
  await page.keyboard.press("s");
  await expectSelected(page, "1073");
  await page.keyboard.press("s");
  await expectSelected(page, "1073");
  await page.keyboard.press("w");
  await expectSelected(page, "1072");
  expect(requests.opens).toEqual([]);
  expect(requests.ratings).toEqual([]);
  expect(requests.unexpected).toEqual([]);
});

test("搜索、显示方式、个人清单和榜单返回后保留当前可见选择及本地记录", async ({ page, context }) => {
  const requests = await mockArcade(context);
  await context.addInitScript(() => {
    localStorage.setItem("parallellines.catalog-library.v1", JSON.stringify({
      version: 1, wantedIds: ["1002", "1004", "1006"],
      recent: [{ projectId: "1005", lastOpenedAt: 3 }, { projectId: "1007", lastOpenedAt: 2 }, { projectId: "1008", lastOpenedAt: 1 }],
    }));
  });
  await page.setViewportSize({ width: 1280, height: 1000 });
  await page.goto("/");
  const cards = page.locator(".catalog-card");
  const search = page.getByRole("searchbox", { name: "搜索游戏名称" });
  const submitSearch = page.getByRole("button", { name: "搜索", exact: true });
  await search.fill("测试游戏");
  await submitSearch.click();
  await expect(cards).toHaveCount(8);
  await expect(submitSearch).toBeFocused();
  await expectSelected(page, "1002");
  await page.keyboard.press("d");
  await expectSelected(page, "1003");
  await search.fill("");
  await submitSearch.click();
  await expect(cards).toHaveCount(15);
  await expectSelected(page, "1003");
  await page.getByRole("button", { name: "列表显示" }).click();
  await page.keyboard.press("w");
  await expectSelected(page, "1002");
  await page.getByRole("button", { name: "网格显示" }).click();
  await page.keyboard.press("a");
  await expectSelected(page, "1001");
  await libraryButton(page, "想玩清单").click();
  await expect(cards).toHaveCount(3);
  await expectSelected(page, "1002");
  await page.keyboard.press("d");
  await expectSelected(page, "1004");
  await libraryButton(page, "最近打开").click();
  await expect(cards).toHaveCount(3);
  await expectSelected(page, "1005");
  await page.keyboard.press("d");
  await expectSelected(page, "1007");
  await libraryButton(page, "全部游戏").click();
  await expect(cards).toHaveCount(15);
  await expectSelected(page, "1007");
  await page.getByRole("button", { name: "列表显示" }).click();
  await page.keyboard.press("w");
  await expectSelected(page, "1006");
  for (const view of ["作者榜", "贡献榜"]) {
    await page.locator(".catalog-rail").getByRole("button", { name: view, exact: true }).click();
    await expect(page.getByRole("heading", { name: view, exact: true })).toBeVisible();
    await page.keyboard.press("d");
    await expect(cards).toHaveCount(0);
    const gameView = page.locator(".catalog-rail").getByRole("button", { name: "全部游戏", exact: true });
    await gameView.click();
    await expect(gameView).toBeFocused();
    await expectSelected(page, "1006");
    await page.keyboard.press("s");
    await expectSelected(page, "1007");
    await page.keyboard.press("w");
    await expectSelected(page, "1006");
  }
  const library = await page.evaluate(() => JSON.parse(localStorage.getItem("parallellines.catalog-library.v1")!));
  expect(library.wantedIds).toEqual(["1002", "1004", "1006"]);
  expect(library.recent.map((item: { projectId: string }) => item.projectId)).toEqual(["1005", "1007", "1008"]);
  expect(requests.opens).toEqual([]);
  expect(requests.ratings).toEqual([]);
  expect(requests.unexpected).toEqual([]);
});

test("正式图片铺满卡片，标题作者与操作不重叠，收藏和打开不改变卡片几何", async ({ page, context }) => {
  const requests = await mockArcade(context);
  await page.setViewportSize({ width: 1280, height: 1000 });
  await page.goto("/");
  const cards = page.locator(".catalog-card");
  await expect(cards).toHaveCount(15);
  await expect(page.locator(".catalog-card__author-label, .catalog-card__stats, .catalog-card__views, .catalog-card__rating-trigger, .catalog-card__rating-panel, .catalog-card__rating-error")).toHaveCount(0);
  for (const width of [320, 390, 600, 800, 960, 1280, 1536, 1920]) {
    await page.setViewportSize({ width, height: 1000 });
    const layouts = await cards.evaluateAll((items) => items.map((card) => {
      const screen = card.querySelector(".catalog-card__screen")!.getBoundingClientRect();
      const image = card.querySelector(".catalog-card__media img")!.getBoundingClientRect();
      const title = card.querySelector(".catalog-card__title-link")!;
      const author = card.querySelector(".catalog-card__author")!;
      const wanted = card.querySelector(".catalog-card__wanted")!;
      const open = card.querySelector(".catalog-card__open")!;
      const boxes = [title, author, wanted, open].map((element) => element.getBoundingClientRect());
      const contained = (box: DOMRect) => box.width > 0 && box.height > 0 && box.left >= screen.left - 1 && box.top >= screen.top - 1
        && box.right <= screen.right + 1 && box.bottom <= screen.bottom + 1;
      const separate = (left: DOMRect, right: DOMRect) => left.right <= right.left + 1 || right.right <= left.left + 1
        || left.bottom <= right.top + 1 || right.bottom <= left.top + 1;
      return {
        id: card.getAttribute("data-project-id"),
        coverFillsCard: Math.abs(image.left - screen.left) < 1 && Math.abs(image.top - screen.top) < 1
          && Math.abs(image.width - screen.width) < 1 && Math.abs(image.height - screen.height) < 1,
        contained: boxes.every(contained),
        noOverlap: boxes.every((box, index) => boxes.slice(index + 1).every((other) => separate(box, other))),
        titleColor: getComputedStyle(title).color,
        authorColor: getComputedStyle(author).color,
      };
    }));
    for (const layout of layouts) {
      expect(layout.coverFillsCard, `${width}px ${layout.id} 封面`).toBe(true);
      expect(layout.contained, `${width}px ${layout.id} 内容范围`).toBe(true);
      expect(layout.noOverlap, `${width}px ${layout.id} 文字与操作`).toBe(true);
      expect(layout.titleColor).toBe("rgb(255, 255, 255)");
      expect(layout.authorColor).not.toBe(layout.titleColor);
    }
  }
  const before = await cards.evaluateAll((items) => items.map((item) => item.getBoundingClientRect().height));
  await projectCard(page, "1001").locator(".catalog-card__wanted").click();
  await expect(projectCard(page, "1001").locator(".catalog-card__wanted")).toHaveAttribute("aria-pressed", "true");
  await openTarget(page, '.catalog-card[data-project-id="1001"] .catalog-card__open');
  await expect.poll(() => requests.opens).toEqual(["1001"]);
  expect(await cards.evaluateAll((items) => items.map((item) => item.getBoundingClientRect().height))).toEqual(before);
  expect(requests.ratings).toEqual([]);
  expect(requests.unexpected).toEqual([]);
});

test("输入、控件确认和弹窗保留原操作，左键中键与键盘均只记录一次打开", async ({ page, context }) => {
  const requests = await mockArcade(context);
  await page.setViewportSize({ width: 1280, height: 1000 });
  await page.goto("/");
  await expectSelected(page, "1001");
  const search = page.getByRole("searchbox", { name: "搜索游戏名称" });
  await search.fill("wasd");
  await search.press("d");
  await expect(search).toHaveValue("wasdd");
  await expectSelected(page, "1001");
  await search.fill("");
  for (const name of ["游戏分类", "游戏排序"]) {
    await page.getByRole("combobox", { name }).focus();
    await page.keyboard.press("s");
    await expectSelected(page, "1001");
  }
  const second = projectCard(page, "1002");
  await second.locator(".catalog-card__wanted").focus();
  await page.keyboard.press("Enter");
  await expect(second.locator(".catalog-card__wanted")).toHaveAttribute("aria-pressed", "true");
  expect(requests.opens).toEqual([]);
  await page.keyboard.press("d");
  await expectSelected(page, "1003");
  await second.locator(".catalog-card__author button").click();
  await expect(page.locator(".catalog-author-dialog")).toBeVisible();
  await page.keyboard.press("s");
  await expectSelected(page, "1002");
  await page.getByRole("button", { name: "关闭作者窗口" }).click();
  await expect(page.locator(".catalog-author-dialog")).not.toBeVisible();
  await expect(second.locator(".catalog-card__author button")).toBeFocused();
  await page.keyboard.press("d");
  await expectSelected(page, "1003");
  const submission = page.getByRole("button", { name: "投稿游戏", exact: true });
  await submission.click();
  await expect(page.locator(".catalog-submission-dialog")).toBeVisible();
  await page.keyboard.press("d");
  await expectSelected(page, "1003");
  await page.getByRole("button", { name: "关闭投稿窗口" }).click();
  await expect(page.locator(".catalog-submission-dialog")).not.toBeVisible();
  await expect(submission).toBeFocused();
  await page.keyboard.press("d");
  await expectSelected(page, "1006");
  for (const gesture of ["left", "middle", "keyboard"] as const) {
    await openTarget(page, '.catalog-card[data-project-id="1003"] .catalog-card__open', gesture);
  }
  await expect.poll(() => requests.opens).toEqual(["1003", "1003", "1003"]);
  expect(requests.ratings).toEqual([]);
  expect(requests.unexpected).toEqual([]);
});

test("排序与筛选重置分页，列表维持真实顺序，空结果不保留选择或意外打开", async ({ page, context }) => {
  const requests = await mockArcade(context, 28);
  await page.setViewportSize({ width: 1280, height: 1000 });
  await page.goto("/");
  await page.getByRole("button", { name: "列表显示", exact: true }).click();
  await expect(page.locator(".catalog-card")).toHaveCount(24);
  await page.getByRole("button", { name: "加载更多", exact: true }).click();
  await expect(page.locator(".catalog-card")).toHaveCount(28);
  await page.getByRole("combobox", { name: "游戏排序" }).selectOption("hot");
  await expect(page.locator(".catalog-card")).toHaveCount(24);
  await expect(page.locator(".catalog-card").first()).toHaveAttribute("data-project-id", "1028");
  await expectSelected(page, "1001");
  await page.getByRole("combobox", { name: "游戏分类" }).selectOption("casual");
  await expectSelected(page, "1028");
  await page.getByRole("button", { name: "列表显示" }).click();
  expect(await projectIds(page)).toEqual(["1028", ...Array.from({ length: 13 }, (_, index) => String(1002 + index * 2))]);
  for (const width of [390, 1280]) {
    await page.setViewportSize({ width, height: 1000 });
    const layout = await page.locator(".catalog-card").evaluateAll((cards) => ({
      pageOverflow: document.documentElement.scrollWidth > innerWidth + 1,
      cardOverflow: cards.some((card) => card.scrollWidth > card.clientWidth + 1),
      contentContained: cards.every((card) => {
        const box = card.getBoundingClientRect();
        return [...card.querySelectorAll(".catalog-card__title-link, .catalog-card__author, .catalog-card__wanted, .catalog-card__open")]
          .every((element) => {
            const content = element.getBoundingClientRect();
            return content.left >= box.left - 1 && content.right <= box.right + 1
              && content.top >= box.top - 1 && content.bottom <= box.bottom + 1;
          });
      }),
    }));
    expect(layout.pageOverflow).toBe(false);
    expect(layout.cardOverflow).toBe(false);
    expect(layout.contentContained).toBe(true);
  }
  await page.keyboard.press("s");
  await expectSelected(page, "1002");
  await page.keyboard.press("d");
  await expectSelected(page, "1002");
  await page.keyboard.press("w");
  await expectSelected(page, "1028");
  await page.getByRole("searchbox", { name: "搜索游戏名称" }).fill("测试游戏4");
  await page.getByRole("button", { name: "搜索", exact: true }).click();
  await expect(page.locator(".catalog-card")).toHaveCount(1);
  await expectSelected(page, "1004");
  await page.getByRole("searchbox", { name: "搜索游戏名称" }).fill("没有这种游戏");
  await page.getByRole("button", { name: "搜索", exact: true }).click();
  await expect(page.locator(".catalog-card.is-selected")).toHaveCount(0);
  await page.keyboard.press("Enter");
  expect(requests.opens).toEqual([]);
  expect(requests.unexpected).toEqual([]);
});

test("分类预览覆盖首批以外全部分类，按实际列数限一行，完整分类分页和全目录搜索可达", async ({ page, context }) => {
  // 最新 30 款全部属于第一类；其后 18/6 款用于捕获旧全站前24条造成的分类遗漏。
  const requests = await mockArcade(context, 54);
  const categories = [
    { id: "41", slug: "server-new", name: "服务器新增分类", projects: requests.projects.slice(0, 30) },
    { id: "42", slug: "server-other", name: "服务端另一分类", projects: requests.projects.slice(30, 48) },
    { id: "43", slug: "server-six", name: "服务端六款分类", projects: requests.projects.slice(48) },
  ];
  await context.route("**/api/v1/catalog", async (route) => {
    await route.fulfill({ headers: { "access-control-allow-origin": "*" }, json: {
      data: { categories: categories.map((category) => ({ ...category, icon_url: null })) },
    } });
  });
  await page.setViewportSize({ width: 1536, height: 1000 });
  await page.goto("/");
  await expect(page.locator(".catalog-group__heading h2")).toHaveText(["精选推荐", ...categories.map((category) => category.name)]);
  await expect(page.getByRole("combobox", { name: "游戏分类" }).locator("option"))
    .toHaveText(["全部", ...categories.map((category) => category.name)]);
  await expect(page.locator(".catalog-results")).toHaveText("54 个游戏");
  const featured = page.locator(".catalog-group--featured .catalog-card");
  await expect(featured).toHaveCount(6);
  expect(await featured.evaluateAll((cards) => cards.map((card) => card.getAttribute("data-project-id"))))
    .toEqual(Array.from({ length: 6 }, (_, index) => String(1001 + index)));
  for (const [width, columns] of [[390, 2], [800, 3], [1100, 4], [1536, 5], [1920, 6]] as const) {
    await page.setViewportSize({ width, height: 1000 });
    await expect(page.getByRole("button", { name: "加载更多", exact: true })).toHaveCount(0);
    for (const category of categories) {
      const group = page.locator(".catalog-group").filter({ has: page.getByRole("heading", { name: category.name, exact: true }) });
      const expectedCount = Math.min(category.projects.length, columns);
      const previews = group.locator(".catalog-card");
      await expect(previews).toHaveCount(expectedCount);
      await expect(group.locator(".catalog-group__count"))
        .toHaveText(`共 ${category.projects.length} 款 · 展示 ${expectedCount} 款`);
      expect(await previews.evaluateAll((cards) => cards.map((card) => card.getAttribute("data-project-id"))))
        .toEqual(category.projects.slice(0, expectedCount).map((project) => project.id));
      const geometry = await previews.evaluateAll((cards) => cards.map((card) => {
        const rect = card.getBoundingClientRect();
        return { top: rect.top, width: rect.width, height: rect.height };
      }));
      expect(geometry.every((rect) => rect.width > 0 && rect.height > 0)).toBe(true);
      expect(Math.max(...geometry.map((rect) => rect.top)) - Math.min(...geometry.map((rect) => rect.top)), `${width}px ${category.name} 只展示一行`).toBeLessThan(1);
    }
    const renderedKeys = await page.locator(".catalog-card").evaluateAll((cards) => cards.map((card) => card.getAttribute("data-card-key")));
    expect(renderedKeys.every(Boolean)).toBe(true);
    expect(new Set(renderedKeys).size).toBe(renderedKeys.length);
    await expect(page.locator(".catalog-card.is-selected")).toHaveCount(1);
    expect(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1)).toBe(false);
  }
  // 同一项目可在推荐与分类各出现一次，选中实例、收藏记录和项目 ID 仍各有明确语义。
  const repeated = page.locator('.catalog-card[data-project-id="1001"]');
  await expect(repeated).toHaveCount(2);
  const categoryInstance = page.locator('.catalog-card[data-card-key="server-new:1001"]');
  await categoryInstance.focus();
  await expectSelected(page, "1001");
  await expect(page.locator(".catalog-card.is-selected")).toHaveAttribute("data-card-key", "server-new:1001");
  await page.keyboard.press("d");
  await expectSelected(page, "1002");
  await expect(page.locator(".catalog-card.is-selected")).toHaveAttribute("data-card-key", "server-new:1002");
  await page.keyboard.press("a");
  await expectSelected(page, "1001");
  await categoryInstance.locator(".catalog-card__wanted").click();
  for (const wanted of await repeated.locator(".catalog-card__wanted").all()) {
    await expect(wanted).toHaveAttribute("aria-pressed", "true");
  }
  const wantedIds = await page.evaluate(() => JSON.parse(localStorage.getItem("parallellines.catalog-library.v1")!).wantedIds);
  expect(wantedIds).toEqual(["1001"]);
  await page.getByRole("button", { name: "查看全部服务器新增分类游戏", exact: true }).click();
  await expect(page.getByRole("combobox", { name: "游戏分类" })).toHaveValue("server-new");
  await expect(page.locator(".catalog-card")).toHaveCount(24);
  expect(await projectIds(page)).toEqual(Array.from({ length: 24 }, (_, index) => String(1001 + index)));
  await expect(page.locator(".catalog-group--featured")).toHaveCount(0);
  await page.getByRole("button", { name: "加载更多", exact: true }).click();
  await expect(page.locator(".catalog-card")).toHaveCount(30);
  expect(await projectIds(page)).toEqual(categories[0]!.projects.map((project) => project.id));
  await expect(page.getByRole("button", { name: "加载更多", exact: true })).toHaveCount(0);
  await page.getByRole("combobox", { name: "游戏分类" }).selectOption("all");
  await page.getByRole("searchbox", { name: "搜索游戏名称" }).fill("测试游戏54");
  await page.getByRole("button", { name: "搜索", exact: true }).click();
  await expect(page.locator(".catalog-card")).toHaveCount(1);
  expect(await projectIds(page)).toEqual(["1054"]);
  await expect(page.locator(".catalog-results")).toHaveText("1 个游戏");
  expect(requests.opens).toEqual([]);
  expect(requests.ratings).toEqual([]);
  expect(requests.unexpected).toEqual([]);
});

test("同秒跨分类记录按精确 ID 倒序，保留种子、最近打开和大整数顺序", async ({ page, context }) => {
  const requests = await mockArcade(context);
  const makeProject = (id: string, slug: string, name: string, createdAt: string) => ({
    id, slug, name, url: `https://arcade-game.invalid/${id}`, kind: "external",
    description: null, author_name: "测试作者", author_url: null,
    icon_url: "/uploads/arcade-fixture/content", created_at: createdAt,
    average_score: null, rating_count: 0, rating_score_sum: 0, view_count: 0, my_score: null,
  });
  const sameSecond = "2026-10-09T15:03:41+08:00";
  const newProjects = [
    makeProject("211", "entropy-blade", "熵刃", sameSecond), makeProject("212", "nexus", "NEXUS", sameSecond),
    makeProject("213", "emberfall", "EmberFall", sameSecond), makeProject("214", "nanbeidou", "NANBEIDOU", sameSecond),
    makeProject("215", "shinobi-chronicles", "忍者游戏", sameSecond), makeProject("216", "illusion-prototype", "回廊", sameSecond),
  ];
  const seedProjects = [
    makeProject("800", "merge-watermelon", "合成大西瓜", "2026-10-08T00:00:00Z"),
    makeProject("500", "clock-out", "打工摸鱼", "2026-10-08T00:00:00Z"),
  ];
  const largeIds = ["9007199254740992", "9007199254740993", "9999999999999999", "10000000000000000"];
  await context.route("**/api/v1/catalog", async (route) => {
    await route.fulfill({ headers: { "access-control-allow-origin": "*" }, json: { data: { categories: [
      { id: "1", slug: "puzzle", name: "解谜", icon_url: null, projects: [
        ...newProjects.filter((_, index) => index % 2 === 0), ...seedProjects,
        ...largeIds.map((id) => makeProject(id, `large-id-${id}`, `大整数 ${id}`, "2026-10-07T00:00:00Z")),
      ] },
      { id: "2", slug: "casual", name: "休闲", icon_url: null, projects: newProjects.filter((_, index) => index % 2 !== 0) },
    ] } } });
  });
  await context.addInitScript(() => {
    localStorage.setItem("parallellines.catalog-library.v1", JSON.stringify({
      version: 1, wantedIds: [], recent: [{ projectId: "211", lastOpenedAt: 42 }, { projectId: "216", lastOpenedAt: 42 }],
    }));
  });
  await page.goto("/");
  await expect(page.locator(".catalog-card")).toHaveCount(14);
  expect(await page.locator(".catalog-group--featured .catalog-card").evaluateAll((cards) => cards.map((card) => card.getAttribute("data-project-id"))))
    .toEqual(["216", "215", "214", "213", "212", "211"]);
  await expectSelected(page, "216");
  await page.getByRole("button", { name: "列表显示" }).click();
  expect(await projectIds(page)).toEqual(["216", "215", "214", "213", "212", "211", "500", "800", ...[...largeIds].reverse()]);
  await libraryButton(page, "最近打开").click();
  await expect(page.locator(".catalog-card")).toHaveCount(2);
  expect(await projectIds(page)).toEqual(["211", "216"]);
  expect(requests.opens).toEqual([]);
  expect(requests.unexpected).toEqual([]);
});

test("方向键按筛选后实际网格和列表边界移动，仅消费移动且不拦截编辑控件", async ({ page, context }) => {
  const requests = await mockArcade(context);
  await page.setViewportSize({ width: 1280, height: 1000 });
  await page.goto("/");
  await page.getByRole("searchbox", { name: "搜索游戏名称" }).fill("测试游戏");
  await page.getByRole("button", { name: "搜索", exact: true }).click();
  await expect(page.locator(".catalog-card")).toHaveCount(8);
  await expectSelected(page, "1002");
  await page.evaluate(() => {
    document.addEventListener("keydown", event => {
      requestAnimationFrame(() => document.body.setAttribute("data-arrow-prevented", String(event.defaultPrevented)));
    });
  });
  const pressArrow = async (key: string, id: string, consumed: boolean) => {
    await page.locator("body").evaluate(body => body.setAttribute("data-arrow-prevented", "pending"));
    await page.keyboard.press(key);
    await expectSelected(page, id);
    await expect(page.locator("body")).toHaveAttribute("data-arrow-prevented", String(consumed));
  };
  await pressArrow("ArrowUp", "1002", false);
  await pressArrow("ArrowLeft", "1002", false);
  await pressArrow("ArrowRight", "1003", true);
  await pressArrow("ArrowLeft", "1002", true);
  await pressArrow("ArrowDown", "1007", true);
  await pressArrow("ArrowRight", "1008", true);
  await pressArrow("ArrowRight", "1009", true);
  await pressArrow("ArrowRight", "1009", false);
  await pressArrow("ArrowDown", "1009", false);
  await pressArrow("ArrowUp", "1004", true);
  await pressArrow("ArrowLeft", "1003", true);
  await page.setViewportSize({ width: 960, height: 1000 });
  await pressArrow("ArrowUp", "1003", false);
  await pressArrow("ArrowRight", "1004", true);
  await pressArrow("ArrowRight", "1004", false);
  await pressArrow("ArrowDown", "1007", true);
  await pressArrow("ArrowUp", "1004", true);
  await page.getByRole("button", { name: "列表显示" }).click();
  await pressArrow("ArrowDown", "1005", true);
  await pressArrow("ArrowRight", "1005", false);
  await pressArrow("ArrowUp", "1004", true);
  const search = page.getByRole("searchbox", { name: "搜索游戏名称" });
  await search.fill("text");
  await pressArrow("ArrowLeft", "1004", false);
  await pressArrow("ArrowDown", "1004", false);
  await page.locator(".catalog-page").evaluate(container => {
    for (const tag of ["input", "textarea", "div"]) {
      const field = document.createElement(tag);
      field.setAttribute("data-testid", "arrow-edit-" + tag);
      if (tag === "div") field.contentEditable = "true";
      container.append(field);
    }
  });
  for (const tag of ["input", "textarea", "div"]) {
    await page.getByTestId("arrow-edit-" + tag).fill("editable text");
    for (const key of ["ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight"]) {
      await pressArrow(key, "1004", false);
    }
  }
  expect(requests.opens).toEqual([]);
  expect(requests.ratings).toEqual([]);
  expect(requests.unexpected).toEqual([]);
});

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
  return { opens, ratings, unexpected };
}

/** 选择状态必须对应真实可见卡片，页面始终只能有一个独立选框。 */
async function expectSelected(page: Page, id: string) {
  await expect(page.locator(".catalog-card.is-selected")).toHaveAttribute("data-project-id", id);
  await expect(page.locator(".catalog-card__selection-frame")).toHaveCount(1);
}

test("长标题和作者单行省略，同宽卡片跨行等高，触屏保留 44px 操作区域", async ({ page, context }) => {
  const requests = await mockArcade(context);
  await page.goto("/");
  await expect(page.locator(".catalog-card")).toHaveCount(9);
  await expect(page.locator(".catalog-card__title-link").first()).toHaveAttribute("title", longName);
  await expect(page.locator(".catalog-card__author").first()).toHaveAttribute("title", longAuthor);
  for (const width of [320, 390, 600, 960, 1280, 1536, 1920]) {
    await page.setViewportSize({ width, height: 1000 });
    const layout = await page.locator(".catalog-card").evaluateAll((cards) => ({
      heights: cards.map((card) => card.getBoundingClientRect().height),
      overflow: document.documentElement.scrollWidth > innerWidth,
    }));
    expect(Math.max(...layout.heights) - Math.min(...layout.heights)).toBeLessThan(1);
    expect(layout.overflow).toBe(false);
  }
  const truncation = await page.locator(".catalog-card").first().evaluate((card) =>
    [card.querySelector(".catalog-card__title-link")!, card.querySelector(".catalog-card__author a")!]
      .map((element) => ({ whiteSpace: getComputedStyle(element).whiteSpace, overflow: getComputedStyle(element).textOverflow, clipped: element.scrollWidth > element.clientWidth })),
  );
  expect(truncation.every((style) => style.whiteSpace === "nowrap" && style.overflow === "ellipsis" && style.clipped)).toBe(true);
  const phone = await context.browser()!.newContext({ viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true });
  try {
    await mockArcade(phone);
    const touchPage = await phone.newPage();
    await touchPage.goto(baseURL);
    await expect(touchPage.locator(".catalog-card")).toHaveCount(9);
    for (const selector of [".catalog-card__title-link", ".catalog-card__author a", ".catalog-card__wanted", ".catalog-card__open"]) {
      const box = await touchPage.locator(selector).first().boundingBox();
      expect(box!.height).toBeGreaterThanOrEqual(44);
    }
  } finally {
    await phone.close();
  }
  expect(requests.unexpected).toEqual([]);
});

test("WASD 使用当前网格列数，行边界不越界，Enter 复用新标签和最近打开入口", async ({ page, context }) => {
  const requests = await mockArcade(context);
  await page.setViewportSize({ width: 1280, height: 1000 });
  await page.goto("/");
  await expectSelected(page, "1001");
  await page.keyboard.press("d");
  await expectSelected(page, "1002");
  await page.keyboard.press("w");
  await expectSelected(page, "1002");
  await page.keyboard.press("s");
  await expectSelected(page, "1006");
  await page.keyboard.press("s");
  await expectSelected(page, "1009");
  await page.keyboard.press("s");
  await page.keyboard.press("d");
  await expectSelected(page, "1009");
  await page.keyboard.press("w");
  await expectSelected(page, "1005");
  await page.keyboard.press("a");
  await expectSelected(page, "1005");
  await page.setViewportSize({ width: 960, height: 1000 });
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

test("鼠标选择卡片、收藏及打开链接后，WASD 仍能继续选择且不触发其他操作", async ({ page, context }) => {
  const requests = await mockArcade(context);
  await page.setViewportSize({ width: 1280, height: 1000 });
  await page.goto("/");
  await expectSelected(page, "1001");
  const second = page.locator('.catalog-card[data-project-id="1002"]');
  const third = page.locator('.catalog-card[data-project-id="1003"]');

  // 鼠标从搜索框切到卡片热度区域后，选择与键盘焦点必须能继续配合。
  await page.getByRole("searchbox", { name: "搜索游戏名称" }).focus();
  await second.locator(".catalog-card__heat").click();
  await expectSelected(page, "1002");
  await page.keyboard.press("d");
  await expectSelected(page, "1003");

  // 收藏按钮保留点击结果，随后四个方向只移动选框，不再触发收藏或打开。
  await second.locator(".catalog-card__wanted").click();
  await expect(second.locator(".catalog-card__wanted")).toHaveAttribute("aria-pressed", "true");
  await page.keyboard.press("d");
  await expectSelected(page, "1003");
  await page.keyboard.press("s");
  await expectSelected(page, "1007");
  await page.keyboard.press("w");
  await expectSelected(page, "1003");
  await page.keyboard.press("a");
  await expectSelected(page, "1002");
  await expect(second.locator(".catalog-card__wanted")).toHaveAttribute("aria-pressed", "true");
  await expect(third.locator(".catalog-card__wanted")).toHaveAttribute("aria-pressed", "false");
  expect(requests.opens).toEqual([]);

  // 三个原生打开入口返回目录后会留下链接焦点，WASD 仍应接续当前卡片。
  for (const selector of [".catalog-card__media-link", ".catalog-card__title-link", ".catalog-card__open"]) {
    const target = third.locator(selector);
    const popupPromise = context.waitForEvent("page");
    await target.click();
    const popup = await popupPromise;
    await expect(popup.getByRole("heading", { name: "Mock game opened" })).toBeVisible();
    await popup.close();
    await expect(target).toBeFocused();
    await expectSelected(page, "1003");
    await page.keyboard.press("d");
    await expectSelected(page, "1004");
  }
  await expect.poll(() => requests.opens).toEqual(["1003", "1003", "1003"]);
  expect(requests.ratings).toEqual([]);
  expect(requests.unexpected).toEqual([]);
});

test("连续加载更多保留按钮焦点时，WASD 能跨批次移动且 Enter 仍加载游戏", async ({ page, context }) => {
  const requests = await mockArcade(context, 73);
  await page.setViewportSize({ width: 1280, height: 1000 });
  await page.goto("/");
  const cards = page.locator(".catalog-card");
  const loadMore = page.getByRole("button", { name: "加载更多", exact: true });
  await expect(cards).toHaveCount(24);
  await page.locator('.catalog-card[data-project-id="1024"] .catalog-card__heat').click();
  await expectSelected(page, "1024");

  // 首次追加后按钮仍存在并持有焦点，四个方向应接续选框并跨过首批末行。
  await loadMore.click();
  await expect(cards).toHaveCount(48);
  await expect(loadMore).toBeFocused();
  await page.keyboard.press("s");
  await expectSelected(page, "1028");
  await page.keyboard.press("a");
  await expectSelected(page, "1027");
  await page.keyboard.press("w");
  await expectSelected(page, "1023");
  await page.keyboard.press("d");
  await expectSelected(page, "1024");

  // Enter 保留加载按钮的原生操作，不能同时启动当前游戏；追加后继续跨过第二批边界。
  await page.locator('.catalog-card[data-project-id="1048"] .catalog-card__heat').click();
  await loadMore.focus();
  await page.keyboard.press("Enter");
  await expect(cards).toHaveCount(72);
  await expect(loadMore).toBeFocused();
  await expectSelected(page, "1048");
  expect(requests.opens).toEqual([]);
  await page.keyboard.press("s");
  await expectSelected(page, "1052");

  // 最后一批不足一行，按钮移除后仍能落到最后一项并返回上一行。
  await page.locator('.catalog-card[data-project-id="1072"] .catalog-card__heat').click();
  await loadMore.click();
  await expect(cards).toHaveCount(73);
  await expect(loadMore).toHaveCount(0);
  await page.keyboard.press("s");
  await expectSelected(page, "1073");
  await page.keyboard.press("w");
  await expectSelected(page, "1069");
  expect(requests.opens).toEqual([]);
  expect(requests.ratings).toEqual([]);
  expect(requests.unexpected).toEqual([]);
});

test("搜索、显示方式、个人清单和榜单返回目录后，WASD 接续当前可见游戏", async ({ page, context }) => {
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
  await expectSelected(page, "1001");

  // 搜索提交按钮与两种显示方式均保留真实焦点，方向键只移动当前结果内的选框。
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
  await expect(cards).toHaveCount(9);
  await page.keyboard.press("s");
  await expectSelected(page, "1007");
  await page.getByRole("button", { name: "列表显示" }).click();
  await page.keyboard.press("w");
  await expectSelected(page, "1006");
  await page.getByRole("button", { name: "网格显示" }).click();
  await page.keyboard.press("w");
  await expectSelected(page, "1002");

  // 切换个人范围应按新结果选择；键盘移动不能顺便改动想玩或最近打开记录。
  await page.getByRole("button", { name: "想玩清单", exact: true }).click();
  await expect(cards).toHaveCount(3);
  await expectSelected(page, "1002");
  await page.keyboard.press("d");
  await expectSelected(page, "1004");
  await page.getByRole("button", { name: "最近打开", exact: true }).click();
  await expect(cards).toHaveCount(3);
  await expectSelected(page, "1005");
  await page.keyboard.press("d");
  await expectSelected(page, "1007");
  await page.getByRole("button", { name: "全部游戏", exact: true }).click();
  await expect(cards).toHaveCount(9);
  await expectSelected(page, "1007");
  await page.keyboard.press("a");
  await expectSelected(page, "1006");

  // 榜单页面不接管方向键；通过顶部按钮返回后无需清除焦点即可接续原选择。
  for (const view of ["作者榜", "贡献榜"]) {
    await page.getByRole("button", { name: view, exact: true }).click();
    await expect(page.getByRole("heading", { name: view, exact: true })).toBeVisible();
    await page.keyboard.press("d");
    await expect(cards).toHaveCount(0);
    const gameView = page.getByRole("button", { name: "游戏目录", exact: true });
    await gameView.click();
    await expect(gameView).toBeFocused();
    await expectSelected(page, "1006");
    await page.keyboard.press("d");
    await expectSelected(page, "1007");
    await page.keyboard.press("a");
    await expectSelected(page, "1006");
  }
  const library = await page.evaluate(() => JSON.parse(localStorage.getItem("parallellines.catalog-library.v1")!));
  expect(library.wantedIds).toEqual(["1002", "1004", "1006"]);
  expect(library.recent.map((item: { projectId: string }) => item.projectId)).toEqual(["1005", "1007", "1008"]);
  expect(requests.opens).toEqual([]);
  expect(requests.ratings).toEqual([]);
  expect(requests.unexpected).toEqual([]);
});

test("封面铺满掌机屏幕，标题作者与底部操作不重叠，评分和浏览量不再展示", async ({ page, context }) => {
  const requests = await mockArcade(context);
  await page.setViewportSize({ width: 1280, height: 1000 });
  await page.goto("/");
  const cards = page.locator(".catalog-card");
  await expect(cards).toHaveCount(9);
  const first = cards.first();
  await expect(first.locator(".catalog-card__author")).toHaveText(longAuthor);
  await expect(page.locator(".catalog-card__author-label, .catalog-card__stats, .catalog-card__views, .catalog-card__rating-trigger, .catalog-card__rating-panel, .catalog-card__rating-error")).toHaveCount(0);
  // 文本和控件都应叠在封面内；长名称不能挤进右侧操作，也不能遮挡右上热度。
  for (const width of [320, 390, 600, 960, 1280, 1536, 1920]) {
    await page.setViewportSize({ width, height: 1000 });
    const layout = await first.evaluate((card) => {
      const screen = card.querySelector(".catalog-card__screen")!.getBoundingClientRect();
      const image = card.querySelector(".catalog-card__media img")!.getBoundingClientRect();
      const title = card.querySelector(".catalog-card__title-link")!;
      const author = card.querySelector(".catalog-card__author")!;
      const heat = card.querySelector(".catalog-card__heat")!;
      const wanted = card.querySelector(".catalog-card__wanted")!;
      const open = card.querySelector(".catalog-card__open")!;
      const titleBox = title.getBoundingClientRect();
      const authorBox = author.getBoundingClientRect();
      const heatBox = heat.getBoundingClientRect();
      const wantedBox = wanted.getBoundingClientRect();
      const openBox = open.getBoundingClientRect();
      const contained = (box: DOMRect) => box.left >= screen.left - 1 && box.top >= screen.top - 1
        && box.right <= screen.right + 1 && box.bottom <= screen.bottom + 1;
      const separate = (left: DOMRect, right: DOMRect) => left.right <= right.left + 1 || right.right <= left.left + 1
        || left.bottom <= right.top + 1 || right.bottom <= left.top + 1;
      return {
        coverFillsScreen: Math.abs(image.left - screen.left) < 1 && Math.abs(image.top - screen.top) < 1
          && Math.abs(image.width - screen.width) < 1 && Math.abs(image.height - screen.height) < 1,
        contained: [titleBox, authorBox, heatBox, wantedBox, openBox].every(contained),
        noOverlap: [[titleBox, authorBox], [titleBox, wantedBox], [titleBox, openBox], [authorBox, wantedBox],
          [authorBox, openBox], [wantedBox, openBox], [heatBox, titleBox], [heatBox, authorBox]].every(([left, right]) => separate(left!, right!)),
        heatAtTopRight: heatBox.left >= screen.left + screen.width / 2 && heatBox.bottom <= screen.top + screen.height / 2,
        infoAtBottomLeft: titleBox.left < screen.left + screen.width / 2 && authorBox.bottom > screen.top + screen.height / 2,
        actionsAtBottomRight: openBox.left + openBox.width / 2 > screen.left + screen.width / 2
          && openBox.bottom > screen.top + screen.height / 2,
        titleColor: getComputedStyle(title).color,
        authorColor: getComputedStyle(author.querySelector("a")!).color,
      };
    });
    expect(layout.coverFillsScreen, `封面应铺满屏幕：${width}px`).toBe(true);
    expect(layout.contained, `内容应位于屏幕内：${width}px`).toBe(true);
    expect(layout.noOverlap, `文字与控件不能重叠：${width}px`).toBe(true);
    expect(layout.heatAtTopRight, `热度应位于右上：${width}px`).toBe(true);
    expect(layout.infoAtBottomLeft, `标题作者应位于左下：${width}px`).toBe(true);
    expect(layout.actionsAtBottomRight, `开始按钮应位于右下：${width}px`).toBe(true);
    expect(layout.titleColor).toBe("rgb(255, 255, 255)");
    expect(layout.authorColor).not.toBe(layout.titleColor);
  }
  const before = await cards.evaluateAll((items) => items.map((item) => item.getBoundingClientRect().height));
  await first.locator(".catalog-card__wanted").click();
  await expect(first.locator(".catalog-card__wanted")).toHaveAttribute("aria-pressed", "true");
  const popupPromise = context.waitForEvent("page");
  await first.locator(".catalog-card__open").click();
  const popup = await popupPromise;
  await expect(popup.getByRole("heading", { name: "Mock game opened" })).toBeVisible();
  await popup.close();
  await expect.poll(() => requests.opens).toEqual(["1001"]);
  expect(await cards.evaluateAll((items) => items.map((item) => item.getBoundingClientRect().height))).toEqual(before);
  expect(requests.ratings).toEqual([]);
  expect(requests.unexpected).toEqual([]);
});

test("输入、控件确认和作者弹窗保留原操作，鼠标与中键仍只记录一次", async ({ page, context }) => {
  const requests = await mockArcade(context);
  await page.goto("/");
  await expectSelected(page, "1001");
  const search = page.getByRole("searchbox", { name: "搜索游戏名称" });
  await search.fill("wasd");
  await search.press("d");
  await expect(search).toHaveValue("wasdd");
  await expectSelected(page, "1001");
  await search.fill("");
  // 原生 select 持有焦点时保留自身键盘操作，不能移动页面选框。
  for (const name of ["游戏分类", "游戏排序"]) {
    await page.getByRole("combobox", { name }).focus();
    await page.keyboard.press("s");
    await expectSelected(page, "1001");
  }
  const second = page.locator('.catalog-card[data-project-id="1002"]');
  await second.locator(".catalog-card__wanted").focus();
  await expectSelected(page, "1002");
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
  await page.getByRole("button", { name: "投稿游戏", exact: true }).click();
  await expect(page.locator(".catalog-submission-dialog")).toBeVisible();
  await page.keyboard.press("d");
  await expectSelected(page, "1003");
  await page.getByRole("button", { name: "关闭投稿窗口" }).click();
  // 关闭投稿会恢复顶部按钮焦点，直接按方向键仍应接续原选择。
  await expect(page.locator(".catalog-submission-dialog")).not.toBeVisible();
  await expect(page.getByRole("button", { name: "投稿游戏", exact: true })).toBeFocused();
  await page.keyboard.press("d");
  await expectSelected(page, "1004");
  const third = page.locator('.catalog-card[data-project-id="1003"]');
  const target = third.locator(".catalog-card__open");
  for (const button of ["left", "middle"] as const) {
    const popupPromise = context.waitForEvent("page");
    await target.click({ button });
    const popup = await popupPromise;
    await expect(popup.getByRole("heading", { name: "Mock game opened" })).toBeVisible();
    await popup.close();
  }
  // 原链接获得焦点后 Enter 仍走浏览器的默认打开，不能被窗口监听再次启动游戏。
  const keyboardPopupPromise = context.waitForEvent("page");
  await target.focus();
  await target.press("Enter");
  const keyboardPopup = await keyboardPopupPromise;
  await expect(keyboardPopup.getByRole("heading", { name: "Mock game opened" })).toBeVisible();
  await keyboardPopup.close();
  await expect.poll(() => requests.opens).toEqual(["1003", "1003", "1003"]);
  expect(requests.ratings).toEqual([]);
  expect(requests.unexpected).toEqual([]);
});

test("排序、筛选、列表与加载更多始终按当前可见结果选择", async ({ page, context }) => {
  const requests = await mockArcade(context, 28);
  await page.setViewportSize({ width: 1280, height: 1000 });
  await page.goto("/");
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
  // 列表沿用同一套封面与操作，窄屏切换后也不能出现卡片内部或页面横向溢出。
  for (const width of [390, 1280]) {
    await page.setViewportSize({ width, height: 1000 });
    const layout = await page.locator(".catalog-card").evaluateAll((cards) => ({
      pageOverflow: document.documentElement.scrollWidth > innerWidth,
      // 独立选框按设计向外延伸 7px，只用未选卡片的滚动宽度判断实际内容溢出。
      cardOverflow: cards.some((card) => !card.classList.contains("is-selected") && card.scrollWidth > card.clientWidth + 1),
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
  await expect(page.locator(".catalog-card__selection-frame")).toHaveCount(0);
  await page.keyboard.press("Enter");
  expect(requests.opens).toEqual([]);
  expect(requests.unexpected).toEqual([]);
});

test("同秒跨分类新增记录按 ID 倒序默认选中最新项，保留种子及最近打开顺序和大整数精度", async ({ page, context }) => {
  const requests = await mockArcade(context);
  const makeProject = (id: string, slug: string, name: string, createdAt: string) => ({
    id, slug, name, url: `https://arcade-game.invalid/${id}`, kind: "external",
    description: null, author_name: "测试作者", author_url: null,
    icon_url: "/uploads/arcade-fixture/content", created_at: createdAt,
    average_score: null, rating_count: 0, rating_score_sum: 0, view_count: 0, my_score: null,
  });
  const sameSecond = "2026-10-09T15:03:41+08:00";
  const newProjects = [
    makeProject("211", "entropy-blade", "熵刃", sameSecond),
    makeProject("212", "nexus", "NEXUS", sameSecond),
    makeProject("213", "emberfall", "EmberFall", sameSecond),
    makeProject("214", "nanbeidou", "NANBEIDOU", sameSecond),
    makeProject("215", "shinobi-chronicles", "忍者游戏", sameSecond),
    makeProject("216", "illusion-prototype", "回廊", sameSecond),
  ];
  // 分类展开顺序与最新顺序相反；旧种子的 ID 顺序也故意与约定 seedOrder 相反。
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
  const cards = page.locator(".catalog-card");
  await expect(cards).toHaveCount(12);
  expect(await cards.evaluateAll((items) => items.map((item) => item.getAttribute("data-project-id"))))
    .toEqual(["216", "215", "214", "213", "212", "211", "500", "800", ...[...largeIds].reverse()]);
  await expect(cards.first().getByRole("heading", { name: "回廊", exact: true })).toBeVisible();
  await expectSelected(page, "216");
  await page.getByRole("button", { name: "最近打开", exact: true }).click();
  await expect(cards).toHaveCount(2);
  expect(await cards.evaluateAll((items) => items.map((item) => item.getAttribute("data-project-id"))))
    .toEqual(["211", "216"]);
  expect(requests.opens).toEqual([]);
  expect(requests.unexpected).toEqual([]);
});

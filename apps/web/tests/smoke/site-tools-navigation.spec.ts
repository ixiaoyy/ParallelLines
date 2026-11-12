import { expect, test, type Page } from "@playwright/test";

const baseURL = process.env.PLAYWRIGHT_BASE_URL ?? "http://127.0.0.1:5173";
const toolsURL = "https://tools.pingxingxian.space/";
const entries = [
  { path: "/games?view=authors", key: "games", selectors: [".catalog-site-navigation a[href]", ".catalog-footer .site-navigation a[href]"], captures: [".catalog-site-navigation", ".catalog-footer .site-navigation"] },
  { path: "/tools/excel-formulas", key: "excel", selectors: [".formula-back-link", ".formula-site-footer .site-navigation a[href]"], captures: [".formula-site-header", ".formula-site-footer .site-navigation"] },
  { path: "/tools/bead-pattern", key: "bead", selectors: [".bead-brand", ".bead-back", ".bead-footer .site-navigation a[href]"], captures: [".bead-header", ".bead-footer .site-navigation"] },
] as const;

test.use({ serviceWorkers: "block" });

/** 所有接口与站外目标均在浏览器内替换，工具首页只返回本地 HTML，不访问生产。 */
async function isolateNavigation(page: Page) {
  const origin = new URL(baseURL).origin;
  expect(["127.0.0.1", "localhost", "[::1]"].includes(new URL(baseURL).hostname)).toBe(true);
  const unexpected: string[] = [];
  const documents: string[] = [];
  const navigations: string[] = [];
  page.on("request", (request) => {
    if (request.isNavigationRequest() && request.frame() === page.mainFrame()) documents.push(request.url());
  });
  page.on("framenavigated", (frame) => {
    if (frame === page.mainFrame()) navigations.push(frame.url());
  });
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.context().route("**/*", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    if (url.href === toolsURL && request.resourceType() === "document") {
      await route.fulfill({ contentType: "text/html; charset=utf-8", body: "<!doctype html><meta charset='utf-8'><h1>本地工具站目标</h1>" });
    } else if (url.pathname.startsWith("/api/")) {
      if (!["GET", "OPTIONS"].includes(request.method())) unexpected.push(`${request.method()} ${url.href}`);
      await route.fulfill({ json: { data: url.pathname.endsWith("/catalog") ? { categories: [] } : null } });
    } else if (url.origin !== origin || !["GET", "HEAD"].includes(request.method())) {
      unexpected.push(`${request.method()} ${url.href}`);
      await route.abort();
    } else {
      await route.continue();
    }
  });
  return { unexpected, documents, navigations };
}

/** 按容器选择器返回工具或工具品牌链接，不把同容器的游戏链接纳入点击目标。 */
function toolsLink(page: Page, selector: string) {
  return page.locator(selector).filter({ hasText: /工具|平行线/ });
}

test("四产品入口保持正确地址，工具品牌链接继续直达工具首页", async ({ page }, testInfo) => {
  const state = await isolateNavigation(page);
  for (const width of [1440, 921, 390, 320]) {
    await page.setViewportSize({ width, height: 900 });
    for (const entry of entries) {
      await page.goto(entry.path);
      for (const selector of entry.selectors) {
        const link = toolsLink(page, selector);
        await expect(link).toHaveAttribute("href", toolsURL);
        expect(await link.getAttribute("target")).toBeNull();
      }
      const nav = page.getByRole("navigation", { name: "页脚导航", exact: true });
      await expect(nav.getByRole("link", { name: "游戏", exact: true })).toHaveAttribute("href", "/");
      await expect(nav.getByRole("link")).toHaveText(["游戏", "圈子", "工具", "聊天"]);
      await expect(nav.getByRole("link", { name: "圈子", exact: true })).toHaveAttribute("href", "https://forum.pingxingxian.space/");
      await expect(nav.getByRole("link", { name: "聊天", exact: true })).toHaveAttribute("href", "https://chat.pingxingxian.space/");
      for (const link of await nav.getByRole("link").all()) {
        const box = await link.boundingBox();
        expect(box!.width).toBeGreaterThanOrEqual(44);
        expect(box!.height).toBeGreaterThanOrEqual(44);
      }
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
      if (entry.key === "games") {
        expect(await page.locator(".catalog-header").evaluate((header) => {
          const nav = header.querySelector(".catalog-site-navigation")!.getBoundingClientRect();
          return [".catalog-brand", ".catalog-account"].every((selector) => {
            const box = header.querySelector(selector)!.getBoundingClientRect();
            return nav.right <= box.left || box.right <= nav.left || nav.bottom <= box.top || box.bottom <= nav.top;
          });
        })).toBe(true);
      }
      for (const [index, selector] of entry.captures.entries()) {
        await page.locator(selector).screenshot({ path: testInfo.outputPath(`${entry.key}-nav-${index}-${width}.png`) });
      }
    }
  }
  expect(state.unexpected).toEqual([]);
});

test("鼠标和键盘都单次同页直达工具站，不经过旧路由或打开新窗口", async ({ page, context }) => {
  const state = await isolateNavigation(page);
  for (const entry of entries) {
    for (const [index, selector] of entry.selectors.entries()) {
      await page.goto(entry.path);
      const link = toolsLink(page, selector);
      await expect(link).toHaveAttribute("href", toolsURL);
      const documentStart = state.documents.length;
      const navigationStart = state.navigations.length;
      if (index % 2 === 0) {
        await link.click();
      } else {
        await link.focus();
        await link.press("Enter");
      }
      await expect(page).toHaveURL(toolsURL);
      await expect(page.getByRole("heading", { name: "本地工具站目标", exact: true })).toBeVisible();
      expect(state.documents.slice(documentStart)).toEqual([toolsURL]);
      expect(state.navigations.slice(navigationStart)).toEqual([toolsURL]);
      expect(context.pages()).toHaveLength(1);
    }
  }
  expect(state.unexpected).toEqual([]);
});

for (const product of [
  { name: "圈子", url: "https://forum.pingxingxian.space/" },
  { name: "聊天", url: "https://chat.pingxingxian.space/" },
]) {
  test(`${product.name}在游戏顶栏和页脚均可鼠标或键盘同标签直达`, async ({ page, context }) => {
    const state = await isolateNavigation(page);
    await page.route(`${product.url}**`, (route) => route.fulfill({
      contentType: "text/html; charset=utf-8",
      body: `<!doctype html><meta charset="utf-8"><h1>本地${product.name}目标</h1>`,
    }));
    for (const selector of [".catalog-site-navigation", ".catalog-footer .site-navigation"]) {
      await page.goto("/games?view=authors");
      const link = page.locator(selector).getByRole("link", { name: product.name, exact: true });
      expect(await link.getAttribute("target")).toBeNull();
      if (selector === ".catalog-site-navigation") await link.click();
      else {
        await link.focus();
        await link.press("Enter");
      }
      await expect(page).toHaveURL(product.url);
      expect(context.pages()).toHaveLength(1);
    }
    expect(state.unexpected).toEqual([]);
  });
}

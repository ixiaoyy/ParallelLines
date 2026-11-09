import { expect, test } from "@playwright/test";

const baseURL = process.env.PLAYWRIGHT_BASE_URL ?? "http://127.0.0.1:5173";
const toolsOrigin = "https://tools.pingxingxian.space";

test.use({ serviceWorkers: "block" });

test.beforeEach(async ({ context }) => {
  const localOrigin = new URL(baseURL).origin;
  // 保留真实主站页面和路由，工具站只模拟导航落点；禁止访问生产接口或站外资源。
  await context.route("**/*", async route => {
    const url = new URL(route.request().url());
    if (url.origin === toolsOrigin) {
      return route.fulfill({ contentType: "text/html; charset=utf-8", body: "<!doctype html><meta charset=\"utf-8\"><title>工具站导航测试</title><h1>工具站导航测试</h1>" });
    }
    if (url.origin !== localOrigin) return route.abort();
    if (url.pathname.startsWith("/api/")) {
      let data: unknown = null;
      if (url.pathname.endsWith("/catalog/overview")) data = { categories: [], hero: { projects: [], total: 0, next_offset: null } };
      if (url.pathname.endsWith("/catalog")) data = { categories: [] };
      if (url.pathname.endsWith("/site/settings")) data = { settings: {}, updated_at: null };
      if (url.pathname.endsWith("/site/visits")) data = { recorded: false };
      return route.fulfill({ json: { data } });
    }
    return route.continue();
  });
});

for (const path of ["/tools", "/tools/"]) {
  test(`${path} 直达新工具站并保留入口参数与片段`, async ({ page }) => {
    const suffix = "?source=qa&tag=one&tag=two&empty=#entry";
    await page.goto(path + suffix);
    await expect(page).toHaveURL(toolsOrigin + "/" + suffix);
    await expect(page).toHaveTitle("工具站导航测试");
  });
}

test("SPA 历史导航也真正跨域，不只更新主站地址栏", async ({ page }) => {
  await page.goto("/tools/excel-formulas");
  await expect(page.getByRole("heading", { name: "Excel 公式速查", exact: true })).toBeVisible();
  // 沿用已有历史事件回归方式，覆盖没有经过网关 HTTP 请求的 SPA 跳转。
  await page.evaluate(() => {
    history.pushState(null, "", "/tools?source=spa#entry");
    dispatchEvent(new PopStateEvent("popstate", { state: history.state }));
  });
  await expect(page).toHaveURL(toolsOrigin + "/?source=spa#entry");
  await expect(page).toHaveTitle("工具站导航测试");
});

const entries = [
  { path: "/", selectors: [".catalog-site-navigation", ".site-navigation"], names: ["工具", "工具"] },
  { path: "/tools/excel-formulas?lesson=person-total", selectors: [".formula-back-link", ".site-navigation"], names: ["返回工具列表", "工具"] },
  { path: "/tools/bead-pattern", selectors: [".bead-brand", ".bead-back", ".site-navigation"], names: ["平行线", "返回工具", "工具"] },
];

for (const entry of entries) {
  test(`${entry.path} 原工具入口文字保留并在新标签页打开`, async ({ page, context }) => {
    await page.goto(entry.path);
    const originalURL = page.url();
    for (const [index, selector] of entry.selectors.entries()) {
      const container = page.locator(selector);
      const link = selector.endsWith("navigation") ? container.getByRole("link", { name: "工具", exact: true }) : container;
      await expect(link).toHaveText(entry.names[index]);
      await expect(link).toHaveAttribute("href", "/tools");
      await expect(link).toHaveAttribute("target", "_blank");
      await expect(link).toHaveAttribute("rel", "noopener noreferrer");
      const popupPromise = context.waitForEvent("page");
      await link.focus();
      await link.press("Enter");
      const popup = await popupPromise;
      await expect(popup).toHaveURL(toolsOrigin + "/");
      await expect(popup).toHaveTitle("工具站导航测试");
      expect(await popup.evaluate(() => window.opener === null)).toBe(true);
      await popup.close();
      await expect(page).toHaveURL(originalURL);
    }
    if (entry.path === "/") {
      const game = page.locator(".catalog-site-navigation").getByRole("link", { name: "游戏", exact: true });
      await expect(game).toHaveAttribute("href", "/");
      expect(await game.getAttribute("target")).toBeNull();
    }
  });
}

test("名单核对旧别名保留固定 op 查询及片段，Excel 其它查询不受入口跳转影响", async ({ page }) => {
  await page.goto("/tools/list-compare?lesson=ignored&op=clean&source=old#excel-local-processor");
  await expect(page).toHaveURL(/\/tools\/excel-formulas\?op=compare#excel-local-processor$/);
  await expect(page.locator("#compare-operator-title")).toBeVisible();
  await page.goto("/tools/excel-formulas?lesson=person-total&op=clean&source=old");
  await expect(page.getByRole("heading", { name: "同一个人有多笔，算他的总金额", exact: true })).toBeVisible();
  await expect(page.getByRole("region", { name: "本地操作面板", exact: true })).toBeVisible();
  await expect(page).toHaveURL(/lesson=person-total&op=clean&source=old$/);
});

import { expect, test } from "@playwright/test";

import { fixture, TOPIC, USER } from "./fixtures/forum";

test.use({ serviceWorkers: "block" });

test("目录使用独立论坛入口，旧论坛筛选与主题访问保持兼容", async ({ page }, testInfo) => {
  const state = await fixture(page);
  await page.goto("/");
  await expect(page.locator(".catalog-page")).toBeVisible();
  await expect(page.locator('a[href="/forum"]')).toHaveCount(0);
  expect(state.requested.some((path) => path.includes("/topics"))).toBe(false);

  await page.goto("/forum");
  await expect(page.locator(".forum-home")).toBeVisible();
  await expect(page.getByRole("link", { name: TOPIC.title, exact: true }).first()).toBeVisible();
  const search = page.getByRole("search", { name: "搜索首页主题" });
  await search.getByRole("searchbox").fill("固定主题");
  await search.getByRole("searchbox").press("Enter");
  await expect(page).toHaveURL(/\/forum\?title=/);
  await page.reload();
  await expect(page.locator(".forum-home")).toBeVisible();
  for (const width of [1280, 390, 320]) {
    await page.setViewportSize({ width, height: 900 });
    await expect(page.locator(".forum-home")).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
    await page.screenshot({ path: testInfo.outputPath(`forum-${width}.png`), fullPage: true });
  }
  await page.setViewportSize({ width: 1280, height: 900 });
  await page.getByRole("link", { name: TOPIC.title, exact: true }).first().click();
  await expect(page).toHaveURL(/\/topics\/201\/forum-entry/);
  await expect(page.getByRole("heading", { name: TOPIC.title })).toBeVisible();
  await page.locator('.brand[href="/forum"]').click();
  await expect(page).toHaveURL(/\/forum$/);
  expect(state.errors).toEqual([]);
  expect(state.unexpected).toEqual([]);
});

test("普通登录保留发帖回跳，发帖回复经真实页面提交到模拟接口", async ({ page }) => {
  const state = await fixture(page);
  await page.goto("/new-topic?board=lounge");
  await expect(page).toHaveURL(/\/auth\?redirect=/);
  const form = page.getByRole("form", { name: "登录表单" });
  await form.getByRole("textbox", { name: "用户名 / 邮箱 / 手机号", exact: true }).fill(USER.username);
  await form.getByPlaceholder("请输入密码").fill("fixture-password");
  await form.getByRole("button", { name: /^登\s*录$/ }).click();
  await expect(page).toHaveURL(/\/new-topic\?board=lounge$/);
  await page.getByRole("textbox", { name: "标题", exact: true }).fill("恢复后的发帖请求");
  await page.locator('.topic-md-editor .cm-content[contenteditable="true"]').fill("恢复后的发帖正文。");
  await page.getByRole("button", { name: /^发\s*布$/ }).last().click();
  await expect(page.getByRole("heading", { name: "恢复后的发帖请求" })).toBeVisible();
  await page.getByRole("button", { name: "回复", exact: true }).first().click();
  await page.locator('.reply-composer-sheet .cm-content[contenteditable="true"]').fill("恢复后的回复正文。");
  await page.getByRole("dialog").getByRole("button", { name: "发布", exact: true }).click();
  await expect(page.getByText("恢复后的回复正文。", { exact: true })).toBeVisible();
  expect(state.writes.map((write) => write.path)).toEqual(["/auth/login", "/boards/lounge/topics", "/topics/201/posts"]);
  expect(state.writes[1].data).toMatchObject({ title: "恢复后的发帖请求", raw_md: "恢复后的发帖正文。" });
  expect(state.writes[2].data).toMatchObject({ raw_md: "恢复后的回复正文。" });
  expect(state.errors).toEqual([]);
  expect(state.unexpected).toEqual([]);
});

test("普通注册与后台专用登录分别保留，普通成员不能进入后台", async ({ page }) => {
  const state = await fixture(page);
  await page.goto("/auth?mode=register");
  await expect(page.getByRole("form", { name: "注册表单" })).toBeVisible();
  await page.goto("/auth?redirect=/admin&mode=register");
  await expect(page.getByRole("form", { name: "登录表单" })).toBeVisible();
  await expect(page.getByRole("form", { name: "注册表单" })).toHaveCount(0);
  await page.getByRole("textbox", { name: "用户名 / 邮箱 / 手机号", exact: true }).fill(USER.username);
  await page.getByPlaceholder("请输入密码").fill("fixture-password");
  await page.getByRole("button", { name: /^登\s*录$/ }).click();
  await expect(page).toHaveURL(/\/$/);
  await expect(page.locator(".catalog-page")).toBeVisible();
  await page.goto("/admin/forum");
  await expect(page).toHaveURL(/\/forbidden\?required=admin/);
  await page.goto("/admin/moderation");
  await expect(page).toHaveURL(/\/forbidden\?required=moderation/);
  expect(state.requested.some((path) => path.startsWith("GET /admin/"))).toBe(false);
  expect(state.errors).toEqual([]);
  expect(state.unexpected).toEqual([]);
});

test("论坛品牌与主题不残留到原目录后台，原后台保持独立布局", async ({ page }) => {
  const state = await fixture(page, "admin");
  await page.goto("/forum");
  await expect(page.locator(".forum-home")).toBeVisible();
  await expect.poll(() => page.evaluate(() => document.documentElement.style.getPropertyValue("--primary"))).toBe("#d946ef");
  // 用浏览器历史事件单独验证同一 SPA 离开旧论坛兼容页的清理。
  await page.evaluate(() => {
    history.pushState(null, "", "/");
    dispatchEvent(new PopStateEvent("popstate", { state: history.state }));
  });
  await expect(page.locator(".catalog-page")).toBeVisible();
  await expect(page.locator(".forum-home")).toHaveCount(0);
  await expect(page.locator(".admin-console-shell")).toHaveCount(0);
  await expect.poll(() => page.evaluate(() => document.documentElement.style.getPropertyValue("--primary"))).toBe("");
  expect(await page.evaluate(() => document.documentElement.getAttribute("data-interface-theme"))).toBeNull();
  // 站点槽现在由根应用接手；只清理论坛描述，品牌与唯一图谱继续保留。
  await expect(page.locator("#seo-site-structured-data")).toHaveCount(1);
  await expect(page.locator("#seo-site-structured-data")).not.toContainText("固定数据验证");
  await page.goto("/admin");
  await expect(page.locator(".admin-console-shell")).toHaveCount(0);
  await expect(page).toHaveTitle(/目录管理与访问统计/);
  expect(state.errors).toEqual([]);
  expect(state.unexpected).toEqual([]);
});

test("登录后的四产品导航不遮住品牌、通知或账号", async ({ page }, testInfo) => {
  const state = await fixture(page, "user");
  await page.goto("/");
  await expect(page.locator(".catalog-header .notification-trigger")).toBeVisible();
  for (const width of [390, 360, 320]) {
    await page.setViewportSize({ width, height: 900 });
    expect(await page.locator(".catalog-header").evaluate((header) => {
      const nav = header.querySelector(".catalog-site-navigation")!.getBoundingClientRect();
      return [".catalog-brand", ".catalog-account", ".notification-trigger"].every((selector) => {
        const box = header.querySelector(selector)!.getBoundingClientRect();
        return nav.right <= box.left || box.right <= nav.left || nav.bottom <= box.top || box.bottom <= nav.top;
      });
    })).toBe(true);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
    await page.locator(".catalog-header").screenshot({ path: testInfo.outputPath(`logged-in-header-${width}.png`) });
  }
  expect(state.errors).toEqual([]);
  expect(state.unexpected).toEqual([]);
});

test("默认进入游戏目录，四产品导航同标签切换且不改变游戏入口", async ({ page }, testInfo) => {
  const state = await fixture(page);
  await page.goto("/?source=qa#entry");
  await expect(page).toHaveURL(/\/\?source=qa#entry$/);
  const nav = page.getByRole("navigation", { name: "页脚导航", exact: true });
  await expect(page.locator(".catalog-footer").getByRole("navigation", { name: "页脚导航" })).toHaveCount(1);
  await expect(nav).toHaveText(/游戏\s*\|\s*圈子\s*\|\s*工具\s*\|\s*聊天/);
  await expect(nav.getByRole("link")).toHaveText(["游戏", "圈子", "工具", "聊天"]);
  await expect(nav.getByRole("link", { name: "游戏", exact: true })).toHaveAttribute("href", "/");
  await expect(nav.getByRole("link", { name: "圈子", exact: true })).toHaveAttribute("href", "https://forum.pingxingxian.space/");
  await expect(nav.getByRole("link", { name: "聊天", exact: true })).toHaveAttribute("href", "https://chat.pingxingxian.space/");
  await expect(nav.locator('a[href="/forum"]')).toHaveCount(0);
  for (const width of [2028, 1280, 1024, 800, 390, 320]) {
    await page.setViewportSize({ width, height: 900 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
    await expect(nav).toHaveCSS("position", "static");
    await nav.scrollIntoViewIfNeeded();
    // 页脚现行结构使用弹性换行；四入口与品牌、介绍和个人清单提示均不能互相遮挡。
    const footerLayout = await page.locator(".catalog-footer").evaluate(footer => {
      const navigation = footer.querySelector("nav")!.getBoundingClientRect();
      const brand = footer.querySelector("div")!.getBoundingClientRect();
      const about = footer.querySelector(".catalog-footer__about")!.getBoundingClientRect();
      const hint = footer.querySelector(".catalog-library__hint")!.getBoundingClientRect();
      return {
        separated: navigation.left >= brand.right + 8 || navigation.top >= brand.bottom + 8,
        aboutGap: about.top - navigation.bottom,
        hintGap: hint.top - about.bottom,
      };
    });
    expect(footerLayout.separated).toBe(true);
    expect(footerLayout.aboutGap).toBeGreaterThanOrEqual(8);
    expect(footerLayout.hintGap).toBeGreaterThanOrEqual(0);
    const beforeScroll = await page.evaluate(() => window.scrollY);
    const beforeBox = await nav.boundingBox();
    await page.evaluate(() => window.scrollTo(0, 0));
    const afterBox = await nav.boundingBox();
    expect(afterBox!.y - beforeBox!.y).toBeCloseTo(beforeScroll, 0);
    await page.screenshot({ path: testInfo.outputPath(`games-entry-${width}.png`), fullPage: true });
    await page.locator(".catalog-footer").screenshot({ path: testInfo.outputPath(`games-footer-${width}.png`) });
  }
  // 只验证跨站导航合同；工具站响应在本地拦截，不访问生产或写入统计。
  await page.route("https://tools.pingxingxian.space/**", route =>
    route.fulfill({ contentType: "text/html; charset=utf-8", body: "<!doctype html><meta charset='utf-8'><title>工具站导航测试</title>" }),
  );
  const toolsLink = nav.getByRole("link", { name: "工具", exact: true });
  await expect(toolsLink).toHaveAttribute("href", "https://tools.pingxingxian.space/");
  expect(await toolsLink.getAttribute("target")).toBeNull();
  await toolsLink.click();
  await expect(page).toHaveURL("https://tools.pingxingxian.space/");
  expect(page.context().pages()).toHaveLength(1);
  await page.goto("/games?source=compat#entry");
  await expect(page).toHaveURL(/\/games\?source=compat#entry$/);
  await expect(page.locator(".catalog-page")).toBeVisible();
  await page.reload();
  await expect(page).toHaveURL(/\/games\?source=compat#entry$/);
  await page.goto("/play");
  await expect(page).toHaveURL(/\/$/);
  expect(state.requested.some(path => /daily-reports|pdf-translations/.test(path))).toBe(false);
  expect(state.errors).toEqual([]);
  expect(state.unexpected).toEqual([]);
});

import { expect, test } from "@playwright/test";

import { fixture, TOPIC, USER } from "./fixtures/forum";

test.use({ serviceWorkers: "block" });

test("独立论坛根入口保留原主站内容、筛选、旧首页和帖子片段", async ({ page }, testInfo) => {
  const state = await fixture(page);
  await page.goto("/");
  await expect(page.locator(".forum-home")).toBeVisible();
  await expect(page).toHaveTitle("平行线 ParallelLines · 圈子");
  await expect(page.locator(".catalog-page")).toHaveCount(0);
  await expect(page.getByRole("link", { name: TOPIC.title, exact: true }).first()).toBeVisible();
  expect(state.requested.some((path) => path.includes("/catalog"))).toBe(false);
  const nav = page.getByRole("navigation", { name: "页脚导航", exact: true });
  await expect(nav.getByRole("link")).toHaveText(["游戏", "圈子", "工具", "聊天"]);
  await expect(nav.getByRole("link", { name: "游戏", exact: true })).toHaveAttribute("href", "https://pingxingxian.space/");
  await expect(nav.getByRole("link", { name: "圈子", exact: true })).toHaveAttribute("href", "/");
  await expect(nav.getByRole("link", { name: "工具", exact: true })).toHaveAttribute("href", "https://tools.pingxingxian.space/");
  await expect(nav.getByRole("link", { name: "聊天", exact: true })).toHaveAttribute("href", "https://chat.pingxingxian.space/");
  for (const width of [1440, 921, 390, 320]) {
    await page.setViewportSize({ width, height: 900 });
    for (const link of await nav.getByRole("link").all()) {
      const box = await link.boundingBox();
      expect(box!.width).toBeGreaterThanOrEqual(44);
      expect(box!.height).toBeGreaterThanOrEqual(44);
    }
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
    await page.screenshot({ path: testInfo.outputPath(`forum-home-${width}.png`), fullPage: true });
    await nav.screenshot({ path: testInfo.outputPath(`forum-navigation-${width}.png`) });
  }
  await page.goto("/forum?title=固定主题#top");
  await expect(page).toHaveURL(/\/\?title=.*#top$/);
  await page.reload();
  await expect(page.locator(".forum-home")).toBeVisible();
  await page.getByRole("link", { name: TOPIC.title, exact: true }).first().click();
  await expect(page).toHaveURL(/\/topics\/201\/forum-entry/);
  await expect(page.getByRole("heading", { name: TOPIC.title })).toBeVisible();
  await page.locator('.brand[href="/"]').click();
  await expect(page).toHaveURL(/\/$/);
  expect(state.errors).toEqual([]);
  expect(state.unexpected).toEqual([]);
});

test("论坛原账号登录后按原合同发布主题和回复，普通成员仍不能进入后台", async ({ page }) => {
  const state = await fixture(page);
  await page.goto("/new-topic?board=lounge");
  await expect(page).toHaveURL(/\/auth\?redirect=/);
  const form = page.getByRole("form", { name: "登录表单" });
  await form.getByRole("textbox", { name: "用户名 / 邮箱 / 手机号", exact: true }).fill(USER.username);
  await form.getByPlaceholder("请输入密码").fill("fixture-password");
  await form.getByRole("button", { name: /^登\s*录$/ }).click();
  await expect(page).toHaveURL(/\/new-topic\?board=lounge$/);
  await page.getByRole("textbox", { name: "标题", exact: true }).fill("独立论坛完整发帖回归");
  await page.locator('.topic-md-editor .cm-content[contenteditable="true"]').fill("原论坛业务完整保留。");
  await page.getByRole("button", { name: /^发\s*布$/ }).last().click();
  await expect(page.getByRole("heading", { name: "独立论坛完整发帖回归" })).toBeVisible();
  await page.getByRole("button", { name: "回复", exact: true }).first().click();
  await page.locator('.reply-composer-sheet .cm-content[contenteditable="true"]').fill("独立论坛回复回归。");
  await page.getByRole("dialog").getByRole("button", { name: "发布", exact: true }).click();
  await expect(page.getByText("独立论坛回复回归。", { exact: true })).toBeVisible();
  expect(state.writes.map((write) => write.path)).toEqual(["/auth/login", "/boards/lounge/topics", "/topics/201/posts"]);
  expect(state.writes[1].data).toMatchObject({ title: "独立论坛完整发帖回归", raw_md: "原论坛业务完整保留。" });
  expect(state.writes[2].data).toMatchObject({ raw_md: "独立论坛回复回归。" });
  await page.goto("/admin");
  await expect(page).toHaveURL(/\/forbidden\?required=admin/);
  expect(state.requested.some((path) => path.startsWith("GET /admin/"))).toBe(false);
  expect(state.errors).toEqual([]);
  expect(state.unexpected).toEqual([]);
});

test("聊天入口鼠标和键盘均同标签直达 Chat，不携带论坛令牌", async ({ page, context }) => {
  const state = await fixture(page, "user");
  const navigations: string[] = [];
  await page.route("https://chat.pingxingxian.space/**", (route) => {
    const request = route.request();
    navigations.push(request.url());
    expect(request.headers().authorization).toBeUndefined();
    return route.fulfill({ contentType: "text/html; charset=utf-8", body: "<!doctype html><meta charset='utf-8'><h1>本地 Chat 目标</h1>" });
  });
  for (const keyboard of [false, true]) {
    await page.goto("/");
    const link = page.getByRole("navigation", { name: "页脚导航", exact: true }).getByRole("link", { name: "聊天", exact: true });
    expect(await link.getAttribute("target")).toBeNull();
    if (keyboard) {
      await link.focus();
      await link.press("Enter");
    } else {
      await link.click();
    }
    await expect(page).toHaveURL("https://chat.pingxingxian.space/");
    await expect(page.getByRole("heading", { name: "本地 Chat 目标" })).toBeVisible();
  }
  expect(navigations).toEqual(["https://chat.pingxingxian.space/", "https://chat.pingxingxian.space/"]);
  expect(context.pages()).toHaveLength(1);
  expect(state.errors).toEqual([]);
  expect(state.unexpected).toEqual([]);
});

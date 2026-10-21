import { expect, test, type Page } from "@playwright/test";

import type { UserPublic } from "../../src/features/auth/model";
import type { BoardResponse } from "../../src/features/boards/model";
import type { PostResponse } from "../../src/features/posts/model";
import type { TopicResponse } from "../../src/features/topics/model";

test.use({ serviceWorkers: "block" });

const NOW = "2026-10-19T08:00:00Z";
const USER: UserPublic = {
  id: "101", username: "forum_fixture", email: "forum-fixture@example.com", avatar_url: null,
  display_name: null, bio: null, website_url: null, location: null, role: "user", level: 1,
  trust_level: 1, trust_level_label: "基础成员", points_balance: 0, experience_total: 50,
  experience_to_next_level: 100, level_progress_percent: 0, status: "active",
  two_factor_enabled: false, profile_visibility: "public", show_activity: true,
  interface_theme: "colorful", locale: "zh-CN", created_at: NOW,
};
const BOARD: BoardResponse = {
  id: "10", slug: "lounge", name: "闲聊", description: "论坛入口回归固定数据。",
  color: "#409EFF", avatar_url: null, owner_id: null, parent_board_id: null,
  parent_board_slug: null, parent_board_name: null, visibility: "public", required_tags: [],
  allowed_tags: [], post_template: null, default_notification_level: "normal", default_sort: "latest",
  topic_count: 1, post_count: 1, follower_count: 0, is_following: false,
  notification_level: null, can_create_topic: true, created_at: NOW, updated_at: NOW,
};
const TOPIC: TopicResponse = {
  id: "201", slug: "forum-entry", title: "恢复论坛入口的固定主题", board_id: "10",
  board_slug: "lounge", board_name: "闲聊", board_color: "#409EFF", board_visibility: "public",
  author_id: "101", author_name: USER.username, author_avatar_url: null, author_role: "user",
  author_is_persona: false, author_persona_kind: null, author_level: 1, author_trust_level: 1,
  author_trust_level_label: "基础成员", tags: [], accepted_answer_post_id: null,
  solved_at: null, solved_by_id: null, answer_mode: false, vote_score: 0, vote_count: 0,
  my_vote: 0, poll: null, topic_type: "regular", visibility: "public", status: "open",
  pinned: false, featured: false, view_count: 1, reply_count: 0, like_count: 0, hot_score: 1,
  last_posted_at: NOW, created_at: NOW, updated_at: NOW, merged_into_topic_id: null,
  share_url: "/topics/201/forum-entry", excerpt: "入口恢复后的固定正文。",
};

/** 生成明确归属的模拟回复；测试不会连接数据库或向真实论坛写入。 */
function post(number: number, body: string): PostResponse {
  return {
    id: String(300 + number), topic_id: TOPIC.id, user_id: USER.id, author_name: USER.username,
    author_avatar_url: null, author_role: "user", author_is_persona: false, author_persona_kind: null,
    author_level: 1, author_trust_level: 1, author_trust_level_label: "基础成员", parent_id: null,
    post_number: number, raw_md: body, cooked_html: `<p>${body}</p>`, reply_count: 0, like_count: 0,
    accepted_answer: false, vote_score: 0, vote_count: 0, my_vote: 0,
    share_url: `${TOPIC.share_url}#post-${number}`, deleted_at: null, created_at: NOW, updated_at: NOW,
  };
}

/** 拦截全部业务接口，记录真实页面提交的参数，并阻止站外请求。 */
async function fixture(page: Page, role?: "user" | "admin") {
  const state = {
    errors: [] as string[], unexpected: [] as string[], requested: [] as string[],
    writes: [] as { path: string; data: unknown }[],
    topic: { ...TOPIC }, posts: [post(1, "入口恢复后的固定正文。")],
  };
  const user = { ...USER, role: role ?? "user" };
  if (role) {
    await page.addInitScript(() => localStorage.setItem("parallellines.access_token", "fixture-only"));
  }
  page.on("pageerror", (error) => state.errors.push(error.message));
  await page.route("**/*", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    if (!url.pathname.startsWith("/api/")) {
      const localOrigin = new URL(process.env.PLAYWRIGHT_BASE_URL ?? "http://127.0.0.1:5173").origin;
      return url.origin === localOrigin ? route.continue() : route.abort();
    }
    const path = url.pathname.replace(/^\/api\/v1/, "");
    const method = request.method();
    state.requested.push(`${method} ${path}`);
    const send = (data: unknown) => route.fulfill({ json: { data } });
    if (path === "/site/settings") {
      return send({ settings: { site_title: "平行线", site_tagline: "固定数据验证", brand_primary_color: "#d946ef" }, updated_at: null });
    }
    if (path === "/site/visits") return send({ recorded: false });
    if (path === "/catalog" || path === "/admin/catalog") return send({ categories: [] });
    if (path === "/admin/analytics") return send({ totals: { page_views: 0, unique_visitors: 0, external_referrals: 0 }, traffic_sources: [], entry_pages: [], daily: [] });
    if (path === "/auth/oauth/providers") return send({ providers: [] });
    if (path === "/auth/me") return send(user);
    if (path === "/auth/login") {
      state.writes.push({ path, data: request.postDataJSON() });
      return send({ access_token: "fixture-only", refresh_token: "fixture-refresh", token_type: "bearer", user, session_id: "fixture-session", two_factor_required: false, challenge_token: null });
    }
    if (path === "/auth/fablespace/access") return send({ access_allowed: false, capabilities: [], access_level: null, expires_at: null, authorization_version: 0 });
    if (path === "/site/extensions" || path === "/tags") return send([]);
    if (path === "/drafts") {
      if (method === "DELETE") return send(true);
      if (method === "PUT") return send({ ...request.postDataJSON(), id: "fixture-draft", user_id: USER.id, version: 1, updated_at: NOW });
      return send([]);
    }
    if (path === "/drafts/lookup") return send(null);
    if (path === "/notifications") return send({ notifications: [], unread_count: 0 });
    if (path === "/notifications/stream") return route.fulfill({ status: 204, body: "" });
    if (path === "/boards") return send([BOARD]);
    if (path === "/boards/lounge") return send({ ...BOARD, latest_topics: [state.topic], child_boards: [] });
    if (path === "/boards/lounge/topics" && method === "POST") {
      const data = request.postDataJSON() as { title: string; raw_md: string };
      state.writes.push({ path, data });
      state.topic = { ...state.topic, title: data.title };
      state.posts = [post(1, data.raw_md)];
      return send(state.topic);
    }
    if (path === "/topics" || path === "/search" || path === "/boards/lounge/topics") return send([state.topic]);
    if (path === "/topics/201") return send(state.topic);
    if (path === "/topics/201/posts" && method === "POST") {
      const data = request.postDataJSON() as { raw_md: string };
      state.writes.push({ path, data });
      const reply = post(state.posts.length + 1, data.raw_md);
      state.posts.push(reply);
      return send(reply);
    }
    if (path === "/topics/201/posts") return send(state.posts);
    if (path === "/topics/201/notification-level") return send({ topic_id: "201", notification_level: "normal", last_read_post_number: 0 });
    if (path === "/users/id/101") return send({ ...user, is_persona: false, persona_kind: null, can_edit: true, topic_count: 1, post_count: 1, following_count: 0, follower_count: 0, badges: [] });
    if (path === "/users/forum_fixture/topics") return send([state.topic]);
    if (path === "/users/forum_fixture/activity") return send([]);
    state.unexpected.push(`${method} ${path}`);
    return route.fulfill({ status: 501, json: { error: { code: "unmocked_api", message: path } } });
  });
  return state;
}

test("目录无论坛入口，手动访问与论坛筛选在桌面和手机均保留", async ({ page }, testInfo) => {
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
  await expect(page).toHaveURL(/\/games$/);
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
  // 首页刻意不提供论坛入口，用浏览器历史事件单独验证同一 SPA 离开论坛的清理。
  await page.evaluate(() => {
    history.pushState(null, "", "/");
    dispatchEvent(new PopStateEvent("popstate", { state: history.state }));
  });
  await expect(page.locator(".catalog-page")).toBeVisible();
  await expect(page.locator(".forum-home")).toHaveCount(0);
  await expect(page.locator(".admin-console-shell")).toHaveCount(0);
  await expect.poll(() => page.evaluate(() => document.documentElement.style.getPropertyValue("--primary"))).toBe("");
  expect(await page.evaluate(() => document.documentElement.getAttribute("data-interface-theme"))).toBeNull();
  await expect(page.locator("#seo-site-structured-data")).toHaveCount(0);
  await page.goto("/admin");
  await expect(page.locator(".admin-console-shell")).toHaveCount(0);
  await expect(page).toHaveTitle(/目录管理与访问统计/);
  expect(state.errors).toEqual([]);
  expect(state.unexpected).toEqual([]);
});

test("默认进入游戏目录，圈子禁用，工具为空状态且不加载具体工具", async ({ page }, testInfo) => {
  const state = await fixture(page);
  await page.goto("/?source=qa#entry");
  await expect(page).toHaveURL(/\/games\?source=qa#entry$/);
  const nav = page.getByRole("navigation", { name: "页脚导航", exact: true });
  await expect(page.locator(".catalog-footer__inner").getByRole("navigation", { name: "页脚导航" })).toHaveCount(1);
  await expect(nav).toHaveText(/游戏\s*\|\s*圈子\s*\|\s*工具/);
  await expect(nav.getByRole("link")).toHaveText(["游戏", "工具"]);
  await expect(nav.getByRole("link", { name: "游戏", exact: true })).toHaveAttribute("href", "/games");
  await expect(nav.getByRole("button", { name: "圈子，暂未开放", exact: true })).toBeDisabled();
  await expect(nav.locator('a[href="/forum"]')).toHaveCount(0);
  for (const width of [1280, 390, 320]) {
    await page.setViewportSize({ width, height: 900 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
    await expect(nav).toHaveCSS("position", "static");
    await nav.scrollIntoViewIfNeeded();
    const beforeScroll = await page.evaluate(() => window.scrollY);
    const beforeBox = await nav.boundingBox();
    await page.evaluate(() => window.scrollTo(0, 0));
    const afterBox = await nav.boundingBox();
    expect(afterBox!.y - beforeBox!.y).toBeCloseTo(beforeScroll, 0);
    if (width > 800) {
      const clearance = await page.locator(".catalog-footer").evaluate(footer => {
        const nav = footer.querySelector("nav")!.getBoundingClientRect();
        const cat = getComputedStyle(footer, "::after");
        const catLeft = footer.getBoundingClientRect().right - parseFloat(cat.right) - parseFloat(cat.width);
        return catLeft - nav.right;
      });
      expect(clearance).toBeGreaterThanOrEqual(8);
    }
    await page.screenshot({ path: testInfo.outputPath(`games-entry-${width}.png`), fullPage: true });
  }
  await nav.getByRole("link", { name: "工具", exact: true }).click();
  await expect(page).toHaveURL(/\/tools$/);
  await expect(page.getByRole("heading", { name: "暂无可用工具", exact: true })).toBeVisible();
  await expect(page.getByRole("link", { name: /个人日报助手|PDF 英文化/ })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "圈子，暂未开放", exact: true })).toBeDisabled();
  for (const width of [1280, 390, 320]) {
    await page.setViewportSize({ width, height: 900 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
    await expect(nav).toHaveCSS("position", "static");
    await nav.scrollIntoViewIfNeeded();
    const beforeScroll = await page.evaluate(() => window.scrollY);
    const beforeBox = await nav.boundingBox();
    await page.evaluate(() => window.scrollTo(0, 0));
    const afterBox = await nav.boundingBox();
    expect(afterBox!.y - beforeBox!.y).toBeCloseTo(beforeScroll, 0);
    await page.screenshot({ path: testInfo.outputPath(`tools-entry-${width}.png`), fullPage: true });
  }
  await page.reload();
  await expect(page.getByRole("heading", { name: "暂无可用工具", exact: true })).toBeVisible();
  await page.getByRole("link", { name: "去看看游戏", exact: true }).click();
  await expect(page).toHaveURL(/\/games$/);
  await page.goto("/play");
  await expect(page).toHaveURL(/\/games$/);
  expect(state.requested.some(path => /daily-reports|pdf-translations/.test(path))).toBe(false);
  expect(state.errors).toEqual([]);
  expect(state.unexpected).toEqual([]);
});

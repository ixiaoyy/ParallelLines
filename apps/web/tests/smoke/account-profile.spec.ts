import { expect, test, type Page } from "@playwright/test";

import type { UserPublic } from "../../src/features/auth/model";
import type { TopicResponse } from "../../src/features/topics/model";
import type { UserProfile } from "../../src/features/users/model";

test.use({ serviceWorkers: "block" });

const NOW = "2026-11-12T08:00:00Z";
const USER: UserPublic = {
  id: "101", username: "account_fixture", email: "account-fixture@example.invalid",
  display_name: "个人中心测试", bio: "仅用于本地模拟接口回归。", avatar_url: null,
  website_url: null, location: null, role: "admin", status: "active", level: 3,
  trust_level: 1, trust_level_label: "基础成员", points_balance: 0, experience_total: 6121,
  experience_to_next_level: 0, level_progress_percent: 100, two_factor_enabled: false,
  profile_visibility: "public", show_activity: true, interface_theme: "light",
  locale: "zh-CN", created_at: NOW,
};
const PROFILE: UserProfile = {
  ...USER, is_persona: false, persona_kind: null, can_edit: true,
  topic_count: 2, post_count: 3, following_count: 0, follower_count: 0, badges: [],
};
const TOPIC: TopicResponse = {
  id: "201", slug: "account-layout", title: "Codex 内置浏览器秒退、无法启动：Windows 11 排查记录",
  board_id: "10", board_slug: "lounge", board_name: "闲聊", board_color: "#409EFF",
  board_visibility: "public", author_id: USER.id, author_name: USER.username,
  author_avatar_url: null, author_role: USER.role, author_is_persona: false,
  author_persona_kind: null, author_level: 3, author_trust_level: 1,
  author_trust_level_label: "基础成员", tags: ["浏览器"], accepted_answer_post_id: null,
  solved_at: null, solved_by_id: null, answer_mode: false, vote_score: 0, vote_count: 0,
  my_vote: 0, poll: null, topic_type: "regular", visibility: "public", status: "open",
  pinned: false, featured: false, view_count: 10, reply_count: 3, like_count: 0, hot_score: 1,
  last_posted_at: NOW, created_at: NOW, updated_at: NOW, merged_into_topic_id: null,
  share_url: "/topics/201/account-layout",
  excerpt: "这是一段本地验证摘要，用于检查长标题、正文和操作菜单是否仍有足够空间，不连接真实论坛或浏览器服务。",
};

/** 拦截本地页面全部接口；auth 标记只控制模拟登录，任何站外请求和未知接口都会记录为失败。 */
async function fixture(page: Page, authenticated = true) {
  const state = {
    authenticated, logoutFails: false, profileFails: false, meFails: false,
    logoutCalls: 0, unexpected: [] as string[], errors: [] as string[],
  };
  await page.addInitScript((loggedIn) => {
    localStorage.setItem("parallellines.locale", "zh-CN");
    if (loggedIn) localStorage.setItem("parallellines.access_token", "fixture-only-not-a-real-token");
  }, authenticated);
  page.on("pageerror", error => state.errors.push(error.message));
  const origin = new URL(process.env.PLAYWRIGHT_BASE_URL ?? "http://127.0.0.1:5173").origin;
  await page.route("**/*", async route => {
    const request = route.request();
    const url = new URL(request.url());
    if (url.origin !== origin) {
      state.unexpected.push(`External: ${url.origin}${url.pathname}`);
      return route.abort();
    }
    if (!url.pathname.startsWith("/api/")) return route.continue();
    const path = decodeURIComponent(url.pathname.replace(/^\/api\/v1/, ""));
    const send = (data: unknown) => route.fulfill({ json: { data } });
    const fail = (status: number, code: string) => route.fulfill({
      status, json: { error: { code, message: "本地模拟接口失败" } },
    });
    if (path === "/site/settings") return send({ settings: { site_title: "平行线", site_tagline: "本地回归验证" }, updated_at: null });
    if (path === "/site/extensions" || path === "/tags") return send([]);
    if (path === "/site/visits") return send({ recorded: false });
    if (path === "/auth/oauth/providers") return send({ providers: [] });
    if (path === "/auth/me") {
      if (state.meFails) return fail(503, "service_unavailable");
      return state.authenticated ? send(USER) : fail(401, "unauthorized");
    }
    if (path === "/auth/logout" && request.method() === "POST") {
      state.logoutCalls += 1;
      if (state.logoutFails) return fail(503, "service_unavailable");
      state.authenticated = false;
      return send({ logged_out: true });
    }
    if (path === "/auth/fablespace/access") return send({ access_allowed: false, capabilities: [], access_level: null, expires_at: null, authorization_version: 0 });
    if (path === "/notifications") return send({ notifications: [], unread_count: 0 });
    if (path === "/notifications/stream") return route.fulfill({ status: 204, body: "" });
    if (path === "/boards") return send([]);
    if (path === "/users/account_fixture" || path === "/users/id/101") {
      return state.profileFails ? fail(503, "service_unavailable") : send({ ...PROFILE, can_edit: state.authenticated });
    }
    if (path === "/users/account_fixture/topics") return send([
      TOPIC,
      { ...TOPIC, id: "202", slug: "long-title", title: "连续字符标题_ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_检查换行且不挤占正文", share_url: "/topics/202/long-title" },
    ]);
    if (path === "/users/account_fixture/activity") return send([]);
    if (path === "/users/account_fixture/relationship") return send({
      target_user_id: USER.id, target_username: USER.username,
      following: false, ignored: false, blocked: false, followed_by: false,
    });
    state.unexpected.push(`${request.method()} ${path}`);
    return fail(501, "unmocked_api");
  });
  return state;
}

/** 通过真实账号菜单退出，不直接改缓存或伪造注销完成状态。 */
async function logout(page: Page) {
  await page.locator(".account-menu__summary").click();
  await page.getByRole("button", { name: "退出", exact: true }).click();
}

test("个人主题在侧栏断点和手机中保留正文宽度", async ({ page }, testInfo) => {
  const state = await fixture(page);
  await page.goto("/account");
  await expect(page.locator(".topic-row--profile")).toHaveCount(2);
  for (const width of [1440, 1080, 1024, 921, 920, 861, 860, 721, 720, 390, 320]) {
    await page.setViewportSize({ width, height: 900 });
    const dimensions = await page.locator(".topic-row--profile").evaluateAll(rows => rows.map(row => {
      const main = row.querySelector(".topic-main")!.getBoundingClientRect();
      const bounds = row.getBoundingClientRect();
      const title = row.querySelector(".topic-title")!.getBoundingClientRect();
      const menu = row.querySelector(".topic-admin-actions")!.getBoundingClientRect();
      return {
        main: main.width, row: bounds.width, titleRight: title.right, menuLeft: menu.left,
        overflow: row.scrollWidth > row.clientWidth + 1,
        pageOverflow: document.documentElement.scrollWidth > innerWidth + 1,
      };
    }));
    for (const dimension of dimensions) {
      expect(dimension.main, `正文宽度 ${width}px`).toBeGreaterThan(dimension.row * 0.5);
      expect(dimension.titleRight, `标题避让菜单 ${width}px`).toBeLessThanOrEqual(dimension.menuLeft + 1);
      expect(dimension.overflow, `卡片溢出 ${width}px`).toBe(false);
      expect(dimension.pageOverflow, `页面溢出 ${width}px`).toBe(false);
    }
    const sidebar = await page.locator(".profile-sidebar").evaluate(aside => ({
      width: aside.getBoundingClientRect().width,
      cardWidth: aside.querySelector(".profile-side-card")!.getBoundingClientRect().width,
    }));
    expect(sidebar.cardWidth, `侧栏卡片填满容器 ${width}px`).toBeCloseTo(sidebar.width, 0);
    if ([1440, 1024, 721, 390, 320].includes(width)) {
      await page.evaluate(() => window.scrollTo(0, 0));
      await page.screenshot({ path: testInfo.outputPath(`account-${width}.png`), fullPage: true });
      // 把卡片放在固定顶栏与底栏之间，避免截图把固定导航误拍成正文遮挡。
      await page.locator(".topic-row--profile").first().evaluate(row => {
        window.scrollTo(0, window.scrollY + row.getBoundingClientRect().top - 110);
      });
      await page.locator(".topic-row--profile").first().screenshot({ path: testInfo.outputPath(`topic-${width}.png`) });
    }
  }
  await page.setViewportSize({ width: 1024, height: 900 });
  await page.locator(".topic-overflow-menu summary").first().click();
  await expect(page.getByRole("button", { name: `删除主题：${TOPIC.title}`, exact: true })).toBeVisible();
  expect(state.unexpected).toEqual([]);
  expect(state.errors).toEqual([]);
});

for (const path of ["/account", "/account/profile", "/account/settings"]) {
  test(`${path} 退出成功后转登录并保留完整回跳地址`, async ({ page }, testInfo) => {
    const state = await fixture(page);
    const target = `${path}?source=regression#section`;
    await page.goto(target);
    await expect(page.locator(".profile-copy h1")).toHaveText(USER.display_name!);
    await logout(page);
    await expect(page).toHaveURL(url => url.pathname === "/auth" && url.searchParams.get("redirect") === target);
    await expect(page.getByRole("form", { name: "登录表单" })).toBeVisible();
    await expect(page.getByText("正在加载用户资料…", { exact: true })).toHaveCount(0);
    expect(await page.evaluate(() => localStorage.getItem("parallellines.access_token"))).toBeNull();
    expect(state.logoutCalls).toBe(1);
    expect(state.unexpected).toEqual([]);
    expect(state.errors).toEqual([]);
    if (path === "/account") await page.screenshot({ path: testInfo.outputPath("logged-out.png"), fullPage: true });
  });
}

test("公开成员页退出后保持原地址并恢复匿名访问", async ({ page }) => {
  const state = await fixture(page);
  await page.goto("/members/101");
  await expect(page.getByRole("link", { name: "编辑资料", exact: true })).toBeVisible();
  await logout(page);
  await expect(page).toHaveURL(/\/members\/101$/);
  await expect(page.locator(".profile-copy h1")).toHaveText(USER.display_name!);
  await expect(page.getByRole("link", { name: "编辑资料", exact: true })).toHaveCount(0);
  await expect(page.locator(".topic-row--profile")).toHaveCount(2);
  await expect(page.getByText("正在加载用户资料…", { exact: true })).toHaveCount(0);
  expect(state.logoutCalls).toBe(1);
  expect(state.unexpected).toEqual([]);
  expect(state.errors).toEqual([]);
});

test("远端退出失败时保留页面、登录凭据并提示失败", async ({ page }) => {
  const state = await fixture(page);
  state.logoutFails = true;
  await page.goto("/account");
  await expect(page.locator(".profile-copy h1")).toHaveText(USER.display_name!);
  await logout(page);
  await expect(page.getByText("远端未注销，当前会话尚未确认失效。请检查网络后重试。", { exact: true })).toBeVisible();
  await expect(page).toHaveURL(/\/account$/);
  await expect(page.locator(".profile-copy h1")).toHaveText(USER.display_name!);
  expect(await page.evaluate(() => localStorage.getItem("parallellines.access_token"))).toBe("fixture-only-not-a-real-token");
  expect(state.logoutCalls).toBe(1);
  expect(state.unexpected).toEqual([]);
  expect(state.errors).toEqual([]);
});

test("资料接口失败显示错误，匿名公开资料仍可加载", async ({ page }) => {
  const state = await fixture(page, false);
  state.profileFails = true;
  await page.goto("/members/101");
  await expect(page.locator(".profile-state--error")).toBeVisible();
  await expect(page.getByText("正在加载用户资料…", { exact: true })).toHaveCount(0);
  state.profileFails = false;
  await page.reload();
  await expect(page.locator(".profile-copy h1")).toHaveText(USER.display_name!);
  await expect(page.locator(".topic-row--profile")).toHaveCount(2);
  expect(state.unexpected).toEqual([]);
  expect(state.errors).toEqual([]);
});

test("匿名直接访问个人中心由既有路由守卫转登录", async ({ page }) => {
  const state = await fixture(page, false);
  await page.goto("/account");
  await expect(page).toHaveURL(url => url.pathname === "/auth" && url.searchParams.get("redirect") === "/account");
  await expect(page.getByRole("form", { name: "登录表单" })).toBeVisible();
  expect(state.unexpected).toEqual([]);
  expect(state.errors).toEqual([]);
});

for (const failure of ["error", "anonymous"] as const) {
  test(`个人中心刷新当前会话后展示${failure === "error" ? "错误" : "登录入口"}，不陷入加载`, async ({ page }) => {
    const state = await fixture(page);
    await page.clock.setFixedTime(new Date(NOW));
    await page.goto("/account");
    await expect(page.locator(".profile-copy h1")).toHaveText(USER.display_name!);
    state.meFails = failure === "error";
    state.authenticated = failure !== "anonymous";
    // 让既有账号缓存过期，经浏览器断网恢复事件触发真实查询，而非直接改 Vue Query 状态。
    await page.clock.setFixedTime(new Date(new Date(NOW).getTime() + 6 * 60_000));
    await page.evaluate(() => window.dispatchEvent(new Event("offline")));
    const refresh = page.waitForResponse(response => response.url().endsWith("/auth/me"));
    await page.evaluate(() => window.dispatchEvent(new Event("online")));
    await refresh;
    if (failure === "error") {
      await expect(page.locator(".profile-state--error")).toBeVisible();
    } else {
      await expect(page.getByText("请先登录后查看个人中心。", { exact: false })).toBeVisible();
      const login = page.locator(".profile-state").getByRole("link", { name: "登录/注册", exact: true });
      await expect(login).toHaveAttribute("href", "/auth?redirect=/account");
      await login.click();
      await expect(page.getByRole("form", { name: "登录表单" })).toBeVisible();
    }
    await expect(page.getByText("正在加载用户资料…", { exact: true })).toHaveCount(0);
    expect(state.unexpected).toEqual([]);
    expect(state.errors).toEqual([]);
  });
}

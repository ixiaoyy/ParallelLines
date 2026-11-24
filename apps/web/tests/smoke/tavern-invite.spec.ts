import { expect, test, type BrowserContext } from "@playwright/test";

const FLOW = "a".repeat(21) + "A";
const LEGACY_BEARER = "b".repeat(42) + "A";
const INVITE = "/tavern/invite";
const TAVERN = "https://tavern.pingxingxian.space";
const STORAGE_KEY = "parallellines.tavern-invite-flow.v1";
const SUBJECT = "9007199254740993";
const EPOCH = "a".repeat(32);
const USER = {
  id: SUBJECT, username: SUBJECT, email: "invite@example.test", avatar_url: null, display_name: null,
  bio: null, website_url: null, location: null, role: "user", level: 1, trust_level: 0,
  trust_level_label: "新用户", points_balance: 0, experience_total: 0, experience_to_next_level: 100,
  level_progress_percent: 0, status: "active", two_factor_enabled: false, profile_visibility: "public",
  show_activity: true, interface_theme: "system", locale: "zh-CN", created_at: "2026-11-18T00:00:00Z",
};
test.use({ locale: "zh-CN" });

/** 只向隔离前端提供主站真实形状的会话、注册与验证码响应，外部导航全部拦截。 */
async function fixture(context: BrowserContext, origin: string, state: { signedIn: boolean; unavailable?: boolean; currentId?: string }) {
  await context.addInitScript(() => { Object.defineProperty(navigator, "webdriver", { get: () => false }); });
  const requests: Array<{ url: string; referer?: string; body: string | null }> = [];
  await context.route("**/*", async (route) => {
    const request = route.request();
    requests.push({ url: request.url(), referer: request.headers().referer, body: request.postData() });
    const url = new URL(request.url());
    if (url.origin === TAVERN) return route.fulfill({ contentType: "text/html", body: "<main>Element fixture</main>" });
    if (url.origin !== origin) return route.abort();
    if (!url.pathname.startsWith("/api/v1/")) return route.continue();
    const reply = (data: unknown) => route.fulfill({ json: { data } });
    const status = { authenticated: state.signedIn, subject: state.signedIn ? SUBJECT : null, auth_epoch: state.signedIn ? EPOCH : null };
    switch (url.pathname.slice("/api/v1".length)) {
      case "/auth/unified/state":
        return state.unavailable ? route.fulfill({ status: 503, json: { error: { code: "unavailable" } } }) : reply(status);
      case "/auth/unified/bootstrap":
        if (state.signedIn) return reply({
          ...status, access_token: "fixture.access", token_type: "bearer", expires_in: 300, session_id: "fixture-session", user: USER,
        });
        break;
      case "/auth/me":
        if (state.signedIn) return reply({ ...USER, id: state.currentId ?? USER.id });
        return route.fulfill({ status: 401, json: { error: { code: "invalid_token" } } });
      case "/auth/oauth/providers":
        return reply({ providers: [] });
      case "/auth/register":
        return reply({ email: USER.email, expires_in: 600 });
      case "/auth/verify-email":
        state.signedIn = true;
        return reply({ access_token: "fixture.access", refresh_token: "fixture.refresh", token_type: "bearer" });
      case "/site/visits":
        return reply({});
    }
    return route.fulfill({ status: 404, json: { error: { code: "fixture_unhandled" } } });
  });
  return requests;
}

test("新用户只在主站注册和验证，完成后才按固定片段进入酒馆", async ({ context, page, baseURL }) => {
  const origin = new URL(baseURL!).origin;
  const state = { signedIn: false };
  const requests = await fixture(context, origin, state);
  await page.goto(INVITE + "#" + FLOW);
  await expect(page).toHaveURL(origin + "/auth?redirect=/tavern/invite");
  expect(await page.evaluate(key => sessionStorage.getItem(key), STORAGE_KEY)).toBe(FLOW);
  expect(requests.some(({ url }) => url.startsWith(TAVERN))).toBe(false);
  const separateTab = await context.newPage();
  await separateTab.goto(INVITE);
  await expect(separateTab.getByRole("alert")).toContainText("没有有效邀请");
  await separateTab.close();

  await page.goto("/auth?mode=register&redirect=/tavern/invite");
  const form = page.getByRole("form", { name: "注册表单" });
  await form.getByPlaceholder("用户名", { exact: true }).fill("invite-fixture");
  await form.getByPlaceholder("邮箱", { exact: true }).fill(USER.email);
  await form.getByPlaceholder("至少 8 位密码").fill("fixture-password");
  await form.getByPlaceholder("再次输入密码").fill("fixture-password");
  await form.getByRole("button", { name: /^注\s*册$/ }).click();
  await expect(page.getByRole("form", { name: "验证码激活表单" })).toBeVisible();
  expect(requests.some(({ url }) => url.startsWith(TAVERN))).toBe(false);
  await page.getByPlaceholder("6 位验证码").fill("123456");
  await page.getByRole("button", { name: "激活账号" }).click();
  await expect(page).toHaveURL(TAVERN + "/#/tavern-invite-return/" + FLOW + "/" + SUBJECT);
  expect(requests.filter(({ url }) => url.startsWith(origin)).every(({ url, referer, body }) =>
    ![url, referer, body].some(value => value?.includes(FLOW)))).toBe(true);
});

test("主站暂不可用时保留邀请，恢复后免输密码并清标签存储", async ({ context, page, baseURL }) => {
  const origin = new URL(baseURL!).origin;
  const state = { signedIn: true, unavailable: true };
  const requests = await fixture(context, origin, state);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(INVITE + "#" + FLOW);
  await expect(page.getByRole("alert")).toContainText("暂时无法确认主站登录");
  await expect(page).toHaveURL(origin + INVITE);
  await expect(page.locator('input[type="password"]')).toHaveCount(0);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  expect(await page.evaluate(key => sessionStorage.getItem(key), STORAGE_KEY)).toBe(FLOW);
  expect(requests.some(({ url }) => url.startsWith(TAVERN))).toBe(false);
  await page.screenshot({ path: "test-results/tavern-invite-retry-mobile.png" });
  state.unavailable = false;
  const retry = page.getByRole("button", { name: /重\s*试/ });
  await retry.focus();
  await retry.press("Enter");
  await expect(page).toHaveURL(TAVERN + "/#/tavern-invite-return/" + FLOW + "/" + SUBJECT);
  await page.goto(INVITE);
  await expect(page.getByRole("alert")).toContainText("没有有效邀请");
});

test("无效的新片段清旧邀请，查询参数不会被当成邀请", async ({ context, page, baseURL }) => {
  const origin = new URL(baseURL!).origin;
  const requests = await fixture(context, origin, { signedIn: true });
  await page.addInitScript(({ key, token }) => window.sessionStorage.setItem(key, token), { key: STORAGE_KEY, token: FLOW });
  await page.goto(INVITE + "#" + LEGACY_BEARER);
  await expect(page.getByRole("alert")).toContainText("没有有效邀请");
  await expect(page).toHaveURL(origin + INVITE);
  expect(await page.evaluate(key => sessionStorage.getItem(key), STORAGE_KEY)).toBeNull();
  const isolated = await context.newPage();
  await isolated.goto(INVITE + "?flow=" + FLOW);
  await expect(isolated.getByRole("alert")).toContainText("没有有效邀请");
  await expect(isolated).toHaveURL(origin + INVITE);
  await isolated.getByRole("link", { name: "返回游戏" }).click();
  await expect.poll(() => requests.filter(({ url }) => url.endsWith("/site/visits")).map(({ body }) => body)).toHaveLength(1);
  expect(requests.find(({ url }) => url.endsWith("/site/visits"))?.body).not.toContain(INVITE);
});

test("只信任实时主站身份；换号中的不一致阻止交接", async ({ context, page, baseURL }) => {
  const origin = new URL(baseURL!).origin;
  const requests = await fixture(context, origin, { signedIn: true, currentId: "9007199254740994" });
  await page.goto(INVITE + "?subject=123#" + FLOW);
  await expect(page.getByRole("alert")).toContainText("暂时无法确认主站登录");
  await expect(page).toHaveURL(origin + INVITE);
  expect(requests.some(({ url }) => url.startsWith(TAVERN))).toBe(false);
  expect(await page.evaluate(key => sessionStorage.getItem(key), STORAGE_KEY)).toBe(FLOW);
  expect(requests.some(({ url }) => url.endsWith("/auth/me"))).toBe(true);
});

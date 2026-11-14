import { expect, test, type BrowserContext, type Page, type Route } from "@playwright/test";

const MAIN = "http://127.0.0.1:4183";
const CIRCLE = "http://127.0.0.1:4184";
const fixture = "/tests/smoke/unified-fixture.html";
type Control = { subject: string | null; outage: boolean; exchanges: number; credentials: number; privateRoute?: Route; privateUnauthorized?: boolean; holdExchange?: boolean; pendingExchange?: Route };

function user(id: string) {
  return { id, username: id, email: id + "@example.test", avatar_url: null, display_name: null, bio: null, website_url: null, location: null,
    role: "user", level: 1, trust_level: 0, trust_level_label: "新用户", points_balance: 0, experience_total: 0, experience_to_next_level: 100,
    level_progress_percent: 0, status: "active", two_factor_enabled: false, profile_visibility: "public", show_activity: true,
    interface_theme: "system", locale: "zh-CN", created_at: "2026-11-15T00:00:00Z" };
}
function access(subject: string) {
  return { authenticated: true, subject, auth_epoch: subject.repeat(32), access_token: subject + ".token", token_type: "bearer", expires_in: 300,
    session_id: subject + "-sid", user: user(subject) };
}
async function intercept(context: BrowserContext, control: Control) {
  await context.route("**/*", async route => {
    const url = new URL(route.request().url());
    if (![MAIN, CIRCLE].includes(url.origin)) return route.abort();
    if (!url.pathname.startsWith("/api/")) return route.continue();
    const payload = route.request().postDataJSON();
    const reply = (data: unknown) => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ data }) });
    if (url.pathname === "/api/v1/auth/unified/state") {
      if (control.outage) return route.fulfill({ status: 503, contentType: "application/json", body: '{"error":{"code":"unavailable"}}' });
      return reply(control.subject ? { authenticated: true, subject: control.subject, auth_epoch: control.subject.repeat(32) } : { authenticated: false, subject: null, auth_epoch: null });
    }
    if (url.pathname === "/api/v1/auth/unified/bootstrap" && control.subject) return reply(access(control.subject));
    if (url.pathname === "/api/v1/auth/unified/authorize" && control.subject) {
      const callback = new URL(payload.redirect_uri);
      callback.search = new URLSearchParams({ state: payload.state, code: control.subject.repeat(64) }).toString();
      return reply({ redirect_url: callback.href });
    }
    if (url.pathname === "/api/v1/auth/unified/exchange" && control.subject) {
      control.exchanges += 1;
      expect(url.origin).toBe(CIRCLE); expect(payload.code_verifier).toMatch(/^[A-Za-z0-9_-]{43}$/);
      if (control.holdExchange) { control.pendingExchange = route; control.holdExchange = false; return; }
      return reply(access(control.subject));
    }
    if (url.pathname === "/api/v1/private-test") {
      if (control.privateUnauthorized) return route.fulfill({ status: 401, contentType: "application/json", body: '{"error":{"code":"invalid_token"}}' });
      control.privateRoute = route; return;
    }
    if (/\/auth\/(login|register|refresh)$/.test(url.pathname)) control.credentials += 1;
    return route.fulfill({ status: 404, contentType: "application/json", body: '{"error":{"code":"fixture_unhandled"}}' });
  });
}
async function snapshot(page: Page): Promise<Record<string, unknown>> {
  return page.evaluate(() => (window as unknown as { unifiedTest: { snapshot(): Record<string, unknown> } }).unifiedTest.snapshot());
}
async function start(page: Page) {
  await page.goto(CIRCLE + fixture);
  await page.waitForFunction(() => !!(window as unknown as { unifiedTest: unknown }).unifiedTest);
  await page.evaluate(() => (window as unknown as { unifiedTest: { start(): void } }).unifiedTest.start());
}
async function signalMain(page: Page) {
  const frame = page.frames().find(item => item.url().startsWith(MAIN + "/auth/unified/state"));
  expect(frame).toBeTruthy();
  await frame!.evaluate(() => window.dispatchEvent(new Event("pl:unified-auth-change")));
}

test("游客保持公开入口，不触发凭据登录或兑换", async ({ context, page }) => {
  const control: Control = { subject: null, outage: false, exchanges: 0, credentials: 0 }; await intercept(context, control);
  await start(page);
  await expect.poll(async () => (await snapshot(page)).availability).toBe("anonymous");
  expect(page.url()).toBe(CIRCLE + fixture); expect(control.exchanges).toBe(0); expect(control.credentials).toBe(0);
  await expect(page.locator('input[type="password"]')).toHaveCount(0);
});

test("主站已登录无密码进入圈子；换号隔离迟到响应；故障与退出分开", async ({ context, page }) => {
  const control: Control = { subject: "A", outage: false, exchanges: 0, credentials: 0 }; await intercept(context, control);
  await start(page);
  await expect.poll(async () => (await snapshot(page)).subject).toBe("A");
  expect((await snapshot(page)).refresh).toBeNull(); expect(control.credentials).toBe(0); expect(control.exchanges).toBe(1);
  const delayed = page.evaluate(() => (window as unknown as { unifiedTest: { privateRequest(): Promise<string> } }).unifiedTest.privateRequest());
  await expect.poll(() => !!control.privateRoute).toBe(true);
  control.subject = "B"; await signalMain(page);
  await expect.poll(async () => (await snapshot(page)).subject).toBe("B");
  expect((await snapshot(page)).user).toMatchObject({ id: "B" });
  await control.privateRoute!.fulfill({ status: 200, contentType: "application/json", body: '{"data":{"owner":"A"}}' });
  expect(await delayed).toBe("identity_changed");
  control.outage = true; await signalMain(page);
  await expect.poll(async () => (await snapshot(page)).availability).toBe("unavailable");
  expect((await snapshot(page)).subject).toBe("B");
  control.outage = false; control.subject = null; await signalMain(page);
  await expect.poll(async () => (await snapshot(page)).availability).toBe("anonymous");
  expect((await snapshot(page)).token).toBeNull(); expect((await snapshot(page)).user).toBeNull();
});

test("失效登录链接只显示必要错误与重试，移动端无解释墙", async ({ context, page }) => {
  await intercept(context, { subject: null, outage: false, exchanges: 0, credentials: 0 });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(MAIN + "/auth/unified?state=bad");
  await expect(page.getByRole("heading", { name: "登录", exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: /重\s*试/ })).toBeVisible();
  await expect(page.locator('input[type="password"]')).toHaveCount(0);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: "test-results/unified-login-mobile.png" });
});

test("A兑换在途时主站换成B，B不复用迟到的A兑换", async ({ context, page }) => {
  const control: Control = { subject: "A", outage: false, exchanges: 0, credentials: 0, holdExchange: true };
  await intercept(context, control); await start(page);
  await expect.poll(() => !!control.pendingExchange).toBe(true);
  control.subject = "B"; await signalMain(page);
  // 确认B状态已进入父页，再送达早先A的成功响应。
  await expect.poll(async () => (await snapshot(page)).mainStatusSubject).toBe("B");
  await control.pendingExchange!.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ data: access("A") }) });
  await expect.poll(async () => (await snapshot(page)).subject).toBe("B");
  expect((await snapshot(page)).user).toMatchObject({ id: "B" }); expect(control.exchanges).toBe(2);
});

test("同页401续发遇故障保留身份，确认主站过期则清旧身份", async ({ context, page }) => {
  const control: Control = { subject: "A", outage: false, exchanges: 0, credentials: 0, privateUnauthorized: true };
  await intercept(context, control); await start(page);
  await expect.poll(async () => (await snapshot(page)).subject).toBe("A");
  control.outage = true;
  const request = () => page.evaluate(() => (window as unknown as { unifiedTest: { privateRequest(): Promise<string> } }).unifiedTest.privateRequest());
  expect(await request()).toBe("unified_auth_unavailable");
  expect((await snapshot(page)).availability).toBe("unavailable"); expect((await snapshot(page)).subject).toBe("A");
  control.outage = false; control.subject = null;
  expect(await request()).toBe("identity_changed");
  expect((await snapshot(page)).availability).toBe("anonymous"); expect((await snapshot(page)).user).toBeNull();
});

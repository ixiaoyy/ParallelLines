import { expect, test, type BrowserContext, type Page } from "@playwright/test";
import { fixture, USER } from "./fixtures/forum";

test.use({ serviceWorkers: "block", locale: "zh-CN" });

const tokenKey = "parallellines.access_token";
const deskPreview = "http://127.0.0.1:15223";
type Snapshot = { revision: string; config: { global?: { background?: string } } | null };

/** 模拟同源网关和云配置响应；浏览器仍运行真实的主站登录页及工作台。 */
async function connect(page: Page, origin: string, state: { snapshot: Snapshot; puts: string[]; reads: string[] }) {
  await fixture(page);
  await page.route("**/*", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    if (url.origin !== origin) return route.abort();
    if (url.pathname.startsWith("/desk/")) {
      const response = await route.fetch({ url: deskPreview + url.pathname + url.search });
      try {
        return await route.fulfill({ response });
      } finally {
        await response.dispose();
      }
    }
    const account = request.headers().authorization;
    if (url.pathname === "/api/v1/auth/me" && account === "Bearer second-account") {
      return route.fulfill({ json: { data: { ...USER, id: "900", username: "fixture-second" } } });
    }
    if (url.pathname !== "/api/v1/workspace/config") return route.fallback();
    if (request.method() === "PUT") {
      const { config, expected_revision } = request.postDataJSON();
      state.puts.push(account + ":" + expected_revision);
      if (expected_revision !== state.snapshot.revision) {
        return route.fulfill({
          status: 409,
          json: { error: { code: "workspace_revision_conflict", details: { current_revision: state.snapshot.revision } } },
        });
      }
      state.snapshot = { revision: String(Number(expected_revision) + 1), config };
      return route.fulfill({ status: expected_revision === "0" ? 201 : 200, json: { data: state.snapshot } });
    }
    state.reads.push(account ?? "");
    return route.fulfill({ json: { data: state.snapshot } });
  });
}

test.afterEach(async ({ page }) => page.unrouteAll({ behavior: "wait" }));

async function logIn(page: Page) {
  const form = page.getByRole("form", { name: "登录表单" });
  await form.getByRole("textbox", { name: "用户名 / 邮箱 / 手机号", exact: true }).fill(USER.username);
  await form.getByPlaceholder("请输入密码").fill("fixture-password");
  await form.getByRole("button", { name: /^登\s*录$/ }).click();
}

/** 在独立标签页更新同源的主站凭据，让工作台收到浏览器自己的 storage 事件。 */
async function changeSession(context: BrowserContext, origin: string, token: string) {
  const authTab = await context.newPage();
  await authTab.route(origin + "/fixture-auth", route => route.fulfill({ body: "<!doctype html>" }));
  await authTab.goto(origin + "/fixture-auth");
  await authTab.evaluate(([key, value]) => localStorage.setItem(key, value), [tokenKey, token]);
  await authTab.close();
}

test("工作台经主站登录回跳，首传须确认，两台设备的冲突保留本地编辑", async ({ page, browser, baseURL }, testInfo) => {
  const origin = new URL(baseURL!).origin;
  const state = { snapshot: { revision: "0", config: null } as Snapshot, puts: [] as string[], reads: [] as string[] };
  await connect(page, origin, state);
  await page.goto("/desk/");
  await page.locator(".sync-pill").click();
  await page.getByRole("link", { name: "前往主站登录" }).click();
  await expect(page).toHaveURL(/\/auth\?redirect=\/desk\/$/);
  await logIn(page);
  await expect(page).toHaveURL(/\/desk\/$/);
  await expect(page.locator(".sync-pill")).toContainText("待首次同步");
  expect(state.puts).toEqual([]);
  await page.locator(".sync-pill").click();
  await page.getByRole("button", { name: "确认上传当前本地布局到云端" }).click();
  await expect(page.locator(".sync-pill")).toContainText("已同步 v1");
  expect(state.puts).toEqual(["Bearer fixture-only:0"]);

  const device = await browser.newContext();
  try {
    await changeSession(device, origin, "fixture-only");
    const other = await device.newPage();
    await connect(other, origin, state);
    await other.goto(origin + "/desk/");
    await expect(other.locator(".sync-pill")).toContainText("已同步 v1");

    await page.getByRole("button", { name: /主题$/ }).click();
    await page.locator(".theme-swatch").nth(1).click();
    await expect(page.locator(".sync-pill")).toContainText("已同步 v2");

    await other.getByRole("button", { name: /主题$/ }).click();
    await other.locator(".theme-swatch").nth(2).click();
    const draft = await other.evaluate(() => localStorage.getItem("global"));
    await expect(other.locator(".sync-pill")).toContainText("云端冲突");
    expect(await other.evaluate(() => localStorage.getItem("global"))).toBe(draft);
    expect(state.puts).toEqual(["Bearer fixture-only:0", "Bearer fixture-only:1", "Bearer fixture-only:1"]);
    expect(state.snapshot.revision).toBe("2");

    await other.locator(".sync-pill").click();
    await expect(other.getByText(/本地基准版本 v1/)).toBeVisible();
    await expect(other.getByRole("button", { name: "采用云端最新版本（v2）" })).toBeVisible();
    await other.screenshot({ path: testInfo.outputPath("conflict.png"), animations: "disabled" });
    await other.getByRole("button", { name: "采用云端最新版本（v2）" }).click();
    await expect(other.locator(".sync-pill")).toContainText("已同步 v2");
    expect(await other.evaluate(() => localStorage.getItem("global"))).not.toBe(draft);
    await other.unrouteAll({ behavior: "wait" });
  } finally {
    await device.close();
  }
});

test("换号取消待同步，刷新后仍保留布局且不对新账号加载或写入", async ({ page, context, baseURL }, testInfo) => {
  const origin = new URL(baseURL!).origin;
  const state = { snapshot: { revision: "0", config: null } as Snapshot, puts: [] as string[], reads: [] as string[] };
  await changeSession(context, origin, "fixture-only");
  await connect(page, origin, state);
  await page.clock.install();
  await page.goto("/desk/");
  await expect(page.locator(".sync-pill")).toContainText("待首次同步");
  await page.locator(".sync-pill").click();
  await page.getByRole("button", { name: "确认上传当前本地布局到云端" }).click();
  await expect(page.locator(".sync-pill")).toContainText("已同步 v1");
  await page.getByRole("button", { name: /主题$/ }).click();
  await page.locator(".theme-swatch").nth(1).click();
  await expect(page.locator(".sync-pill")).toContainText("待保存");
  const draft = await page.evaluate(() => localStorage.getItem("global"));

  await changeSession(context, origin, "second-account");
  await expect(page.locator(".sync-pill")).toContainText("本地模式");
  await page.clock.fastForward(2000);
  expect(state.puts).toEqual(["Bearer fixture-only:0"]);
  await page.reload();
  await expect(page.locator(".sync-pill")).toHaveClass(/sync-account_changed/);
  expect(await page.evaluate(() => localStorage.getItem("global"))).toBe(draft);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.locator(".sync-pill").click();
  await expect(page.getByText(/此浏览器的布局已绑定另一账号/)).toBeVisible();
  await expect(page.getByRole("button", { name: /同步到云端/ })).toHaveCount(0);
  await page.screenshot({ path: testInfo.outputPath("account-changed.png"), animations: "disabled" });
  await changeSession(context, origin, "fixture-only");
  await expect(page.locator(".sync-pill")).toContainText("待保存");
  expect(await page.evaluate(() => localStorage.getItem("global"))).toBe(draft);
  expect(state.puts).toEqual(["Bearer fixture-only:0"]);
  expect(state.reads).not.toContain("Bearer second-account");
});

test("原有主站登录仍通过前端路由返回发帖页", async ({ page }) => {
  const state = await fixture(page);
  await page.goto("/new-topic?board=lounge");
  await expect(page).toHaveURL(/\/auth\?redirect=/);
  await logIn(page);
  await expect(page).toHaveURL(/\/new-topic\?board=lounge$/);
  await expect(page.getByRole("textbox", { name: "标题", exact: true })).toBeVisible();
  expect(state.writes.map(write => write.path)).toEqual(["/auth/login"]);
});

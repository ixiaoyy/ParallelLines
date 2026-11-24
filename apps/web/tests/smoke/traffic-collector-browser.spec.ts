import { readFileSync } from "node:fs";
import { expect, test } from "@playwright/test";
import type { Browser, BrowserContext, Page, Route } from "@playwright/test";

// 真实 Chromium 的 Cookie/fetch/离页机制 + 全网络替身；不代替目标 CSP 或真实采集链路验收。

const COLLECTOR = readFileSync(new URL("../../public/traffic-collector.v1.js", import.meta.url), "utf8");
const ENDPOINT = "https://pingxingxian.space/api/v1/site/traffic";
const MAIN_SESSION = "fixture-only-http-only-main-session";
const NOW = new Date("2026-11-17T04:00:00Z");
const SITES: Record<string, string> = {
  "pingxingxian.space": "games",
  "tools.pingxingxian.space": "tools",
  "chat.pingxingxian.space": "chat",
  "api.pingxingxian.space": "api",
};

interface TrafficPayload {
  visitor_id: string;
  identity_scope: string;
  events: Array<{ event_id: string; site_key: string; event_name: string; path: string; referrer: string | null }>;
}

interface CapturedTraffic {
  headers: Record<string, string>;
  rawBody: string;
  payload: TrafficPayload;
}

declare global {
  interface Window {
    __fixtureTraffic: { aborts: number; errors: string[] };
  }
}

/** 仅为自有合成页面：所有请求先拦截，无 continue、真实服务、外部脚本或数据库。 */
async function isolatedBrowser(browser: Browser) {
  const context = await browser.newContext({ serviceWorkers: "block" });
  const pendingRoutes = new Set<Route>();
  const state = {
    requests: [] as CapturedTraffic[],
    blocked: [] as string[],
    errors: [] as string[],
    mainDocumentCookies: [] as string[],
    failedRequests: [] as string[],
    hang: false,
  };
  await context.addCookies([{
    name: "fixture_main_session",
    value: MAIN_SESSION,
    url: "https://pingxingxian.space/",
    httpOnly: true,
    secure: true,
    sameSite: "Lax",
  }]);
  await context.addInitScript(() => {
    // 此例只检查自有本地替身上的浏览器机制，不连接或绕过任何真实站点的检测。
    if (location.protocol !== "https:" || !["pingxingxian.space", "tools.pingxingxian.space", "chat.pingxingxian.space", "api.pingxingxian.space"].includes(location.hostname)) return;
    Object.defineProperty(navigator, "webdriver", { configurable: true, get: () => false });
    localStorage.setItem("parallellines.access_token", "fixture-only-private-access-token");
    window.__fixtureTraffic = { aborts: 0, errors: [] };
    const originalFetch = window.fetch.bind(window);
    window.fetch = (input, init) => {
      const traffic = input === "https://pingxingxian.space/api/v1/site/traffic";
      if (traffic) init?.signal?.addEventListener("abort", () => { window.__fixtureTraffic.aborts += 1; }, { once: true });
      const result = originalFetch(input, init);
      return traffic ? result.catch((error: Error) => {
        window.__fixtureTraffic.errors.push(error.name);
        throw error;
      }) : result;
    };
  });
  context.on("page", (page) => {
    page.on("pageerror", (error) => state.errors.push(error.message));
    page.on("requestfailed", (request) => {
      if (request.url() === ENDPOINT) state.failedRequests.push(request.failure()?.errorText ?? "unknown");
    });
  });
  await context.route("**/*", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    if (request.url() === ENDPOINT && request.method() === "POST") {
      const rawBody = request.postData() ?? "";
      state.requests.push({ headers: await request.allHeaders(), rawBody, payload: JSON.parse(rawBody) as TrafficPayload });
      // 不调用 continue：悬挂在浏览器网络替身，等待本页 AbortController 或 context.close 取消。
      if (state.hang) { pendingRoutes.add(route); return; }
      return route.fulfill({
        status: 202,
        contentType: "application/json",
        headers: { "Access-Control-Allow-Origin": request.headers().origin ?? url.origin, "Cache-Control": "no-store" },
        body: JSON.stringify({ data: { accepted: 1 } }),
      });
    }
    const site = SITES[url.hostname];
    if (url.protocol === "https:" && site && request.isNavigationRequest() && request.resourceType() === "document") {
      if (site === "games") state.mainDocumentCookies.push((await request.allHeaders()).cookie ?? "");
      const attr = site === "api" ? 'data-website-id="api"' : `data-site="${site}"`;
      return route.fulfill({
        contentType: "text/html;charset=UTF-8",
        body: `<!doctype html><html><head><meta charset="utf-8"><title>Local collector browser fixture</title>
          <script ${attr}>${COLLECTOR.replace(/<\/script/gi, "<\\/script")}</script></head><body>
          <button id="ordinary-button">普通按钮</button><output id="count">0</output>
          <a id="ordinary-navigation" href="/pdf/split?private-query=fixture-private#private-fragment">普通导航</a>
          <output id="route">initial</output>
          <script>
          document.getElementById('ordinary-button').addEventListener('click', function () {
            document.getElementById('count').textContent = String(Number(document.getElementById('count').textContent) + 1);
          });
          document.getElementById('ordinary-navigation').addEventListener('click', function (event) {
            event.preventDefault(); history.pushState({}, '', this.href);
            document.getElementById('route').textContent = location.pathname;
          });
          </script></body></html>`,
      });
    }
    state.blocked.push(request.url());
    return route.abort("blockedbyclient");
  });
  const close = async () => {
    // 浏览器可能已因 AbortController 取消本请求；清理只针对本 fixture 自己暂停的路由。
    await Promise.allSettled([...pendingRoutes].map(route => route.abort("aborted")));
    await context.close();
  };
  return { context, state, close };
}

/** 使用可控浏览器时钟，只加速统计等待；不伪造 document.cookie 或请求头行为。 */
async function openFixture(context: BrowserContext, url: string, referrer?: string): Promise<Page> {
  const page = await context.newPage();
  await page.clock.install({ time: NOW });
  await page.clock.pauseAt(NOW);
  await page.goto(url, { referer: referrer });
  await page.clock.runFor(2050);
  await expect.poll(async () => (await context.cookies()).find(cookie => cookie.name === "px_traffic_id")?.value).toMatch(/^[a-f0-9-]{36}$/);
  return page;
}

function assertAnonymousRequest(request: CapturedTraffic, origin: string) {
  expect(request.headers.cookie).toBeUndefined();
  expect(request.headers.authorization).toBeUndefined();
  expect(request.headers.origin).toBe(origin);
  expect(request.headers.referer).toBeUndefined();
  expect(request.headers["content-type"]).toBe("text/plain;charset=UTF-8");
  expect(request.rawBody).not.toMatch(/fixture-only|private-query|private-fragment|private-chat-id|private-user-id|filename|secret-token/);
}

test("真实 Chromium 跨正式子域共享匿名 Cookie，普通采集省略会话凭据并规范路径", async ({ browser }, testInfo) => {
  const { context, state, close } = await isolatedBrowser(browser);
  try {
    const identities: string[] = [];
    for (const [url, site, path] of [
      ["https://pingxingxian.space/games?private-query=fixture-private#private-fragment", "games", "/games"],
      ["https://tools.pingxingxian.space/pdf/merge?filename=fixture-private.pdf#private-fragment", "tools", "/pdf/merge"],
      ["https://chat.pingxingxian.space/c/private-chat-id?token=secret-token#private-fragment", "chat", "/c/:chat"],
      ["https://api.pingxingxian.space/console/private-user-id?token=secret-token#private-fragment", "api", "/console"],
    ]) {
      const before = state.requests.length;
      const page = await openFixture(context, url, "https://referrer.fixture.test/source?private-query=fixture-private");
      expect(await page.evaluate(() => document.cookie)).not.toContain(MAIN_SESSION);
      await page.clock.runFor(30000);
      await expect.poll(() => state.requests.length).toBe(before + 1);
      const request = state.requests[before];
      assertAnonymousRequest(request, new URL(url).origin);
      expect(request.payload.identity_scope).toBe("shared");
      expect(request.payload.events.map(event => ({ site: event.site_key, path: event.path }))).toEqual([{ site, path }]);
      expect(request.payload.events[0].referrer).toBe("https://referrer.fixture.test");
      identities.push(request.payload.visitor_id);
      await page.close();
    }
    const cookie = (await context.cookies()).find(value => value.name === "px_traffic_id");
    expect(cookie?.domain).toBe(".pingxingxian.space");
    expect(cookie?.secure).toBe(true);
    expect(cookie?.httpOnly).toBe(false);
    expect(new Set(identities).size).toBe(1);
    expect(identities[0]).toBe(cookie?.value);
    expect(state.mainDocumentCookies.some(value => value.includes(MAIN_SESSION))).toBe(true);
    expect(state.errors).toEqual([]);
    await testInfo.attach("collector-browser-mechanism", {
      contentType: "application/json",
      body: JSON.stringify({ interceptedRequests: state.requests.length, sharedCookieDomain: cookie?.domain, oneSharedIdentity: new Set(identities).size === 1, networkMode: "fulfill-or-abort-only" }),
    });
  } finally {
    await close();
  }
});

test("真实离页发送省略 Cookie 和 Authorization，导航不会重复发送同一个事件", async ({ browser }) => {
  const { context, state, close } = await isolatedBrowser(browser);
  try {
    const page = await openFixture(context, "https://chat.pingxingxian.space/c/private-chat-id?token=secret-token");
    expect(state.requests.length).toBe(0);
    // 真正换文档会触发浏览器的 visibility/pagehide；目标仍由同一兜底路由提供纯合成页面。
    await page.goto("https://chat.pingxingxian.space/admin/fixture-finished");
    await page.clock.runFor(2050);
    await expect.poll(() => state.requests.length).toBe(1);
    assertAnonymousRequest(state.requests[0], "https://chat.pingxingxian.space");
    expect(state.requests[0].payload.events.map(event => event.path)).toEqual(["/c/:chat"]);
    expect(new Set(state.requests.flatMap(request => request.payload.events.map(event => event.event_id))).size).toBe(1);
    expect(state.errors).toEqual([]);
  } finally {
    await close();
  }
});

test("统计请求悬挂不阻塞普通按钮与 SPA 导航，三秒中止后不重试", async ({ browser }) => {
  const { context, state, close } = await isolatedBrowser(browser);
  try {
    const page = await openFixture(context, "https://tools.pingxingxian.space/pdf/merge?filename=fixture-private.pdf");
    state.hang = true;
    // 在当前可控时刻提交已有队列，便于精确验证三秒上限；仍使用真实 Chromium fetch。
    await page.evaluate(() => window.dispatchEvent(new PageTransitionEvent("pagehide")));
    await expect.poll(() => state.requests.length).toBe(1);
    await page.getByRole("button", { name: "普通按钮", exact: true }).click({ force: true, timeout: 2000 });
    await expect(page.locator("#count")).toHaveText("1");
    await page.getByRole("link", { name: "普通导航", exact: true }).click({ force: true, timeout: 2000 });
    await expect(page.locator("#route")).toHaveText("/pdf/split");
    expect(new URL(page.url()).pathname).toBe("/pdf/split");
    expect(state.requests.length).toBe(1);
    await page.clock.runFor(2999);
    expect(await page.evaluate(() => window.__fixtureTraffic.aborts)).toBe(0);
    await page.clock.runFor(1);
    await expect.poll(() => page.evaluate(() => window.__fixtureTraffic.aborts)).toBe(1);
    await expect.poll(() => page.evaluate(() => window.__fixtureTraffic.errors)).toContain("AbortError");
    await page.clock.runFor(300000);
    await page.evaluate(() => window.dispatchEvent(new PageTransitionEvent("pagehide")));
    expect(state.requests.length).toBe(1);
    assertAnonymousRequest(state.requests[0], "https://tools.pingxingxian.space");
    expect(state.errors).toEqual([]);
  } finally {
    await close();
  }
});

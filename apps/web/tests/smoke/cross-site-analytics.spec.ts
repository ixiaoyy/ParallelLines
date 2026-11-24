import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";

import type { AnalyticsOverview } from "../../src/features/analytics/model";
import type { TrafficOverview, TrafficSiteFilter } from "../../src/features/analytics/trafficModel";
import { USER } from "./fixtures/forum";

const NOW = "2026-11-17T04:00:00Z";
type FixtureMode = "ready" | "disabled" | "not_connected" | "error" | "full";

/** 构造明确标为替身的统计数据，检查展示口径，不代替真实流量或线上接入验收。 */
function trafficFixture(siteKey: TrafficSiteFilter, mode: FixtureMode): TrafficOverview {
  const empty = mode === "disabled" || mode === "not_connected";
  const totals = empty ? {} : {
    page_views: 1_200,
    unique_visitors: 125,
    shared_unique_visitors: 100,
    site_only_visitors: 20,
    ephemeral_visitors: 5,
    new_visitors: 75,
    returning_visitors: 45,
    actions: 43,
  };
  return {
    enabled: mode !== "disabled",
    status: mode === "disabled" ? "disabled" : mode === "not_connected" ? "not_connected" : "ready",
    start_date: "2026-10-19",
    end_date: "2026-11-17",
    site_key: siteKey,
    timezone: "Asia/Shanghai",
    generated_at: NOW,
    data_through: empty ? null : NOW,
    last_ingested_at: empty ? null : NOW,
    collection_started_at: empty ? null : "2026-10-19T00:00:00Z",
    cache_seconds: 300,
    queue: { status: mode === "disabled" ? "disabled" : mode === "full" ? "full" : "ok", pending: mode === "full" ? 20_000 : 2, dropped_events: mode === "full" ? 8 : 0 },
    totals,
    previous: empty ? {} : { page_views: 1_000, unique_visitors: 110, shared_unique_visitors: 90, new_visitors: 70, returning_visitors: 40, actions: 40 },
    series: empty ? [] : [
      { day: "2026-11-15", page_views: 200, unique_visitors: 30, shared_unique_visitors: 20 },
      { day: "2026-11-16", page_views: 400, unique_visitors: 50, shared_unique_visitors: 40 },
      { day: "2026-11-17", page_views: 600, unique_visitors: 75, shared_unique_visitors: 60 },
    ],
    sites: [
      { site_key: "games", name: "游戏", status: empty ? "disabled" : "collecting", last_received_at: empty ? null : NOW, page_views: empty ? null : 800, unique_visitors: empty ? null : 100, actions: empty ? null : 20 },
      { site_key: "forum", name: "圈子", status: empty ? "disabled" : "no_activity", last_received_at: empty ? null : NOW, page_views: empty ? null : 0, unique_visitors: empty ? null : 0, actions: empty ? null : 0 },
      { site_key: "tools", name: "工具", status: empty ? "not_connected" : "collecting", last_received_at: empty ? null : NOW, page_views: empty ? null : 400, unique_visitors: empty ? null : 55, actions: empty ? null : 23 },
      { site_key: "chat", name: "Chat", status: "not_connected", last_received_at: null, page_views: null, unique_visitors: null, actions: null },
      { site_key: "api", name: "模型网关", status: empty ? "disabled" : "stale", last_received_at: empty ? null : "2026-11-10T04:00:00Z", page_views: empty ? null : 0, unique_visitors: empty ? null : 0, actions: empty ? null : 0 },
    ],
    traffic_sources: empty ? [] : [{ source_type: "search", source_name: "bing.com", page_views: 400, unique_visitors: 35 }],
    top_pages: empty ? [] : [{ site_key: "games", path: "/games", page_views: 800, unique_visitors: 100 }],
    top_actions: empty ? [] : [{ site_key: "tools", event_name: "tool_download", path: "/tools/pdf", count: 23, unique_visitors: 20 }],
    retention: empty ? {} : { eligible_visitors: 20, returned_visitors: 5, rate: 25, cohort_start: "2026-10-19", cohort_end: "2026-11-09" },
  };
}

/** 原有报表的独立替身，确保新增跨站流量不会替换原字段或权限入口。 */
const legacy: AnalyticsOverview = {
  start_date: "2026-10-19",
  end_date: "2026-11-17",
  totals: { page_views: 90, unique_visitors: 40, authenticated_member_visitors: 1, anonymous_visitors: 39, operator_visitors: 2, external_referrals: 30, dau: 1, mau: 2, registrations: 3, topics: 1, posts: 2, likes: 2, flags: 0 },
  series: [{ day: "2026-11-17", page_views: 90, unique_visitors: 40, dau: 1, registrations: 3, topics: 1, posts: 2, likes: 2, flags: 0 }],
  traffic_sources: [],
  entry_pages: [],
  top_boards: [],
  top_topics: [],
  top_users: [],
};

/** 拦截全部接口和站外请求；所有点击与截图仅针对本地页面及固定替身。 */
async function installFixture(page: Page, initialMode: FixtureMode = "ready") {
  const state = { mode: initialMode, trafficRequests: 0, lastSite: "all", errors: [] as string[] };
  await page.clock.setFixedTime(new Date(NOW));
  await page.addInitScript(() => localStorage.setItem("parallellines.access_token", "fixture-only-traffic-token"));
  page.on("pageerror", (error) => state.errors.push(error.message));
  await page.route("**/*", async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname.replace(/^\/api\/v1/, "");
    const local = new URL(process.env.PLAYWRIGHT_BASE_URL ?? "http://127.0.0.1:5173").origin;
    if (!url.pathname.startsWith("/api/")) return url.origin === local ? route.continue() : route.abort();
    const send = (data: unknown) => route.fulfill({ json: { data } });
    if (path === "/auth/me") return send({ ...USER, role: "admin", is_persona: false });
    if (path === "/site/settings") return send({ settings: { site_title: "平行线", brand_primary_color: "#409eff" }, updated_at: NOW });
    if (path === "/site/extensions" || path === "/auth/oauth/providers") return send([]);
    if (path === "/site/visits" || path === "/site/traffic") return send({ recorded: false, accepted: 0 });
    if (path === "/notifications") return send({ notifications: [], unread_count: 0 });
    if (path === "/notifications/stream") return route.fulfill({ status: 204, body: "" });
    if (path === "/admin/analytics/traffic") {
      state.trafficRequests += 1;
      const selected = url.searchParams.get("site_key") ?? "all";
      const siteKey = (["all", "games", "forum", "tools", "chat", "api"] as const).find((key) => key === selected) ?? "all";
      state.lastSite = siteKey;
      if (state.mode === "error") return route.fulfill({ status: 503, json: { error: { code: "traffic_unavailable", message: "fixture failure", details: {} } } });
      return send(trafficFixture(siteKey, state.mode));
    }
    if (path === "/admin/analytics") return send(legacy);
    if (path === "/admin/analytics/reports") return send([{ id: "daily_activity", name: "每日活跃趋势", description: "原有安全报表替身", columns: ["day", "page_views"] }]);
    if (path === "/admin/analytics/reports/daily_activity") return send({ id: "daily_activity", name: "每日活跃趋势", description: "原有安全报表替身", columns: ["day", "page_views"], rows: [{ day: "2026-11-17", page_views: 90 }] });
    return send(null);
  });
  return state;
}

/** 直接检查内容边界，避免上层 overflow 隐藏让 scrollWidth 假通过；表格仅允许在自己的容器内横滚。 */
async function assertTrafficFitsViewport(page: Page) {
  const layout = await page.evaluate(() => {
    const selectors = [
      ".traffic-panel", ".traffic-heading", ".traffic-site-filters", ".traffic-site-filters button",
      ".traffic-freshness", ".traffic-metrics", ".traffic-metric", ".traffic-metric > *", ".traffic-identity-note",
      ".traffic-trend", ".traffic-chart", ".traffic-sites", ".traffic-table-wrap",
      ".traffic-rankings", ".traffic-actions", ".traffic-privacy",
    ];
    return {
      viewport: innerWidth,
      boxes: selectors.flatMap((selector) => Array.from(document.querySelectorAll<HTMLElement>(selector)).map((element) => {
        const box = element.getBoundingClientRect();
        return { selector, left: box.left, right: box.right, width: box.width };
      })),
    };
  });
  expect(layout.boxes.length).toBeGreaterThan(20);
  for (const box of layout.boxes) {
    expect(box.left, `${box.selector} 左侧溢出：${JSON.stringify(layout)}`).toBeGreaterThanOrEqual(-1);
    expect(box.right, `${box.selector} 右侧溢出：${JSON.stringify(layout)}`).toBeLessThanOrEqual(layout.viewport + 1);
  }
  return layout;
}

test("综合和分站使用独立口径，原报表保留，不因窗口焦点自动重刷", async ({ page }, testInfo) => {
  const state = await installFixture(page);
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto("/admin/analytics");
  await expect(page.getByRole("heading", { name: "全系统分析", exact: true })).toBeVisible();
  const panel = page.locator(".traffic-panel");
  await expect(panel.getByRole("heading", { name: "跨站流量", exact: true })).toBeVisible();
  await expect(panel.locator(".traffic-metric").filter({ hasText: "跨站去重 UV" }).locator("strong")).toHaveText("100");
  await expect(panel.locator(".traffic-metric").filter({ hasText: "浏览量 PV" }).locator("strong")).toHaveText("1,200");
  await expect(panel.locator(".traffic-metric").filter({ hasText: "7 日回访率" }).locator("strong")).toHaveText("25%");
  await expect(panel.getByText(/仅站内标识 20/)).toBeVisible();
  await expect(panel.getByRole("row").filter({ has: page.getByRole("button", { name: "Chat", exact: true }) })).toContainText("未接入");
  await expect(panel.getByRole("row").filter({ has: page.getByRole("button", { name: "Chat", exact: true }) })).toContainText("—");
  await panel.getByRole("button", { name: "查看日数据" }).click();
  await expect(panel.locator("#traffic-daily-table")).toContainText("2026-11-17");
  await expect(page.getByRole("heading", { name: "原主站访问与用户增长" })).toBeVisible();
  const beforeFocus = state.trafficRequests;
  await page.evaluate(() => window.dispatchEvent(new Event("focus")));
  await page.waitForTimeout(250);
  expect(state.trafficRequests).toBe(beforeFocus);
  const layout = await assertTrafficFitsViewport(page);
  await testInfo.attach("traffic-desktop-layout", { body: JSON.stringify(layout, null, 2), contentType: "application/json" });
  await page.evaluate(() => scrollTo(0, 0));
  await page.screenshot({ path: testInfo.outputPath("traffic-desktop.png"), fullPage: true });
  await panel.getByRole("navigation", { name: "选择分析站点" }).getByRole("button", { name: "工具", exact: true }).click();
  await expect.poll(() => state.lastSite).toBe("tools");
  await expect(panel.getByRole("heading", { name: "本站访客 UV" })).toBeVisible();
  await page.getByRole("button", { name: "打开预设报表" }).click();
  await expect(page.getByText("原有安全报表替身", { exact: true })).toBeVisible();
  expect(state.errors).toEqual([]);
});

test("手机与窄屏不横向溢出，统计排除偏好可恢复", async ({ page }, testInfo) => {
  const state = await installFixture(page);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/admin/analytics");
  await expect(page.locator(".traffic-metrics")).toBeVisible();
  const exclude = page.getByRole("button", { name: "排除此浏览器统计", exact: true });
  await exclude.click();
  await expect(page.getByRole("button", { name: "已排除此浏览器 · 恢复统计" })).toHaveAttribute("aria-pressed", "true");
  expect(await page.evaluate(() => document.cookie)).toContain("px_traffic_exclude=1");
  await page.getByRole("button", { name: "已排除此浏览器 · 恢复统计" }).click();
  await expect(exclude).toHaveAttribute("aria-pressed", "false");
  for (const width of [390, 320, 860]) {
    await page.setViewportSize({ width, height: width === 860 ? 1000 : 844 });
    const layout = await assertTrafficFitsViewport(page);
    await testInfo.attach(`traffic-${width}-layout`, { body: JSON.stringify(layout, null, 2), contentType: "application/json" });
    const tableWrap = page.locator(".traffic-sites > .traffic-table-wrap");
    const scroll = await tableWrap.evaluate((element) => {
      element.scrollLeft = element.scrollWidth;
      const lastCell = element.querySelector("th:last-child")?.getBoundingClientRect();
      const container = element.getBoundingClientRect();
      const result = { moved: element.scrollLeft, total: element.scrollWidth, visible: element.clientWidth, lastCellRight: lastCell?.right ?? Infinity, containerRight: container.right };
      element.scrollLeft = 0;
      return result;
    });
    if (scroll.total > scroll.visible) expect(scroll.moved).toBeGreaterThan(0);
    expect(scroll.lastCellRight).toBeLessThanOrEqual(scroll.containerRight + 1);
    await page.evaluate(() => scrollTo(0, 0));
    await page.screenshot({ path: testInfo.outputPath(`traffic-${width}.png`), fullPage: true });
    if (width === 390) await page.screenshot({ path: testInfo.outputPath("traffic-mobile.png") });
    // 保留真实固定导航，另截滚动后的指标与表格，避免长图中的固定栏遮挡造成误判。
    if (width <= 390) {
      await page.locator(".traffic-metrics").evaluate((element) => scrollTo(0, element.getBoundingClientRect().top + scrollY - 80));
      await page.screenshot({ path: testInfo.outputPath(`traffic-${width}-metrics.png`) });
      await tableWrap.evaluate((element) => { element.scrollLeft = element.scrollWidth; });
      await page.locator(".traffic-sites").evaluate((element) => scrollTo(0, element.getBoundingClientRect().top + scrollY - 80));
      await page.screenshot({ path: testInfo.outputPath(`traffic-${width}-table-right.png`) });
      await tableWrap.evaluate((element) => { element.scrollLeft = 0; });
    }
  }
  expect(state.errors).toEqual([]);
});

test("未启用和未接入不冒充零流量", async ({ page }) => {
  const state = await installFixture(page, "disabled");
  await page.goto("/admin/analytics");
  await expect(page.getByText("跨站流量采集尚未启用", { exact: true })).toBeVisible();
  await expect(page.locator(".traffic-metrics")).toHaveCount(0);
  await expect(page.locator(".traffic-sites-table")).toContainText("—");
  state.mode = "not_connected";
  await page.getByRole("button", { name: "刷新分析数据", exact: true }).click();
  await expect(page.getByText("尚未收到各站的流量数据", { exact: true })).toBeVisible();
  await expect(page.locator(".traffic-metrics")).toHaveCount(0);
  expect(state.errors).toEqual([]);
});

test("队列异常提示少计，报表失败仍可查看原主站分析", async ({ page }) => {
  const state = await installFixture(page, "full");
  await page.goto("/admin/analytics");
  await expect(page.getByText(/采集队列已满/)).toBeVisible();
  await expect(page.getByText(/待处理 20,000 条 · 丢弃 8 条/)).toBeVisible();
  state.mode = "error";
  await page.getByRole("button", { name: "刷新分析数据", exact: true }).click();
  await expect(page.getByText(/更新失败，当前保留上次成功读取的汇总/)).toBeVisible();
  await expect(page.locator(".traffic-metrics")).toBeVisible();
  await expect(page.getByRole("heading", { name: "原主站访问与用户增长" })).toBeVisible();
  expect(state.errors).toEqual([]);
});

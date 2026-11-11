import { readFileSync } from "node:fs";
import { expect, test, type Page } from "@playwright/test";

import {
  buildSeoSiteAlternateNames,
  buildSeoSiteDescription,
  buildSeoSiteName,
  buildSiteStructuredData,
} from "../../src/shared/seo/structuredData";

const TITLE = "平行线 ParallelLines（pingxingxian）· 发现游戏、工具与创意";
const DESCRIPTION = "平行线 ParallelLines（pingxingxian）是发现游戏、实用工具与创意内容的空间。浏览游戏目录，探索办公与创作工具；兴趣圈子暂未开放。";
const SITE_NAME = "平行线 ParallelLines";
const TOOLS_URL = "https://tools.pingxingxian.space/";
const BASE_URL = process.env.PLAYWRIGHT_BASE_URL ?? "http://127.0.0.1:5193";
const LOCAL_ORIGIN = new URL(BASE_URL).origin;

test.use({ serviceWorkers: "block" });

/**
 * 全部业务接口由空公开目录替身接管，其他站外请求直接阻止，不访问真实服务或写库。
 * @param page - 本地页面；即便 API 配置指向独立 origin，也只能返回浏览器内替身。
 * @returns 页面错误与未登记接口记录，供调用方确认没有隐藏失败。
 */
async function isolateBrandPage(page: Page) {
  expect(["127.0.0.1", "localhost", "[::1]"].includes(new URL(BASE_URL).hostname)).toBe(true);
  const errors: string[] = [];
  const unexpectedApi: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.route("**/*", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    // 即便开发配置使用独立 API origin，也只在浏览器内返回替身，绝不转发。
    if (url.pathname.startsWith("/api/")) {
      const method = request.method();
      const headers = {
        "access-control-allow-origin": LOCAL_ORIGIN,
        "access-control-allow-methods": "GET, POST, OPTIONS",
        "access-control-allow-headers": "content-type, authorization, x-visitor-id",
      };
      if (method === "OPTIONS") return route.fulfill({ status: 204, headers, body: "" });
      const send = (data: unknown) => route.fulfill({ headers, json: { data } });
      if (method === "GET" && url.pathname === "/api/v1/catalog/overview") {
        return send({ categories: [], hero: { projects: [], total: 0, next_offset: null } });
      }
      if (method === "GET" && url.pathname === "/api/v1/catalog") return send({ categories: [] });
      if (method === "GET" && url.pathname === "/api/v1/auth/me") return send(null);
      if (method === "POST" && url.pathname === "/api/v1/site/visits") return send({ recorded: false });
      unexpectedApi.push(`${method} ${url.pathname}`);
      return route.fulfill({ status: 501, headers, json: { error: { code: "unmocked_api", message: url.pathname } } });
    }
    if (url.origin !== LOCAL_ORIGIN || !["GET", "HEAD"].includes(request.method())) {
      return route.abort();
    }
    return route.continue();
  });
  return { errors, unexpectedApi };
}

/**
 * 核对 Vue 接管后的同一首页合同，参数和兼容地址不得污染规范地址。
 * @param page - 已导航至根入口或 `/games` 的本地页面。
 * @returns 断言完成时结束；发现元信息、介绍或导航偏离约定时抛出测试失败。
 */
async function expectBrandMeta(page: Page) {
  await expect(page.locator(".catalog-page")).toBeVisible();
  await expect(page).toHaveTitle(TITLE);
  for (const selector of ['meta[name="description"]', 'meta[property="og:description"]', 'meta[name="twitter:description"]']) {
    await expect(page.locator(selector)).toHaveCount(1);
    await expect(page.locator(selector)).toHaveAttribute("content", DESCRIPTION);
  }
  for (const selector of ['meta[property="og:title"]', 'meta[name="twitter:title"]']) {
    await expect(page.locator(selector)).toHaveCount(1);
    await expect(page.locator(selector)).toHaveAttribute("content", TITLE);
  }
  await expect(page.locator('meta[property="og:site_name"]')).toHaveAttribute("content", SITE_NAME);
  await expect(page.locator('meta[name="robots"]')).toHaveAttribute("content", "index,follow");
  await expect(page.locator('meta[name="keywords"]')).toHaveCount(0);
  await expect(page.locator('link[rel="canonical"]')).toHaveCount(1);
  await expect(page.locator('link[rel="canonical"]')).toHaveAttribute("href", `${LOCAL_ORIGIN}/`);
  await expect(page.locator('meta[property="og:url"]')).toHaveAttribute("content", `${LOCAL_ORIGIN}/`);
  await expect(page.locator(".catalog-footer__about")).toHaveText(DESCRIPTION);
  const footerNav = page.getByRole("navigation", { name: "页脚导航", exact: true });
  await expect(footerNav.getByRole("button", { name: "圈子，暂未开放", exact: true })).toBeDisabled();
  await expect(footerNav.getByRole("link", { name: "工具", exact: true })).toHaveAttribute("href", TOOLS_URL);
  await expect(footerNav.getByRole("link", { name: "游戏", exact: true })).toHaveAttribute("href", "/");
  await expect(page.locator('a[href="/forum"]')).toHaveCount(0);
}

test("静态应用壳保留同一品牌标题、说明和分享元信息", () => {
  const shell = readFileSync(new URL("../../index.html", import.meta.url), "utf8");
  expect(shell.match(/<title>/g)).toHaveLength(1);
  expect(shell).toContain(`<title>${TITLE}</title>`);
  for (const name of ["description", "twitter:description"]) {
    expect(shell).toContain(`<meta name="${name}" content="${DESCRIPTION}"`);
  }
  expect(shell).toContain(`<meta property="og:description" content="${DESCRIPTION}"`);
  expect(shell).toContain(`<meta property="og:title" content="${TITLE}"`);
  expect(shell).toContain(`<meta name="twitter:title" content="${TITLE}"`);
  expect(shell).toContain(`<meta property="og:site_name" content="${SITE_NAME}"`);
  expect(shell).toContain('<link rel="canonical" href="https://pingxingxian.space/"');
  expect(shell).not.toContain('name="keywords"');
});

test("根入口与 games 兼容地址的品牌元信息和可见介绍一致", async ({ page }) => {
  const state = await isolateBrandPage(page);
  for (const path of ["/", "/games", "/?source=seo#brand", "/games?source=seo#brand"]) {
    await page.goto(path);
    await expect(page).toHaveURL(new URL(path, BASE_URL).href);
    await expectBrandMeta(page);
  }
  await page.reload();
  await expectBrandMeta(page);
  expect(state.errors).toEqual([]);
  expect(state.unexpectedApi).toEqual([]);
  // 此轮不修改旧站点图谱 owner；本地静态壳没有服务端注入，不能将其当成生产 JSON-LD 验收。
});

test("品牌页脚在桌面和两种手机宽度可读且无横向溢出", async ({ page }, testInfo) => {
  const state = await isolateBrandPage(page);
  await page.goto("/");
  await expectBrandMeta(page);
  for (const width of [1280, 390, 320]) {
    await page.setViewportSize({ width, height: 900 });
    const footer = page.locator(".catalog-footer");
    const about = page.locator(".catalog-footer__about");
    await footer.scrollIntoViewIfNeeded();
    await page.evaluate(() => document.fonts.ready);
    await expect(about).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
    const bounds = await about.evaluate((element) => {
      const rect = element.getBoundingClientRect();
      return { left: rect.left, right: rect.right, viewport: innerWidth, fits: element.scrollWidth <= element.clientWidth + 1 };
    });
    expect(bounds.left).toBeGreaterThanOrEqual(0);
    expect(bounds.right).toBeLessThanOrEqual(bounds.viewport + 1);
    expect(bounds.fits).toBe(true);
    await footer.screenshot({ path: testInfo.outputPath(`brand-footer-${width}.png`), animations: "disabled" });
  }
  expect(state.errors).toEqual([]);
  expect(state.unexpectedApi).toEqual([]);
});

test("结构化品牌别名去重并保留自定义名称、规范地址和 Logo", () => {
  expect(buildSeoSiteName(" 平行线 ")).toBe("平行线 ParallelLines");
  expect(buildSeoSiteName("平行线 PARALLELLINES")).toBe("平行线 PARALLELLINES");
  expect(buildSeoSiteDescription(SITE_NAME)).toBe(DESCRIPTION);
  expect(buildSeoSiteAlternateNames("平行线", "https://PINGXINGXIAN.space/")).toEqual([
    "平行线", "ParallelLines", "pingxingxian", "pingxingxian.space",
  ]);
  expect(buildSeoSiteAlternateNames("PINGXINGXIAN", "https://pingxingxian.space/")).toEqual([
    "PINGXINGXIAN", "平行线", "ParallelLines", "pingxingxian.space",
  ]);
  const graph = buildSiteStructuredData({
    title: "云游馆 & 创意", siteUrl: "https://pingxingxian.space/", description: "自定义站点说明", logoUrl: "/custom-logo.svg",
  });
  expect(graph).toEqual({
    "@context": "https://schema.org",
    "@graph": [
      {
        "@type": "WebSite", "@id": "https://pingxingxian.space/#website", url: "https://pingxingxian.space/",
        name: "云游馆 & 创意 ParallelLines", alternateName: ["云游馆 & 创意", "平行线", "ParallelLines", "pingxingxian", "pingxingxian.space"],
        description: "自定义站点说明", inLanguage: "zh-CN", publisher: { "@id": "https://pingxingxian.space/#organization" },
      },
      {
        "@type": "Organization", "@id": "https://pingxingxian.space/#organization", url: "https://pingxingxian.space/",
        name: "云游馆 & 创意 ParallelLines", alternateName: ["云游馆 & 创意", "平行线", "ParallelLines", "pingxingxian", "pingxingxian.space"],
        logo: { "@type": "ImageObject", url: "https://pingxingxian.space/custom-logo.svg" },
      },
    ],
  });
});

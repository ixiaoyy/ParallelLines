import { expect, test as base, type Page } from "@playwright/test";
import * as XLSX from "xlsx";

const baseURL = process.env.PLAYWRIGHT_BASE_URL ?? "http://127.0.0.1:5173";
const origin = new URL(baseURL).origin;
const forumTagline = "论坛专用固定描述";
const forumDescription = `平行线 ParallelLines：${forumTagline}。浏览公开版块与可追溯讨论。`;

// 固定期望独立于路由实现，防止错误文案、规范地址或论坛残留被生产常量自证通过。
const publicPages = [
  {
    path: "/",
    title: "AI 游戏 · GPT / Claude Code / Kimi · 点开即玩 | 平行线 ParallelLines",
    description: "平行线 ParallelLines 收录 AI 网页游戏，探索 GPT、Claude Code、Kimi 等工具带来的游戏创意。涵盖策略、卡牌、解谜、角色扮演与休闲玩法，按分类和热度发现游戏，点开即玩。",
    readySelector: ".catalog-page",
  },
  {
    path: "/tools",
    title: "工具 · 平行线",
    description: "Excel 公式速查与拼豆图纸生成器，支持公式学习、图片转换、色号用量统计与图纸导出。",
    heading: "工具",
  },
  {
    path: "/tools/excel-formulas",
    title: "Excel 公式速查 · 平行线",
    description: "文职常用公式，按步骤照着做。",
    heading: "Excel 公式速查",
  },
  {
    path: "/tools/bead-pattern",
    title: "拼豆图纸生成器 · 平行线",
    description: "将图片转换为拼豆图纸，查看色号和用量。",
    heading: "拼豆图纸生成器",
  },
  {
    path: "/play/generals-soldiers",
    title: "将军战小兵 · 平行线",
    description: "在平行线与电脑进行将军战小兵对弈。",
    heading: "将军战小兵",
  },
  {
    path: "/play/snake-escape",
    title: "蛇蛇出洞 · 平行线",
    description: "按顺序放走彩色小蛇，避开阻挡，在倒计时结束前清空棋盘。",
    heading: "蛇蛇出洞",
  },
  {
    path: "/play/flappy-dunk",
    title: "飞翼灌篮 · 平行线",
    description: "点按让带翅膀的篮球跳跃，从上方穿过篮圈，挑战连续进球和最高分。",
    heading: "飞翼灌篮",
  },
] as const;

const [catalog, tools, excel] = publicPages;

// 保留真实 SPA、游戏和工具静态文件；全部接口由浏览器拦截，站外请求不离开本机。
const test = base.extend<{ localSeo: void }>({
  localSeo: [async ({ context, page }, use) => {
    const errors: string[] = [];
    const unexpected: string[] = [];
    page.on("pageerror", error => errors.push(error.message));
    await context.route("**/*", async route => {
      const request = route.request();
      const url = new URL(request.url());
      // 本地 API 可使用独立端口；先模拟接口，避免将其误当站外资源阻断。
      if (!url.pathname.startsWith("/api/")) return url.origin === origin ? route.continue() : route.abort();
      const path = url.pathname.replace(/^\/api\/v1/, "");
      const send = (data: unknown) => route.fulfill({ json: { data } });
      if (path === "/site/settings") {
        return send({ settings: { site_title: "平行线", site_tagline: forumTagline }, updated_at: null });
      }
      if (path === "/site/visits") return send({ recorded: false });
      if (path === "/catalog") return send({ categories: [] });
      if (["/topics", "/boards", "/tags", "/site/extensions"].includes(path)) return send([]);
      if (path === "/auth/me") return send(null);
      unexpected.push(`${request.method()} ${path}`);
      return route.fulfill({ status: 501, json: { error: { code: "unmocked_api", message: path } } });
    });
    await use();
    expect(unexpected, "公开 SEO 回归不应请求未声明的业务接口").toEqual([]);
    expect(errors, "真实页面不应出现运行时异常").toEqual([]);
  }, { auto: true }],
});

test.use({ serviceWorkers: "block" });

/** 核对唯一站点图谱、品牌和默认 Logo；公开工具或游戏不能残留论坛专用描述。 */
async function expectSiteSchema(page: Page, isForum = false): Promise<void> {
  const script = page.locator('head script#seo-site-structured-data[type="application/ld+json"]');
  await expect(script).toHaveCount(1);
  await expect(page.locator('head script[type="application/ld+json"]')).toHaveCount(1);
  const schema: unknown = JSON.parse(await script.textContent() ?? "null");
  expect(schema).toMatchObject({
    "@context": "https://schema.org",
    "@graph": [
      {
        "@type": "WebSite", "@id": `${origin}/#website`, url: `${origin}/`,
        name: "平行线 ParallelLines", description: expect.stringMatching(/\S/),
        publisher: { "@id": `${origin}/#organization` },
      },
      {
        "@type": "Organization", "@id": `${origin}/#organization`, url: `${origin}/`,
        name: "平行线 ParallelLines",
        logo: { "@type": "ImageObject", url: `${origin}/logo-lines-mark.png` },
      },
    ],
  });
  // script 不属于可见文本，读取原始 JSON 文本核对论坛描述，避免空文本造成误判。
  if (isForum) {
    await expect.poll(() => script.textContent()).toContain(forumTagline);
  } else {
    await expect.poll(() => script.textContent()).not.toContain(forumTagline);
    await expect.poll(() => script.textContent()).not.toContain("浏览公开版块与可追溯讨论");
  }
}

/** 等待当前页元数据落位，并同时检查分享元数据、规范地址及重复标签。 */
async function expectPageSeo(
  page: Page,
  expected: { path: string; title: string; description: string },
  isForum = false,
): Promise<void> {
  await expect(page).toHaveTitle(expected.title);
  await expect(page.locator("head title")).toHaveCount(1);
  const canonical = `${origin}${expected.path}`;
  for (const [selector, content] of [
    ['meta[name="description"]', expected.description],
    ['meta[name="robots"]', "index,follow"],
    ['meta[property="og:title"]', expected.title],
    ['meta[property="og:description"]', expected.description],
    ['meta[property="og:url"]', canonical],
    ['meta[name="twitter:title"]', expected.title],
    ['meta[name="twitter:description"]', expected.description],
  ]) {
    const tag = page.locator(`head ${selector}`);
    await expect(tag).toHaveCount(1);
    await expect(tag).toHaveAttribute("content", content!);
  }
  await expect(page.locator('head link[rel="canonical"]')).toHaveCount(1);
  await expect(page.locator('head link[rel="canonical"]')).toHaveAttribute("href", canonical);
  await expectSiteSchema(page, isForum);
}

for (const entry of publicPages) {
  test(`公开页面 ${entry.path} 使用独立元数据和唯一站点图谱`, async ({ page }) => {
    await page.goto(entry.path);
    if ("readySelector" in entry) await expect(page.locator(entry.readySelector)).toBeVisible();
    else await expect(page.getByRole("heading", { name: entry.heading, exact: true })).toBeVisible();
    await expectPageSeo(page, entry);
  });
}

test("games 别名的规范地址仍指向根目录", async ({ page }) => {
  await page.goto("/games");
  await expect(page.locator(".catalog-page")).toBeVisible();
  await expectPageSeo(page, catalog);
});

for (const brand of [
  {
    title: "测试展馆", name: "测试展馆 ParallelLines",
    alternateNames: ["测试展馆", "平行线", "ParallelLines", "canonical.example.test"],
  },
  {
    title: "平行线 ParallelLines", name: "平行线 ParallelLines",
    alternateNames: ["平行线", "ParallelLines", "canonical.example.test"],
  },
] as const) {
  test(`首屏品牌 ${brand.title} 经论坛往返工具后保留原站名与规范身份`, async ({ page }) => {
    const canonicalOrigin = "https://canonical.example.test";
    const logoUrl = "https://cdn.example.test/custom-logo.webp";
    const website = {
      "@type": "WebSite", "@id": `${canonicalOrigin}/#website`, url: `${canonicalOrigin}/`,
      name: brand.name, alternateName: brand.alternateNames,
      description: "首屏固定站点描述", inLanguage: "zh-CN",
      publisher: { "@id": `${canonicalOrigin}/#organization` },
    };
    const organization = {
      "@type": "Organization", "@id": `${canonicalOrigin}/#organization`, url: `${canonicalOrigin}/`,
      name: brand.name, alternateName: brand.alternateNames,
      logo: { "@type": "ImageObject", url: logoUrl },
    };
    const serverSchema = { "@context": "https://schema.org", "@graph": [website, organization] };
    // 服务端正文保留原站名，图谱使用完整品牌；已有英文品牌不能凭别名被反向删去。
    await page.route(url => url.origin === origin && url.pathname === "/", async route => {
      const response = await route.fetch();
      const html = await response.text();
      const script = `<script type="application/ld+json" id="seo-site-structured-data">${JSON.stringify(serverSchema)}</script>`;
      const fallback = `<main class="seo-fallback"><nav><a href="/">${brand.title}</a></nav></main>`;
      const body = html
        .replace("<!-- parallellines-seo-head-end -->", `${script}<!-- parallellines-seo-head-end -->`)
        .replace("<!-- parallellines-seo-body -->", `<!-- parallellines-seo-body -->${fallback}`);
      await route.fulfill({ response, body });
    });
    // 论坛仍加载自己的公开设置；仅覆盖该接口，确保真实外壳更新不会重置规范域名或站名。
    await page.route(url => url.pathname.startsWith("/api/") && url.pathname.endsWith("/site/settings"), route =>
      route.fulfill({ json: { data: {
        settings: { site_title: brand.title, site_tagline: forumTagline, brand_logo_url: logoUrl }, updated_at: null,
      } } }),
    );
    await page.goto("/");
    await expect(page.locator(".catalog-page")).toBeVisible();
    const stages = [
      { path: "/", title: catalog.title.replace("平行线 ParallelLines", brand.name), description: catalog.description.replace("平行线 ParallelLines", brand.name) },
      { path: "/tools", title: `工具 · ${brand.title}`, description: tools.description },
      { path: "/forum", title: brand.name, description: `${brand.name}：${forumTagline}。浏览公开版块与可追溯讨论。` },
      { path: "/tools", title: `工具 · ${brand.title}`, description: tools.description },
    ];
    for (const [index, stage] of stages.entries()) {
      if (index === 1) {
        await page.getByRole("navigation", { name: "页脚导航" }).getByRole("link", { name: "工具", exact: true }).click();
      } else if (stage.path === "/forum") {
        await page.evaluate(() => {
          history.pushState(null, "", "/forum");
          dispatchEvent(new PopStateEvent("popstate", { state: history.state }));
        });
        await expect(page.locator(".forum-home")).toBeVisible();
      } else if (index === 3) {
        await page.goBack();
      }
      await expect(page).toHaveTitle(stage.title);
      await expect(page.locator('head meta[name="description"]')).toHaveAttribute("content", stage.description);
      await expect(page.locator('head link[rel="canonical"]')).toHaveCount(1);
      await expect(page.locator('head link[rel="canonical"]')).toHaveAttribute("href", `${canonicalOrigin}${stage.path}`);
      await expect(page.locator('head meta[property="og:site_name"]')).toHaveAttribute("content", brand.name);
      await expect(page.locator('head meta[property="og:url"]')).toHaveAttribute("content", `${canonicalOrigin}${stage.path}`);
      const script = page.locator('head script[type="application/ld+json"]');
      await expect(script).toHaveCount(1);
      const schema: unknown = JSON.parse(await script.textContent() ?? "null");
      expect(schema).toMatchObject({
        "@context": "https://schema.org",
        "@graph": [{ ...website, description: expect.stringMatching(/\S/) }, organization],
      });
      if (stage.path === "/forum") await expect.poll(() => script.textContent()).toContain(forumTagline);
      else await expect.poll(() => script.textContent()).not.toContain(forumTagline);
    }
  });
}

test("同一 SPA 在论坛、目录和工具间切换时图谱不丢失且无旧描述或重复标签", async ({ page }) => {
  const forum = { path: "/forum", title: "平行线 ParallelLines", description: forumDescription };
  await page.goto("/forum");
  await expect(page.locator(".forum-home")).toBeVisible();
  await expectPageSeo(page, forum, true);
  // 目录没有论坛入口，用浏览器历史事件验证同一文档内的布局卸载和重新挂载。
  await page.evaluate(() => {
    history.pushState(null, "", "/");
    dispatchEvent(new PopStateEvent("popstate", { state: history.state }));
  });
  await expect(page.locator(".catalog-page")).toBeVisible();
  await expectPageSeo(page, catalog);
  await page.getByRole("navigation", { name: "页脚导航" }).getByRole("link", { name: "工具", exact: true }).click();
  await expect(page.getByRole("heading", { name: "工具", exact: true })).toBeVisible();
  await expectPageSeo(page, tools);
  await page.goBack();
  await expect(page.locator(".catalog-page")).toBeVisible();
  await expectPageSeo(page, catalog);
  await page.goBack();
  await expect(page.locator(".forum-home")).toBeVisible();
  await expectPageSeo(page, forum, true);
});

test("有效与无效教程参数保留基础规范地址、原教程定位和回退", async ({ page }) => {
  await page.goto("/tools/excel-formulas?lesson=person-total");
  await expect(page.getByRole("heading", { name: "同一个人有多笔，算他的总金额", exact: true })).toBeVisible();
  await expect(page.getByTestId("lesson-formula")).toContainText("SUMIFS(");
  await expect(page.getByTestId("expected-result")).toContainText("250");
  await expectPageSeo(page, excel);
  await page.reload();
  await expect(page.getByTestId("lesson-formula")).toContainText("SUMIFS(");
  await expectPageSeo(page, excel);
  await page.goto("/tools/excel-formulas?lesson=not-a-lesson");
  await expect(page.getByTestId("lesson-formula")).toContainText("SUM(");
  await expect(page.getByTestId("paste-target")).toHaveText("粘贴位置：练习表 C2");
  await expect(page.getByTestId("expected-result")).toContainText("750");
  await expectPageSeo(page, excel);
});

test("工具目录下的工作簿与拼豆样例仍返回真实文件并可读取", async ({ page }) => {
  await page.goto("/tools/excel-formulas");
  const workbookResponse = await page.request.get("/tools/excel-formulas/excel-formula-practice.xlsx");
  expect(workbookResponse.status()).toBe(200);
  const bytes = await workbookResponse.body();
  expect(bytes.subarray(0, 2).toString()).toBe("PK");
  const workbook = XLSX.read(bytes, { type: "buffer" });
  expect(workbook.SheetNames).toEqual(expect.arrayContaining(["练习", "数据", "名单"]));
  expect(workbook.Sheets["练习"]?.D3?.v).toBe(250);
  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("link", { name: "下载练习表", exact: true }).first().click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toBe("excel-formula-practice.xlsx");
  expect(await download.failure()).toBeNull();

  const sampleResponse = await page.request.get("/tools/bead-pattern/pixel-example.svg");
  expect(sampleResponse.status()).toBe(200);
  expect(sampleResponse.headers()["content-type"]).toContain("image/svg+xml");
  await page.goto("/tools/bead-pattern");
  await page.getByRole("button", { name: "体验简单图案", exact: true }).click();
  await expect(page.getByRole("heading", { name: "盆栽示例", exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "生成图纸", exact: true })).toBeEnabled();
  const canvas = page.getByRole("img", { name: "拼豆图案画布", exact: true });
  await expect(canvas).toBeVisible();
  expect(await canvas.evaluate(element => element instanceof HTMLCanvasElement && element.width > 0 && element.height > 0)).toBe(true);
});

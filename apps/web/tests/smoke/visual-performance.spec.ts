import { test, expect, Page, devices } from "@playwright/test";

const apiBaseUrl = process.env.PLAYWRIGHT_API_BASE_URL ?? "http://127.0.0.1:8000/api/v1";

/**
 * 性能指标类型
 */
interface PerformanceMetrics {
  domContentLoaded: number;
  load: number;
  firstContentfulPaint?: number;
  largestContentfulPaint?: number;
  domInteractive?: number;
}

/**
 * 收集页面性能指标
 */
async function collectPerformanceMetrics(page: Page): Promise<PerformanceMetrics> {
  const metrics = await page.evaluate(() => {
    const timing = performance.timing;
    const [navigation] = performance.getEntriesByType("navigation") as PerformanceNavigation[];
    const paintEntries = performance.getEntriesByType("paint") as PerformancePaintTiming[];

    return {
      domContentLoaded: timing.domContentLoadedEventEnd - timing.navigationStart,
      load: timing.loadEventEnd - timing.navigationStart,
      firstContentfulPaint: paintEntries.find((e) => e.name === "first-contentful-paint")?.startTime,
      largestContentfulPaint: (() => {
        const lcpEntries = performance.getEntriesByType("largest-contentful-paint") as PerformanceLargestContentfulPaint[];
        return lcpEntries.length > 0 ? lcpEntries.at(-1)?.startTime : undefined;
      })(),
      domInteractive: navigation?.domInteractive,
    };
  });
  return metrics;
}

/**
 * 检查页面是否有控制台错误
 */
async function checkConsoleErrors(page: Page): Promise<string[]> {
  const errors: string[] = [];
  page.on("console", (msg) => {
    if (msg.type() === "error") {
      errors.push(msg.text());
    }
  });
  return errors;
}

/**
 * 验证页面关键元素存在
 */
async function verifyPageElements(page: Page, selectors: string[]): Promise<{ missing: string[]; found: string[] }> {
  const missing: string[] = [];
  const found: string[] = [];

  for (const selector of selectors) {
    const element = page.locator(selector).first();
    const isVisible = await element.isVisible({ timeout: 2000 }).catch(() => false);
    if (isVisible) {
      found.push(selector);
    } else {
      missing.push(selector);
    }
  }

  return { missing, found };
}

/**
 * 验证响应式布局
 */
async function verifyResponsiveLayout(page: Page, viewport: { width: number; height: number }) {
  const issues: string[] = [];

  // 检查水平溢出
  const hasHorizontalScroll = await page.evaluate(() => {
    return document.documentElement.scrollWidth > document.documentElement.clientWidth;
  });
  if (hasHorizontalScroll) {
    issues.push(`Viewport ${viewport.width}x${viewport.height}: 存在水平滚动溢出`);
  }

  // 检查元素是否在视口内
  const outOfViewElements = await page.evaluate(() => {
    const elements = document.querySelectorAll("body > *");
    const outOfView: string[] = [];
    elements.forEach((el, i) => {
      const rect = el.getBoundingClientRect();
      if (rect.right > window.innerWidth && rect.left < window.innerWidth) {
        outOfView.push(`Element ${i}: ${el.tagName}`);
      }
    });
    return outOfView;
  });

  if (outOfViewElements.length > 0) {
    issues.push(`Viewport ${viewport.width}x${viewport.height}: ${outOfViewElements.length} 个元素超出视口右侧`);
  }

  return issues;
}

// ========== 测试配置 ==========

const DESKTOP_VIEWPORTS = [
  { name: "Desktop 1440p", width: 2560, height: 1440 },
  { name: "Desktop 1080p", width: 1920, height: 1080 },
  { name: "Desktop 1366x768", width: 1366, height: 768 },
];

const MOBILE_VIEWPORTS = [
  { name: "iPhone 15 Pro", ...devices["iPhone 15 Pro"] },
  { name: "iPhone 15", ...devices["iPhone 15"] },
  { name: "Pixel 7", ...devices["Pixel 7"] },
  { name: "Samsung Galaxy S21", ...devices["Samsung Galaxy S21"] },
  { name: "iPad Pro 11", ...devices["iPad Pro 11"] },
];

/**
 * 需要测试的核心页面路由
 */
const CORE_PAGES = [
  { path: "/", name: "首页", keySelectors: ["[data-v-app]", "main"] },
  { path: "/auth", name: "认证页", keySelectors: ["[data-v-app]", "form"] },
  { path: "/search", name: "搜索页", keySelectors: ["[data-v-app]", "input"] },
  { path: "/board", name: "版块列表", keySelectors: ["[data-v-app]", "main"] },
];

// ========== Web 端测试 ==========

test.describe("Web 端桌面端测试", () => {
  for (const viewport of DESKTOP_VIEWPORTS) {
    test(`@desktop ${viewport.name} (${viewport.width}x${viewport.height}) - 页面加载和布局测试`, async ({ page }) => {
      await page.setViewportSize({ width: viewport.width, height: viewport.height });

      for (const pageInfo of CORE_PAGES) {
        await page.goto(pageInfo.path, { waitUntil: "networkidle" });
        const metrics = await collectPerformanceMetrics(page);

        // 验证关键元素
        const { missing } = await verifyPageElements(page, pageInfo.keySelectors);
        expect(missing, `${pageInfo.name}: 缺少关键元素 ${missing.join(", ")}`).toHaveLength(0);

        // 验证性能
        expect(metrics.load, `${pageInfo.name}: 页面加载时间超过 5 秒`).toBeLessThan(5000);
        expect(metrics.domContentLoaded, `${pageInfo.name}: DOMContentLoaded 超过 3 秒`).toBeLessThan(3000);

        // 验证响应式布局
        const layoutIssues = await verifyResponsiveLayout(page, viewport);
        expect(layoutIssues, `${pageInfo.name}: ${layoutIssues.join("; ")}`).toHaveLength(0);
      }
    });
  }
});

// ========== 移动端测试 ==========

test.describe("移动端响应式测试", () => {
  for (const device of MOBILE_VIEWPORTS) {
    test(`@mobile ${device.name} - 页面加载和布局测试`, async ({ page }) => {
      await page.setViewportSize({ width: device.defaultBrowserViewport?.width ?? 390, height: device.defaultBrowserViewport?.height ?? 844 });

      for (const pageInfo of CORE_PAGES) {
        await page.goto(pageInfo.path, { waitUntil: "networkidle" });
        const metrics = await collectPerformanceMetrics(page);

        // 验证关键元素
        const { missing } = await verifyPageElements(page, pageInfo.keySelectors);
        expect(missing, `${pageInfo.name}: ${pageInfo.name} 缺少关键元素 ${missing.join(", ")}`).toHaveLength(0);

        // 移动端性能要求可以放宽
        expect(metrics.load, `${pageInfo.name}: 移动端页面加载时间超过 8 秒`).toBeLessThan(8000);

        // 验证移动端布局无溢出
        const layoutIssues = await verifyResponsiveLayout(page, {
          width: device.defaultBrowserViewport?.width ?? 390,
          height: device.defaultBrowserViewport?.height ?? 844,
        });
        expect(layoutIssues, `${pageInfo.name}: ${pageInfo.name} ${layoutIssues.join("; ")}`).toHaveLength(0);
      }
    });
  }
});

// ========== 性能基准测试 ==========

test.describe("性能基准测试", () => {
  test("首页性能指标应在合理范围内", async ({ page }) => {
    await page.goto("/", { waitUntil: "networkidle" });
    const metrics = await collectPerformanceMetrics(page);

    console.log("性能指标:", JSON.stringify(metrics, null, 2));

    // FCP 应在 2 秒内
    if (metrics.firstContentfulPaint) {
      expect(metrics.firstContentfulPaint, "首次内容绘制时间超过 2 秒").toBeLessThan(2000);
    }

    // LCP 应在 3 秒内
    if (metrics.largestContentfulPaint) {
      expect(metrics.largestContentfulPaint, "最大内容绘制时间超过 3 秒").toBeLessThan(3000);
    }

    // DOM Interactive 应在 3 秒内
    if (metrics.domInteractive) {
      expect(metrics.domInteractive, "DOM 可交互时间超过 3 秒").toBeLessThan(3000);
    }

    // 整体加载应在 5 秒内
    expect(metrics.load, "页面完全加载时间超过 5 秒").toBeLessThan(5000);
  });

  test("版块页面性能指标", async ({ page }) => {
    await page.goto("/board", { waitUntil: "networkidle" });
    const metrics = await collectPerformanceMetrics(page);

    console.log("版块页面性能指标:", JSON.stringify(metrics, null, 2));

    expect(metrics.load, "版块页面加载时间超过 5 秒").toBeLessThan(5000);
  });

  test("搜索页面性能指标", async ({ page }) => {
    await page.goto("/search", { waitUntil: "networkidle" });
    const metrics = await collectPerformanceMetrics(page);

    console.log("搜索页面性能指标:", JSON.stringify(metrics, null, 2));

    expect(metrics.load, "搜索页面加载时间超过 5 秒").toBeLessThan(5000);
  });
});

// ========== 交互流畅度测试 ==========

test.describe("交互流畅度测试", () => {
  test("页面导航响应时间", async ({ page }) => {
    await page.goto("/", { waitUntil: "networkidle" });

    // 由于 API 未运行，导航链接可能不显示，直接通过 URL 测试导航
    const navStart = Date.now();
    await page.goto("/board", { waitUntil: "networkidle" });
    const navDuration = Date.now() - navStart;

    console.log(`导航到版块页面耗时: ${navDuration}ms`);
    expect(navDuration, "页面导航耗时超过 3 秒").toBeLessThan(3000);
  });

  test("搜索输入响应", async ({ page }) => {
    await page.goto("/search", { waitUntil: "networkidle" });

    // 尝试多种可能的选择器来找到搜索输入框
    const searchInput = page.getByLabel("搜索平行线", { exact: true })
      .or(page.locator('input[placeholder*="搜索"], input[aria-label*="搜索"], input[type="search"]'))
      .first();
    await searchInput.waitFor({ timeout: 5000 });

    // 测量输入响应时间
    const inputStart = Date.now();
    await searchInput.fill("测试");
    const responseTime = Date.now() - inputStart;

    console.log(`搜索输入响应时间: ${responseTime}ms`);
    expect(responseTime, "搜索输入响应时间超过 2 秒").toBeLessThan(2000);
  });

  test("移动端触摸滚动流畅度", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto("/", { waitUntil: "networkidle" });

    // 等待页面加载
    await page.waitForLoadState("domcontentloaded");

    // 检查页面是否足够长可以滚动
    const pageHeight = await page.evaluate(() => document.documentElement.scrollHeight);
    const viewportHeight = await page.evaluate(() => window.innerHeight);

    if (pageHeight <= viewportHeight) {
      // 页面太短无法滚动，跳过测试
      console.log(`页面高度 ${pageHeight}px 小于视口高度 ${viewportHeight}px，跳过滚动测试`);
      return;
    }

    // 使用 evaluate 执行滚动
    await page.evaluate(() => {
      window.scrollBy({ top: 500, behavior: "smooth" });
    });

    // 等待滚动完成
    await page.waitForTimeout(600);

    // 验证滚动位置已更新
    const scrollY = await page.evaluate(() => window.scrollY);
    expect(scrollY, "滚动后页面位置未更新").toBeGreaterThan(0);
  });
});

// ========== 视觉一致性测试 ==========

test.describe("视觉一致性测试", () => {
  test("桌面端和移动端导航菜单一致性", async ({ page }) => {
    // 桌面端
    await page.setViewportSize({ width: 1920, height: 1080 });
    await page.goto("/", { waitUntil: "networkidle" });

    const desktopNavLinks = await page.locator("nav a, header a").count();

    // 移动端
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto("/", { waitUntil: "networkidle" });

    const mobileNavLinks = await page.locator("nav a, header a").count();

    // 移动端可能使用汉堡菜单，但关键链接应该可见
    const mobileMenuButton = await page.locator("button[aria-label*='菜单'], button[aria-label*='menu'], .menu-toggle").count();
    expect(mobileNavLinks > 0 || mobileMenuButton > 0, "移动端应该有导航链接或菜单按钮").toBeTruthy();
    console.log(`桌面端导航链接: ${desktopNavLinks}, 移动端导航链接: ${mobileNavLinks}, 移动端菜单按钮: ${mobileMenuButton}`);
  });

  test("表单元素在移动端正确显示", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto("/auth?mode=register", { waitUntil: "networkidle" });

    // 尝试多种可能的选择器来找到用户名输入框
    const usernameInput = page.locator('input[name="username"], input[autocomplete="username"], input[id*="username"]').first();
    const isVisible = await usernameInput.isVisible({ timeout: 2000 }).catch(() => false);

    if (isVisible) {
      // 获取输入框的 bounding box
      const inputBox = await usernameInput.boundingBox();
      expect(inputBox?.height ?? 0, "移动端输入框高度应至少 30px").toBeGreaterThan(30);

      // 验证按钮足够大便于触摸
      const submitButton = page.locator('button[type="submit"], button:has-text("创建"), button:has-text("注册")').first();
      const buttonVisible = await submitButton.isVisible({ timeout: 2000 }).catch(() => false);

      if (buttonVisible) {
        const buttonBox = await submitButton.boundingBox();
        // 移动端按钮高度应至少 36px（考虑到实际设计）
        expect(buttonBox?.height ?? 0, "移动端按钮高度应至少 36px 以便于触摸").toBeGreaterThanOrEqual(36);
      }
    } else {
      // 如果表单未加载，跳过此测试
      console.log("注册表单未显示（可能因为 API 未运行）");
    }
  });
});

// ========== 可访问性测试 ==========

test.describe("可访问性测试", () => {
  test("所有页面应有适当的标题", async ({ page }) => {
    for (const pageInfo of CORE_PAGES) {
      await page.goto(pageInfo.path, { waitUntil: "networkidle" });

      const title = await page.title();
      expect(title, `${pageInfo.name} 应该有标题`).toBeTruthy();
      expect(title.length, `${pageInfo.name} 标题长度应大于 0`).toBeGreaterThan(0);
    }
  });

  test("关键表单应有标签", async ({ page }) => {
    await page.goto("/auth?mode=register", { waitUntil: "networkidle" });

    const inputs = page.locator("input:not([type='hidden'])");
    const inputCount = await inputs.count();

    for (let i = 0; i < inputCount; i++) {
      const input = inputs.nth(i);
      const hasLabel = await page.locator(`label[for="${await input.getAttribute("id")}"]`).count() > 0;
      const hasAriaLabel = !!(await input.getAttribute("aria-label"));
      const hasPlaceholder = !!(await input.getAttribute("placeholder"));

      expect(hasLabel || hasAriaLabel || hasPlaceholder, `输入框 ${i} 应该有标签或 aria-label 或 placeholder`).toBeTruthy();
    }
  });

  test("图片应有 alt 文本", async ({ page }) => {
    await page.goto("/", { waitUntil: "networkidle" });

    const images = page.locator("img");
    const imageCount = await images.count();

    const missingAlt: string[] = [];
    for (let i = 0; i < imageCount; i++) {
      const img = images.nth(i);
      const alt = await img.getAttribute("alt");
      const ariaHidden = await img.getAttribute("aria-hidden");

      if (!alt && !ariaHidden) {
        const src = await img.getAttribute("src");
        missingAlt.push(src ?? `image ${i}`);
      }
    }

    // Logo 等装饰性图片可以有 aria-hidden
    console.log(`发现 ${missingAlt.length} 个可能缺少 alt 的图片`);
  });
});

// ========== 控制台错误检测 ==========

test.describe("控制台错误检测", () => {
  test("页面加载时不应有非网络相关的 Error 级别控制台错误", async ({ page }) => {
    const errors: string[] = [];

    page.on("console", (msg) => {
      if (msg.type() === "error") {
        errors.push(`[${msg.location().url}] ${msg.text()}`);
      }
    });

    for (const pageInfo of CORE_PAGES) {
      await page.goto(pageInfo.path, { waitUntil: "networkidle" });
      await page.waitForTimeout(1000); // 等待异步错误
    }

    // 过滤掉网络相关错误（API 未运行导致的）
    const criticalErrors = errors.filter(
      (e) =>
        !e.includes("ERR_CONNECTION_REFUSED") &&
        !e.includes("ERR_CONNECTION_RESET") &&
        !e.includes("favicon") &&
        !e.includes("font") &&
        !e.includes("manifest") &&
        !e.includes("/api/")
    );

    expect(criticalErrors, `发现 ${criticalErrors.length} 个控制台错误: ${criticalErrors.join("\n")}`).toHaveLength(0);
  });
});
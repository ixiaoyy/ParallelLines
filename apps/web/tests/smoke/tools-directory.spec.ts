import { mkdir } from "node:fs/promises";
import { resolve } from "node:path";
import { expect, test } from "@playwright/test";

test.beforeEach(async ({ page }) => {
  // 聚合页验证不向后台写入访问统计，工具本身仍通过真实页面和静态资源运行。
  await page.route(url => url.pathname.startsWith("/api/"), route => route.fulfill({ json: { data: null } }));
  await page.goto("/tools");
});

test("聚合页默认列出真实工具，独立工具入口仍可用", async ({ page }) => {
  await expect(page.getByRole("heading", { name: "工具", exact: true })).toBeVisible();
  await expect(page.locator("main article")).toHaveCount(2);
  await expect(page.getByRole("heading", { name: "Excel 公式速查", exact: true })).toBeVisible();
  const beadCard = page.locator("article").filter({ has: page.getByRole("heading", { name: "拼豆图纸生成器", exact: true }) });
  await beadCard.getByRole("link", { name: /打开工具/ }).click();
  await expect(page).toHaveURL(/\/tools\/bead-pattern$/);
  await expect(page.getByRole("img", { name: "拼豆图案画布", exact: true })).toBeVisible();
  await page.getByRole("link", { name: /返回工具/ }).click();
  const excelCard = page.locator("article").filter({ has: page.getByRole("heading", { name: "Excel 公式速查", exact: true }) });
  await excelCard.getByRole("link", { name: /打开工具/ }).click();
  await expect(page).toHaveURL(/\/tools\/excel-formulas/);
});

test("分类与名称用途搜索组合生效，无匹配后可清除恢复", async ({ page }) => {
  const search = page.getByRole("searchbox", { name: "搜索工具名称或用途", exact: true });
  await page.getByRole("button", { name: /^办公/ }).click();
  await expect(page.locator("main article")).toHaveCount(1);
  await expect(page.getByRole("heading", { name: "Excel 公式速查", exact: true })).toBeVisible();
  await search.fill("色号");
  await expect(page.locator("main article")).toHaveCount(0);
  await expect(page.getByText("没有找到匹配的工具。", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "清除筛选", exact: true }).click();
  await expect(search).toHaveValue("");
  await expect(page.locator("main article")).toHaveCount(2);
  await search.fill("  eXcEl  ");
  await expect(page.locator("main article")).toHaveCount(1);
  await expect(page.getByRole("heading", { name: "Excel 公式速查", exact: true })).toBeVisible();
  await search.fill("色号");
  await expect(page.getByRole("heading", { name: "拼豆图纸生成器", exact: true })).toBeVisible();
  await page.getByRole("button", { name: /^创作/ }).click();
  await expect(page.locator("main article")).toHaveCount(1);
  await expect(page.getByRole("button", { name: /^创作/ })).toHaveAttribute("aria-pressed", "true");
});

test("分类筛选支持键盘操作", async ({ page }) => {
  const category = page.getByRole("button", { name: /^创作/ });
  await category.focus();
  await page.keyboard.press("Enter");
  await expect(category).toHaveAttribute("aria-pressed", "true");
  await expect(page.locator("main article")).toHaveCount(1);
  await expect(page.getByRole("heading", { name: "拼豆图纸生成器", exact: true })).toBeVisible();
});

test("工具网格在桌面并排，手机单列且无横向溢出", async ({ page }) => {
  const output = resolve(process.cwd(), "../../.tmp/tools-directory-qa");
  await mkdir(output, { recursive: true });
  for (const width of [320, 390, 1440]) {
    await page.setViewportSize({ width, height: 900 });
    await expect(page.locator("main article")).toHaveCount(2);
    const cards = await page.locator("main article").evaluateAll(elements => elements.map(element => {
      const rect = element.getBoundingClientRect();
      return { top: rect.top, left: rect.left, width: rect.width };
    }));
    if (width === 1440) {
      expect(Math.abs(cards[0].top - cards[1].top)).toBeLessThan(2);
      expect(cards[1].left).toBeGreaterThan(cards[0].left + cards[0].width);
    } else expect(cards[1].top).toBeGreaterThan(cards[0].top);
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width + 1);
    await page.screenshot({ path: resolve(output, `tools-${width}.png`), fullPage: true });
  }
});

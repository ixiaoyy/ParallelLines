import { readFile } from "node:fs/promises";
import { expect, test, type Page } from "@playwright/test";

test.beforeEach(async ({ context, page }) => {
  await context.grantPermissions(["clipboard-read", "clipboard-write"]);
  await page.route(url => url.pathname.startsWith("/api/"), route => route.fulfill({ json: { data: null } }));
  await page.goto("/tools/list-compare");
  // 验证重定向到带 op=compare 的 Excel 工具页面
  await expect(page).toHaveURL(/\/tools\/excel-formulas\?op=compare$/);
  await expect(page.locator("#compare-operator-title")).toBeVisible();
});

async function resultText(page: Page, title: string): Promise<string> {
  const group = page.locator(".list-compare-operator__group").filter({ has: page.getByRole("heading", { name: new RegExp(`^${title}`) }) });
  return (await group.locator("pre").textContent())?.trim() ?? "";
}

test("空名单给出明确提示，示例可核对重复项、空行、中文和前导零", async ({ page }) => {
  await page.getByRole("button", { name: "开始核对", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("名单 A 和名单 B 都还没有内容");
  await expect(page.getByRole("heading", { name: "核对结果", exact: true })).toHaveCount(0);

  await page.getByRole("button", { name: "填入示例", exact: true }).click();
  await expect(page.locator("#compare-list-a-summary")).toHaveText("有效 7 条，已忽略 1 个空行");
  await expect(page.locator("#compare-list-b-summary")).toHaveText("有效 6 条");
  await expect(page.getByText("数据仅在当前浏览器处理，不上传服务器。", { exact: true })).toBeVisible();

  await page.getByRole("button", { name: "开始核对", exact: true }).click();
  expect(await resultText(page, "两边都有")).toBe("李四\n001\n王五");
  expect(await resultText(page, "仅 A 有")).toBe("张三\n张三\nAlice\n1");
  expect(await resultText(page, "仅 B 有")).toBe("002\n赵六\nalice");
  await expect(page.getByRole("heading", { name: "仅 B 有 3 条", exact: true })).toBeVisible();
});

test("去重、忽略英文大小写和单侧空输入按页面规则生效", async ({ page }) => {
  await page.getByLabel("名单 A").fill("张三");
  await page.getByRole("button", { name: "开始核对", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("名单 B 还没有可核对的内容");

  await page.getByRole("button", { name: "填入示例", exact: true }).click();
  await page.getByLabel("去重，相同条目只保留第一次出现").check();
  await expect(page.locator("#compare-list-a-summary")).toHaveText("有效 7 条，已忽略 1 个空行，去重后 6 条");
  await page.getByRole("button", { name: "开始核对", exact: true }).click();
  expect(await resultText(page, "仅 A 有")).toBe("张三\nAlice\n1");

  await page.getByLabel("忽略英文大小写，不影响中文和数字").check();
  await expect(page.getByText("名单或选项已经改过，下面仍是上一次的结果。", { exact: false })).toBeVisible();
  await page.getByRole("button", { name: "开始核对", exact: true }).click();
  expect(await resultText(page, "两边都有")).toBe("李四\n001\n王五\nAlice");
  expect(await resultText(page, "仅 A 有")).toBe("张三\n1");
  expect(await resultText(page, "仅 B 有")).toBe("002\n赵六");
  await expect(page.locator(".list-compare-operator__group").filter({ has: page.getByRole("heading", { name: /^仅 B 有/ }) }).getByText("没有条目")).toHaveCount(0);
});

test("直接粘贴的单列文本保留前导零，复制和下载不改变顺序", async ({ page }) => {
  await page.getByLabel("名单 A").fill("001\n1\n\n  001 \n张三");
  await page.getByLabel("名单 B").fill("001\r\n张三\r\n");
  await expect(page.locator("#compare-list-a-summary")).toHaveText("有效 4 条，已忽略 1 个空行");
  await page.getByRole("button", { name: "开始核对", exact: true }).click();
  expect(await resultText(page, "两边都有")).toBe("001\n张三");
  expect(await resultText(page, "仅 A 有")).toBe("1\n001");
  await expect(page.locator(".list-compare-operator__group").filter({ has: page.getByRole("heading", { name: /^仅 B 有/ }) }).getByText("没有条目", { exact: true })).toBeVisible();

  await page.getByRole("button", { name: "复制两边都有", exact: true }).click();
  await expect.poll(() => page.evaluate(() => navigator.clipboard.readText())).toBe("001\r\n张三");

  const [download] = await Promise.all([
    page.waitForEvent("download"),
    page.getByRole("button", { name: "下载仅 A 有", exact: true }).click(),
  ]);
  expect(download.suggestedFilename()).toBe("仅A有.txt");
  const content = await readFile(await download.path(), "utf8");
  expect(content).toBe("\uFEFF1\r\n001");

  await page.getByRole("button", { name: /^清\s*空$/ }).click();
  await expect(page.getByLabel("名单 A")).toHaveValue("");
  await expect(page.getByRole("heading", { name: "核对结果", exact: true })).toHaveCount(0);
});

test("窄屏可以完成核对且没有横向溢出", async ({ page }) => {
  for (const width of [320, 390]) {
    await page.setViewportSize({ width, height: 800 });
    await page.getByRole("button", { name: "填入示例", exact: true }).click();
    await page.getByRole("button", { name: "开始核对", exact: true }).click();
    expect(await resultText(page, "两边都有")).toBe("李四\n001\n王五");
    const columns = await page.locator(".list-compare-operator__column").evaluateAll(elements => elements.map(element => element.getBoundingClientRect().top));
    expect(columns[1]).toBeGreaterThan(columns[0]);
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width + 1);
  }
});

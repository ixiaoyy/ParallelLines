import { expect, test } from "@playwright/test";

test("瓜体实验室从游乐场进入后可以投放、切换流动性并返回", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));

  await page.goto("/play");
  await page.getByRole("link", { name: /瓜体实验室/ }).click();

  await expect(page).toHaveURL(/\/play\/melon$/);
  await expect(page.locator(".topbar")).toHaveCount(0);
  const game = page.frameLocator('iframe[title="瓜体实验室 · 半流体西瓜游戏"]');
  const canvas = game.locator("#game");
  await expect(canvas).toHaveAttribute("data-phase", "playing");
  await expect(game.locator("#loading")).toBeHidden();

  await game.getByRole("button", { name: "帮助" }).click();
  await expect(game.getByRole("dialog", { name: "一点物理，一点好运" })).toBeVisible();
  await game.getByRole("button", { name: "返回游戏" }).click();

  await game.getByRole("button", { name: "果汁" }).click();
  await expect(game.getByRole("button", { name: "果汁" })).toHaveAttribute("aria-pressed", "true");

  const before = Number(await canvas.getAttribute("data-fruits"));
  await canvas.click({ position: { x: 100, y: 100 } });
  await expect.poll(async () => Number(await canvas.getAttribute("data-fruits"))).toBeGreaterThan(before);

  await game.getByRole("button", { name: "搅动果池" }).click();
  await expect.poll(async () => Number(await game.locator("#energy-value").innerText())).toBeLessThan(100);

  await game.getByRole("button", { name: "暂停" }).click();
  await expect(game.getByRole("dialog", { name: "让果冻歇一会儿" })).toBeVisible();
  await expect(canvas).toHaveAttribute("data-phase", "paused");
  await game.getByRole("button", { name: "继续游戏" }).click();
  await expect(canvas).toHaveAttribute("data-phase", "playing");

  await page.goBack();
  await expect(page).toHaveURL(/\/play$/);
  await expect(page.locator(".topbar")).toBeVisible();
  expect(errors).toEqual([]);
});

test("瓜体实验室在手机宽度显示触屏控制且没有横向溢出", async ({ page }) => {
  for (const width of [320, 390]) {
    await page.setViewportSize({ width, height: 844 });
    await page.goto("/play/melon");

    const game = page.frameLocator('iframe[title="瓜体实验室 · 半流体西瓜游戏"]');
    await expect(game.locator("#game")).toHaveAttribute("data-phase", "playing");
    await expect(game.getByRole("button", { name: "向左倾斜" })).toBeVisible();

    const layout = await game.locator("body").evaluate(() => ({
      width: document.documentElement.scrollWidth,
      viewport: window.innerWidth,
    }));
    expect(layout.width, `${width}px 游戏横向溢出`).toBeLessThanOrEqual(layout.viewport);
    expect(await page.evaluate(() => document.documentElement.scrollWidth), `${width}px 页面横向溢出`)
      .toBeLessThanOrEqual(width);
  }
});

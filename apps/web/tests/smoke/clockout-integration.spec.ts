import { expect, test } from "@playwright/test";

test("准点下班从游乐场进入后可以完成首个目标、暂停并打开地图", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));

  await page.goto("/play");
  await page.getByRole("link", { name: /准点下班/ }).click();

  await expect(page).toHaveURL(/\/play\/clockout$/);
  await expect(page.locator(".topbar")).toHaveCount(0);
  const game = page.frameLocator('iframe[title="准点下班 · 18 关完整版"]');
  await expect(game.locator("#home")).toHaveClass(/show/);
  await expect(game.locator("#level-options > button")).toHaveCount(18);

  await game.locator("#start-btn").click();
  await expect(game.locator("#home")).not.toHaveClass(/show/);
  await expect(game.locator("#goal-btn")).toContainText("拿起背包");

  await page.keyboard.down("e");
  await page.waitForTimeout(450);
  await page.keyboard.up("e");
  await expect(game.locator("#goal-btn")).toContainText("呼叫电梯");

  await game.locator("#pause-btn").click();
  await expect(game.locator("#pause-sheet")).toHaveClass(/show/);
  await game.locator("#resume-btn").click();
  await expect(game.locator("#pause-sheet")).not.toHaveClass(/show/);

  await game.locator("#pause-btn").press("m");
  await expect(game.locator("#map-sheet")).toHaveClass(/show/);
  await game.locator("#map-close").click();

  await page.goBack();
  await expect(page).toHaveURL(/\/play$/);
  await expect(page.locator(".topbar")).toBeVisible();
  expect(errors).toEqual([]);
});

test("准点下班在手机和横屏保持完整布局与触屏操作", async ({ page }) => {
  for (const [width, height] of [[320, 844], [390, 844], [844, 390]]) {
    await page.setViewportSize({ width, height });
    await page.goto("/play/clockout");

    const game = page.frameLocator('iframe[title="准点下班 · 18 关完整版"]');
    await expect(game.locator("#home")).toHaveClass(/show/);
    await game.locator("#start-btn").click();
    await expect(game.locator("#action-btn")).toBeVisible();

    const layout = await game.locator("body").evaluate(() => ({
      width: document.documentElement.scrollWidth,
      viewport: window.innerWidth,
    }));
    expect(layout.width, `${width}×${height} 游戏横向溢出`).toBeLessThanOrEqual(layout.viewport);
    expect(await page.evaluate(() => document.documentElement.scrollWidth), `${width}×${height} 页面横向溢出`)
      .toBeLessThanOrEqual(width);
  }
});

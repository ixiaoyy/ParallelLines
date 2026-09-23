import path from "node:path";

import { expect, test } from "@playwright/test";

const screenshotDir = process.env.GAME_QA_SCREENSHOT_DIR;

test("玩家执将军可跳吃、悔棋并切换皮肤", async ({ page }) => {
  await page.goto("/play");
  await expect(page.locator(".play-gallery > a")).toHaveCount(3);
  if (screenshotDir) await page.screenshot({ path: path.join(screenshotDir, "play-hub-desktop.png"), fullPage: true });
  await page.getByRole("link", { name: /将军战小兵/ }).click();
  await expect(page.getByRole("heading", { name: "将军战小兵" })).toBeVisible();
  if (screenshotDir) await page.screenshot({ path: path.join(screenshotDir, "game-setup-default-desktop.png"), fullPage: true });
  await page.getByRole("button", { name: "游戏规则" }).click();
  await expect(page.getByRole("dialog", { name: "游戏规则" })).toBeVisible();
  await page.getByRole("button", { name: "明白了" }).click();
  await expect(page.getByRole("dialog", { name: "游戏规则" })).toBeHidden();
  await page.getByRole("button", { name: /将军方/ }).click();
  await page.getByRole("button", { name: /困难/ }).click();
  await page.getByRole("button", { name: "科技" }).click();
  await expect(page.locator(".gs-page")).toHaveAttribute("data-theme", "tech");
  if (screenshotDir) await page.screenshot({ path: path.join(screenshotDir, "game-setup-desktop.png"), fullPage: true });

  await page.getByRole("button", { name: /开始对弈/ }).click();
  await page.getByRole("button", { name: "第5行第2列，将军" }).click();
  await expect(page.getByRole("button", { name: "第4行第2列，空格，可落子，跳吃路径" })).toBeVisible();
  await expect(page.locator(".gs-cell__path")).toHaveCount(1);
  await page.getByRole("button", { name: "第3行第2列，小兵，可跳吃" }).click();
  await expect(page.locator(".gs-score")).toContainText("14");
  await page.getByRole("button", { name: "悔棋" }).click();
  await expect(page.locator(".gs-score")).toContainText("15");
  if (screenshotDir) await page.screenshot({ path: path.join(screenshotDir, "game-board-desktop.png"), fullPage: true });
});

test("游乐场卡片在窄屏保持完整且没有横向溢出", async ({ page }) => {
  for (const width of [390, 320]) {
    await page.setViewportSize({ width, height: 844 });
    await page.goto("/play");
    await expect(page.locator(".play-gallery > a")).toHaveCount(3);
    expect(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth)).toBe(false);
    if (screenshotDir) await page.screenshot({ path: path.join(screenshotDir, `play-hub-${width}.png`), fullPage: true });
  }
});

test("手机上能完成设置并保持棋盘不横向溢出", async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 844 });
  await page.goto("/play/generals-soldiers");
  for (const name of ["经典", "中国风", "现代", "自然", "科技"]) {
    await page.getByRole("button", { name }).click();
  }
  await page.getByRole("button", { name: /将军方/ }).click();
  if (screenshotDir) await page.screenshot({ path: path.join(screenshotDir, "game-setup-mobile.png"), fullPage: true });
  await page.getByRole("button", { name: /开始对弈/ }).click();
  await expect(page.locator(".gs-board .gs-cell")).toHaveCount(25);
  await expect(page.getByLabel("棋盘标记说明")).toBeVisible();
  if (screenshotDir) await page.screenshot({ path: path.join(screenshotDir, "game-board-mobile.png"), fullPage: true });
  const hasHorizontalOverflow = await page.evaluate(() => document.documentElement.scrollWidth > innerWidth);
  expect(hasHorizontalOverflow).toBe(false);
});

test("玩家执小兵时电脑先走且棋局返回玩家回合", async ({ page }) => {
  const gameErrors: string[] = [];
  page.on("pageerror", (error) => gameErrors.push(error.message));
  page.on("console", (message) => {
    if (message.type() === "error" && message.text().includes("游戏电脑")) gameErrors.push(message.text());
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/play/generals-soldiers");
  if (screenshotDir) await page.screenshot({ path: path.join(screenshotDir, "game-setup-default-390.png"), fullPage: true });
  await page.getByRole("button", { name: /开始对弈/ }).click();
  await expect(page.locator(".gs-turn")).toHaveText("将军先行 · 电脑准备中");
  if (screenshotDir) await page.screenshot({ path: path.join(screenshotDir, "game-opening-390.png"), fullPage: true });
  await expect(page.locator(".gs-cell--last")).toHaveCount(0);
  await page.waitForTimeout(350);
  await expect(page.locator(".gs-cell--last")).toHaveCount(0);
  await expect(page.locator(".gs-turn")).toHaveText("轮到你走", { timeout: 3_000 });
  await expect(page.locator(".gs-cell--last-from")).toHaveCount(1);
  await expect(page.locator(".gs-cell--last")).toHaveCount(1);
  expect(gameErrors).toEqual([]);
  await expect(page.locator(".gs-board .gs-cell")).toHaveCount(25);
  const cells = page.locator(".gs-board .gs-cell");
  let playerMoved = false;
  for (let index = 0; index < 25; index += 1) {
    if (!(await cells.nth(index).getAttribute("aria-label"))?.includes("小兵")) continue;
    await cells.nth(index).click();
    const destination = page.locator('.gs-cell[aria-label*="可落子"]').first();
    if (await destination.count()) {
      await destination.click();
      playerMoved = true;
      break;
    }
    await cells.nth(index).click();
  }
  expect(playerMoved).toBe(true);
  await expect(page.locator(".gs-turn")).toHaveText("电脑思考中");
  await expect(page.locator(".gs-turn")).toHaveText("轮到你走", { timeout: 3_000 });
  expect(gameErrors).toEqual([]);
  expect(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth)).toBe(false);
  if (screenshotDir) await page.screenshot({ path: path.join(screenshotDir, "game-board-default-390.png"), fullPage: true });
});

import path from "node:path";

import { expect, test } from "@playwright/test";

test.use({ hasTouch: true });
const screenshots = process.env.GAME_QA_SCREENSHOT_DIR;

test("飞球页面实际空格穿圈计分、暂停、重开和最高分保存", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.clock.install();
  await page.goto("/play/flappy-dunk");
  await expect(page.getByRole("heading", { name: /飞翼.*灌篮/ })).toBeVisible();
  const court = page.locator(".flappy-dunk__surface");
  const canvas = court.locator("canvas");
  await page.getByTestId("dunk-start").click();
  await expect(court).toHaveAttribute("data-phase", "running");

  // 用真实空格输入控制第一球，推进浏览器时钟而不注入游戏内部状态。
  await page.clock.runFor(800);
  await canvas.press("Space");
  await page.clock.runFor(550);
  await canvas.press("Space");
  await page.clock.runFor(1100);
  await expect(page.getByTestId("dunk-score")).toHaveText("1");
  await expect(court).toHaveAttribute("data-phase", "running");
  await page.getByRole("button", { name: "暂停", exact: true }).click();
  await page.clock.runFor(5000);
  await expect(court).toHaveAttribute("data-phase", "paused");
  await expect(page.getByTestId("dunk-score")).toHaveText("1");
  if (screenshots) await page.screenshot({ path: path.join(screenshots, "dunk-desktop.png"), fullPage: true });

  await page.getByRole("button", { name: "继续游戏", exact: true }).first().click();
  await expect(court).toHaveAttribute("data-phase", "running");
  await page.getByRole("button", { name: "重新开始", exact: true }).click();
  await expect(court).toHaveAttribute("data-phase", "ready");
  await expect(page.getByTestId("dunk-score")).toHaveText("0");
  expect(await page.evaluate(() => localStorage.getItem("parallellines.flappy-dunk.best.v1"))).toBe("1");
  await page.reload();
  await expect(page.locator(".flappy-dunk__scoreboard").getByText("1", { exact: true })).toHaveCount(1);
  expect(errors).toEqual([]);
});

test("飞球页面在手机宽度可触屏起跳且没有横向溢出", async ({ page }) => {
  await page.clock.install();
  for (const width of [320, 390]) {
    await page.setViewportSize({ width, height: 844 });
    await page.goto("/play/flappy-dunk");
    const court = page.locator(".flappy-dunk__surface");
    const canvas = court.locator("canvas");
    await canvas.scrollIntoViewIfNeeded();
    const rect = await canvas.boundingBox();
    expect(rect).not.toBeNull();
    if (!rect) throw new Error("canvas rectangle unavailable");
    await page.touchscreen.tap(rect.x + rect.width * 0.25, rect.y + rect.height * 0.25);
    await expect(court).toHaveAttribute("data-phase", "running");
    await page.getByRole("button", { name: "暂停", exact: true }).click();
    await page.locator(".flappy-dunk__dialog").getByRole("button", { name: "继续游戏", exact: true }).click();
    await page.clock.runFor(10_000);
    await expect(court).toHaveAttribute("data-phase", "over");
    const restart = page.getByTestId("dunk-restart");
    // 比较实际文字与按钮的中心，避免只检查 CSS 声明而漏掉样式覆盖。
    const offset = await restart.evaluate((button) => {
      const range = document.createRange();
      range.selectNodeContents(button.querySelector("span")!);
      const text = range.getBoundingClientRect();
      const rect = button.getBoundingClientRect();
      return Math.abs(text.x + text.width / 2 - rect.x - rect.width / 2);
    });
    expect(offset).toBeLessThanOrEqual(1);
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width);
    if (screenshots) await page.screenshot({ path: path.join(screenshots, `dunk-${width}.png`), fullPage: true });
  }
});

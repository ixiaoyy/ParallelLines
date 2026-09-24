import { expect, test } from "@playwright/test";

test("游乐场在当前页面打开小鱼游戏，保留游玩与浏览器返回", async ({ page }) => {
  await page.goto("/play");
  await page.getByRole("link", { name: /平行消消乐/ }).click();

  await expect(page).toHaveURL(/\/play\/match3$/);
  await expect(page.locator(".topbar")).toHaveCount(0);
  await expect(page.getByRole("navigation")).toHaveCount(0);
  await expect(page.locator(".ambient-surface")).toBeVisible();
  await expect(page.locator(".fish-piece")).toHaveCount(9);
  await expect(page.getByRole("group", { name: "游戏设置" })).toBeVisible();

  const fish = page.locator(".fish-piece").first();
  await expect(fish).toBeEnabled();
  await fish.click();
  await expect.poll(() => page.locator(".fish-tray img").count()).toBeGreaterThan(0);
  await expect.poll(() => page.evaluate(() =>
    window.localStorage.getItem("parallellines.match3.ambient-state"),
  )).not.toBeNull();

  await page.goBack();
  await expect(page).toHaveURL(/\/play$/);
  await expect(page.locator(".topbar")).toBeVisible();
});

test("小鱼游戏在手机、横屏和桌面完整呈现", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));

  for (const [width, height] of [[320, 568], [390, 844], [844, 390], [1440, 900]]) {
    await page.setViewportSize({ width, height });
    await page.goto("/play/match3");
    await expect(page.locator(".fish-piece")).toHaveCount(9);
    const layout = await page.evaluate(() => ({
      width: document.documentElement.scrollWidth,
      height: document.documentElement.scrollHeight,
      brokenImages: [...document.images].filter((image) => image.complete && image.naturalWidth === 0).length,
      minimumFishTarget: Math.min(...[...document.querySelectorAll(".fish-piece")]
        .map((fish) => fish.getBoundingClientRect().width)),
    }));
    expect(layout.width, `${width}×${height} 横向溢出`).toBeLessThanOrEqual(width);
    expect(layout.height, `${width}×${height} 纵向溢出`).toBeLessThanOrEqual(height);
    expect(layout.brokenImages, `${width}×${height} 图片`).toBe(0);
    expect(layout.minimumFishTarget, `${width}×${height} 点鱼区域`).toBeGreaterThanOrEqual(44);
  }

  expect(errors).toEqual([]);
});

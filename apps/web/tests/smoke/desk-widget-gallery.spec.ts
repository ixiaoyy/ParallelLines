import { expect, test, type Page } from "@playwright/test";

// 使用本地 Desk 的 /desk/ 构建预览，不连接生产或真实天气服务。
test.use({ baseURL: "http://127.0.0.1:15224", locale: "zh-CN", serviceWorkers: "block" });

function dialog(page: Page) {
  return page.getByRole("dialog", { name: "添加组件" });
}

async function openGallery(page: Page) {
  await page.locator(".desk-quick-bar").getByRole("button", { name: "添加组件", exact: true }).click();
  await expect(dialog(page).getByRole("textbox", { name: "搜索组件" })).toBeFocused();
}

async function setup(page: Page) {
  const requests: string[] = [];
  await page.route("**/*", route => {
    const url = route.request().url();
    if (url.startsWith("http://127.0.0.1:15224/")) return route.continue();
    requests.push(url);
    return route.abort();
  });
  await page.goto("/desk/");
  return requests;
}

async function savedWidget(page: Page, material: string) {
  return page.evaluate((name) => {
    const data = JSON.parse(localStorage.getItem("config") ?? "{}");
    return [...(data.list ?? []), ...(data.affix ?? [])].find(item => item.material === name);
  }, material);
}

test("搜索、键盘关闭和栅格比例；添加后圆角 0 可刷新并再次编辑", async ({ page }, info) => {
  await setup(page);
  await openGallery(page);
  const gallery = dialog(page);
  for (const name of ["基础搜索栏", "自定义倒计时", "导航收藏页"]) {
    await expect(gallery.getByRole("button", { name: new RegExp(name) })).toBeVisible();
  }
  const query = gallery.getByRole("textbox", { name: "搜索组件" });
  await query.fill("查无此组件");
  await expect(gallery.getByRole("status")).toHaveText("没有匹配的组件");
  await gallery.getByRole("button", { name: "清空搜索" }).click();
  await expect(query).toHaveValue("");
  await expect(query).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(gallery).toBeHidden();
  await expect(page.locator(".desk-quick-bar").getByRole("button", { name: "添加组件", exact: true })).toBeFocused();

  await openGallery(page);
  await gallery.getByRole("button", { name: /占位区块/ }).click();
  const preview = gallery.locator(".preview-card-shell");
  // 读取比例计算出的目标高度，避免前一个组件的尺寸过渡影响测量。
  const height = () => preview.evaluate(el => Number.parseFloat((el as HTMLElement).style.height));
  await expect.poll(height).toBeGreaterThan(0);
  const initial = await height();
  await gallery.getByRole("spinbutton", { name: "高度" }).fill("4");
  await expect.poll(height).toBeGreaterThan(initial + 12);
  const add = gallery.getByRole("button", { name: "添加到桌面" });
  await gallery.getByRole("spinbutton", { name: "宽度" }).fill("13");
  await expect(add).toBeDisabled();
  await gallery.getByRole("spinbutton", { name: "宽度" }).fill("6");
  await gallery.getByRole("textbox", { name: "自定义文本" }).fill("栅格回归");
  await gallery.getByRole("button", { name: "外观" }).click();
  const radius = gallery.getByRole("spinbutton", { name: "圆角" });
  await radius.fill("0");
  await radius.evaluate(el => el.scrollIntoView({ block: "center" }));
  await page.screenshot({ path: info.outputPath("widget-gallery-desktop.png"), animations: "disabled" });
  await add.click();
  await expect.poll(() => savedWidget(page, "Empty")).toMatchObject({
    position: 1, w: 6, h: 4, borderRadius: 0, componentSetting: { customText: "栅格回归" },
  });

  await page.reload();
  const widget = page.locator(".grid-item-Empty .item-content");
  await expect(widget).toHaveText("栅格回归");
  await expect(widget).toHaveCSS("border-radius", "0px");
  await page.getByRole("button", { name: /编辑$/ }).click();
  await widget.click({ button: "right" });
  await page.getByText("组件编辑", { exact: true }).click();
  await expect(page.getByPlaceholder("可配置显示自定义文本")).toHaveValue("栅格回归");
});

test("天气、闹钟只读预览；固定草稿交给完整配置后保留右下锚点", async ({ page }) => {
  const requests = await setup(page);
  await openGallery(page);
  const gallery = dialog(page);
  await gallery.getByRole("button", { name: /天气/ }).click();
  await expect(gallery.getByText("天气示例", { exact: true })).toBeVisible();
  expect(requests.some(url => url.includes("open-meteo.com"))).toBe(false);
  expect(await savedWidget(page, "WeatherCard")).toBeUndefined();
  await gallery.getByRole("button", { name: /闹钟与定时/ }).click();
  await expect(gallery.getByText("定时器示例 · 未启动")).toBeVisible();
  await expect(gallery.locator(".alarm-card")).toHaveCount(0);
  await gallery.getByRole("button", { name: "固定", exact: true }).click();
  await gallery.getByRole("spinbutton", { name: "宽度" }).fill("360");
  await gallery.getByRole("spinbutton", { name: "高度" }).fill("220");
  await gallery.getByRole("button", { name: "高级设置" }).click();
  await gallery.getByLabel("固定锚点").selectOption("4");
  await gallery.getByRole("spinbutton", { name: "距右" }).fill("18");
  await gallery.getByRole("spinbutton", { name: "距下" }).fill("20");
  await gallery.getByRole("button", { name: "打开完整配置" }).click();
  await expect(gallery).toBeHidden();
  const legacy = page.locator(".easy-dialog-main").filter({ hasText: "添加组件" });
  await legacy.getByRole("button", { name: "确认", exact: true }).click();
  await expect.poll(() => savedWidget(page, "AlarmTimer")).toMatchObject({
    position: 2, w: 360, h: 220, affixInfo: { mode: 4, x: 18, y: 20 },
  });
  await page.reload();
  const widget = page.locator(".affix-item").filter({ has: page.locator(".alarm-card") });
  await expect(widget).toHaveCSS("right", "18px");
  await expect(widget).toHaveCSS("bottom", "20px");
});

test("窄屏展开设置后，添加按钮仍在屏幕内可操作", async ({ page }, info) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await setup(page);
  await openGallery(page);
  const gallery = dialog(page);
  await gallery.getByRole("button", { name: /占位区块/ }).click();
  await gallery.getByRole("button", { name: "高级设置" }).click();
  const add = gallery.getByRole("button", { name: "添加到桌面" });
  await expect(add).toBeInViewport({ ratio: 1 });
  await page.screenshot({ path: info.outputPath("widget-gallery-mobile.png"), animations: "disabled" });
  await page.setViewportSize({ width: 320, height: 700 });
  await expect(add).toBeInViewport({ ratio: 1 });
  await add.click();
  await expect(gallery).toBeHidden();
  await expect.poll(() => savedWidget(page, "Empty")).toMatchObject({ position: 1 });
});

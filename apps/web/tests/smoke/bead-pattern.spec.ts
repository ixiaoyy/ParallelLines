import { mkdir, readFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { expect, test, type BrowserContext, type Download, type Page } from "@playwright/test";

const baseURL = process.env.PLAYWRIGHT_BASE_URL ?? "http://127.0.0.1:5173";
const screenshotDir = resolve(dirname(fileURLToPath(import.meta.url)), "../../../../.tmp/bead-qa");
const pngSignature = Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]);

/** 使用真实页面和本地素材，拦截后台及站外请求，避免验收产生访问统计写入。 */
async function isolateLocalTool(context: BrowserContext): Promise<void> {
  const origin = new URL(baseURL).origin;
  await context.route("**/*", async (route) => {
    const url = new URL(route.request().url());
    if (url.pathname.startsWith("/api/")) {
      await route.fulfill({ json: { data: null } });
    } else if (url.origin !== origin) {
      await route.abort();
    } else {
      await route.continue();
    }
  });
}

/** 从用户实际看到的材料表读取色号和颗数，不读取 Vue 状态或调用生产算法。 */
async function readMaterials(page: Page): Promise<Record<string, number>> {
  const disclosure = page.locator("details").filter({ has: page.locator('table[aria-label="材料清单"]') });
  if (await disclosure.getAttribute("open") === null) await disclosure.locator("summary").click();
  return page.getByRole("table", { name: "材料清单", exact: true }).locator("tbody tr").evaluateAll((rows) => {
    const result: Record<string, number> = {};
    for (const row of rows) {
      const cells = Array.from(row.querySelectorAll("td"));
      const code = cells[1]?.textContent?.trim().match(/^SE?\d{2,3}$/)?.[0];
      const count = Number(cells.at(-1)?.textContent?.replace(/[^\d]/g, ""));
      if (code && Number.isFinite(count)) result[code] = count;
    }
    return result;
  });
}

/** 等待真实异步生成完成，确保后续编辑与导出使用新图纸。 */
async function generate(page: Page): Promise<void> {
  const button = page.getByRole("button", { name: "生成图纸", exact: true });
  await button.click();
  await expect(button).toBeEnabled();
  await expect(page.getByRole("img", { name: "拼豆图案画布", exact: true })).toBeVisible();
  await page.evaluate(() => new Promise<void>((resolve) => requestAnimationFrame(() => requestAnimationFrame(() => resolve()))));
}

/** 独立构造已知答案：8×8，白豆32格、橙豆16格、透明空格16格。 */
async function createFixture(page: Page): Promise<Buffer> {
  const base64 = await page.evaluate(() => {
    const canvas = document.createElement("canvas");
    canvas.width = 8;
    canvas.height = 8;
    const context = canvas.getContext("2d")!;
    context.fillStyle = "#ffffff";
    context.fillRect(0, 0, 8, 4);
    context.fillStyle = "#ff8200";
    context.fillRect(0, 4, 4, 4);
    return canvas.toDataURL("image/png").split(",")[1];
  });
  return Buffer.from(base64, "base64");
}

/** 经文件选择入口导入已知图案，并以8格输出验证白豆与透明空格。 */
async function loadFixture(page: Page): Promise<void> {
  await expect(page.getByRole("button", { name: "生成图纸", exact: true })).toBeEnabled();
  await page.locator('input[type="file"]').setInputFiles({
    name: "known-beads.png",
    mimeType: "image/png",
    buffer: await createFixture(page),
  });
  await expect(page.getByRole("heading", { name: "known-beads.png", exact: true })).toBeVisible();
  await page.getByRole("spinbutton", { name: "图纸长边格数", exact: true }).fill("8");
  await page.getByRole("combobox", { name: "最多颜色数", exact: true }).selectOption("8");
  await generate(page);
  await expect.poll(() => readMaterials(page)).toEqual({ S01: 32, S03: 16 });
}

/** 找到画布上真实绘出的橙格再点击，避免依赖生产渲染的边距或格子尺寸常量。 */
async function eraseOneOrangeCell(page: Page): Promise<void> {
  await page.getByRole("button", { name: "编号图纸", exact: true }).click();
  await page.getByRole("button", { name: /橡皮$/ }).click();
  await page.evaluate(() => new Promise<void>((resolve) => requestAnimationFrame(() => requestAnimationFrame(() => resolve()))));
  const canvas = page.getByRole("img", { name: "拼豆图案画布", exact: true });
  const point = await canvas.evaluate((element) => {
    const image = element as HTMLCanvasElement;
    const context = image.getContext("2d")!;
    const pixels = context.getImageData(0, 0, image.width, image.height).data;
    for (let y = 2; y < image.height - 2; y += 1) {
      for (let x = 2; x < image.width - 2; x += 1) {
        const isOrange = (pixelX: number, pixelY: number) => {
          const index = (pixelY * image.width + pixelX) * 4;
          return pixels[index] === 255 && pixels[index + 1] === 130
            && pixels[index + 2] === 0 && pixels[index + 3] === 255;
        };
        if (isOrange(x, y) && isOrange(x - 2, y) && isOrange(x + 2, y)
          && isOrange(x, y - 2) && isOrange(x, y + 2)) {
          const bounds = image.getBoundingClientRect();
          return { x: x * bounds.width / image.width, y: y * bounds.height / image.height };
        }
      }
    }
    throw new Error("测试图纸未显示预期的 S03 橙色格子");
  });
  await canvas.click({ position: point });
  await expect.poll(() => readMaterials(page)).toEqual({ S01: 32, S03: 15 });
}

/** 读取浏览器实际下载内容，防止只有下载按钮而没有有效产物。 */
async function readDownload(download: Download): Promise<Buffer> {
  expect(await download.failure()).toBeNull();
  const path = await download.path();
  expect(path).not.toBeNull();
  return readFile(path!);
}

test.beforeEach(async ({ context }) => {
  await isolateLocalTool(context);
});

test("从工具目录进入，默认示例可用，人像转换遵守格数和限色设置", async ({ page }) => {
  await page.goto("/tools");
  const card = page.locator("article").filter({ has: page.getByRole("heading", { name: "拼豆图纸生成器", exact: true }) });
  await card.getByRole("link", { name: /打开工具/ }).click();
  await expect(page).toHaveURL(/\/tools\/bead-pattern$/);
  await expect(page.getByRole("heading", { name: "拼豆图纸生成器", exact: true })).toBeVisible();
  await expect(page.getByRole("img", { name: "拼豆图案画布", exact: true })).toBeVisible();
  await expect.poll(async () => Object.keys(await readMaterials(page)).length).toBeGreaterThan(0);
  const simple = await readMaterials(page);
  expect(Object.keys(simple).length).toBeLessThanOrEqual(8);
  expect(Object.values(simple).reduce((sum, count) => sum + count, 0)).toBeLessThan(32 * 32);

  await page.getByRole("button", { name: "体验人像", exact: true }).click();
  await page.getByRole("spinbutton", { name: "图纸长边格数", exact: true }).fill("64");
  await page.getByRole("combobox", { name: "最多颜色数", exact: true }).selectOption("24");
  await generate(page);
  await expect.poll(async () => Object.values(await readMaterials(page)).reduce((sum, count) => sum + count, 0)).toBe(64 * 64);
  const portrait = await readMaterials(page);
  expect(Object.keys(portrait).length).toBeLessThanOrEqual(24);
  expect(Object.keys(portrait).length).toBeGreaterThan(2);
  await mkdir(screenshotDir, { recursive: true });
  await page.screenshot({ path: resolve(screenshotDir, "bead-portrait.png"), fullPage: true });
  await page.getByRole("button", { name: "原图", exact: true }).click();
  await expect(page.getByRole("button", { name: "原图", exact: true })).toHaveAttribute("aria-pressed", "true");
  await page.getByRole("button", { name: "效果图", exact: true }).click();
  await expect(page.getByRole("img", { name: "拼豆图案画布", exact: true })).toBeVisible();
});

test("白豆与透明空格分开统计，真实擦除与撤销同步更新最终用量", async ({ page }) => {
  await page.goto("/tools/bead-pattern");
  await loadFixture(page);
  await eraseOneOrangeCell(page);
  await page.getByRole("button", { name: /撤销$/ }).click();
  await expect.poll(() => readMaterials(page)).toEqual({ S01: 32, S03: 16 });

  // 一次鼠标移动跨过八格，要求连续擦除整行，并以一次操作撤销。
  await page.getByRole("button", { name: "效果图", exact: true }).click();
  await page.getByRole("button", { name: /橡皮$/ }).click();
  await page.evaluate(() => new Promise<void>((resolve) => requestAnimationFrame(() => requestAnimationFrame(() => resolve()))));
  const canvas = page.getByRole("img", { name: "拼豆图案画布", exact: true });
  await canvas.scrollIntoViewIfNeeded();
  const box = await canvas.boundingBox();
  expect(box).not.toBeNull();
  const y = box!.y + box!.height / 16;
  await page.mouse.move(box!.x + box!.width / 16, y);
  await page.mouse.down();
  await page.mouse.move(box!.x + box!.width * 15 / 16, y, { steps: 1 });
  await page.mouse.up();
  await expect.poll(() => readMaterials(page)).toEqual({ S01: 24, S03: 16 });
  await page.getByRole("button", { name: /撤销$/ }).click();
  await expect.poll(() => readMaterials(page)).toEqual({ S01: 32, S03: 16 });
});

test("下载图纸和效果图为真实 PNG，CSV 与编辑后网格一致且不上传文件", async ({ page }) => {
  await page.goto("/tools/bead-pattern");
  await expect(page.getByRole("img", { name: "拼豆图案画布", exact: true })).toBeVisible();
  const mutations: string[] = [];
  page.on("request", (request) => {
    if (["POST", "PUT", "PATCH", "DELETE"].includes(request.method())) mutations.push(request.url());
  });
  await loadFixture(page);
  await eraseOneOrangeCell(page);

  const csvPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: "导出材料清单", exact: true }).click();
  const csvDownload = await csvPromise;
  expect(csvDownload.suggestedFilename()).toMatch(/\.csv$/);
  const csv = (await readDownload(csvDownload)).toString("utf8");
  expect(csv.startsWith("\uFEFF")).toBe(true);
  const rows = [...csv.matchAll(/^"Artkal S 系列 5 mm","(SE?\d{2,3})","#[0-9a-fA-F]{6}","(\d+)"$/gm)];
  const exported = Object.fromEntries(rows.map((row) => [row[1], Number(row[2])]));
  expect(exported).toEqual({ S01: 32, S03: 15 });
  expect(exported).toEqual(await readMaterials(page));
  expect(csv).toContain('"合计","","","47"');

  const previewPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: "下载效果图", exact: true }).click();
  const preview = await readDownload(await previewPromise);
  expect(preview.subarray(0, 8)).toEqual(pngSignature);
  const pixelCounts = await page.evaluate(async (base64) => {
    const image = new Image();
    image.src = `data:image/png;base64,${base64}`;
    await image.decode();
    const canvas = document.createElement("canvas");
    canvas.width = image.naturalWidth;
    canvas.height = image.naturalHeight;
    const context = canvas.getContext("2d")!;
    context.drawImage(image, 0, 0);
    const counts = { white: 0, orange: 0, empty: 0, other: 0 };
    for (let row = 0; row < 8; row += 1) {
      for (let column = 0; column < 8; column += 1) {
        const [r, g, b, alpha] = context.getImageData(
          Math.floor((column + 0.5) * canvas.width / 8),
          Math.floor((row + 0.5) * canvas.height / 8), 1, 1,
        ).data;
        if (alpha === 0) counts.empty += 1;
        else if (r === 255 && g === 255 && b === 255) counts.white += 1;
        else if (r === 255 && g === 130 && b === 0) counts.orange += 1;
        else counts.other += 1;
      }
    }
    return counts;
  }, preview.toString("base64"));
  expect(pixelCounts).toEqual({ white: 32, orange: 15, empty: 17, other: 0 });

  const chartPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: /下载图纸$/ }).click();
  const chart = await readDownload(await chartPromise);
  expect(chart.subarray(0, 8)).toEqual(pngSignature);
  expect(chart.readUInt32BE(16)).toBeGreaterThan(preview.readUInt32BE(16));
  expect(chart.readUInt32BE(20)).toBeGreaterThan(preview.readUInt32BE(20));
  expect(mutations).toEqual([]);
});

test("精确取景使用裁剪后的比例和颜色，恢复整图可找回透明空格", async ({ page }) => {
  await page.goto("/tools/bead-pattern");
  await loadFixture(page);
  await page.getByText("裁剪图片（可选）", { exact: true }).click();
  await page.getByText("精确调整取景", { exact: true }).click();
  const width = page.getByRole("spinbutton", { name: "取景宽度百分比", exact: true });
  await width.fill("50");
  await width.press("Tab");
  await generate(page);
  await expect.poll(() => readMaterials(page)).toEqual({ S01: 16, S03: 16 });
  await expect(page.getByText(/4\s*×\s*8/).first()).toBeVisible();
  await page.getByRole("button", { name: "保留整图", exact: true }).click();
  await generate(page);
  await expect.poll(() => readMaterials(page)).toEqual({ S01: 32, S03: 16 });
});

test("错误文件展示已确认提示，保留已有图纸并允许重新选择有效图片", async ({ page }) => {
  await page.goto("/tools/bead-pattern");
  await loadFixture(page);
  const input = page.locator('input[type="file"]');
  await input.setInputFiles({ name: "invalid.txt", mimeType: "text/plain", buffer: Buffer.from("not an image") });
  await expect(page.getByText("请选择 JPG、PNG 或 WebP 图片。", { exact: true })).toBeVisible();
  expect(await readMaterials(page)).toEqual({ S01: 32, S03: 16 });

  await input.setInputFiles({ name: "broken.png", mimeType: "image/png", buffer: Buffer.from("broken png data") });
  await expect(page.getByText("无法读取这张图片，请换一张图片重试。", { exact: true })).toBeVisible();
  await input.setInputFiles({ name: "large.png", mimeType: "image/png", buffer: Buffer.alloc(10 * 1024 * 1024 + 1) });
  await expect(page.getByText("图片不能超过 10 MB，请压缩后重试。", { exact: true })).toBeVisible();
  await loadFixture(page);
  await expect(page.getByText("图片不能超过 10 MB，请压缩后重试。", { exact: true })).toHaveCount(0);
});

test("A4 打印预览分块覆盖整张图纸，图块图片和末页材料清单均可用", async ({ page }) => {
  // 只拦截系统打印调用，继续执行生产打印页的生成、分页和图片加载。
  await page.addInitScript(() => { window.print = () => { document.documentElement.dataset.printRequested = "true"; }; });
  await page.goto("/tools/bead-pattern");
  await loadFixture(page);
  await page.getByRole("spinbutton", { name: "图纸长边格数", exact: true }).fill("64");
  await generate(page);
  await page.getByRole("button", { name: "打印 / 另存 PDF", exact: true }).click();
  const frame = page.frameLocator('iframe[title="拼豆图纸打印预览"]');
  await expect(frame.locator("html")).toHaveAttribute("data-print-requested", "true");
  const regions = await frame.locator("section").evaluateAll((sections) => sections.flatMap((section) => {
    const match = section.textContent?.match(/列\s+(\d+)–(\d+)\s*\/\s*行\s+(\d+)–(\d+)/);
    return match ? [{ left: Number(match[1]), right: Number(match[2]), top: Number(match[3]), bottom: Number(match[4]) }] : [];
  }));
  expect(regions.length).toBeGreaterThan(1);
  const covered = new Set<string>();
  for (const region of regions) {
    for (let row = region.top; row <= region.bottom; row += 1) {
      for (let column = region.left; column <= region.right; column += 1) {
        const cell = `${column},${row}`;
        expect(covered.has(cell)).toBe(false);
        expect(column).toBeGreaterThanOrEqual(1);
        expect(column).toBeLessThanOrEqual(64);
        expect(row).toBeGreaterThanOrEqual(1);
        expect(row).toBeLessThanOrEqual(64);
        covered.add(cell);
      }
    }
  }
  expect(covered.size).toBe(64 * 64);
  expect(await frame.locator("img").evaluateAll((images) => images.every((image) => image.complete && image.naturalWidth > 0))).toBe(true);
  await expect(frame.getByRole("heading", { name: /材料清单/ })).toBeVisible();
  const materialText = await frame.getByRole("table").textContent();
  expect(materialText).toContain("S01");
  expect(materialText).toContain("S03");
});

test("手机与桌面无全页横向溢出，大图在工作区内滚动且键盘可操作", async ({ page }) => {
  await mkdir(screenshotDir, { recursive: true });
  for (const width of [320, 390, 1440]) {
    await page.setViewportSize({ width, height: 900 });
    await page.goto("/tools/bead-pattern");
    await expect(page.getByRole("img", { name: "拼豆图案画布", exact: true })).toBeVisible();
    await page.getByRole("button", { name: "编号图纸", exact: true }).click();
    await page.evaluate(() => new Promise<void>((resolve) => requestAnimationFrame(() => requestAnimationFrame(() => resolve()))));
    const dimensions = await page.evaluate(() => ({ viewport: window.innerWidth, content: document.documentElement.scrollWidth }));
    expect(dimensions.content).toBeLessThanOrEqual(dimensions.viewport + 1);
    if (width < 500) {
      const area = page.getByLabel("图纸工作区", { exact: true });
      expect(await area.evaluate((element) => element.scrollWidth)).toBeGreaterThan(await area.evaluate((element) => element.clientWidth));
      await area.evaluate((element) => { element.scrollLeft = 100; });
      expect(await area.evaluate((element) => element.scrollLeft)).toBeGreaterThan(0);
    }
    const button = page.getByRole("button", { name: "效果图", exact: true });
    await button.focus();
    await expect(button).toBeFocused();
    await page.keyboard.press("Enter");
    await expect(button).toHaveAttribute("aria-pressed", "true");
    await page.screenshot({ path: resolve(screenshotDir, `bead-${width}.png`), fullPage: true });
    if (width === 1440) {
      // 最大格数仍要实际放大编号图纸，缩放仅改变显示尺寸，不能改变材料数量。
      await page.getByRole("spinbutton", { name: "图纸长边格数", exact: true }).fill("128");
      await generate(page);
      const originalMaterials = await readMaterials(page);
      await page.getByRole("button", { name: "编号图纸", exact: true }).click();
      await page.evaluate(() => new Promise<void>((resolve) => requestAnimationFrame(() => requestAnimationFrame(() => resolve()))));
      const canvas = page.getByRole("img", { name: "拼豆图案画布", exact: true });
      const initialWidth = await canvas.evaluate((element) => element.getBoundingClientRect().width);
      const bufferWidth = await canvas.evaluate((element) => (element as HTMLCanvasElement).width);
      await page.getByRole("combobox", { name: "图纸缩放", exact: true }).selectOption("200");
      await expect.poll(() => canvas.evaluate((element) => element.getBoundingClientRect().width)).toBeGreaterThan(initialWidth * 1.8);
      expect(await canvas.evaluate((element) => (element as HTMLCanvasElement).width)).toBe(bufferWidth);
      expect(await readMaterials(page)).toEqual(originalMaterials);
      expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width + 1);
    }
  }
});

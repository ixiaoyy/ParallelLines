import { test, expect } from "@playwright/test";
import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";

const phase = process.env.CATALOG_RESPONSIVE_PHASE ?? "after";
const origin = process.env.PLAYWRIGHT_BASE_URL ?? "http://127.0.0.1:5202";
const output = process.env.CATALOG_RESPONSIVE_OUTPUT;

for (const width of [1920, 1440, 390]) {
  test(`category density and art bounds at ${width}px`, async ({ page, context }, testInfo) => {
    test.setTimeout(120_000);
    await page.setViewportSize({ width, height: width < 700 ? 844 : 1080 });
    await page.emulateMedia({ reducedMotion: "reduce" });
    await context.route("**/*", async (route) => {
      if (!["GET", "HEAD"].includes(route.request().method())) return route.abort();
      await route.continue();
    });
    await page.goto(new URL("/games", origin).href);
    await expect(page.locator("[data-category-section='horror']")).toBeVisible();
    await page.evaluate(async () => { await document.fonts.ready; });
    const folder = output ?? testInfo.outputDir;
    await mkdir(folder, { recursive: true });
    const rows = [];
    for (const key of ["casual", "horror", "exploration", "farming"]) {
      const section = page.locator(`[data-category-section='${key}']`);
      await section.scrollIntoViewIfNeeded();
      await expect.poll(() => section.locator(".catalog-card img").first().evaluate((img: HTMLImageElement) => img.complete && img.naturalWidth > 0)).toBe(true);
      await expect.poll(() => section.locator(".catalog-category-art img").evaluate((img: HTMLImageElement) => img.complete && img.naturalWidth > 0)).toBe(true);
      await page.mouse.move(0, 0);
      const row = await section.evaluate((element) => {
        const rail = element.querySelector(".catalog-category-rail__viewport")!;
        const rect = rail.getBoundingClientRect();
        const box = element.getBoundingClientRect();
        const header = element.querySelector("header")!.getBoundingClientRect();
        const art = element.querySelector(".catalog-category-art")!.getBoundingClientRect();
        const cards = [...element.querySelectorAll(".catalog-card")].map((card) => {
          const b = card.getBoundingClientRect();
          return { width: b.width, height: b.height, x: b.x, right: b.right, id: card.getAttribute("data-project-id") };
        });
        return { key: element.getAttribute("data-category-section"), sectionWidth: box.width, railWidth: rect.width, headerHeight: header.height, artTopFromSection: art.top - box.top, artBottomFromHeader: art.bottom - header.bottom, completeVisible: cards.filter((c) => c.x >= rect.x - 1 && c.right <= rect.right + 1).length, totalCards: cards.length, firstCards: cards.slice(0, 8), nextArrow: !!element.querySelector(".catalog-category-rail__arrow--next") };
      });
      rows.push(row);
      await section.screenshot({ path: path.join(folder, `${phase}-${width}-${key}.png`) });
    }
    const environment = await page.evaluate(() => ({ innerWidth, innerHeight, clientWidth: document.documentElement.clientWidth, scrollWidth: document.documentElement.scrollWidth, pixelRatio: devicePixelRatio, visualScale: visualViewport?.scale, wrap: document.querySelector(".catalog-page__wrap")!.getBoundingClientRect().width, sidebar: getComputedStyle(document.querySelector(".catalog-page")!).getPropertyValue("--catalog-rail-width"), resources: performance.getEntriesByType("resource").map((e) => e.name).filter((url) => /CatalogHomePage-.*\.(js|css)/.test(url)) }));
    await writeFile(path.join(folder, `${phase}-${width}-metrics.json`), JSON.stringify({ environment, rows }, null, 2));
    expect(environment.scrollWidth).toBeLessThanOrEqual(environment.clientWidth);
    if (phase === "after") {
      for (const row of rows) expect(row.artTopFromSection, `${row.key} illustration stays inside its title band`).toBeGreaterThanOrEqual(0);
      expect(rows[1]!.totalCards).toBe(3);
      expect(rows[1]!.firstCards.every((c) => c.width <= 220)).toBe(true);
      expect(rows[3]!.firstCards[0]!.width).toBeLessThanOrEqual(340);
      expect(rows[3]!.nextArrow).toBe(false);
      expect(rows[2]!.completeVisible).toBeGreaterThanOrEqual(width >= 1800 ? 7 : width >= 1200 ? 5 : 2);
      await page.evaluate(() => scrollTo({ top: 0, behavior: "instant" }));
      await expect.poll(() => page.evaluate(() => scrollY)).toBe(0);
      await page.screenshot({ path: path.join(folder, `${phase}-${width}-viewport.png`) });
    }
  });
}

test("all nonempty categories have sparse safe accents and art", async ({ page }) => {
  test.skip(phase === "before");
  test.setTimeout(120_000);
  await page.goto(new URL("/games", origin).href);
  await expect(page.locator("[data-category-section]").first()).toBeVisible();
  const rows = [];
  for (const width of [1920, 390]) {
    await page.setViewportSize({ width, height: 1080 });
    for (const section of await page.locator("[data-category-section]").all()) {
      await section.scrollIntoViewIfNeeded();
      const value = await section.evaluate((element) => {
        const header = element.querySelector("header")!.getBoundingClientRect();
        const art = element.querySelector(".catalog-category-art")!.getBoundingClientRect();
        const controls = [...element.querySelectorAll("header h2, header .catalog-group__meta, header .catalog-group__description")].map((e) => e.getBoundingClientRect());
        const micros = [...element.querySelectorAll(".catalog-micro-accents__item")].filter((e) => getComputedStyle(e).display !== "none").map((e) => {
          const r = e.getBoundingClientRect();
          return { kind: e.getAttribute("data-micro-kind"), insideHeader: r.x >= header.x && r.right <= header.right && r.y >= header.y && r.bottom <= header.bottom, blocked: controls.some((c) => r.x < c.right && r.right > c.x && r.y < c.bottom && r.bottom > c.y), pointerEvents: getComputedStyle(e).pointerEvents, loaded: (e.querySelector("img") as HTMLImageElement).naturalWidth > 0 };
        });
        return { key: element.getAttribute("data-category-section"), artInside: art.top >= header.top && art.bottom <= header.bottom, micros };
      });
      if (output) await section.locator("header").screenshot({ path: path.join(output, `header-${width}-${value.key}.png`) });
      expect(value.artInside, `${width}:${value.key} main art`).toBe(true);
      expect(value.micros.length).toBeGreaterThanOrEqual(2);
      expect(value.micros.length).toBeLessThanOrEqual(5);
      for (const micro of value.micros) {
        expect(micro.insideHeader && !micro.blocked && micro.pointerEvents === "none", `${width}:${value.key}:${micro.kind}`).toBe(true);
      }
      rows.push({ width, ...value });
    }
    if (output) await page.screenshot({ path: path.join(output, `after-${width}-full.png`), fullPage: true });
  }
  if (output) await writeFile(path.join(output, "all-category-accents.json"), JSON.stringify(rows, null, 2));
});

test("measured column transitions and local arrows preserve all records", async ({ page }) => {
  test.skip(phase === "before");
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto(new URL("/games", origin).href);
  const rail = page.locator("[data-category-rail='action'] .catalog-category-rail__viewport");
  await expect(rail).toBeVisible();
  for (const [width, count] of [[999, 4], [1000, 5], [1199, 5], [1200, 6]]) {
    await page.setViewportSize({ width: width!, height: 1080 });
    const visible = await rail.evaluate((e) => {
      const r = e.getBoundingClientRect();
      return [...e.querySelectorAll(".catalog-card")].filter((card) => { const b = card.getBoundingClientRect(); return b.x >= r.x - 1 && b.right <= r.right + 1; }).length;
    });
    expect(visible, `${width}px real complete cards`).toBe(count);
  }
  const ids = await page.locator("[data-category-section='exploration'] .catalog-card").evaluateAll((cards) => cards.map((c) => c.getAttribute("data-project-id")));
  const sectionOrder = await page.locator("[data-category-section]").evaluateAll((sections) => sections.map((s) => s.getAttribute("data-category-section")));
  await page.getByRole("button", { name: "下一组探索游戏", exact: true }).click();
  await expect.poll(() => page.locator("[data-category-rail='exploration'] .catalog-category-rail__viewport").evaluate((e) => e.scrollLeft)).toBeGreaterThan(0);
  expect(await page.locator("[data-category-section='exploration'] .catalog-card").count()).toBe(ids.length);
  expect(ids.length).toBeGreaterThan(6);
  await page.getByRole("button", { name: "多动脑子", exact: true }).click();
  expect(await page.locator("[data-category-section]").evaluateAll((sections) => sections.map((s) => s.getAttribute("data-category-section")))).toEqual(sectionOrder);
  expect(await page.locator("[data-category-section='exploration'] .catalog-card").evaluateAll((cards) => cards.map((c) => c.getAttribute("data-project-id")))).toEqual(ids);
});

test("single real farming cover and illustration are ready before snapshots", async ({ page }) => {
  test.skip(phase === "before");
  await page.goto(new URL("/games", origin).href);
  for (const width of [1920, 1440]) {
    await page.setViewportSize({ width, height: 1080 });
    const section = page.locator("[data-category-section='farming']");
    await section.scrollIntoViewIfNeeded();
    await expect.poll(() => section.locator("img").evaluateAll((images) => images.every((img) => (img as HTMLImageElement).complete && (img as HTMLImageElement).naturalWidth > 0))).toBe(true);
    expect(await section.locator(".catalog-card").count()).toBe(1);
    expect(await section.locator(".catalog-card").evaluate((e) => e.getBoundingClientRect().width)).toBeLessThanOrEqual(340);
    if (output) await section.screenshot({ path: path.join(output, `after-${width}-farming.png`) });
  }
});

test("settled top viewport captures", async ({ page }) => {
  test.skip(phase === "before");
  await page.goto(new URL("/games", origin).href);
  await expect(page.locator("[data-category-section]").first()).toBeVisible();
  for (const width of [1920, 1440, 390]) {
    await page.setViewportSize({ width, height: width < 700 ? 844 : 1080 });
    await page.evaluate(() => scrollTo({ top: 0, behavior: "instant" }));
    await expect.poll(() => page.evaluate(() => scrollY)).toBe(0);
    await expect(page.locator("h1")).toBeInViewport();
    if (output) await page.screenshot({ path: path.join(output, `after-${width}-viewport.png`) });
  }
});

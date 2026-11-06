import { test, expect } from "@playwright/test";
import { existsSync, readFileSync } from "node:fs";
import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { catalogPublicFixture } from "./catalog-public-fixture";

const phase = process.env.CATALOG_RESPONSIVE_PHASE ?? "after";
const origin = process.env.PLAYWRIGHT_BASE_URL ?? "http://127.0.0.1:5202";
const output = process.env.CATALOG_RESPONSIVE_OUTPUT;
const snapshotPath = process.env.CATALOG_RESPONSIVE_SNAPSHOT;
const snapshot = snapshotPath ? JSON.parse(readFileSync(snapshotPath, "utf8")) as {
  data: { categories: Parameters<typeof catalogPublicFixture>[1] };
} : undefined;

test.use({ serviceWorkers: "block" });
test.beforeEach(async ({ context }) => {
  const localOrigin = new URL(origin).origin;
  const roots = [fileURLToPath(new URL("../../../../static/web", import.meta.url)),
    fileURLToPath(new URL("../../public", import.meta.url))];
  await context.route("**/*", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    if (!["GET", "HEAD"].includes(request.method())) return route.abort();
    if (!snapshot) return route.continue();
    // 离线验收只用冻结的公开目录与工作区正式封面，不访问外链、线上 API 或 CDN。
    if (url.origin !== localOrigin) return route.abort();
    if (url.pathname.startsWith("/static/web/")) {
      const key = decodeURIComponent(url.pathname.slice("/static/web/".length));
      const file = roots.map((root) => ({ root, file: path.resolve(root, key) }))
        .find(({ root, file }) => file.startsWith(root + path.sep) && existsSync(file))?.file;
      return file ? route.fulfill({ path: file }) : route.fulfill({ status: 404 });
    }
    if (url.pathname === "/api/v1/site/settings") return route.fulfill({ json: { data: { settings: {}, updated_at: null } } });
    if (url.pathname === "/api/v1/catalog") return route.fulfill({ json: snapshot });
    const paged = catalogPublicFixture(url, snapshot.data.categories);
    if (paged) return route.fulfill({ json: paged });
    if (url.pathname.startsWith("/api/")) return route.fulfill({ status: 404 });
    return route.continue();
  });
});

for (const width of [1920, 1440, 390]) {
  test(`category density and art bounds at ${width}px`, async ({ page }, testInfo) => {
    test.setTimeout(120_000);
    await page.setViewportSize({ width, height: width < 700 ? 844 : 1080 });
    await page.emulateMedia({ reducedMotion: "reduce" });
    await page.goto(new URL("/games", origin).href);
    await expect(page.locator("[data-category-section='horror']")).toBeVisible();
    await page.evaluate(async () => { await document.fonts.ready; });
    const folder = output ?? testInfo.outputDir;
    await mkdir(folder, { recursive: true });
    const rows = [];
    for (const key of ["casual", "horror", "exploration", "farming"]) {
      const section = page.locator(`[data-category-section='${key}']`);
      await section.scrollIntoViewIfNeeded();
      await section.evaluate((element) => element.scrollIntoView({ block: "center", behavior: "instant" }));
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

test("compact category headings keep all artwork and tiny, non-interactive accents", async ({ page }) => {
  test.skip(phase === "before");
  test.setTimeout(120_000);
  await page.goto(new URL("/games", origin).href);
  await expect(page.locator("[data-category-section]").first()).toBeVisible();
  const rows = [];
  for (const width of [1920, 921, 760, 390, 320]) {
    await page.setViewportSize({ width, height: 1080 });
    const mobile = width <= 760;
    for (const section of await page.locator("[data-category-section]").all()) {
      await section.scrollIntoViewIfNeeded();
      await expect.poll(() => section.locator(".catalog-card__cover img").first()
        .evaluate((img: HTMLImageElement) => img.complete && img.naturalWidth > 0)).toBe(true);
      await expect.poll(() => section.locator("header img")
        .evaluateAll((images) => images.every((img) => (img as HTMLImageElement).naturalWidth > 0))).toBe(true);
      const value = await section.evaluate((element) => {
        const header = element.querySelector("header")!.getBoundingClientRect();
        const art = element.querySelector(".catalog-category-art")!.getBoundingClientRect();
        const title = element.querySelector("header h2 button")!;
        const more = element.querySelector("header .catalog-group__meta button")!.getBoundingClientRect();
        const cover = element.querySelector(".catalog-card__cover")!.getBoundingClientRect();
        const compass = element.querySelector("[data-accent-kind='compass']");
        const within = (inner: DOMRect, outer: DOMRect) => inner.x >= outer.x && inner.right <= outer.right && inner.y >= outer.y && inner.bottom <= outer.bottom;
        const controls = [...element.querySelectorAll("header h2, header .catalog-group__meta, header .catalog-group__description")].map((e) => e.getBoundingClientRect());
        const measureAccent = (e: Element) => {
          const r = e.getBoundingClientRect();
          return { kind: e.getAttribute("data-micro-kind") ?? e.getAttribute("data-accent-kind"),
            edge: Math.max(e.clientWidth, e.clientHeight), insideHeader: within(r, header),
            blocked: controls.some((c) => r.x < c.right && r.right > c.x && r.y < c.bottom && r.bottom > c.y),
            pointerEvents: getComputedStyle(e).pointerEvents };
        };
        return { key: element.getAttribute("data-category-section"), headerHeight: header.height,
          artWidth: art.width, artHeight: art.height, artInside: within(art, header), artAfterTitle: art.x >= title.getBoundingClientRect().right,
          titleFits: title.scrollWidth <= title.clientWidth, moreHeight: more.height, moreRightGap: header.right - more.right,
          coverHeight: cover.height,
          micros: [...element.querySelectorAll(".catalog-micro-accents__item, [data-accent-kind='branch-paper']")].map(measureAccent),
          compass: compass ? { ...measureAccent(compass), onCover: within(compass.getBoundingClientRect(), cover) } : null };
      });
      const label = `${width}:${value.key}`;
      expect(value.headerHeight, label).toBe(mobile ? 48 : 54);
      expect(value.headerHeight, label).toBeLessThan(value.coverHeight);
      expect(value.artWidth, label).toBeGreaterThan(0);
      expect(value.artWidth, label).toBeLessThanOrEqual(mobile ? 44 : 64);
      expect(value.artHeight, label).toBeLessThanOrEqual(mobile ? 23 : 32);
      expect(value.artInside && value.artAfterTitle && value.titleFits, label).toBe(true);
      expect(value.moreHeight, label).toBeGreaterThanOrEqual(44);
      expect(value.moreRightGap, label).toBeLessThanOrEqual(1);
      expect(value.micros.length, label).toBe(["casual", "rts", "horror"].includes(value.key ?? "") ? 4 : 3);
      for (const micro of value.micros) {
        expect(micro.insideHeader && !micro.blocked && micro.pointerEvents === "none", `${label}:${micro.kind}`).toBe(true);
        expect(micro.edge, label).toBeGreaterThan(0);
        expect(micro.edge, label).toBeLessThanOrEqual(mobile ? 4 : 6);
      }
      if (value.key === "exploration") {
        expect(value.compass?.onCover, label).toBe(true);
        expect(value.compass?.pointerEvents, label).toBe("none");
        expect(value.compass?.edge, label).toBeGreaterThan(0);
        expect(value.compass?.edge, label).toBeLessThanOrEqual(mobile ? 4 : 6);
      }
      rows.push({ width, ...value });
    }
    if (output && [1920, 390].includes(width)) {
      await page.screenshot({ path: path.join(output, `after-${width}-full.png`), fullPage: true });
    }
  }
  if (output) await writeFile(path.join(output, "all-category-accents.json"), JSON.stringify(rows, null, 2));
});

test("measured column transitions and local arrows preserve all records", async ({ page }) => {
  test.skip(phase === "before");
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto(new URL("/games", origin).href);
  const rail = page.locator("[data-category-rail='action'] .catalog-category-rail__viewport");
  await rail.scrollIntoViewIfNeeded();
  await expect(rail).toBeVisible();
  for (const [width, count] of [[999, 4], [1000, 5], [1199, 5], [1200, 6]]) {
    await page.setViewportSize({ width: width!, height: 1080 });
    await expect.poll(() => rail.evaluate((e) => {
      const r = e.getBoundingClientRect();
      return [...e.querySelectorAll(".catalog-card")].filter((card) => { const b = card.getBoundingClientRect(); return b.x >= r.x - 1 && b.right <= r.right + 1; }).length;
    }), `${width}px real complete cards`).toBe(count);
  }
  await page.locator("[data-category-section='exploration']").scrollIntoViewIfNeeded();
  await expect.poll(() => page.locator("[data-category-section='exploration'] .catalog-card").count()).toBeGreaterThan(0);
  const ids = await page.locator("[data-category-section='exploration'] .catalog-card").evaluateAll((cards) => cards.map((c) => c.getAttribute("data-project-id")));
  const sectionOrder = await page.locator("[data-category-section]").evaluateAll((sections) => sections.map((s) => s.getAttribute("data-category-section")));
  await page.getByRole("button", { name: "下一组探索游戏", exact: true }).click();
  await expect.poll(() => page.locator("[data-category-rail='exploration'] .catalog-category-rail__viewport").evaluate((e) => e.scrollLeft)).toBeGreaterThan(0);
  const appendedIds = await page.locator("[data-category-section='exploration'] .catalog-card").evaluateAll((cards) => cards.map((c) => c.getAttribute("data-project-id")));
  expect(appendedIds.slice(0, ids.length)).toEqual(ids);
  expect(appendedIds.length).toBeGreaterThanOrEqual(ids.length);
  await page.getByRole("button", { name: "多动脑子", exact: true }).click();
  expect(await page.locator("[data-category-section]").evaluateAll((sections) => sections.map((s) => s.getAttribute("data-category-section")))).toEqual(sectionOrder);
  expect(await page.locator("[data-category-section='exploration'] .catalog-card").evaluateAll((cards) => cards.map((c) => c.getAttribute("data-project-id")))).toEqual(appendedIds);
  const more = page.getByRole("button", { name: "查看全部探索游戏" });
  await more.focus();
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/(?:\?|&)category=exploration(?:&|$)/);
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("探索");
});

test("single real farming cover and illustration are ready before snapshots", async ({ page }) => {
  test.skip(phase === "before");
  await page.goto(new URL("/games", origin).href);
  for (const width of [1920, 1440]) {
    await page.setViewportSize({ width, height: 1080 });
    const section = page.locator("[data-category-section='farming']");
    await section.scrollIntoViewIfNeeded();
    await expect(section.locator(".catalog-card")).toHaveCount(1);
    await expect.poll(() => section.locator("img").evaluateAll((images) => images.every((img) => (img as HTMLImageElement).complete && (img as HTMLImageElement).naturalWidth > 0))).toBe(true);
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

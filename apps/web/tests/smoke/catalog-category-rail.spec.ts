import { expect, test, type BrowserContext, type Locator, type Page } from "@playwright/test";

const baseURL = process.env.PLAYWRIGHT_BASE_URL ?? "http://127.0.0.1:5199";
const localHost = (hostname: string) => ["127.0.0.1", "localhost", "[::1]"].includes(hostname);

interface CatalogCategory {
  id: string;
  slug: string;
  name: string;
  projects: Array<{ id: string; [key: string]: unknown }>;
}
interface CatalogPayload {
  data: { categories: CatalogCategory[]; [key: string]: unknown };
  [key: string]: unknown;
}
const guards = new WeakMap<BrowserContext, { writes: string[]; externalNavigations: string[] }>();

async function readOnlyCatalog(context: BrowserContext): Promise<CatalogPayload> {
  expect(localHost(new URL(baseURL).hostname)).toBe(true);
  const response = await context.request.get(new URL("/api/v1/catalog", baseURL).href);
  expect(response.ok()).toBe(true);
  const catalog = await response.json() as CatalogPayload;
  expect(catalog.data.categories.length).toBeGreaterThan(0);
  const guard = { writes: [] as string[], externalNavigations: [] as string[] };
  guards.set(context, guard);
  await context.route("**/*", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    if (!["GET", "HEAD"].includes(request.method())) {
      guard.writes.push(`${request.method()} ${url.pathname}`);
      await route.fulfill({ status: 409, json: { error: { code: "LOCAL_RAIL_TEST_WRITE_BLOCKED" } } });
      return;
    }
    if (!localHost(url.hostname)) {
      if (request.isNavigationRequest()) guard.externalNavigations.push(url.href);
      await route.abort();
      return;
    }
    if (url.pathname === "/api/v1/catalog") {
      await route.fulfill({ json: catalog });
      return;
    }
    await route.continue();
  });
  return catalog;
}

async function openCatalog(page: Page, path = "/games?topic=brain"): Promise<void> {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto(new URL(path, baseURL).href);
  await expect(page.locator(".catalog-group--featured [data-hero-slot]")).toHaveCount(6);
  await expect(page.locator("[data-category-rail]").first()).toBeVisible();
  await page.evaluate(async () => { await document.fonts.ready; });
  await page.mouse.move(0, 0);
}

function railFor(page: Page, slug: string): Locator {
  return page.locator(`[data-category-rail=${JSON.stringify(slug)}]`);
}

async function railState(rail: Locator) {
  return rail.locator(".catalog-category-rail__viewport").evaluate((viewport) => {
    const box = viewport.getBoundingClientRect();
    const cards = [...viewport.querySelectorAll<HTMLElement>(".catalog-card")];
    return {
      scrollLeft: viewport.scrollLeft,
      scrollWidth: viewport.scrollWidth,
      clientWidth: viewport.clientWidth,
      ids: cards.map((card) => card.dataset.projectId ?? ""),
      visibleIds: cards.filter((card) => {
        const bounds = card.getBoundingClientRect();
        return bounds.right > box.left + 1 && bounds.left < box.right - 1;
      }).map((card) => card.dataset.projectId ?? ""),
    };
  });
}

async function otherState(page: Page, slug: string) {
  return page.evaluate((selectedSlug) => ({
    heroIds: [...document.querySelectorAll<HTMLElement>(".catalog-group--featured .catalog-card")]
      .map((card) => card.dataset.projectId),
    otherRails: [...document.querySelectorAll<HTMLElement>("[data-category-rail]")]
      .filter((rail) => rail.dataset.categoryRail !== selectedSlug)
      .map((rail) => ({ slug: rail.dataset.categoryRail, scrollLeft: rail.querySelector(".catalog-category-rail__viewport")?.scrollLeft })),
    topic: new URL(location.href).searchParams.get("topic"),
  }), slug);
}

test.afterEach(async ({ context }) => {
  const guard = guards.get(context);
  if (guard) {
    expect(guard.writes).toEqual([]);
    expect(guard.externalNavigations).toEqual([]);
  }
  expect(context.pages()).toHaveLength(1);
});

test("a category arrow reveals later real games without changing routes, other rails or hero", async ({ page, context }) => {
  const catalog = await readOnlyCatalog(context);
  const category = catalog.data.categories.find((entry) => entry.projects.length > 6)!;
  expect(category).toBeDefined();
  await page.setViewportSize({ width: 921, height: 1100 });
  await openCatalog(page);
  const rail = railFor(page, category.slug);
  const before = await railState(rail);
  expect([...before.ids].sort()).toEqual(category.projects.map((project) => project.id).sort());
  expect(new Set(before.ids).size).toBe(before.ids.length);
  expect(before.scrollWidth).toBeGreaterThan(before.clientWidth);
  const unrelated = await otherState(page, category.slug);
  const initialUrl = page.url();
  await rail.getByRole("button", { name: `下一组${category.name}游戏`, exact: true }).click();
  await expect.poll(async () => (await railState(rail)).scrollLeft).toBeGreaterThan(before.scrollLeft);
  await expect.poll(async () => (await railState(rail)).visibleIds.some((id) => !before.visibleIds.includes(id))).toBe(true);
  expect((await railState(rail)).ids).toEqual(before.ids);
  expect(await otherState(page, category.slug)).toEqual(unrelated);
  expect(page.url()).toBe(initialUrl);
  await expect(page.locator(".catalog-controls")).toHaveCount(0);
  await expect(rail.getByRole("button", { name: `上一组${category.name}游戏`, exact: true })).toBeVisible();
});

test("the real single farming game has no filler or ineffective rail arrows", async ({ page, context }) => {
  const catalog = await readOnlyCatalog(context);
  const farming = catalog.data.categories.find((category) => category.slug === "farming")!;
  expect(farming).toBeDefined();
  expect(farming.projects).toHaveLength(1);
  await page.setViewportSize({ width: 921, height: 1100 });
  await openCatalog(page);
  const rail = railFor(page, farming.slug);
  await expect(rail.locator(".catalog-card")).toHaveCount(1);
  expect((await railState(rail)).ids).toEqual([farming.projects[0]!.id]);
  await expect(rail.locator(".catalog-category-rail__arrow")).toHaveCount(0);
});

test("Tab reaches native game links and arrow keys affect only a focused rail", async ({ page, context }) => {
  const catalog = await readOnlyCatalog(context);
  const category = catalog.data.categories.find((entry) => entry.projects.length > 6)!;
  await page.setViewportSize({ width: 921, height: 1100 });
  await openCatalog(page);
  const rail = railFor(page, category.slug);
  const viewport = rail.locator(".catalog-category-rail__viewport");
  await viewport.focus();
  await expect(viewport).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(rail.locator(".catalog-card__open").first()).toBeFocused();
  const before = await railState(rail);
  const unrelated = await otherState(page, category.slug);
  const initialUrl = page.url();
  await page.getByRole("searchbox", { name: "搜索游戏名称", exact: true }).focus();
  await page.keyboard.press("ArrowRight");
  expect((await railState(rail)).scrollLeft).toBe(before.scrollLeft);
  await viewport.focus();
  await page.keyboard.press("ArrowRight");
  await expect.poll(async () => (await railState(rail)).scrollLeft).toBeGreaterThan(before.scrollLeft);
  expect(await otherState(page, category.slug)).toEqual(unrelated);
  expect(page.url()).toBe(initialUrl);
});

test.describe("390px touch viewport", () => {
  test.use({ hasTouch: true });

  test("category overflow stays local and its touch arrow reaches later cards", async ({ page, context }) => {
    const catalog = await readOnlyCatalog(context);
    const category = catalog.data.categories.find((entry) => entry.projects.length > 6)!;
    await page.setViewportSize({ width: 390, height: 844 });
    await openCatalog(page);
    const rail = railFor(page, category.slug);
    const before = await railState(rail);
    const unrelated = await otherState(page, category.slug);
    const initialUrl = page.url();
    expect(before.scrollWidth).toBeGreaterThan(before.clientWidth);
    await rail.getByRole("button", { name: `下一组${category.name}游戏`, exact: true }).tap();
    await expect.poll(async () => (await railState(rail)).visibleIds.some((id) => !before.visibleIds.includes(id))).toBe(true);
    expect(await otherState(page, category.slug)).toEqual(unrelated);
    expect(page.url()).toBe(initialUrl);
    const containment = await page.evaluate(() => ({
      documentOverflow: document.documentElement.scrollWidth > document.documentElement.clientWidth,
      rails: [...document.querySelectorAll(".catalog-category-rail__viewport")].map((viewport) => {
        const box = viewport.getBoundingClientRect();
        return box.left >= 0 && box.right <= document.documentElement.clientWidth + 1;
      }),
    }));
    expect(containment.documentOverflow).toBe(false);
    expect(containment.rails.length).toBeGreaterThan(0);
    expect(containment.rails.every(Boolean)).toBe(true);
  });
});

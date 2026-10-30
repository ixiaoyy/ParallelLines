import { expect, test, type BrowserContext, type Page } from "@playwright/test";

const baseURL = process.env.PLAYWRIGHT_BASE_URL ?? "http://127.0.0.1:5199";
const localHost = (hostname: string) => ["127.0.0.1", "localhost", "[::1]"].includes(hostname);
const tabs = [
  { id: "all", name: "全部推荐" },
  { id: "nostalgia", name: "经典怀旧" },
  { id: "quick", name: "即玩即乐" },
  { id: "brain", name: "多动脑子" },
] as const;
const nostalgiaSlugs = new Set([
  "super-mario", "csgo-desert", "astra-9dbd59a9718b252daedf", "astra-2a8764b03af3aca71817",
]);

interface ApiProject {
  id: string;
  slug: string;
  name: string;
  ai_rating?: { score: number | null; [key: string]: unknown } | null;
  [key: string]: unknown;
}
interface CatalogPayload {
  data: {
    categories: Array<{ id: string; slug: string; name: string; projects: ApiProject[]; [key: string]: unknown }>;
    [key: string]: unknown;
  };
  [key: string]: unknown;
}
interface NetworkGuard {
  nonReads: string[];
  externalNavigations: string[];
}
const guards = new WeakMap<BrowserContext, NetworkGuard>();

async function localCatalog(context: BrowserContext): Promise<CatalogPayload> {
  expect(localHost(new URL(baseURL).hostname)).toBe(true);
  const response = await context.request.get(new URL("/api/v1/catalog", baseURL).href);
  expect(response.ok()).toBe(true);
  const payload = await response.json() as CatalogPayload;
  expect(payload.data.categories.length).toBeGreaterThan(0);
  return payload;
}

async function readOnlyPreview(context: BrowserContext, catalog: CatalogPayload | (() => CatalogPayload)): Promise<void> {
  const guard: NetworkGuard = { nonReads: [], externalNavigations: [] };
  guards.set(context, guard);
  await context.route("**/*", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    if (!["GET", "HEAD"].includes(request.method())) {
      guard.nonReads.push(`${request.method()} ${url.pathname}`);
      await route.fulfill({ status: 409, json: { error: { code: "LOCAL_HERO_TEST_WRITE_BLOCKED" } } });
      return;
    }
    if (!localHost(url.hostname)) {
      if (request.isNavigationRequest()) guard.externalNavigations.push(url.href);
      await route.abort();
      return;
    }
    if (url.pathname === "/api/v1/catalog") {
      await route.fulfill({ json: typeof catalog === "function" ? catalog() : catalog });
      return;
    }
    await route.continue();
  });
}

function withNostalgiaCount(catalog: CatalogPayload, count: number): CatalogPayload {
  const nostalgia = catalog.data.categories.flatMap((category) => category.projects)
    .filter((project) => nostalgiaSlugs.has(project.slug));
  expect(new Set(nostalgia.map((project) => project.slug))).toEqual(nostalgiaSlugs);
  const keep = new Set(nostalgia.slice(0, count).map((project) => project.slug));
  return {
    ...catalog,
    data: {
      ...catalog.data,
      categories: catalog.data.categories.map((category) => ({
        ...category,
        // Only remove real records; every retained rating and metadata field is unchanged.
        projects: category.projects.filter((project) => !nostalgiaSlugs.has(project.slug) || keep.has(project.slug)),
      })),
    },
  };
}

async function ready(page: Page): Promise<void> {
  await expect(page.locator(".catalog-group--featured [data-hero-slot]")).toHaveCount(6);
  await expect(page.locator(".catalog-group:not(.catalog-group--featured)").first()).toBeVisible();
  await page.evaluate(async () => { await document.fonts.ready; });
  await page.mouse.move(0, 0);
}

async function layout(page: Page) {
  return page.evaluate(() => {
    const rect = (element: Element) => {
      const value = element.getBoundingClientRect();
      const round = (number: number) => Math.round(number * 1000) / 1000;
      return { x: round(value.x + scrollX), y: round(value.y + scrollY), width: round(value.width), height: round(value.height) };
    };
    const hero = document.querySelector(".catalog-group--featured .catalog-grid--featured");
    if (!hero) throw new Error("Expected the persistent hero mosaic");
    return {
      heading: document.querySelector("h1")?.textContent,
      hero: rect(hero),
      slots: [...hero.querySelectorAll("[data-hero-slot]")].map((slot) => ({ slot: slot.getAttribute("data-hero-slot"), rect: rect(slot) })),
      sections: [...document.querySelectorAll(".catalog-group:not(.catalog-group--featured)")].map((section) => ({
        label: section.getAttribute("aria-label"),
        count: section.querySelector(".catalog-group__count")?.textContent,
        rect: rect(section),
        cards: [...section.querySelectorAll(".catalog-card")].map((card) => ({ id: card.getAttribute("data-project-id"), rect: rect(card) })),
      })),
    };
  });
}

async function heroIds(page: Page): Promise<string[]> {
  return page.locator(".catalog-group--featured .catalog-card").evaluateAll((cards) => cards.map((card) => card.getAttribute("data-project-id") ?? ""));
}

async function resultIds(page: Page): Promise<string[]> {
  return page.locator(".catalog-card").evaluateAll((cards) => cards.map((card) => card.getAttribute("data-project-id") ?? ""));
}

async function selectTopic(page: Page, id: typeof tabs[number]["id"]): Promise<void> {
  const tab = tabs.find((entry) => entry.id === id)!;
  const button = page.getByRole("navigation", { name: "发现游戏", exact: true }).getByRole("button", { name: tab.name, exact: true });
  await button.click();
  await expect(button).toHaveAttribute("aria-pressed", "true");
  await expect.poll(() => new URL(page.url()).searchParams.get("topic")).toBe(id === "all" ? null : id);
  await page.mouse.move(0, 0);
}

async function expectEmptySlots(page: Page, matchingCount: number): Promise<void> {
  const hero = page.locator(".catalog-group--featured");
  await expect(hero.locator(".catalog-card")).toHaveCount(matchingCount);
  await expect(hero.locator(".catalog-hero-slot-empty")).toHaveCount(6 - matchingCount);
  expect(await hero.locator("[data-hero-slot]").evaluateAll((slots) => slots.map((slot) => slot.getAttribute("data-hero-slot"))))
    .toEqual(["0", "1", "2", "3", "4", "5"]);
  expect(await hero.locator(".catalog-hero-slot-empty").evaluateAll((slots) => slots.every((slot) =>
    slot.tagName === "SPAN" && slot.getAttribute("aria-hidden") === "true" && !slot.hasAttribute("tabindex")
    && !slot.hasAttribute("href") && !slot.querySelector("a,button,input,select,textarea,img,[tabindex]"),
  ))).toBe(true);
  if (matchingCount === 0) await expect(hero.locator('.catalog-hero-empty[role="status"]')).toBeVisible();
  else await expect(hero.locator(".catalog-hero-empty")).toHaveCount(0);
}

test.afterEach(async ({ context }) => {
  const guard = guards.get(context);
  if (guard) {
    expect(guard.nonReads).toEqual([]);
    expect(guard.externalNavigations).toEqual([]);
  }
  expect(context.pages()).toHaveLength(1);
});

for (const path of ["/", "/games"]) {
  test(`${path} keeps six hero slots and every category unchanged when switching all four tabs`, async ({ page, context }) => {
    const catalog = await localCatalog(context);
    await readOnlyPreview(context, catalog);
    await page.setViewportSize({ width: 1229, height: 1280 });
    await page.emulateMedia({ reducedMotion: "reduce" });
    await page.goto(new URL(path, baseURL).href);
    await ready(page);
    const baseline = await layout(page);
    expect(baseline.sections.length).toBeGreaterThan(0);
    await expect(page.getByRole("navigation", { name: "发现游戏", exact: true }).getByRole("button")).toHaveText(tabs.map((tab) => tab.name));

    for (const id of ["nostalgia", "quick", "brain", "all"] as const) {
      await selectTopic(page, id);
      await expect(page.locator(".catalog-controls")).toHaveCount(0);
      await expect.poll(() => layout(page)).toEqual(baseline);
      const query = new URL(page.url()).searchParams;
      for (const key of ["q", "category", "author", "scope", "feed"]) expect(query.has(key)).toBe(false);
      if (id === "nostalgia") {
        const expected = catalog.data.categories.flatMap((category) => category.projects)
          .filter((project) => nostalgiaSlugs.has(project.slug)).map((project) => project.id);
        expect((await heroIds(page)).sort()).toEqual(expected.sort());
        await expectEmptySlots(page, expected.length);
      } else {
        await expect(page.locator(".catalog-group--featured .catalog-card")).toHaveCount(6);
      }
    }
  });
}

test("Back and refresh restore only the hero selection and keep the category layout", async ({ page, context }) => {
  await readOnlyPreview(context, await localCatalog(context));
  await page.setViewportSize({ width: 1229, height: 1280 });
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto(new URL("/games", baseURL).href);
  await ready(page);
  const baseline = await layout(page);
  await selectTopic(page, "nostalgia");
  const nostalgicIds = await heroIds(page);
  await selectTopic(page, "quick");
  await page.goBack();
  await expect(page.getByRole("button", { name: "经典怀旧", exact: true })).toHaveAttribute("aria-pressed", "true");
  await expect.poll(() => new URL(page.url()).searchParams.get("topic")).toBe("nostalgia");
  expect(await heroIds(page)).toEqual(nostalgicIds);
  await expect.poll(() => layout(page)).toEqual(baseline);
  await page.reload();
  await ready(page);
  await expect(page.getByRole("button", { name: "经典怀旧", exact: true })).toHaveAttribute("aria-pressed", "true");
  expect(await heroIds(page)).toEqual(nostalgicIds);
  await expect.poll(() => layout(page)).toEqual(baseline);
  await expect(page.locator(".catalog-controls")).toHaveCount(0);
});

test("global search and category results ignore a hero topic and hide the hero tabs", async ({ page, context }) => {
  const catalog = await localCatalog(context);
  await readOnlyPreview(context, catalog);
  const projects = catalog.data.categories.flatMap((category) => category.projects);
  const target = projects.find((project) => !nostalgiaSlugs.has(project.slug) && project.slug !== "fablespace" && project.name.trim())!;
  expect(target).toBeDefined();
  const searchURL = new URL("/games", baseURL);
  searchURL.searchParams.set("q", target.name);
  await page.goto(searchURL.href);
  await expect(page.locator(".catalog-card").first()).toBeVisible();
  const searched = await resultIds(page);
  expect(searched).toContain(target.id);
  searchURL.searchParams.set("topic", "nostalgia");
  await page.goto(searchURL.href);
  await expect.poll(() => resultIds(page)).toEqual(searched);
  await expect(page.locator(".catalog-controls")).toBeVisible();
  await expect(page.locator(".catalog-recommendation-tabs")).toHaveCount(0);
  await expect(page.locator(".catalog-grid--featured")).toHaveCount(0);

  const category = catalog.data.categories.find((entry) => entry.projects.length > 24)
    ?? catalog.data.categories.find((entry) => entry.projects.length > 0)!;
  const categoryURL = new URL("/games", baseURL);
  categoryURL.searchParams.set("category", category.slug);
  await page.goto(categoryURL.href);
  await expect(page.getByRole("heading", { name: category.name, exact: true })).toBeVisible();
  const categorized = await resultIds(page);
  expect(categorized.length).toBeGreaterThan(0);
  expect(categorized.every((id) => category.projects.some((project) => project.id === id))).toBe(true);
  categoryURL.searchParams.set("topic", "brain");
  await page.goto(categoryURL.href);
  await expect.poll(() => resultIds(page)).toEqual(categorized);
  await expect(page.locator(".catalog-recommendation-tabs")).toHaveCount(0);
  await expect(page.locator(".catalog-grid--featured")).toHaveCount(0);
  await expect(page.locator(".catalog-controls")).toBeVisible();
  if (categorized.length < category.projects.length) {
    await page.locator(".catalog-load-more button").click();
    await expect(page.locator(".catalog-card")).toHaveCount(Math.min(category.projects.length, categorized.length + 24));
  }
});

for (const count of [0, 2, 3]) {
  test(`a real ${count}-game topic reserves six inert desktop slots without changing categories`, async ({ page, context }) => {
    const source = await localCatalog(context);
    const catalog = withNostalgiaCount(source, count);
    await readOnlyPreview(context, catalog);
    await page.setViewportSize({ width: 1229, height: 1280 });
    await page.emulateMedia({ reducedMotion: "reduce" });
    await page.goto(new URL("/games", baseURL).href);
    await ready(page);
    const baseline = await layout(page);
    await selectTopic(page, "nostalgia");
    await expectEmptySlots(page, count);
    await expect.poll(() => layout(page)).toEqual(baseline);
    await expect(page.locator(".catalog-controls")).toHaveCount(0);
  });
}

test("390px sparse topics retain the full hero height and two-column categories without overflow", async ({ page, context }) => {
  const source = await localCatalog(context);
  let catalog = source;
  await readOnlyPreview(context, () => catalog);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.emulateMedia({ reducedMotion: "reduce" });
  for (const count of [0, 2, 3]) {
    catalog = withNostalgiaCount(source, count);
    await page.goto(new URL("/games", baseURL).href);
    await ready(page);
    const baseline = await layout(page);
    expect(baseline.slots[0]!.rect.width).toBe(baseline.hero.width);
    expect(baseline.slots[5]!.rect.width).toBe(baseline.hero.width);
    expect(baseline.slots[1]!.rect.y).toBe(baseline.slots[2]!.rect.y);
    expect(baseline.slots[3]!.rect.y).toBe(baseline.slots[4]!.rect.y);
    await selectTopic(page, "nostalgia");
    await expectEmptySlots(page, count);
    await expect.poll(() => layout(page)).toEqual(baseline);
    const mobile = await page.evaluate(() => ({
      overflow: document.documentElement.scrollWidth > document.documentElement.clientWidth,
      columns: [...document.querySelectorAll(".catalog-group:not(.catalog-group--featured) .catalog-grid")]
        .map((grid) => getComputedStyle(grid).gridTemplateColumns.split(/\s+/).length),
    }));
    expect(mobile.overflow).toBe(false);
    expect(mobile.columns.length).toBe(baseline.sections.length);
    expect(mobile.columns.every((columns) => columns === 2)).toBe(true);
  }
});

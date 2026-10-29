import { expect, test, type BrowserContext, type CDPSession, type Locator, type Page } from "@playwright/test";

// Task-only regression: use the real local catalog; no production writes or target-game traffic.
const baseURL = process.env.PLAYWRIGHT_BASE_URL ?? "http://127.0.0.1:5196";
const storageKey = "parallellines.catalog-library.v1";
const localHost = (hostname: string) => ["127.0.0.1", "localhost", "[::1]"].includes(hostname);

interface CatalogProjectResponse {
  id: string;
  name: string;
  view_count: number;
  rating_score_sum: number;
  categoryName?: string;
}

interface CatalogPayload {
  categories: Array<{ name: string; projects: CatalogProjectResponse[] }>;
}

interface LibrarySnapshot {
  wantedIds: string[];
  recent: Array<{ projectId: string }>;
}

async function openLocalCatalog(page: Page, context: BrowserContext) {
  const views: string[] = [];
  const navigations: string[] = [];
  const otherWrites: string[] = [];
  const targets = new Set<string>();
  await context.addInitScript((key) => localStorage.removeItem(key), storageKey);
  await context.route("**/*", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    if (targets.has(url.href) && request.isNavigationRequest()) {
      navigations.push(url.href);
      await route.fulfill({ contentType: "text/html", body: "<!doctype html><title>Intercepted game</title><h1>Local navigation intercepted</h1>" });
      return;
    }
    if (!["GET", "HEAD", "OPTIONS"].includes(request.method())) {
      const match = /\/catalog\/projects\/([^/]+)\/views$/.exec(url.pathname);
      if (match) {
        views.push(decodeURIComponent(match[1]!));
        await route.fulfill({ json: { data: { project_id: decodeURIComponent(match[1]!), view_count: views.length } } });
      } else {
        otherWrites.push(`${request.method()} ${url.pathname}`);
        await route.fulfill({ status: 409, json: { error: { code: "LOCAL_CARD_TEST_WRITE_BLOCKED" } } });
      }
      return;
    }
    if (!localHost(url.hostname)) {
      await route.abort();
      return;
    }
    await route.continue();
  });
  const catalogResponse = page.waitForResponse((response) => new URL(response.url()).pathname === "/api/v1/catalog");
  await page.goto(`${baseURL}/games`);
  const payload = await (await catalogResponse).json() as { data: CatalogPayload };
  await expect(page.locator(".catalog-card").first()).toBeVisible();
  const projects = new Map(payload.data.categories.flatMap((category) => category.projects.map((project) => ({ ...project, categoryName: category.name }))).map((project) => [project.id, project]));
  for (const href of await page.locator(".catalog-card__open").evaluateAll((links) => links.map((link) => (link as HTMLAnchorElement).href))) targets.add(href);
  return { views, navigations, otherWrites, projects };
}

async function readLibrary(page: Page): Promise<LibrarySnapshot> {
  return page.evaluate((key) => JSON.parse(localStorage.getItem(key) ?? '{"wantedIds":[],"recent":[]}') as LibrarySnapshot, storageKey);
}

async function expectOneNativeOpen(page: Page, context: BrowserContext, action: () => Promise<unknown>, expectedId: string, requests: Awaited<ReturnType<typeof openLocalCatalog>>) {
  const opened = context.waitForEvent("page");
  await action();
  const popup = await opened;
  await expect(popup.locator("h1")).toHaveText("Local navigation intercepted");
  await expect.poll(() => requests.views).toEqual([expectedId]);
  expect(requests.navigations).toHaveLength(1);
  expect((await readLibrary(page)).recent.map((entry) => entry.projectId)).toEqual([expectedId]);
  expect(requests.otherWrites).toEqual([]);
  await popup.close();
}

async function touchCenter(target: Locator) {
  await target.scrollIntoViewIfNeeded();
  const box = await target.boundingBox();
  if (!box) throw new Error("Missing touch target geometry");
  return { x: box.x + box.width / 2, y: box.y + box.height / 2 };
}

async function touchStart(session: CDPSession, point: { x: number; y: number }) {
  await session.send("Input.dispatchTouchEvent", { type: "touchStart", touchPoints: [{ ...point, id: 1, radiusX: 2, radiusY: 2, force: 1 }] });
}

async function touchEnd(session: CDPSession) {
  await session.send("Input.dispatchTouchEvent", { type: "touchEnd", touchPoints: [] });
}

test.describe("image cards: desktop", () => {
  test.use({ viewport: { width: 1440, height: 1000 } });

  test("all cards rest as images; hover exposes full title and real aggregate heat", async ({ page, context }) => {
    const requests = await openLocalCatalog(page, context);
    await page.mouse.move(0, 0);
    const rest = await page.locator(".catalog-card").evaluateAll((cards) => cards.map((card) => {
      const details = card.querySelector<HTMLElement>(".catalog-card__details")!;
      const wanted = card.querySelector<HTMLElement>(".catalog-card__wanted")!;
      return { details: getComputedStyle(details).opacity, wanted: getComputedStyle(wanted).opacity,
        names: getComputedStyle(card.querySelector<HTMLElement>(".catalog-card__mobile-name")!).display,
        plays: [...card.querySelectorAll<HTMLElement>(".catalog-card__play")].map((node) => getComputedStyle(node).display),
        links: card.querySelectorAll("a").length };
    }));
    expect(rest.length).toBeGreaterThan(6);
    expect(rest.every((card) => card.details === "0" && card.wanted === "0" && card.names === "none" && card.plays.every((display) => display === "none") && card.links === 1)).toBe(true);
    await expect(page.locator(".catalog-grid--list, .catalog-layout-toggle")).toHaveCount(0);
    // Only the supplied AI slot may display AI data; never synthesize a score from user ratings.
    await expect(page.locator(".catalog-card__ai-rating")).toHaveCount(0);
    await expect(page.locator(".catalog-card__author")).toHaveCount(0);
    const card = page.locator(".catalog-group:not(.catalog-group--featured) .catalog-card").first();
    const project = requests.projects.get((await card.getAttribute("data-project-id"))!)!;
    const restingBox = await card.boundingBox();
    await card.hover();
    await expect(card.locator(".catalog-card__details")).toHaveCSS("opacity", "1");
    await expect(card.locator("h3")).toHaveText(project.name);
    await expect(card.locator("h3")).toHaveCSS("white-space", "normal");
    await expect(card.locator(".catalog-card__category")).toHaveText(project.categoryName!);
    await expect(card.locator(".catalog-card__heat")).toHaveText(`热度 ${(project.view_count ?? 0) + (project.rating_score_sum ?? 0) * 5}`);
    await expect(card.locator(".catalog-card__heat")).toHaveAttribute("title", /5/);
    const revealedBox = await card.boundingBox();
    expect(revealedBox!.height).toBeCloseTo(restingBox!.height, 1);
    expect((await card.locator(".catalog-card__details").boundingBox())!.height).toBeLessThan(revealedBox!.height * .6);
    await page.mouse.move(0, 0);
    await expect(card.locator(".catalog-card__details")).toHaveCSS("opacity", "0");
    expect(requests.views).toEqual([]);
    expect(requests.navigations).toEqual([]);
  });

  test("keyboard focus exposes information; Enter follows one native card link", async ({ page, context }) => {
    const requests = await openLocalCatalog(page, context);
    const card = page.locator(".catalog-card").first();
    const id = (await card.getAttribute("data-project-id"))!;
    const link = card.locator(".catalog-card__open");
    await expect(card.locator("a")).toHaveCount(1);
    await link.focus();
    await expect(card.locator(".catalog-card__details")).toHaveCSS("opacity", "1");
    await expect(card.locator(".catalog-card__wanted")).toHaveCSS("opacity", "1");
    await expectOneNativeOpen(page, context, () => link.press("Enter"), id, requests);
  });

  test("favorite is separate from navigation and view/recent writes; duplicates synchronize", async ({ page, context }) => {
    const requests = await openLocalCatalog(page, context);
    const card = page.locator(".catalog-card").first();
    const id = (await card.getAttribute("data-project-id"))!;
    const instances = page.locator(`.catalog-card[data-project-id="${id}"]`);
    expect(await instances.count()).toBeGreaterThan(1);
    await card.hover();
    await card.locator(".catalog-card__wanted").click();
    for (const button of await instances.locator(".catalog-card__wanted").all()) await expect(button).toHaveAttribute("aria-pressed", "true");
    expect((await readLibrary(page)).wantedIds).toEqual([id]);
    expect((await readLibrary(page)).recent).toEqual([]);
    expect(requests.views).toEqual([]);
    expect(requests.navigations).toEqual([]);
    expect(context.pages()).toHaveLength(1);
    await card.locator(".catalog-card__wanted").focus();
    await page.keyboard.press("Space");
    for (const button of await instances.locator(".catalog-card__wanted").all()) await expect(button).toHaveAttribute("aria-pressed", "false");
    expect((await readLibrary(page)).wantedIds).toEqual([]);
    expect(requests.otherWrites).toEqual([]);
  });
});

test("directory keyboard: root and games ignore obsolete selection shortcuts while Tab reaches the native card link", async ({ page, context }) => {
  const requests = await openLocalCatalog(page, context);
  for (const path of ["/", "/games"]) {
    await page.goto(`${baseURL}${path}`);
    await expect(page.locator(".catalog-card").first()).toBeVisible();
    await expect(page.locator(".catalog-keyboard-hint, .catalog-shortcuts, .catalog-card.is-selected")).toHaveCount(0);
    await expect(page.locator(".catalog-footer")).not.toContainText(/W\s*\/\s*A\s*\/\s*S\s*\/\s*D|Enter\s*开始游戏/);
    // This is blank intro padding, so Enter must not become an implicit game launch.
    await page.locator(".catalog-intro").click({ position: { x: 4, y: 4 } });
    for (const key of ["w", "a", "s", "d", "ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown", "Enter"]) await page.keyboard.press(key);
    await expect(page.locator(".catalog-card.is-selected, .catalog-card[aria-current]")).toHaveCount(0);
    expect(requests.views).toEqual([]);
    expect(requests.navigations).toEqual([]);
    expect(context.pages()).toHaveLength(1);
    await page.locator(".catalog-recommendation-tabs button").last().focus();
    await page.keyboard.press("Tab");
    await expect(page.locator(".catalog-card__open").first()).toBeFocused();
  }
  expect(requests.otherWrites).toEqual([]);
});

for (const width of [390, 320]) {
  test.describe(`image cards: ${width}px touch`, () => {
    test.use({ viewport: { width, height: 844 }, isMobile: true, hasTouch: true, deviceScaleFactor: 1 });

    test("small cards show cover and a single-line name, with no permanent action buttons", async ({ page, context }) => {
      await openLocalCatalog(page, context);
      const cards = page.locator(".catalog-card:not(.catalog-card--featured)");
      const geometry = await cards.evaluateAll((nodes) => nodes.map((node) => {
        const title = node.querySelector<HTMLElement>(".catalog-card__mobile-name")!;
        const wanted = node.querySelector<HTMLElement>(".catalog-card__wanted")!;
        const image = node.querySelector<HTMLImageElement>(".catalog-card__cover img");
        return { titleDisplay: getComputedStyle(title).display, titleWhiteSpace: getComputedStyle(title).whiteSpace,
          titleOverflow: getComputedStyle(title).textOverflow, titleHeight: title.clientHeight,
          wantedOpacity: getComputedStyle(wanted).opacity, wantedPointer: getComputedStyle(wanted).pointerEvents,
          plays: node.querySelectorAll(".catalog-card__play").length, links: node.querySelectorAll("a").length,
          hasImage: Boolean(image), width: node.getBoundingClientRect().width };
      }));
      expect(geometry.length).toBeGreaterThan(2);
      expect(geometry.every((card) => card.titleDisplay === "block" && card.titleWhiteSpace === "nowrap" && card.titleOverflow === "ellipsis" && card.titleHeight < 32 && card.wantedOpacity === "0" && card.wantedPointer === "none" && card.plays === 0 && card.links === 1 && card.hasImage && card.width > 100)).toBe(true);
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
    });

    test("first native touch tap opens once without a hover-only intermediate step", async ({ page, context }) => {
      const requests = await openLocalCatalog(page, context);
      const card = page.locator(".catalog-card:not(.catalog-card--featured)").first();
      const id = (await card.getAttribute("data-project-id"))!;
      await expectOneNativeOpen(page, context, () => card.locator(".catalog-card__open").tap(), id, requests);
    });

    test("native long press exposes favorite, release does not navigate, favorite remains independent", async ({ page, context }) => {
      const requests = await openLocalCatalog(page, context);
      const card = page.locator(".catalog-card:not(.catalog-card--featured)").first();
      const id = (await card.getAttribute("data-project-id"))!;
      const session = await context.newCDPSession(page);
      await touchStart(session, await touchCenter(card.locator(".catalog-card__cover")));
      await expect(card).toHaveClass(/catalog-card--touch-actions/);
      await touchEnd(session);
      await page.waitForTimeout(100);
      expect(requests.views).toEqual([]);
      expect(requests.navigations).toEqual([]);
      await expect(card.locator(".catalog-card__wanted")).toHaveCSS("opacity", "1");
      await card.locator(".catalog-card__wanted").tap();
      await expect(card.locator(".catalog-card__wanted")).toHaveAttribute("aria-pressed", "true");
      expect((await readLibrary(page)).wantedIds).toEqual([id]);
      expect((await readLibrary(page)).recent).toEqual([]);
      expect(requests.views).toEqual([]);
      expect(requests.navigations).toEqual([]);
      expect(context.pages()).toHaveLength(1);
      expect(requests.otherWrites).toEqual([]);
      await session.detach();
    });

    test("dragging beyond the gesture threshold cancels the pending long press", async ({ page, context }) => {
      const requests = await openLocalCatalog(page, context);
      const card = page.locator(".catalog-card:not(.catalog-card--featured)").first();
      const session = await context.newCDPSession(page);
      const point = await touchCenter(card.locator(".catalog-card__cover"));
      await touchStart(session, point);
      await session.send("Input.dispatchTouchEvent", { type: "touchMove", touchPoints: [{ x: point.x, y: point.y - 30, id: 1, radiusX: 2, radiusY: 2, force: 1 }] });
      await page.waitForTimeout(650);
      await expect(card).not.toHaveClass(/catalog-card--touch-actions/);
      await touchEnd(session);
      await page.waitForTimeout(100);
      expect(requests.views).toEqual([]);
      expect(requests.navigations).toEqual([]);
      expect((await readLibrary(page)).wantedIds).toEqual([]);
      expect((await readLibrary(page)).recent).toEqual([]);
      await session.detach();
    });
  });
}

test.describe("image cards: longpress follow-up", () => {
  test.use({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true, deviceScaleFactor: 1 });

  test("longpress then favorite then a new cover tap opens exactly once", async ({ page, context }) => {
    const requests = await openLocalCatalog(page, context);
    const card = page.locator(".catalog-card:not(.catalog-card--featured)").first();
    const id = (await card.getAttribute("data-project-id"))!;
    const session = await context.newCDPSession(page);
    await touchStart(session, await touchCenter(card.locator(".catalog-card__cover")));
    await expect(card).toHaveClass(/catalog-card--touch-actions/);
    await touchEnd(session);
    await page.waitForTimeout(100);
    expect(requests.views).toEqual([]);
    expect(requests.navigations).toEqual([]);
    await card.locator(".catalog-card__wanted").tap();
    await expect(card.locator(".catalog-card__wanted")).toHaveAttribute("aria-pressed", "true");
    expect((await readLibrary(page)).recent).toEqual([]);
    expect(requests.views).toEqual([]);
    await expectOneNativeOpen(page, context, () => card.locator(".catalog-card__open").tap(), id, requests);
    expect((await readLibrary(page)).wantedIds).toEqual([id]);
    await session.detach();
  });
});

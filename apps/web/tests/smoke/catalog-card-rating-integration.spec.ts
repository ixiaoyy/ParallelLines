import { expect, test, type BrowserContext, type Locator, type Page } from "@playwright/test";

import type { CatalogAiRatingResponse } from "../../src/features/catalog/model";

const baseURL = process.env.PLAYWRIGHT_BASE_URL ?? "http://127.0.0.1:5196";
const storageKey = "parallellines.catalog-library.v1";

interface Project {
  id: string;
  name: string;
  url: string;
  ai_rating?: CatalogAiRatingResponse | null;
}

/** Read only the actual integrated local preview; intercept every mutation and target-game navigation. */
async function openIntegratedCatalog(page: Page, context: BrowserContext) {
  const views: string[] = [];
  const gameOpens: string[] = [];
  const otherWrites: string[] = [];
  const targets = new Set<string>();
  await context.addInitScript((key) => localStorage.removeItem(key), storageKey);
  await context.route("**/*", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    if (targets.has(url.href) && request.isNavigationRequest()) {
      gameOpens.push(url.href);
      await route.fulfill({ contentType: "text/html", body: "<!doctype html><title>Intercepted game</title><h1>Local game target intercepted</h1>" });
      return;
    }
    if (!["GET", "HEAD", "OPTIONS"].includes(request.method())) {
      const view = /\/catalog\/projects\/([^/]+)\/views$/.exec(url.pathname);
      if (view) {
        views.push(decodeURIComponent(view[1]!));
        await route.fulfill({ json: { data: { project_id: decodeURIComponent(view[1]!), view_count: 1 } } });
      } else {
        otherWrites.push(`${request.method()} ${url.pathname}`);
        await route.fulfill({ status: 409, json: { error: { code: "LOCAL_INTEGRATION_TEST_WRITE_BLOCKED" } } });
      }
      return;
    }
    if (!["127.0.0.1", "localhost", "[::1]"].includes(url.hostname)) {
      await route.abort();
      return;
    }
    await route.continue();
  });
  const response = page.waitForResponse((result) => new URL(result.url()).pathname === "/api/v1/catalog");
  await page.goto(`${baseURL}/games`);
  const payload = await (await response).json() as { data: { categories: Array<{ slug: string; name: string; projects: Project[] }> } };
  await expect(page.locator(".catalog-card").first()).toBeVisible();
  const projects = new Map(payload.data.categories.flatMap((category) => category.projects).map((project) => [project.id, project]));
  for (const project of projects.values()) targets.add(new URL(project.url, baseURL).href);
  expect(projects.size).toBe(226);
  expect([...projects.values()].filter((project) => project.ai_rating?.score != null)).toHaveLength(22);
  return { views, gameOpens, otherWrites, projects, categories: payload.data.categories };
}

async function cardFor(page: Page, requests: Awaited<ReturnType<typeof openIntegratedCatalog>>, id: string): Promise<Locator> {
  const project = requests.projects.get(id);
  if (!project) throw new Error(`Actual local catalog has no game ${id}`);
  await page.locator(".catalog-search input").fill(project.name);
  await page.locator(".catalog-search input").press("Enter");
  const card = page.locator(`.catalog-card[data-project-id="${id}"]`);
  await expect(card).toHaveCount(1);
  await card.scrollIntoViewIfNeeded();
  return card;
}

async function expectNoGameSideEffects(page: Page, context: BrowserContext, requests: Awaited<ReturnType<typeof openIntegratedCatalog>>) {
  expect(requests.views).toEqual([]);
  expect(requests.gameOpens).toEqual([]);
  expect(requests.otherWrites).toEqual([]);
  expect(context.pages()).toHaveLength(1);
  const saved = await page.evaluate((key) => JSON.parse(localStorage.getItem(key) ?? '{"wantedIds":[],"recent":[]}') as { wantedIds: string[]; recent: unknown[] }, storageKey);
  expect(saved.wantedIds).toEqual([]);
  expect(saved.recent).toEqual([]);
}

test.describe("card/rating/navigation integration: desktop", () => {
  test.use({ viewport: { width: 1440, height: 1000 } });

  test("scored hover badge opens native detail with real provenance/dimensions; Escape restores focus", async ({ page, context }) => {
    const requests = await openIntegratedCatalog(page, context);
    const card = await cardFor(page, requests, "211");
    const project = requests.projects.get("211")!;
    const rating = project.ai_rating!;
    const badge = card.locator(".catalog-ai-rating__badge");
    await expect(badge).toBeHidden();
    await card.hover();
    await expect(badge).toBeVisible();
    await expect(badge.locator("strong")).toHaveText(rating.score!.toFixed(1));
    expect(await badge.evaluate((node) => node.closest("a") === null)).toBe(true);
    await badge.click();
    const dialog = page.locator("dialog.catalog-ai-rating-dialog[open]");
    await expect(dialog).toBeVisible();
    expect(await dialog.evaluate((node) => node.matches(":modal"))).toBe(true);
    await expect(dialog.locator("h2")).toHaveText(project.name);
    await expect(dialog.locator(".catalog-ai-rating-dialog__total strong")).toHaveText(rating.score!.toFixed(1));
    await expect(dialog.locator(".catalog-ai-rating-dialog__provenance")).toContainText("其他 AI 提供，用户采纳");
    await expect(dialog.locator("time")).toHaveAttribute("datetime", rating.evaluated_at ?? rating.reported_review_date!);
    await expect(dialog.locator(".catalog-ai-rating-dialog__provenance")).toContainText("具体时间未提供");
    await expect(dialog.locator(".catalog-ai-rating-dialog__provenance")).toContainText("时区未提供");
    await expect(dialog.locator(".catalog-ai-rating-dialog__provenance")).toContainText(`游戏版本 ${rating.game_version || "未知"}`);
    const dimensions = dialog.locator(".catalog-ai-rating-dialog__dimensions li");
    await expect(dimensions).toHaveCount(rating.dimensions.length);
    for (const [index, dimension] of rating.dimensions.entries()) {
      await expect(dimensions.nth(index).locator(".catalog-ai-rating-dialog__dimension-name > span")).toHaveText(dimension.label);
      await expect(dimensions.nth(index).locator("small")).toHaveText(`权重 ${dimension.weight * 100}%`);
      await expect(dimensions.nth(index).locator("strong")).toHaveText(String(dimension.score));
    }
    await expect(dialog.locator(".catalog-ai-rating-dialog__scope")).toContainText(String(rating.play_scope.reported_description));
    await expect(dialog.locator(".catalog-ai-rating-dialog__limits li")).toHaveText(rating.limitations);
    await expectNoGameSideEffects(page, context, requests);
    await page.mouse.move(0, 0);
    await page.keyboard.press("Escape");
    await expect(dialog).toHaveCount(0);
    await expect(badge).toBeFocused();
    await expectNoGameSideEffects(page, context, requests);
  });

  test("keyboard focus reveals AI button and Enter opens the dialog without launching a game", async ({ page, context }) => {
    const requests = await openIntegratedCatalog(page, context);
    const card = await cardFor(page, requests, "211");
    const badge = card.locator(".catalog-ai-rating__badge");
    await card.locator(".catalog-card__open").focus();
    await expect(badge).toBeVisible();
    await page.keyboard.press("Tab");
    await expect(badge).toBeFocused();
    await page.keyboard.press("Enter");
    await expect(page.locator("dialog.catalog-ai-rating-dialog[open]")).toBeVisible();
    await expectNoGameSideEffects(page, context, requests);
  });

  test("null AI entries have no badge or invented zero score", async ({ page, context }) => {
    const requests = await openIntegratedCatalog(page, context);
    for (const id of ["37", "73"]) {
      expect(requests.projects.get(id)?.ai_rating ?? null).toBeNull();
      const card = await cardFor(page, requests, id);
      await card.hover();
      await expect(card.locator(".catalog-ai-rating, .catalog-card__ai-rating")).toHaveCount(0);
      await expect(card.locator(".catalog-card__heat")).toBeVisible();
    }
    await expectNoGameSideEffects(page, context, requests);
  });

  test("home has no sort/list controls; category navigation keeps image cards and Back restores home", async ({ page, context }) => {
    const requests = await openIntegratedCatalog(page, context);
    const homeIds = await page.locator(".catalog-card").evaluateAll((nodes) => nodes.map((node) => node.getAttribute("data-card-key")));
    await expect(page.locator(".catalog-sort, .catalog-layout-toggle, .catalog-grid--list")).toHaveCount(0);
    const category = requests.categories.find((item) => item.projects.length > 0)!;
    await page.locator('.catalog-navigation__button[aria-controls="catalog-navigation-categories"]').click();
    await page.locator(".catalog-navigation__category").filter({ hasText: new RegExp(`^${category.name}$`) }).click();
    await expect(page).toHaveURL(new RegExp(`category=${category.slug}`));
    await expect(page.locator(".catalog-group--featured")).toHaveCount(0);
    await expect(page.locator(".catalog-card").first()).toBeVisible();
    const imageCards = await page.locator(".catalog-card").evaluateAll((nodes) => nodes.map((node) => ({ image: !!node.querySelector(".catalog-card__cover img"), links: node.querySelectorAll("a").length })));
    expect(imageCards.every((card) => card.image && card.links === 1)).toBe(true);
    await expect(page.locator(".catalog-layout-toggle, .catalog-grid--list")).toHaveCount(0);
    await page.goBack();
    await expect(page).toHaveURL(`${baseURL}/games`);
    await expect(page.locator(".catalog-group--featured")).toHaveCount(1);
    await expect.poll(() => page.locator(".catalog-card").evaluateAll((nodes) => nodes.map((node) => node.getAttribute("data-card-key")))).toEqual(homeIds);
    await expect(page.locator(".catalog-sort, .catalog-layout-toggle")).toHaveCount(0);
    await expectNoGameSideEffects(page, context, requests);
  });
});

test.describe("card/rating integration: touch", () => {
  test.use({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true, deviceScaleFactor: 1 });

  test("hidden AI badge does not steal the first cover tap at its resting footprint", async ({ page, context }) => {
    const requests = await openIntegratedCatalog(page, context);
    const card = await cardFor(page, requests, "211");
    const badge = card.locator(".catalog-ai-rating__badge");
    await page.locator(".catalog-search input").blur();
    await expect(badge).toBeHidden();
    const point = await badge.evaluate((node) => {
      const rect = node.getBoundingClientRect();
      return { x: rect.x + rect.width / 2, y: rect.y + rect.height / 2 };
    });
    expect(await page.evaluate(({ x, y }) => Boolean(document.elementFromPoint(x, y)?.closest(".catalog-card__open")), point)).toBe(true);
    await page.evaluate(() => {
      const events: Array<{ type: string; target: string; focused: string }> = [];
      Object.assign(window, { cardIntegrationTouchEvents: events });
      for (const type of ["pointerdown", "focusin", "pointerup", "click"]) document.addEventListener(type, (event) => {
        const target = event.target instanceof Element ? event.target.closest("button, a, article") : null;
        events.push({ type, target: target?.getAttribute("class") ?? "other", focused: document.activeElement?.getAttribute("class") ?? "other" });
      }, true);
    });
    const popupReady = context.waitForEvent("page", { timeout: 5000 }).catch(() => null);
    await page.touchscreen.tap(point.x, point.y);
    await page.waitForTimeout(250);
    await test.info().attach("native-touch-dispatch", { body: JSON.stringify(await page.evaluate(() => (window as unknown as { cardIntegrationTouchEvents: unknown }).cardIntegrationTouchEvents), null, 2), contentType: "application/json" });
    const popup = await popupReady;
    expect(popup, "first touch must open the native game link, even at a hidden rating badge footprint").not.toBeNull();
    if (!popup) return;
    await expect(popup.locator("h1")).toHaveText("Local game target intercepted");
    await expect.poll(() => requests.views).toEqual(["211"]);
    expect(requests.gameOpens).toHaveLength(1);
    await expect(page.locator("dialog.catalog-ai-rating-dialog[open]")).toHaveCount(0);
    expect(requests.otherWrites).toEqual([]);
    await popup.close();
  });

  test("longpress makes AI detail reachable; dialog opens and closes without game/favorite side effects", async ({ page, context }) => {
    const requests = await openIntegratedCatalog(page, context);
    const card = await cardFor(page, requests, "211");
    await page.locator(".catalog-search input").blur();
    const cover = await card.locator(".catalog-card__cover").boundingBox();
    if (!cover) throw new Error("Missing local game cover");
    const session = await context.newCDPSession(page);
    await session.send("Input.dispatchTouchEvent", { type: "touchStart", touchPoints: [{ x: cover.x + cover.width / 2, y: cover.y + cover.height / 2, id: 1 }] });
    await expect(card).toHaveClass(/catalog-card--touch-actions/);
    await session.send("Input.dispatchTouchEvent", { type: "touchEnd", touchPoints: [] });
    await card.locator(".catalog-ai-rating__badge").tap();
    const dialog = page.locator("dialog.catalog-ai-rating-dialog[open]");
    await expect(dialog).toBeVisible();
    await expect(dialog.locator(".catalog-ai-rating-dialog__dimensions li")).toHaveCount(5);
    await expectNoGameSideEffects(page, context, requests);
    const close = dialog.locator(".catalog-ai-rating-dialog__close");
    const box = await close.boundingBox();
    expect(box && box.x >= 0 && box.y >= 0 && box.x + box.width <= 390 && box.y + box.height <= 844).toBe(true);
    await close.tap();
    await expect(dialog).toHaveCount(0);
    await expectNoGameSideEffects(page, context, requests);
    await session.detach();
  });
});

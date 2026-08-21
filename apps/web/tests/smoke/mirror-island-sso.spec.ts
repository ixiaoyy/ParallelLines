import { expect, test } from "@playwright/test";

test("anonymous forum-account handoff preserves the resume marker through login", async ({ page }) => {
  await page.goto("/play?mirror_sso=1");

  await expect(page).toHaveURL(/\/auth\?redirect=\/play\?mirror_sso=1$/);
});

test("signed-in forum-account handoff issues one ticket and returns to Mirror Island", async ({ page }) => {
  let ticketRequests = 0;
  await page.addInitScript(() => {
    window.localStorage.setItem("parallellines.access_token", "smoke-access-token");
  });
  await page.route("**/api/v1/auth/fablespace/ticket", async (route) => {
    ticketRequests += 1;
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        data: {
          redirect_url: "https://fable.example/api/v1/auth/parallellines/callback?code=smoke-ticket",
          expires_in_seconds: 60,
        },
      }),
    });
  });
  await page.route("https://fable.example/**", async (route) => {
    await route.fulfill({ contentType: "text/html", body: "<title>Mirror SSO complete</title>" });
  });

  await page.goto("/play?mirror_sso=1");

  await expect(page).toHaveURL(
    "https://fable.example/api/v1/auth/parallellines/callback?code=smoke-ticket",
  );
  expect(ticketRequests).toBe(1);
});

test("returning from browser cache does not show a stale navigation failure", async ({ page }) => {
  await page.addInitScript(() => {
    window.localStorage.setItem("parallellines.access_token", "smoke-access-token");
    const nativeSetTimeout = window.setTimeout.bind(window);
    window.setTimeout = ((handler: TimerHandler, timeout?: number, ...args: unknown[]) =>
      nativeSetTimeout(handler, timeout === 8_000 ? 500 : timeout, ...args)) as typeof window.setTimeout;
  });
  await page.route("**/api/v1/auth/fablespace/ticket", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        data: {
          redirect_url: "/play#mirror-sso-pending",
          expires_in_seconds: 60,
        },
      }),
    });
  });

  await page.goto("/play");
  await page.getByRole("button", { name: /私密空间/ }).click();
  await expect(page).toHaveURL(/\/play#mirror-sso-pending$/);

  await page.evaluate(() => {
    window.dispatchEvent(new PageTransitionEvent("pagehide", { persisted: true }));
    window.dispatchEvent(new PageTransitionEvent("pageshow", { persisted: true }));
  });
  await page.waitForTimeout(600);

  await expect(page.getByText("跳转未完成，请重试。")).toHaveCount(0);
  await expect(page.getByRole("button", { name: /私密空间/ })).toBeEnabled();
});

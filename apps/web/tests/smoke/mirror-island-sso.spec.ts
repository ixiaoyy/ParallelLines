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

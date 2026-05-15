import { expect, test } from "@playwright/test";

const apiBaseUrl = process.env.PLAYWRIGHT_API_BASE_URL ?? "http://127.0.0.1:8000/api/v1";

test("register login create topic and reply", async ({ page, request }) => {
  const suffix = Date.now().toString(36);
  const username = `smoke_${suffix}`;
  const password = "strong-pass-123";
  const boardSlug = `smoke-${suffix}`;
  const boardName = `Smoke 测试版块 ${suffix}`;
  const topicTitle = `Smoke 发布主题 ${suffix} 覆盖注册登录发帖回复流程`;
  const topicBody = "环境：CI smoke test。复现步骤：注册、登录、发布主题、回复主题。期望结果：页面显示新主题。";
  const replyBody = `Smoke 回复 ${suffix}：确认回复能通过真实 API 写入并回显。`;

  const registerResponse = await request.post(`${apiBaseUrl}/auth/register`, {
    data: {
      username,
      email: `${username}@example.com`,
      password,
    },
  });
  expect(registerResponse.ok()).toBeTruthy();

  const loginResponse = await request.post(`${apiBaseUrl}/auth/login`, {
    data: { account: username, password },
  });
  expect(loginResponse.ok()).toBeTruthy();
  const loginPayload = (await loginResponse.json()) as {
    data: { access_token: string };
  };
  const token = loginPayload.data.access_token;

  const boardResponse = await request.post(`${apiBaseUrl}/boards`, {
    headers: { Authorization: `Bearer ${token}` },
    data: {
      slug: boardSlug,
      name: boardName,
      description: "Playwright smoke test 自动创建的临时版块。",
      color: "#3B82F6",
    },
  });
  expect(boardResponse.ok()).toBeTruthy();

  await page.addInitScript((accessToken) => {
    window.localStorage.setItem("parallellines.access_token", accessToken);
  }, token);

  await page.goto(`/new-topic?board=${boardSlug}`);
  await expect(page.getByRole("button", { name: boardName })).toBeVisible();
  await page.getByLabel("主题标题").fill(topicTitle);
  await page.getByLabel("正文").fill(topicBody);
  await page.getByRole("textbox", { name: "标签" }).fill("smoke, e2e");
  await page.getByRole("button", { name: "发布主题" }).last().click();

  await expect(page.getByRole("heading", { name: topicTitle })).toBeVisible();
  await page.getByPlaceholder(/例如：我在 PostgreSQL/).fill(replyBody);
  await page.getByRole("button", { name: "发布回复" }).click();
  await expect(page.getByText(replyBody)).toBeVisible();
});

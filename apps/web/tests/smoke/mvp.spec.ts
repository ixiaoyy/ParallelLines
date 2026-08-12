import { expect, test } from "@playwright/test";

const apiBaseUrl = process.env.PLAYWRIGHT_API_BASE_URL ?? "http://127.0.0.1:8000/api/v1";

function buttonName(label: string) {
  return new RegExp(label.split("").map(escapeRegExp).join("\\s*"));
}

function escapeRegExp(value: string) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

test("register login create topic and reply", async ({ page, request }) => {
  const suffix = Date.now().toString(36);
  const username = `smoke_${suffix}`;
  const password = "strong-pass-123";
  const boardSlug = `smoke-${suffix}`;
  const boardName = `Smoke 测试版块 ${suffix}`;
  const topicTitle = `Smoke 发布主题 ${suffix}`;
  const topicBody = "环境：CI smoke test。复现步骤：注册、登录、发布主题、回复主题。期望结果：页面显示新主题。";
  const replyBody = `Smoke 回复 ${suffix}：确认回复能通过真实服务写入并回显。`;

  await page.goto("/auth?mode=register");
  const registerForm = page.getByRole("form", { name: "注册表单" });
  await expect(registerForm).toBeVisible();
  await registerForm.getByLabel("用户名").fill(username);
  await registerForm.getByLabel("邮箱").fill(`${username}@example.com`);
  await registerForm.getByLabel("密码", { exact: true }).fill(password);
  await registerForm.getByLabel("确认密码").fill(password);
  await registerForm.getByRole("button", { name: buttonName("创建账号") }).click();

  const verificationForm = page.getByRole("form", { name: "验证码激活表单" });
  await expect(verificationForm.getByText("验证码已发送，请查收邮件。")).toBeVisible();
  await verificationForm.getByRole("button", { name: buttonName("激活账号") }).click();
  await expect(page.getByRole("banner").getByRole("link", { name: username })).toBeVisible();

  await page.getByRole("button", { name: "退出" }).click();
  await expect(page.getByRole("link", { name: "登录/注册" })).toBeVisible();

  await page.getByRole("link", { name: "登录/注册" }).click();
  const loginForm = page.getByRole("form", { name: "登录表单" });
  await expect(loginForm).toBeVisible();
  await loginForm.getByLabel("用户名或邮箱").fill(username);
  await loginForm.getByLabel("密码").fill(password);
  await loginForm.getByRole("button", { name: buttonName("登录") }).click();
  await expect(page.getByRole("banner").getByRole("link", { name: username })).toBeVisible();

  const token = await page.evaluate(() => window.localStorage.getItem("parallellines.access_token"));
  expect(token).toBeTruthy();

  const boardResponse = await request.post(`${apiBaseUrl}/boards`, {
    headers: { Authorization: `Bearer ${token ?? ""}` },
    data: {
      slug: boardSlug,
      name: boardName,
      description: "Playwright smoke test 自动创建的临时版块。",
      color: "#409EFF",
    },
  });
  expect(boardResponse.ok()).toBeTruthy();

  await page.goto(`/new-topic?board=${boardSlug}`);
  await expect(page.getByRole("button", { name: boardName })).toBeVisible();
  await page.getByLabel("主题标题").fill(topicTitle);
  await page.getByLabel("正文").fill(topicBody);
  await page.getByRole("textbox", { name: "标签" }).fill("原创");
  await page.getByRole("button", { name: buttonName("发布主题") }).last().click();

  await expect(page.getByRole("heading", { name: topicTitle })).toBeVisible();
  await page.getByLabel("回复正文").fill(replyBody);
  await page.getByRole("button", { name: buttonName("发布回复") }).click();
  await expect(page.getByText(replyBody)).toBeVisible();
});

test("board directory expansion and scroll survive history return", async ({ page }) => {
  const now = new Date().toISOString();
  const boards = Array.from({ length: 8 }, (_, index) => ({
    id: String(index + 1),
    slug: `history-board-${index + 1}`,
    name: `历史版块 ${index + 1}`,
    description: `用于返回状态测试的版块 ${index + 1}`,
    color: "#409EFF",
    avatar_url: null,
    owner_id: null,
    parent_board_id: null,
    parent_board_slug: null,
    parent_board_name: null,
    visibility: "public",
    required_tags: [],
    allowed_tags: [],
    post_template: null,
    default_notification_level: "normal",
    default_sort: "latest",
    topic_count: 20 - index,
    post_count: 40 - index,
    follower_count: 0,
    is_following: false,
    notification_level: null,
    can_create_topic: true,
    created_at: now,
    updated_at: now,
  }));
  const tags = Array.from({ length: 9 }, (_, index) => ({
    id: String(index + 1),
    name: `历史标签 ${index + 1}`,
    slug: `history-tag-${index + 1}`,
    topic_count: 20 - index,
  }));

  await page.route(
    (url) => url.pathname.endsWith("/api/v1/boards"),
    (route) => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ data: boards }) }),
  );
  await page.route(
    (url) => url.pathname.endsWith("/api/v1/tags") && url.searchParams.get("limit") === "60",
    (route) => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ data: tags }) }),
  );

  await page.setViewportSize({ width: 390, height: 600 });
  await page.goto("/boards");

  const boardsSection = page.locator('section[aria-labelledby="all-boards-title"]');
  const tagsSection = page.locator('section[aria-labelledby="hot-tags-title"]');
  await expect(boardsSection.getByRole("link")).toHaveCount(6);
  await boardsSection.getByRole("button", { name: "查看全部" }).click();
  await expect(boardsSection.getByRole("link")).toHaveCount(8);
  expect(new URL(page.url()).searchParams.get("boards")).toBe("all");

  await expect(tagsSection.getByRole("link")).toHaveCount(8);
  await tagsSection.getByRole("button", { name: "查看全部" }).click();
  await expect(tagsSection.getByRole("link")).toHaveCount(10);
  expect(new URL(page.url()).searchParams.get("tags")).toBe("all");

  const targetTag = tagsSection.getByRole("link").filter({ hasText: "# 历史标签 9" });
  await targetTag.scrollIntoViewIfNeeded();
  const scrollYBeforeNavigation = await page.evaluate(() => window.scrollY);
  expect(scrollYBeforeNavigation).toBeGreaterThan(0);
  await targetTag.click();
  await expect(page).toHaveURL(/\/search\?/);

  await page.goBack();
  await expect(page).toHaveURL(/\/boards\?/);
  await expect(boardsSection.getByRole("link")).toHaveCount(8);
  await expect(tagsSection.getByRole("link")).toHaveCount(10);
  await expect
    .poll(() => page.evaluate(() => window.scrollY))
    .toBeGreaterThanOrEqual(Math.max(1, scrollYBeforeNavigation - 100));
});

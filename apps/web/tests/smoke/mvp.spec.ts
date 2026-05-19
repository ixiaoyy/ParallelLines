import { expect, test } from "@playwright/test";

const apiBaseUrl = process.env.PLAYWRIGHT_API_BASE_URL ?? "http://127.0.0.1:8000/api/v1";

function buttonName(label: string) {
  return new RegExp(label.split("").map(escapeRegExp).join("\\s*"));
}

function escapeRegExp(value: string) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function topicIdFromUrl(value: string) {
  const segments = new URL(value).pathname.split("/").filter(Boolean);
  if (segments[0] === "topics") {
    return segments[1] ?? "";
  }

  if (segments[0] === "t") {
    return segments[2] ?? "";
  }

  return segments.at(-1) ?? "";
}

test("register login create topic reply and interactions", async ({ page, request }) => {
  const suffix = Date.now().toString(36);
  const username = `smoke_${suffix}`;
  const otherUsername = `smoke_other_${suffix}`;
  const password = "strong-pass-123";
  const boardSlug = `smoke-${suffix}`;
  const boardName = `Smoke 测试版块 ${suffix}`;
  const topicTitle = `Smoke 发布主题 ${suffix} 覆盖注册登录发帖回复流程`;
  const topicBody = "环境：CI smoke test。复现步骤：注册、登录、发布主题、回复主题。期望结果：页面显示新主题。\n\n```ts\nconst smokeCopyCode = \"smoke-copy-code\";\n```";
  const replyBody = `Smoke 回复 ${suffix}：确认回复能通过真实服务写入并回显。`;
  const otherReplyBody = `Smoke 其他用户回复 ${suffix}：用于验证只看楼主会隐藏非楼主楼层。`;

  await page.goto("/auth?mode=register");
  await expect(page.getByRole("heading", { name: "加入平行线，继续清晰讨论。" })).toBeVisible();
  const registerForm = page.getByRole("form", { name: "注册表单" });
  await registerForm.getByLabel("用户名").fill(username);
  await registerForm.getByLabel("邮箱").fill(`${username}@example.com`);
  await registerForm.getByLabel("密码").fill(password);
  await registerForm.getByRole("button", { name: buttonName("创建账号") }).click();
  await expect(page.getByRole("banner").getByRole("link", { name: username })).toBeVisible();

  await page.getByRole("button", { name: "退出" }).click();
  await expect(page.getByRole("link", { name: "登录/注册" })).toBeVisible();

  await page.getByRole("link", { name: "登录/注册" }).click();
  const loginForm = page.getByRole("form", { name: "登录表单" });
  await loginForm.getByLabel("用户名或邮箱").fill(username);
  await loginForm.getByLabel("密码").fill(password);
  await loginForm.getByRole("button", { name: buttonName("登录") }).click();
  await expect(page.getByRole("banner").getByRole("link", { name: username })).toBeVisible();

  const token = await page.evaluate(() => window.localStorage.getItem("parallellines.access_token"));
  expect(token).toBeTruthy();

  const otherRegisterResponse = await request.post(`${apiBaseUrl}/auth/register`, {
    data: {
      username: otherUsername,
      email: `${otherUsername}@example.com`,
      password,
    },
  });
  expect(otherRegisterResponse.ok()).toBeTruthy();
  const otherRegisterPayload = (await otherRegisterResponse.json()) as {
    data: { access_token: string };
  };
  const otherToken = otherRegisterPayload.data.access_token;

  const boardResponse = await request.post(`${apiBaseUrl}/boards`, {
    headers: { Authorization: `Bearer ${token ?? ""}` },
    data: {
      slug: boardSlug,
      name: boardName,
      description: "Playwright smoke test 自动创建的临时版块。",
      color: "#3B82F6",
    },
  });
  expect(boardResponse.ok()).toBeTruthy();

  await page.goto(`/new-topic?board=${boardSlug}`);
  await expect(page.getByRole("button", { name: boardName })).toBeVisible();
  await page.getByLabel("主题标题").fill(topicTitle);
  await page.getByLabel("正文").fill(topicBody);
  await page.getByRole("textbox", { name: "标签" }).fill("smoke, e2e");
  await page.getByRole("button", { name: buttonName("发布主题") }).last().click();

  await expect(page.getByRole("heading", { name: topicTitle })).toBeVisible();
  const topicId = topicIdFromUrl(page.url());
  if (!topicId) {
    throw new Error("Expected topic id in topic detail URL");
  }
  await page.getByLabel("回复正文").fill(replyBody);
  await page.getByRole("button", { name: buttonName("发布回复") }).click();
  await expect(page.getByText(replyBody)).toBeVisible();

  const otherReplyResponse = await request.post(`${apiBaseUrl}/topics/${topicId}/posts`, {
    headers: { Authorization: `Bearer ${otherToken}` },
    data: { raw_md: otherReplyBody },
  });
  expect(otherReplyResponse.ok()).toBeTruthy();
  await page.reload();
  await expect(page.getByText(otherReplyBody)).toBeVisible();

  await page.getByRole("button", { name: buttonName("复制链接") }).click();
  await expect(page.getByRole("status").filter({ hasText: /已复制主题链接|无法访问剪贴板/ })).toBeVisible();

  await page.getByRole("button", { name: buttonName("只看楼主") }).click();
  await expect(page.getByText(/已切换为只看楼主/)).toBeVisible();
  await expect(page.getByText(otherReplyBody)).toBeHidden();
  await page.getByRole("button", { name: buttonName("显示全部") }).click();
  await expect(page.getByText(otherReplyBody)).toBeVisible();

  await page.getByRole("button", { name: buttonName("引用") }).first().click();
  await expect(page.getByLabel("回复正文")).toHaveValue(new RegExp(`> ${username} #1`));

  await page.getByRole("button", { name: buttonName("复制本楼层代码块") }).first().click();
  await expect(page.getByRole("status").filter({ hasText: /已复制代码|无法访问剪贴板/ })).toBeVisible();

  await page.getByRole("button", { name: buttonName("编辑") }).first().click();
  const editedBody = `${topicBody}\n\n编辑巡检 ${suffix}`;
  await page.getByLabel("编辑回复内容").fill(editedBody);
  await page.getByRole("button", { name: buttonName("保存编辑") }).click();
  await expect(page.getByText(`编辑巡检 ${suffix}`)).toBeVisible();

  await page.getByRole("banner").getByRole("link", { name: username }).click();
  await expect(page.getByRole("heading", { name: username, exact: true })).toBeVisible();
  await expect(page.getByRole("link", { name: topicTitle })).toBeVisible();

  const notificationTrigger = page.getByRole("banner").getByRole("button", { name: /^通知，/ });
  await notificationTrigger.click();
  await expect(page.getByRole("dialog", { name: "通知中心" })).toBeVisible();
  await notificationTrigger.click();
  await expect(page.getByRole("dialog", { name: "通知中心" })).toBeHidden();

  await page.getByLabel("搜索平行线", { exact: true }).fill(topicTitle);
  await page.getByLabel("搜索平行线", { exact: true }).press("Enter");
  await expect(page.getByRole("heading", { name: /按错误码/ })).toBeVisible();
  await expect(page.getByRole("link", { name: topicTitle })).toBeVisible();
  await page.getByRole("button", { name: "热门" }).click();
  await page.getByRole("button", { name: "高信号" }).click();

  await page.getByRole("navigation", { name: "主导航" }).getByRole("link", { name: "版块" }).click();
  await expect(page.getByRole("heading", { name: /先搜索问题，再选择版块/ })).toBeVisible();
  await expect(page.getByRole("link", { name: `按主题进入 ${boardName}` })).toBeVisible();

  await page.getByRole("link", { name: "平行线首页" }).click();
  await expect(page.getByLabel("主题发现流").getByRole("link", { name: topicTitle })).toBeVisible();
  await expect(page.getByRole("link", { name: "smoke" }).first()).toBeVisible();
});

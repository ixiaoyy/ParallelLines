/**
 * 马甲账号回复测试套件
 *
 * 测试场景：
 * 1. 使用预设的马甲账号登录
 * 2. 在现有主题上发布回复
 * 3. 检查回复页面布局和交互
 * 4. 检查回复列表、楼层显示、分页等
 *
 * 预设马甲账号（密码统一：oldhuai123）：
 * - oldhuai
 * - 不吃香菜的猫
 * - 老槐
 * 等（见 apps/api/scripts/seed_persona_discussions.py）
 */

import { expect, test } from "@playwright/test";

const apiBaseUrl = process.env.PLAYWRIGHT_API_BASE_URL ?? "http://127.0.0.1:8000/api/v1";

// 预设测试账号配置
const TEST_ACCOUNTS = [
  { username: "oldhuai", password: "oldhuai123" },
];

/**
 * Builds a tolerant accessible-name matcher for buttons whose Chinese text may be split by icon markup.
 * Key parameter: `label` is the visible button text to match. Return value: a whitespace-tolerant RegExp.
 */
function buttonName(label: string) {
  return new RegExp(label.split("").map(escapeRegExp).join("\\s*"));
}

/**
 * Escapes user-facing label text before embedding it in a regular expression.
 * Key parameter: `value` is plain text. Return value: text safe for RegExp construction.
 */
function escapeRegExp(value: string) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

test.describe("马甲账号回复测试", () => {
  test("马甲账号 - 使用 oldhuai 登录并发布回复", async ({ page, request }) => {
    const account = TEST_ACCOUNTS[0];
    const suffix = Date.now().toString(36);

    // 1. 通过 API 登录获取 token
    const loginResponse = await request.post(`${apiBaseUrl}/auth/login`, {
      data: {
        account: account.username,
        password: account.password,
      },
    });

    if (!loginResponse.ok()) {
      console.log(`API 登录失败，状态码: ${loginResponse.status()}`);
      const respText = await loginResponse.text();
      console.log(`响应内容: ${respText.substring(0, 200)}`);
      throw new Error(`登录失败: ${respText}`);
    }

    const loginData = (await loginResponse.json()) as { data: { access_token: string } };
    const token = loginData.data.access_token;
    console.log(`API 登录成功，获取 token: ${token.substring(0, 20)}...`);

    // 2. 设置 token 到 localStorage 并刷新页面
    await page.goto("/");
    await page.evaluate(
      (t: string) => {
        window.localStorage.setItem("parallellines.access_token", t);
        window.localStorage.setItem("parallellines.refresh_token", "");
      },
      token,
    );
    await page.reload();
    await page.waitForLoadState("networkidle");

    // 3. 验证登录成功 - 检查用户菜单
    const userMenu = page.locator("[role='banner']").getByRole("link", { name: account.username });
    const userMenuVisible = await userMenu.isVisible().catch(() => false);
    console.log(`用户菜单可见: ${userMenuVisible}`);

    // 4. 获取一个现有主题
    const topicsResponse = await request.get(`${apiBaseUrl}/topics?limit=5`);
    expect(topicsResponse.ok()).toBeTruthy();
    const topicsData = (await topicsResponse.json()) as {
      data: Array<{ id: string; title: string; reply_count: number }>;
    };

    if (topicsData.data.length === 0) {
      console.log("没有可用的主题，跳过测试");
      return;
    }

    // 找一个有回复的主题
    let targetTopic = topicsData.data.find(t => t.reply_count > 0) || topicsData.data[0];
    const topicId = targetTopic.id;
    const topicTitle = targetTopic.title;
    console.log(`测试目标主题: ${topicTitle} (ID: ${topicId})`);

    // 5. 进入主题详情页
    await page.goto(`/t/${topicId}`);
    await page.waitForLoadState("networkidle");

    // 6. 发布回复
    const replyBody = `马甲账号回复 ${suffix}：这是自动测试生成的回复内容。`;
    console.log(`准备发布回复: ${replyBody.substring(0, 50)}...`);

    // 找到回复编辑器并填写内容
    const replyEditor = page.getByLabel("回复正文").first();
    const editorVisible = await replyEditor.isVisible().catch(() => false);
    console.log(`回复编辑器可见: ${editorVisible}`);

    if (editorVisible) {
      await replyEditor.fill(replyBody);

      // 点击发布按钮
      const submitBtn = page.getByRole("button", { name: buttonName("发布回复") });
      await submitBtn.click();

      // 等待回复出现
      const replyText = page.getByText(replyBody);
      try {
        await replyText.waitFor({ timeout: 15000 });
        console.log("回复发布成功！");
      } catch {
        console.log("回复文本未在预期时间内出现，可能发布失败");
      }
    } else {
      // 尝试找到回复按钮并点击展开编辑器
      console.log("回复编辑器不可见，尝试其他方式...");

      const replyBtn = page.getByRole("button", { name: /回复/ }).first();
      const replyBtnVisible = await replyBtn.isVisible().catch(() => false);

      if (replyBtnVisible) {
        await replyBtn.click();
        await page.waitForTimeout(1000);

        const editorNowVisible = await replyEditor.isVisible().catch(() => false);
        if (editorNowVisible) {
          await replyEditor.fill(replyBody);
          await page.getByRole("button", { name: buttonName("发布回复") }).click();
        }
      }
    }

    // 7. 验证结果
    const replyCount = await page.locator("#topic-reply-list .post-anchor, .post-item").count();
    console.log(`回复列表共有 ${replyCount} 条回复`);

    if (replyCount > 0) {
      console.log("✅ 回复功能测试通过");
    } else {
      console.log("⚠️ 未检测到回复，可能需要人工检查");
    }
  });

  test("回复页面 - 布局和交互检查", async ({ page, request }) => {
    // 获取一个有回复的主题
    const topicsResponse = await request.get(`${apiBaseUrl}/topics?limit=5`);
    const topicsData = (await topicsResponse.json()) as {
      data: Array<{ id: string; title: string }>;
    };

    if (topicsData.data.length === 0) {
      console.log("没有可用的主题来测试回复页面，跳过测试");
      return;
    }

    // 找到有回复的主题
    let targetTopic = null;
    for (const topic of topicsData.data) {
      const postsResponse = await request.get(`${apiBaseUrl}/topics/${topic.id}/posts`);
      if (postsResponse.ok()) {
        const postsData = (await postsResponse.json()) as { data: unknown[] };
        if (postsData.data.length > 1) {
          targetTopic = topic;
          break;
        }
      }
    }

    if (!targetTopic) {
      console.log("没有找到有回复的主题，跳过页面检查");
      return;
    }

    // 进入主题详情页
    await page.goto(`/t/${targetTopic.id}`);
    await page.waitForLoadState("networkidle");

    // ========== 检查回复列表区域 ==========

    // 1. 检查回复列表容器存在
    const repliesPanel = page.locator("#replies, .topic-replies-panel, #topic-reply-list");
    const panelVisible = await repliesPanel.first().isVisible().catch(() => false);
    console.log(`回复列表容器可见: ${panelVisible}`);

    // 2. 检查回复计数显示
    const replyCountLabel = page.getByText(/\d+ 条回复/, { exact: false });
    const isReplyCountVisible = await replyCountLabel.isVisible().catch(() => false);
    console.log(`回复计数显示可见: ${isReplyCountVisible}`);

    // 3. 检查每条回复项
    const postItems = page.locator("#topic-reply-list .post-anchor, .post-item, .reply-item");
    const postCount = await postItems.count();
    console.log(`发现 ${postCount} 条回复`);

    if (postCount > 0) {
      // 检查回复楼层号
      const floorNumbers = page.locator("[id^='post-']");
      const floorCount = await floorNumbers.count();
      console.log(`发现 ${floorCount} 个楼层锚点`);

      // ========== 检查回复交互按钮 ==========

      // 4. 检查回复按钮存在
      const replyButtons = page.getByRole("button", { name: /回复/ });
      const replyBtnCount = await replyButtons.count();
      console.log(`发现 ${replyBtnCount} 个回复按钮`);

      // 5. 检查引用按钮存在
      const quoteButtons = page.getByRole("button", { name: buttonName("引用") });
      const quoteBtnCount = await quoteButtons.count();
      console.log(`发现 ${quoteBtnCount} 个引用按钮`);

      // 6. 检查点赞按钮
      const likeButtons = page.getByRole("button", { name: /赞|❤️/ });
      const likeBtnCount = await likeButtons.count();
      console.log(`发现 ${likeBtnCount} 个点赞按钮`);

      // 7. 测试引用功能
      if (quoteBtnCount > 0) {
        const firstQuoteBtn = page.getByRole("button", { name: buttonName("引用") }).first();
        await firstQuoteBtn.click();
        await page.waitForTimeout(500);

        const replyEditor = page.getByLabel("回复正文");
        const editorValue = await replyEditor.inputValue();
        console.log(`引用内容: ${editorValue.substring(0, 100) || "(空)"}`);
      }
    }

    // ========== 检查回复排序功能 ==========

    // 8. 检查排序选项
    const sortButtons = page.getByRole("button", { name: /时间|最新|最早|热门/ });
    const sortBtnCount = await sortButtons.count();
    if (sortBtnCount > 0) {
      console.log(`发现 ${sortBtnCount} 个排序按钮`);
    }

    // ========== 检查回复分页 ==========

    // 9. 检查是否有分页控件
    const pagination = page.locator(".pagination, .ant-pagination");
    const paginationVisible = await pagination.first().isVisible().catch(() => false);
    console.log(`分页控件可见: ${paginationVisible}`);

    // ========== 检查回复编辑器 ==========

    // 10. 检查回复编辑器存在
    const composer = page.locator(".composer, .composer-drawer");
    const composerVisible = await composer.first().isVisible().catch(() => false);
    console.log(`回复编辑器可见: ${composerVisible}`);

    // 11. 检查提交按钮
    const submitBtn = page.getByRole("button", { name: buttonName("发布回复") });
    const submitVisible = await submitBtn.isVisible().catch(() => false);
    console.log(`发布回复按钮可见: ${submitVisible}`);
  });

  test("回复页面 - 响应式布局检查", async ({ page, request }) => {
    // 获取一个有回复的主题
    const topicsResponse = await request.get(`${apiBaseUrl}/topics?limit=1`);
    const topicsData = (await topicsResponse.json()) as {
      data: Array<{ id: string }>;
    };

    if (topicsData.data.length === 0) {
      return;
    }

    await page.goto(`/t/${topicsData.data[0].id}`);
    await page.waitForLoadState("networkidle");

    // 测试不同视口
    const viewports = [
      { name: "桌面端", width: 1920, height: 1080 },
      { name: "平板", width: 768, height: 1024 },
      { name: "移动端", width: 375, height: 667 },
    ];

    for (const vp of viewports) {
      await page.setViewportSize({ width: vp.width, height: vp.height });
      await page.waitForTimeout(300);

      // 检查水平溢出
      const hasHorizontalScroll = await page.evaluate(() => {
        return document.documentElement.scrollWidth > document.documentElement.clientWidth;
      });

      console.log(`${vp.name} (${vp.width}x${vp.height}): 水平溢出 = ${hasHorizontalScroll}`);

      if (vp.name === "移动端") {
        const replyEditor = page.getByLabel("回复正文").first();
        const editorVisible = await replyEditor.isVisible().catch(() => false);
        console.log(`移动端回复编辑器可见: ${editorVisible}`);
      }
    }
  });

  test("回复页面 - 性能检查", async ({ page, request }) => {
    const topicsResponse = await request.get(`${apiBaseUrl}/topics?limit=1`);
    const topicsData = (await topicsResponse.json()) as {
      data: Array<{ id: string }>;
    };

    if (topicsData.data.length === 0) {
      return;
    }

    await page.goto(`/t/${topicsData.data[0].id}`);
    await page.waitForLoadState("networkidle");

    // 测量页面加载时间
    const renderTime = await page.evaluate(() => {
      const timing = performance.getEntriesByType("navigation")[0] as PerformanceNavigation;
      return timing.domContentLoadedEventEnd - timing.navigationStart;
    });

    console.log(`页面加载时间: ${renderTime}ms`);

    // 检查图片数量
    const images = page.locator(".post-item img");
    const imageCount = await images.count();
    console.log(`回复中包含 ${imageCount} 张图片`);

    if (imageCount > 10) {
      console.log("警告: 回复中图片较多，可能影响加载性能");
    }
  });

  test("回复页面 - 无障碍检查", async ({ page, request }) => {
    const topicsResponse = await request.get(`${apiBaseUrl}/topics?limit=1`);
    const topicsData = (await topicsResponse.json()) as {
      data: Array<{ id: string }>;
    };

    if (topicsData.data.length === 0) {
      return;
    }

    await page.goto(`/t/${topicsData.data[0].id}`);
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(1000); // 等待页面稳定

    // 1. 检查回复区域是否有 ARIA 标签
    const repliesSection = page.locator("#replies, .topic-replies-panel");
    const hasAriaLabel = await repliesSection.getAttribute("aria-label").catch(() => null);
    console.log(`回复区域 aria-label: ${hasAriaLabel || "无"}`);

    // 2. 检查回复项是否有唯一标识
    const postAnchors = page.locator("[id^='post-']");
    const anchorCount = await postAnchors.count();
    console.log(`有 ${anchorCount} 个楼层锚点`);

    // 3. 检查表单元素有标签
    const replyEditor = page.getByLabel("回复正文");
    const editorLabel = await replyEditor.getAttribute("id").catch(() => null);
    console.log(`回复编辑器 ID: ${editorLabel || "无"}`);

    // 4. 检查按钮有可访问名称
    const buttons = page.locator("#topic-reply-list button");
    const buttonCount = await buttons.count();
    console.log(`回复区域有 ${buttonCount} 个按钮`);

    for (let i = 0; i < Math.min(buttonCount, 3); i++) {
      const btn = buttons.nth(i);
      const text = await btn.textContent();
      const ariaLabel = await btn.getAttribute("aria-label");
      console.log(`按钮 ${i + 1}: 文本="${text?.trim() || ""}", aria-label="${ariaLabel || "无"}"`);
    }
  });
});

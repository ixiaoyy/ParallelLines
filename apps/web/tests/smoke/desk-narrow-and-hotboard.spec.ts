import { expect, test, type Page } from "@playwright/test";

// 使用本地 Desk 的 /desk/ 构建预览，mock 热榜接口，不访问生产或外部站点。
test.use({ baseURL: "http://127.0.0.1:15224", locale: "zh-CN", serviceWorkers: "block" });

const MOCK_HOT_LISTS: Record<string, { label: string; site_url: string; items: Array<{ rank: number; title: string; url: string; hot_value: string; tag: string }> }> = {
  weibo: {
    label: "微博热搜",
    site_url: "https://s.weibo.com/top/summary",
    items: [
      { rank: 1, title: "平行线工作台实时热榜上线", url: "https://s.weibo.com/weibo?q=%23test1%23", hot_value: "284.5万", tag: "爆" },
      { rank: 2, title: "窄屏编辑体验全面升级", url: "https://s.weibo.com/weibo?q=%23test2%23", hot_value: "162.0万", tag: "热" },
      { rank: 3, title: "Edge 浏览器实测验收", url: "https://s.weibo.com/weibo?q=%23test3%23", hot_value: "98.3万", tag: "新" },
    ],
  },
  baidu: {
    label: "百度热搜",
    site_url: "https://top.baidu.com/board?tab=realtime",
    items: [
      { rank: 1, title: "百度实时热榜测试条目一", url: "https://www.baidu.com/s?wd=test1", hot_value: "492.1万", tag: "热" },
      { rank: 2, title: "百度实时热榜测试条目二", url: "https://www.baidu.com/s?wd=test2", hot_value: "310.4万", tag: "新" },
    ],
  },
};

async function setupDesk(page: Page, opts?: { failFirstHotList?: boolean }) {
  const hotRequests: string[] = [];
  let failedOnce = false;

  await page.route("**/*", async (route) => {
    const url = route.request().url();
    if (url.includes("/api/v1/workspace/hot-lists")) {
      hotRequests.push(url);
      if (opts?.failFirstHotList && !failedOnce) {
        failedOnce = true;
        return route.fulfill({
          status: 503,
          contentType: "application/json",
          body: JSON.stringify({ error: { code: "hot_list_unavailable", message: "暂时无法获取微博热搜" } }),
        });
      }
      const parsed = new URL(url);
      const source = parsed.searchParams.get("source") ?? "weibo";
      const data = MOCK_HOT_LISTS[source] ?? MOCK_HOT_LISTS.weibo;
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          data: {
            source,
            label: data.label,
            site_url: data.site_url,
            updated_at: new Date().toISOString(),
            stale: false,
            items: data.items,
          },
        }),
      });
    }
    if (url.startsWith("http://127.0.0.1:15224/")) return route.continue();
    return route.abort();
  });

  await page.goto("/desk/");
  return hotRequests;
}

test("390px 窄屏：顶部操作栏无遮挡、主题浮层不裁切、卡片可编辑排序删除", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await setupDesk(page);

  const quickBar = page.locator(".desk-quick-bar");
  await expect(quickBar).toBeVisible();
  const barBox = await quickBar.boundingBox();
  expect(barBox).not.toBeNull();

  // 第一张流式卡片必须在顶部栏下方，不被遮挡
  const firstCard = page.locator(".compact-flow-item").first();
  await expect(firstCard).toBeVisible();
  const cardBox = await firstCard.boundingBox();
  expect(cardBox).not.toBeNull();
  expect(cardBox!.y).toBeGreaterThanOrEqual(barBox!.y + barBox!.height - 4);

  // 点击主题按钮，浮层必须完全在视口内且可点击
  await quickBar.getByRole("button", { name: /主题/ }).click();
  const popover = page.locator(".theme-popover");
  await expect(popover).toBeVisible();
  const popBox = await popover.boundingBox();
  expect(popBox).not.toBeNull();
  expect(popBox!.x).toBeGreaterThanOrEqual(0);
  expect(popBox!.x + popBox!.width).toBeLessThanOrEqual(390);
  await popover.locator(".theme-swatch").first().click();
  await expect(popover).toBeHidden();

  // 点击编辑进入窄屏编辑态：每张卡显示行内编辑条，可排序、可打开编辑弹窗
  await quickBar.getByRole("button", { name: /编辑/ }).click();
  const editBars = page.locator(".compact-edit-bar");
  await expect(editBars.first()).toBeVisible();
  const firstNameBefore = await editBars.nth(0).locator(".compact-edit-name").textContent();
  const secondNameBefore = await editBars.nth(1).locator(".compact-edit-name").textContent();

  await editBars.nth(0).getByRole("button", { name: "↓" }).click();
  await expect(editBars.nth(0).locator(".compact-edit-name")).toHaveText(secondNameBefore!.trim());
  await expect(editBars.nth(1).locator(".compact-edit-name")).toHaveText(firstNameBefore!.trim());

  // 点击编辑按钮能打开组件配置弹窗，且垂直堆叠无横向溢出
  await editBars.filter({ hasText: "实时热榜" }).getByRole("button", { name: /编辑/ }).click();
  const editDialog = page.locator(".easy-dialog-main").filter({ hasText: "编辑组件" });
  await expect(editDialog).toBeVisible();
  const dlgBox = await editDialog.boundingBox();
  expect(dlgBox).not.toBeNull();
  expect(dlgBox!.width).toBeLessThanOrEqual(390);
  await editDialog.locator(".easy-dialog-close").click();
  await expect(editDialog).toBeHidden();

  // 锁定退出编辑态
  await quickBar.getByRole("button", { name: /锁定/ }).click();
  await expect(editBars).toHaveCount(0);
});

test("390px 窄屏：AI 搜索栏可点击输入且移除伪微博热搜模板；实时热榜可切榜与失败重试", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  const hotRequests = await setupDesk(page, { failFirstHotList: true });

  // AI 搜索栏不再包含伪微博热搜模板，输入框可直接点击输入
  const aiSearch = page.locator(".grid-item-AiSearch");
  await expect(aiSearch).toBeVisible();
  await expect(aiSearch.getByRole("button", { name: /微博热搜/ })).toHaveCount(0);
  await expect(aiSearch.getByRole("button", { name: /润色文案/ })).toBeVisible();

  const searchInput = aiSearch.locator(".search-input");
  await searchInput.click();
  await searchInput.fill("测试窄屏输入");
  await expect(searchInput).toHaveValue("测试窄屏输入");

  // 实时热榜首次 503 时显示重试与原站链接，点击重试后恢复展示微博热搜
  const hotBoard = page.locator(".grid-item-HotBoard");
  await expect(hotBoard.getByText("暂时无法获取微博热搜")).toBeVisible();
  await hotBoard.getByRole("button", { name: "重试" }).click();
  await expect(hotBoard.getByText("平行线工作台实时热榜上线")).toBeVisible();
  await expect(hotBoard.getByText("284.5万")).toBeVisible();

  // 切换到百度热搜
  await hotBoard.getByRole("tab", { name: "百度" }).click();
  await expect(hotBoard.getByText("百度实时热榜测试条目一")).toBeVisible();
  expect(hotRequests.some((u) => u.includes("source=baidu"))).toBe(true);
});

test("1280px 桌面端：解锁后卡片直接显示编辑/删除按钮，添加组件预览热榜不触发外网请求", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 800 });
  const hotRequests = await setupDesk(page);
  await expect(page.locator(".grid-item-HotBoard").getByText("平行线工作台实时热榜上线")).toBeVisible();
  const countBeforeGallery = hotRequests.length;

  // 解锁后无需右键，每张卡片右上角直接可见「✎ 编辑」按钮并可左键打开配置弹窗
  await page.locator(".desk-quick-bar").getByRole("button", { name: /编辑/ }).click();
  const slackEditBtn = page.locator(".grid-item-SlackCountdown .card-edit-overlay").getByRole("button", { name: /编辑/ });
  await expect(slackEditBtn).toBeVisible();
  await slackEditBtn.click();
  const editDialog = page.locator(".easy-dialog-main").filter({ hasText: "编辑组件" });
  await expect(editDialog).toBeVisible();
  await editDialog.locator(".easy-dialog-close").click();
  await expect(editDialog).toBeHidden();
  await page.locator(".desk-quick-bar").getByRole("button", { name: /锁定/ }).click();

  await page.locator(".desk-quick-bar").getByRole("button", { name: "添加组件", exact: true }).click();
  const gallery = page.getByRole("dialog", { name: "添加组件" });
  await gallery.getByRole("button", { name: /实时热榜/ }).click();
  await expect(gallery.getByText(/实时热榜条目预览/)).toBeVisible();
  expect(hotRequests.length).toBe(countBeforeGallery);
});

test("今日待办（Planify + Pomatez）：新增、已完成默认折叠、专注倒计时与秒表底栏", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 800 });
  await setupDesk(page);

  const todo = page.locator(".grid-item-TodoList");
  await expect(todo.getByRole("heading", { name: "今日待办" })).toBeVisible();
  // 未开始计时前，底部专注条不显示
  await expect(todo.locator(".focus-bar")).toHaveCount(0);

  const input = todo.getByRole("textbox", { name: "添加待办" });
  await input.fill("整理会议纪要");
  await todo.getByRole("button", { name: "添加", exact: true }).click();
  await input.fill("核对本周周报");
  await input.press("Enter");

  await expect(todo.getByText("整理会议纪要")).toBeVisible();
  await expect(todo.getByText("核对本周周报")).toBeVisible();

  // 勾选「核对本周周报」后进入默认折叠的「已完成 1」
  await todo.getByRole("checkbox", { name: "完成 核对本周周报" }).click();
  await expect(todo.getByRole("button", { name: /已完成 1/ })).toBeVisible();
  await expect(todo.locator(".completed-list")).toHaveCount(0);
  await todo.getByRole("button", { name: /已完成 1/ }).click();
  await expect(todo.locator(".completed-list").getByText("核对本周周报")).toBeVisible();

  // 对「整理会议纪要」启动专注倒计时，底部专注条出现且显示「专注中」与 25:00
  const row = todo.locator(".task-row").filter({ hasText: "整理会议纪要" });
  await row.hover();
  await row.getByRole("button", { name: /专注/ }).click();
  await expect(row.getByText("专注中")).toBeVisible();
  const focusBar = todo.locator(".focus-bar");
  await expect(focusBar).toBeVisible();
  await expect(focusBar.locator(".focus-clock")).toHaveText(/2[45]:[0-5]\d/);

  // 暂停、切换秒表模式、结束关闭底栏
  await focusBar.getByRole("button", { name: "暂停" }).click();
  await expect(focusBar.getByRole("button", { name: "继续" })).toBeVisible();
  await focusBar.locator(".focus-mode-icon").click();
  await expect(focusBar.getByText("秒表正计时")).toBeVisible();
  await expect(focusBar.locator(".focus-clock")).toHaveText("00:00");
  await focusBar.getByRole("button", { name: "结束" }).click();
  await expect(focusBar).toHaveCount(0);
});

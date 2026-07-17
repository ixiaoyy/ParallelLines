import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";

import type { AdminSystemOverviewResponse } from "../../src/features/admin/model";
import type { UserPublic } from "../../src/features/auth/model";

const adminUser: UserPublic = {
  id: "admin-1",
  username: "operator",
  email: "operator@example.com",
  avatar_url: null,
  display_name: "运营管理员",
  bio: null,
  website_url: null,
  location: null,
  role: "admin",
  level: 8,
  trust_level: 4,
  trust_level_label: "负责人",
  points_balance: 0,
  experience_total: 8_000,
  experience_to_next_level: 1_000,
  level_progress_percent: 80,
  status: "active",
  two_factor_enabled: true,
  profile_visibility: "public",
  show_activity: true,
  interface_theme: "system",
  locale: "zh-CN",
  created_at: "2025-01-01T00:00:00Z",
};

const populatedSystem: AdminSystemOverviewResponse = {
  version: "test",
  environment: "test",
  services: [
    { name: "database", status: "ok", detail: "连接正常" },
    { name: "cache", status: "degraded", detail: "响应时间偏高" },
  ],
  stats: {
    users: 1_286,
    boards: 12,
    topics: 438,
    posts: 2_761,
    pending_flags: 3,
    audit_logs: 42,
    spam_actions: 7,
  },
  queue: {
    queued: 2,
    running: 1,
    dead: 1,
    worker: "test",
    poll_seconds: 5,
    batch_size: 10,
    retry_delay_seconds: 60,
    hot_rank_interval_seconds: 300,
    upload_cleanup_interval_seconds: 3_600,
    session_cleanup_interval_seconds: 3_600,
  },
  recent_audit_logs: [
    {
      id: "audit-1",
      actor_id: "admin-1",
      actor_name: "运营管理员",
      action: "moderation.flag_resolved",
      target_type: "flag",
      target_id: "flag-12345678",
      board_id: null,
      data: {},
      created_at: "2026-07-17T08:00:00Z",
    },
  ],
  recent_email_logs: [],
  recent_errors: [],
};

interface AdminApiOptions {
  systemDelay?: Promise<void>;
  systemResponse?: AdminSystemOverviewResponse;
  systemStatus?: number;
}

async function mockAdminApi(page: Page, options: AdminApiOptions = {}) {
  await page.addInitScript(() => {
    window.localStorage.setItem("parallellines.access_token", "responsive-test-token");
  });

  await page.route("**/api/v1/**", async (route) => {
    const url = new URL(route.request().url());

    if (url.pathname.endsWith("/auth/me")) {
      await route.fulfill({ json: { data: adminUser } });
      return;
    }

    if (url.pathname.endsWith("/auth/fablespace/access")) {
      await route.fulfill({
        json: {
          data: {
            access_allowed: false,
            capabilities: [],
            access_level: null,
            expires_at: null,
            authorization_version: 1,
          },
        },
      });
      return;
    }

    if (url.pathname.endsWith("/site/settings")) {
      await route.fulfill({
        json: {
          data: {
            settings: {
              site_title: "平行线",
              brand_logo_url: "/logo-lines-mark.png",
            },
            updated_at: "2026-07-17T00:00:00Z",
          },
        },
      });
      return;
    }

    if (url.pathname.endsWith("/admin/system")) {
      await options.systemDelay;
      const status = options.systemStatus ?? 200;
      await route.fulfill({
        status,
        contentType: "application/json",
        body: JSON.stringify(
          status >= 400
            ? {
                error: {
                  code: "admin_system_unavailable",
                  message: "temporary failure",
                  details: {},
                },
              }
            : { data: options.systemResponse ?? populatedSystem },
        ),
      });
      return;
    }

    if (url.pathname.endsWith("/notifications/stream")) {
      await route.fulfill({
        status: 200,
        contentType: "text/event-stream",
        body: 'event: notifications\ndata: {"notifications":[],"unread_count":0}\n\n',
      });
      return;
    }

    if (url.pathname.endsWith("/notifications")) {
      await route.fulfill({ json: { data: { notifications: [], unread_count: 0 } } });
      return;
    }

    await route.fulfill({ json: { data: {} } });
  });
}

test("admin workbench keeps core information dense and reachable across viewports", async ({
  page,
}) => {
  await page.setViewportSize({ width: 320, height: 844 });
  await mockAdminApi(page);
  await page.goto("/admin");

  await expect(page.getByRole("heading", { name: "工作台" })).toBeVisible();
  await expect(page.locator(".admin-summary-item")).toHaveCount(4);
  await expect(page.getByRole("heading", { name: "需要处理" })).toBeVisible();

  await page.evaluate(() => document.body.scrollTo(0, document.body.scrollHeight));
  await expect.poll(() => page.evaluate(() => document.body.scrollTop)).toBeGreaterThan(0);
  const bottomClearance = await page.evaluate(() => {
    const lastQuickLink = document.querySelector(".admin-quick-grid a:last-child");
    const bottomNav = document.querySelector(".admin-console-shell__bottom-nav");
    if (!lastQuickLink || !bottomNav) {
      return null;
    }
    return {
      contentBottom: lastQuickLink.getBoundingClientRect().bottom,
      navigationTop: bottomNav.getBoundingClientRect().top,
    };
  });
  expect(bottomClearance).not.toBeNull();
  expect(bottomClearance?.contentBottom ?? Number.POSITIVE_INFINITY).toBeLessThanOrEqual(
    bottomClearance?.navigationTop ?? 0,
  );

  for (const viewport of [
    { width: 320, height: 844 },
    { width: 390, height: 844 },
    { width: 860, height: 640 },
    { width: 1440, height: 900 },
  ]) {
    await page.setViewportSize(viewport);
    await page.evaluate(() => document.body.scrollTo(0, 0));

    const layout = await page.evaluate(() => {
      const rect = (element: Element) => {
        const box = element.getBoundingClientRect();
        return {
          top: box.top,
          right: box.right,
          bottom: box.bottom,
          left: box.left,
          width: box.width,
          height: box.height,
        };
      };
      const summaryItems = Array.from(document.querySelectorAll(".admin-summary-item"));
      const bottomNav = document.querySelector(".admin-console-shell__bottom-nav");
      const bottomItems = Array.from(
        document.querySelectorAll(".admin-console-shell__bottom-item"),
      );
      const focusTitle = document.querySelector("#workbench-focus-title");
      const menuButton = document.querySelector(".admin-console-shell__menu-button");
      const notificationButton = document.querySelector(
        ".admin-console-shell__topbar-actions .notification-trigger",
      );
      const mobileBrand = document.querySelector(".admin-console-shell__mobile-brand");
      const mobileBrandLabel = document.querySelector(
        ".admin-console-shell__mobile-brand strong",
      );

      return {
        documentWidth: document.documentElement.scrollWidth,
        viewportWidth: document.documentElement.clientWidth,
        summaryItems: summaryItems.map(rect),
        bottomNavVisible: bottomNav ? getComputedStyle(bottomNav).display !== "none" : false,
        bottomItems: bottomItems.map(rect),
        focusTitle: focusTitle ? rect(focusTitle) : null,
        menuButton: menuButton ? rect(menuButton) : null,
        notificationButton: notificationButton ? rect(notificationButton) : null,
        mobileBrand: mobileBrand ? rect(mobileBrand) : null,
        mobileBrandLabelVisible: mobileBrandLabel
          ? getComputedStyle(mobileBrandLabel).display !== "none"
          : false,
      };
    });

    expect(layout.documentWidth).toBeLessThanOrEqual(layout.viewportWidth);
    expect(layout.summaryItems).toHaveLength(4);

    if (viewport.width <= 680) {
      expect(Math.abs(layout.summaryItems[0].top - layout.summaryItems[1].top)).toBeLessThan(2);
      expect(layout.summaryItems[2].top).toBeGreaterThan(layout.summaryItems[0].top + 20);
      expect(Math.max(...layout.summaryItems.map((item) => item.bottom))).toBeLessThan(
        viewport.height - 64,
      );
      expect(layout.focusTitle?.top ?? viewport.height).toBeLessThan(viewport.height - 64);
    }

    if (viewport.width > 680) {
      const firstRowTop = layout.summaryItems[0].top;
      for (const item of layout.summaryItems) {
        expect(Math.abs(item.top - firstRowTop)).toBeLessThan(2);
      }
    }

    if (viewport.width <= 860) {
      expect(layout.bottomNavVisible).toBe(true);
      expect(layout.bottomItems).toHaveLength(6);
      for (const item of layout.bottomItems) {
        expect(item.width).toBeGreaterThanOrEqual(44);
        expect(item.height).toBeGreaterThanOrEqual(44);
      }
      expect(layout.menuButton?.width ?? 0).toBeGreaterThanOrEqual(44);
      expect(layout.menuButton?.height ?? 0).toBeGreaterThanOrEqual(44);
      expect(layout.notificationButton?.width ?? 0).toBeGreaterThanOrEqual(44);
      expect(layout.notificationButton?.height ?? 0).toBeGreaterThanOrEqual(44);
      expect(layout.mobileBrand?.width ?? 0).toBeGreaterThan(0);
      expect(layout.mobileBrandLabelVisible).toBe(viewport.width > 360);
    } else {
      expect(layout.bottomNavVisible).toBe(false);
    }
  }
});

test("admin workbench preserves loading, healthy-empty, and request-error states", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  let releaseSystemRequest = () => {};
  const systemDelay = new Promise<void>((resolve) => {
    releaseSystemRequest = resolve;
  });
  await mockAdminApi(page, { systemDelay });
  await page.goto("/admin");

  await expect(page.locator(".admin-dashboard-skeleton")).toBeVisible();
  const skeletonCells = await page.locator(".admin-dashboard-skeleton i").evaluateAll((items) =>
    items.slice(0, 4).map((item) => {
      const box = item.getBoundingClientRect();
      return { top: box.top, left: box.left };
    }),
  );
  expect(skeletonCells).toHaveLength(4);
  expect(Math.abs(skeletonCells[0].top - skeletonCells[1].top)).toBeLessThan(2);
  expect(skeletonCells[2].top).toBeGreaterThan(skeletonCells[0].top + 20);
  releaseSystemRequest();
  await expect(page.locator(".admin-summary-item")).toHaveCount(4);

  const healthySystem: AdminSystemOverviewResponse = {
    ...populatedSystem,
    services: populatedSystem.services.map((service) => ({ ...service, status: "ok" })),
    stats: { ...populatedSystem.stats, pending_flags: 0 },
    queue: { ...populatedSystem.queue, dead: 0 },
    recent_audit_logs: [],
  };

  const healthyPage = await page.context().newPage();
  await healthyPage.setViewportSize({ width: 390, height: 844 });
  await mockAdminApi(healthyPage, { systemResponse: healthySystem });
  await healthyPage.goto("/admin");
  await expect(healthyPage.getByText("当前没有需要立即处理的异常")).toBeVisible();
  await expect(healthyPage.getByText("暂无管理操作记录。")).toBeVisible();

  const errorPage = await page.context().newPage();
  await errorPage.setViewportSize({ width: 390, height: 844 });
  await mockAdminApi(errorPage, { systemStatus: 503 });
  await errorPage.goto("/admin");
  const errorAlert = errorPage.getByRole("alert");
  await expect(errorAlert).toContainText("运营数据暂时无法加载");
  const retryButton = errorAlert.getByRole("button", { name: "重新加载" });
  await expect(retryButton).toBeVisible();
  const retryBox = await retryButton.boundingBox();
  expect(retryBox?.height ?? 0).toBeGreaterThanOrEqual(44);
});

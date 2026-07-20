import { createRouter, createWebHistory } from "vue-router";
import type { RouteLocationNormalized } from "vue-router";

import { fetchCurrentUser } from "@/features/auth/api";
import { CURRENT_USER_STALE_TIME_MS, type UserPublic } from "@/features/auth/model";
import { canAccessModeration, isAdmin } from "@/features/auth/permissions";
import { clearAuthTokens, hasAccessToken, isAuthenticationError } from "@/shared/api/client";
import { queryClient } from "@/shared/api/queryClient";
import { queryKeys } from "@/shared/api/queryKeys";
import type { RouteSeoMeta } from "@/shared/seo/meta";

type RequiredAccess = "authenticated" | "admin" | "moderation";
const HASH_SCROLL_RETRY_LIMIT = 40;
const HASH_SCROLL_RETRY_DELAY_MS = 50;
const NOINDEX_ROBOTS = "noindex,nofollow";

declare module "vue-router" {
  interface RouteMeta {
    requiredAccess?: RequiredAccess;
    seo?: RouteSeoMeta;
  }
}

function firstRouteParam(value: string | string[] | undefined) {
  if (Array.isArray(value)) {
    return value[0] ?? "";
  }

  return value ?? "";
}

export const router = createRouter({
  history: createWebHistory(),
  scrollBehavior(to) {
    if (to.hash) {
      return waitForHashTarget(to.hash).then((found) =>
        found ? { el: to.hash, top: 0, left: 0, behavior: "smooth" } : { top: 0, left: 0 },
      );
    }

    return { top: 0, left: 0 };
  },
  routes: [
    {
      path: "/",
      name: "home",
      component: () => import("@/pages/home/HomePage.vue"),
      meta: {
        seo: {
          title: "{siteTitle}",
          description: "{siteTagline}",
          canonicalPath: "/",
        },
      },
    },
    {
      path: "/play",
      name: "play-hub",
      component: () => import("@/pages/play/PlayHubPage.vue"),
      meta: {
        seo: {
          title: "游乐场 · {siteTitle}",
          description: "探索平行线正在生长的可玩项目：私密空间与平行消消乐。",
          canonicalPath: "/play",
        },
      },
    },
    {
      path: "/boards",
      name: "board-directory",
      component: () => import("@/pages/board/BoardDirectoryPage.vue"),
      meta: {
        seo: {
          title: "版块 · {siteTitle}",
          description: "浏览平行线的讨论版块，按主题领域进入高信号问题、经验和资源讨论。",
          canonicalPath: "/boards",
        },
      },
    },
    {
      path: "/auth",
      name: "auth",
      component: () => import("@/pages/auth/AuthPage.vue"),
      meta: {
        seo: {
          title: "登录注册 · {siteTitle}",
          description: "登录或注册平行线账号，继续发布主题、回复讨论和管理个人资料。",
          canonicalPath: "/auth",
          robots: NOINDEX_ROBOTS,
        },
      },
    },
    {
      path: "/forbidden",
      name: "access-denied",
      component: () => import("@/pages/auth/AccessDeniedPage.vue"),
      meta: {
        seo: {
          title: "无权限 · {siteTitle}",
          description: "当前账号没有访问该页面所需的权限。",
          canonicalPath: "/forbidden",
          robots: NOINDEX_ROBOTS,
        },
      },
    },
    {
      path: "/account",
      name: "account-home",
      component: () => import("@/pages/user/UserProfilePage.vue"),
      meta: {
        requiredAccess: "authenticated",
        seo: {
          title: "个人中心 · {siteTitle}",
          description: "查看自己的讨论、资料、成长和账号设置。",
          canonicalPath: "/account",
          robots: NOINDEX_ROBOTS,
        },
      },
    },
    {
      path: "/account/profile",
      name: "account-profile",
      component: () => import("@/pages/user/UserProfilePage.vue"),
      meta: {
        requiredAccess: "authenticated",
        seo: {
          title: "资料设置 · {siteTitle}",
          description: "管理平行线公开资料、头像、简介和个人偏好。",
          canonicalPath: "/account/profile",
          robots: NOINDEX_ROBOTS,
        },
      },
    },
    {
      path: "/account/settings",
      name: "account-settings",
      component: () => import("@/pages/user/UserProfilePage.vue"),
      meta: {
        requiredAccess: "authenticated",
        seo: {
          title: "账号设置 · {siteTitle}",
          description: "管理平行线账号密码和登录邮箱。",
          canonicalPath: "/account/settings",
          robots: NOINDEX_ROBOTS,
        },
      },
    },
    {
      path: "/account/preferences",
      name: "account-preferences",
      component: () => import("@/pages/email/EmailPreferencesPage.vue"),
      meta: {
        requiredAccess: "authenticated",
        seo: {
          title: "偏好设置 · {siteTitle}",
          description: "管理平行线邮件通知、摘要和订阅偏好。",
          canonicalPath: "/account/preferences",
          robots: NOINDEX_ROBOTS,
        },
      },
    },
    {
      path: "/me",
      redirect: { name: "account-home" },
    },
    {
      path: "/members/:id",
      name: "user-profile",
      component: () => import("@/pages/user/UserProfilePage.vue"),
      meta: {
        seo: {
          title: "用户档案 · {siteTitle}",
          description: "查看平行线成员的公开资料、主题和社区活动。",
        },
      },
    },
    {
      path: "/users",
      name: "user-directory",
      component: () => import("@/pages/user/UserDirectoryPage.vue"),
      meta: {
        seo: {
          title: "成员 · {siteTitle}",
          description: "浏览平行线社区成员，发现活跃作者和公开讨论贡献。",
          canonicalPath: "/users",
        },
      },
    },
    {
      path: "/b/:slug",
      name: "board-detail",
      component: () => import("@/pages/board/BoardPage.vue"),
      meta: {
        seo: {
          title: "版块详情 · {siteTitle}",
          description: "查看平行线版块下的最新主题、热门讨论和精华内容。",
        },
      },
    },
    {
      path: "/new-topic",
      name: "new-topic",
      component: () => import("@/pages/topic/NewTopicPage.vue"),
      meta: {
        requiredAccess: "authenticated",
        seo: {
          title: "发布主题 · {siteTitle}",
          description: "在平行线选择版块并发布新的公开讨论主题。",
          canonicalPath: "/new-topic",
          robots: NOINDEX_ROBOTS,
        },
      },
    },
    {
      path: "/invites",
      name: "my-invites",
      component: () => import("@/pages/invites/MyInvitesPage.vue"),
      meta: {
        seo: {
          title: "邀请 · {siteTitle}",
          description: "管理平行线账号邀请记录和邀请链接。",
          canonicalPath: "/invites",
          robots: NOINDEX_ROBOTS,
        },
      },
    },
    {
      path: "/email-preferences",
      redirect: { name: "account-preferences" },
    },
    {
      path: "/messages",
      name: "messages",
      component: () => import("@/pages/messages/MessagesPage.vue"),
      meta: {
        requiredAccess: "authenticated",
        seo: {
          title: "私信 · {siteTitle}",
          description: "查看和管理平行线站内私信对话。",
          canonicalPath: "/messages",
          robots: NOINDEX_ROBOTS,
        },
      },
    },
    {
      path: "/chat",
      redirect: { name: "home" },
    },
    {
      path: "/events",
      name: "events",
      component: () => import("@/pages/events/EventsPage.vue"),
      meta: {
        seo: {
          title: "活动 · {siteTitle}",
          description: "查看平行线社区活动、订阅日历并跟进公开事件安排。",
          canonicalPath: "/events",
        },
      },
    },
    {
      path: "/moderation/reviewables",
      name: "my-reviewables",
      component: () => import("@/pages/moderation/MyReviewablesPage.vue"),
      meta: {
        requiredAccess: "authenticated",
        seo: {
          title: "我的审核 · {siteTitle}",
          description: "查看分配给当前账号的平行线待处理审核事项。",
          canonicalPath: "/moderation/reviewables",
          robots: NOINDEX_ROBOTS,
        },
      },
    },
    {
      path: "/search",
      name: "search",
      component: () => import("@/pages/search/SearchPage.vue"),
      meta: {
        seo: {
          title: "搜索 · {siteTitle}",
          description: "搜索平行线公开主题、标签和作者，快速定位可追溯讨论。",
          canonicalPath: "/search",
          robots: "noindex,follow",
        },
      },
    },
    {
      path: "/admin",
      name: "admin-dashboard",
      component: () => import("@/pages/admin/AdminDashboardPage.vue"),
      meta: {
        requiredAccess: "admin",
        seo: {
          title: "后台 · {siteTitle}",
          description: "查看平行线访问统计、用户管理、内容安全和系统状态。",
          canonicalPath: "/admin",
          robots: NOINDEX_ROBOTS,
        },
      },
    },
    {
      path: "/admin/analytics",
      name: "admin-analytics",
      component: () => import("@/pages/admin/AdminAnalyticsPage.vue"),
      meta: {
        requiredAccess: "admin",
        seo: {
          title: "访问与用户增长 · {siteTitle}",
          description: "查看平行线访问表现、真实用户增长、来源渠道和入口页统计。",
          canonicalPath: "/admin/analytics",
          robots: NOINDEX_ROBOTS,
        },
      },
    },
    {
      path: "/admin/users",
      name: "admin-users",
      component: () => import("@/pages/admin/AdminUsersPage.vue"),
      meta: {
        requiredAccess: "admin",
        seo: {
          title: "用户管理 · {siteTitle}",
          description: "管理平行线用户角色、状态、等级和徽章。",
          canonicalPath: "/admin/users",
          robots: NOINDEX_ROBOTS,
        },
      },
    },
    {
      path: "/admin/fablespace-access",
      name: "admin-fablespace-access",
      component: () => import("@/pages/admin/AdminFableSpaceAccessPage.vue"),
      meta: {
        requiredAccess: "admin",
        seo: {
          title: "AI 产品能力 · {siteTitle}",
          description: "管理 FableSpace 独立产品的创作、运营和产品管理能力。",
          canonicalPath: "/admin/fablespace-access",
          robots: NOINDEX_ROBOTS,
        },
      },
    },
    {
      path: "/admin/system",
      name: "admin-system",
      component: () => import("@/pages/admin/AdminSystemPage.vue"),
      meta: {
        requiredAccess: "admin",
        seo: {
          title: "系统运行 · {siteTitle}",
          description: "查看平行线核心服务、后台任务、邮件和审计运行状态。",
          canonicalPath: "/admin/system",
          robots: NOINDEX_ROBOTS,
        },
      },
    },
    {
      path: "/admin/moderation",
      name: "admin-moderation",
      component: () => import("@/pages/admin/ModerationPage.vue"),
      meta: {
        requiredAccess: "moderation",
        seo: {
          title: "审核后台 · {siteTitle}",
          description: "处理平行线内容审核、举报和隐藏恢复记录。",
          canonicalPath: "/admin/moderation",
          robots: NOINDEX_ROBOTS,
        },
      },
    },
    {
      path: "/t/:slug/:id",
      redirect: (to) => ({
        name: "topic-detail",
        params: {
          id: firstRouteParam(to.params.id),
          slug: firstRouteParam(to.params.slug),
        },
        query: to.query,
        hash: to.hash,
      }),
    },
    {
      path: "/topics/:id/:slug?",
      name: "topic-detail",
      component: () => import("@/pages/topic/TopicDetailPage.vue"),
      meta: {
        seo: {
          title: "主题详情 · {siteTitle}",
          description: "查看平行线公开主题详情、楼层回复和可追溯讨论上下文。",
          ogType: "article",
        },
      },
    },
    {
      path: "/design-system",
      name: "design-system",
      component: () => import("@/pages/design-system/DesignSystemPage.vue"),
      meta: {
        seo: {
          title: "设计系统 · {siteTitle}",
          description: "平行线内部设计系统和界面组件预览。",
          canonicalPath: "/design-system",
          robots: NOINDEX_ROBOTS,
        },
      },
    },
  ],
});

router.beforeEach(async (to) => {
  const requiredAccess = to.meta.requiredAccess;
  if (!requiredAccess) {
    return true;
  }

  const currentUser = await loadCurrentUserForRoute();
  if (!currentUser) {
    return loginRedirect(to);
  }

  if (requiredAccess === "admin" && !isAdmin(currentUser)) {
    return accessDeniedRedirect(to, "admin");
  }

  if (requiredAccess === "moderation" && !canAccessModeration(currentUser)) {
    return accessDeniedRedirect(to, "moderation");
  }

  return true;
});

async function loadCurrentUserForRoute(): Promise<UserPublic | null> {
  if (!hasAccessToken()) {
    return null;
  }

  const cachedUser = queryClient.getQueryData<UserPublic | null>(queryKeys.currentUser);
  const cachedUserState = queryClient.getQueryState(queryKeys.currentUser);
  if (
    cachedUser &&
    cachedUserState?.dataUpdatedAt &&
    Date.now() - cachedUserState.dataUpdatedAt < CURRENT_USER_STALE_TIME_MS
  ) {
    return cachedUser;
  }

  try {
    return await queryClient.fetchQuery({
      queryKey: queryKeys.currentUser,
      queryFn: fetchCurrentUser,
      retry: false,
      staleTime: CURRENT_USER_STALE_TIME_MS,
    });
  } catch (error) {
    if (isAuthenticationError(error)) {
      clearAuthTokens();
      queryClient.setQueryData(queryKeys.currentUser, null);
      return null;
    }

    return queryClient.getQueryData<UserPublic | null>(queryKeys.currentUser) ?? null;
  }
}

function loginRedirect(to: RouteLocationNormalized) {
  return {
    name: "auth",
    query: { redirect: to.fullPath },
  };
}

// Builds the explicit no-permission route for authenticated users who lack the required role.
// `to` is the blocked route and `requiredAccess` is the failed route meta; return value is a Vue Router location.
function accessDeniedRedirect(to: RouteLocationNormalized, requiredAccess: RequiredAccess) {
  return {
    name: "access-denied",
    query: {
      required: requiredAccess,
      from: to.fullPath,
    },
  };
}

// Waits for hash targets rendered by async pages before Vue Router attempts to scroll.
// `hash` is the browser fragment selector (for example `#post-2`); the return value tells
// scrollBehavior whether to scroll to it or fall back to the top. Side effect: schedules short timers.
function waitForHashTarget(hash: string): Promise<boolean> {
  if (typeof document === "undefined") {
    return Promise.resolve(false);
  }

  return new Promise((resolve) => {
    let attempts = 0;
    const checkTarget = () => {
      if (hasHashTarget(hash)) {
        resolve(true);
        return;
      }

      attempts += 1;
      if (attempts >= HASH_SCROLL_RETRY_LIMIT) {
        resolve(false);
        return;
      }

      window.setTimeout(checkTarget, HASH_SCROLL_RETRY_DELAY_MS);
    };

    checkTarget();
  });
}

// Checks a hash selector safely because malformed fragments can throw in querySelector.
// `hash` is passed through from Vue Router; the return value is true only when the element exists.
// Side effect: none.
function hasHashTarget(hash: string): boolean {
  try {
    return Boolean(document.querySelector(hash));
  } catch {
    return false;
  }
}

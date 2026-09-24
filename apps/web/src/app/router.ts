import { createRouter, createWebHistory } from "vue-router";

import { fetchCurrentUser } from "@/features/auth/api";
import { CURRENT_USER_STALE_TIME_MS, type UserPublic } from "@/features/auth/model";
import { isAdmin } from "@/features/auth/permissions";
import { clearAuthTokens, hasAccessToken, isAuthenticationError } from "@/shared/api/client";
import { queryClient } from "@/shared/api/queryClient";
import { queryKeys } from "@/shared/api/queryKeys";
import type { RouteSeoMeta } from "@/shared/seo/meta";

declare module "vue-router" {
  interface RouteMeta {
    requiredAccess?: "admin";
    seo?: RouteSeoMeta;
  }
}

export const router = createRouter({
  history: createWebHistory(),
  scrollBehavior(_to, _from, savedPosition) {
    return savedPosition ?? { top: 0, left: 0 };
  },
  routes: [
    {
      path: "/",
      name: "home",
      component: () => import("@/pages/catalog/CatalogHomePage.vue"),
      meta: {
        seo: {
          title: "{siteName}",
          description: "在平行线按分类发现游戏与互动项目，搜索并查看访客评分。",
          canonicalPath: "/",
        },
      },
    },
    {
      path: "/play/generals-soldiers",
      name: "play-generals-soldiers",
      component: () => import("@/pages/play/GeneralsSoldiersPage.vue"),
      meta: {
        seo: {
          title: "将军战小兵 · {siteTitle}",
          description: "在平行线与电脑进行将军战小兵对弈。",
          canonicalPath: "/play/generals-soldiers",
        },
      },
    },
    {
      path: "/auth",
      name: "auth",
      component: () => import("@/pages/auth/AuthPage.vue"),
      meta: {
        seo: {
          title: "后台登录 · {siteTitle}",
          description: "登录平行线后台管理项目目录与访问统计。",
          canonicalPath: "/auth",
          robots: "noindex,nofollow",
        },
      },
    },
    {
      path: "/admin",
      name: "admin-dashboard",
      component: () => import("@/pages/admin/CatalogAdminPage.vue"),
      meta: {
        requiredAccess: "admin",
        seo: {
          title: "目录管理与访问统计 · {siteTitle}",
          description: "管理平行线项目目录并查看访问统计。",
          canonicalPath: "/admin",
          robots: "noindex,nofollow",
        },
      },
    },
    {
      path: "/admin/:pathMatch(.*)*",
      redirect: { name: "admin-dashboard" },
    },
    {
      path: "/:pathMatch(.*)*",
      redirect: { name: "home" },
    },
  ],
});

router.beforeEach(async (to) => {
  // 后台登录仅服务 /admin；旧注册和论坛地址不再有公开页面入口。
  if (to.name === "auth") {
    return to.query.redirect === "/admin" ? true : { name: "home" };
  }
  if (to.name !== "admin-dashboard") {
    return true;
  }

  const currentUser = await loadCurrentUserForRoute();
  if (!currentUser) {
    return { name: "auth", query: { redirect: "/admin" } };
  }
  return isAdmin(currentUser) ? true : { name: "home" };
});

async function loadCurrentUserForRoute(): Promise<UserPublic | null> {
  if (!hasAccessToken()) {
    return null;
  }

  const cachedUser = queryClient.getQueryData<UserPublic | null>(queryKeys.currentUser);
  const cachedState = queryClient.getQueryState(queryKeys.currentUser);
  if (
    cachedUser &&
    cachedState?.dataUpdatedAt &&
    Date.now() - cachedState.dataUpdatedAt < CURRENT_USER_STALE_TIME_MS
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

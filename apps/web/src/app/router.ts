import { createRouter, createWebHistory } from "vue-router";
import type { RouteLocationNormalized } from "vue-router";

import { fetchCurrentUser } from "@/features/auth/api";
import type { UserPublic } from "@/features/auth/model";
import { canAccessModeration, isAdmin } from "@/features/auth/permissions";
import { clearAuthTokens, hasAccessToken, isAuthenticationError } from "@/shared/api/client";
import { queryClient } from "@/shared/api/queryClient";
import { queryKeys } from "@/shared/api/queryKeys";

type RequiredAccess = "authenticated" | "admin" | "moderation";

declare module "vue-router" {
  interface RouteMeta {
    requiredAccess?: RequiredAccess;
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
      return { el: to.hash, behavior: "smooth" };
    }

    return { top: 0 };
  },
  routes: [
    {
      path: "/",
      name: "home",
      component: () => import("@/pages/home/HomePage.vue"),
    },
    {
      path: "/boards",
      name: "board-directory",
      component: () => import("@/pages/board/BoardDirectoryPage.vue"),
    },
    {
      path: "/auth",
      name: "auth",
      component: () => import("@/pages/auth/AuthPage.vue"),
    },
    {
      path: "/me",
      name: "my-profile",
      component: () => import("@/pages/user/UserProfilePage.vue"),
      beforeEnter: async (to) => {
        const currentUser = await loadCurrentUserForRoute();
        if (!currentUser) {
          return loginRedirect(to);
        }

        return {
          name: "user-profile",
          params: { username: currentUser.username },
        };
      },
    },
    {
      path: "/u/:username",
      name: "user-profile",
      component: () => import("@/pages/user/UserProfilePage.vue"),
    },
    {
      path: "/users",
      name: "user-directory",
      component: () => import("@/pages/user/UserDirectoryPage.vue"),
    },
    {
      path: "/b/:slug",
      name: "board-detail",
      component: () => import("@/pages/board/BoardPage.vue"),
    },
    {
      path: "/new-topic",
      name: "new-topic",
      component: () => import("@/pages/topic/NewTopicPage.vue"),
    },
    {
      path: "/invites",
      name: "my-invites",
      component: () => import("@/pages/invites/MyInvitesPage.vue"),
    },
    {
      path: "/security",
      name: "security",
      component: () => import("@/pages/security/SecurityPage.vue"),
      meta: { requiredAccess: "authenticated" },
    },
    {
      path: "/email-preferences",
      name: "email-preferences",
      component: () => import("@/pages/email/EmailPreferencesPage.vue"),
      meta: { requiredAccess: "authenticated" },
    },
    {
      path: "/messages",
      name: "messages",
      component: () => import("@/pages/messages/MessagesPage.vue"),
      meta: { requiredAccess: "authenticated" },
    },
    {
      path: "/chat",
      redirect: { name: "home" },
    },
    {
      path: "/events",
      name: "events",
      component: () => import("@/pages/events/EventsPage.vue"),
    },
    {
      path: "/moderation/reviewables",
      name: "my-reviewables",
      component: () => import("@/pages/moderation/MyReviewablesPage.vue"),
      meta: { requiredAccess: "authenticated" },
    },
    {
      path: "/search",
      name: "search",
      component: () => import("@/pages/search/SearchPage.vue"),
    },
    {
      path: "/admin",
      name: "admin-dashboard",
      component: () => import("@/pages/admin/AdminDashboardPage.vue"),
      meta: { requiredAccess: "admin" },
    },
    {
      path: "/admin/moderation",
      name: "admin-moderation",
      component: () => import("@/pages/admin/ModerationPage.vue"),
      meta: { requiredAccess: "moderation" },
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
    },
    {
      path: "/design-system",
      name: "design-system",
      component: () => import("@/pages/design-system/DesignSystemPage.vue"),
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
    return { name: "home" };
  }

  if (requiredAccess === "moderation" && !canAccessModeration(currentUser)) {
    return { name: "home" };
  }

  return true;
});

async function loadCurrentUserForRoute(): Promise<UserPublic | null> {
  if (!hasAccessToken()) {
    return null;
  }

  try {
    return await queryClient.fetchQuery({
      queryKey: queryKeys.currentUser,
      queryFn: fetchCurrentUser,
      retry: false,
      staleTime: 0,
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

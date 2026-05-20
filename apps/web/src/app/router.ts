import { createRouter, createWebHistory } from "vue-router";

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
      path: "/u/:username",
      name: "user-profile",
      component: () => import("@/pages/user/UserProfilePage.vue"),
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
    },
    {
      path: "/search",
      name: "search",
      component: () => import("@/pages/search/SearchPage.vue"),
    },
    {
      path: "/admin/moderation",
      name: "admin-moderation",
      component: () => import("@/pages/admin/ModerationPage.vue"),
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

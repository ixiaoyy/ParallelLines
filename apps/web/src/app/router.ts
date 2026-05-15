import { createRouter, createWebHistory } from "vue-router";

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

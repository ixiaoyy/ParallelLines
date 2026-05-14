import { createRouter, createWebHistory } from "vue-router";

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: "/",
      name: "home",
      component: () => import("@/pages/home/HomePage.vue"),
    },
    {
      path: "/design-system",
      name: "design-system",
      component: () => import("@/pages/design-system/DesignSystemPage.vue"),
    },
  ],
});

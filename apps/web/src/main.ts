import { VueQueryPlugin } from "@tanstack/vue-query";
import "ant-design-vue/dist/reset.css";
import { createApp } from "vue";

import App from "@/app/App.vue";
import { router } from "@/app/router";
import { installSiteVisitTracker } from "@/features/analytics/siteVisitTracker";
import { queryClient } from "@/shared/api/queryClient";
import "@/shared/styles/base.scss";

import "@/shared/styles/tokens.scss";
import "@/shared/styles/button-surfaces.scss";
import "@/shared/styles/tone-utilities.scss";

installSiteVisitTracker(router);

createApp(App)
  .use(VueQueryPlugin, { queryClient })
  .use(router)
  .mount("#app");

// 新站不再启用旧论坛离线页与推送；清理当前站点已注册的 Service Worker。
if ("serviceWorker" in navigator) {
  void navigator.serviceWorker
    .getRegistrations()
    .then((registrations) =>
      Promise.all(
        registrations
          .filter((registration) => registration.scope.startsWith(window.location.origin))
          .map((registration) => registration.unregister()),
      ),
    )
    .catch((error) => console.warn("旧站离线服务清理失败", error));
}

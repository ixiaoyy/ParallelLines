import { VueQueryPlugin } from "@tanstack/vue-query";
import "ant-design-vue/dist/reset.css";
import { createPinia } from "pinia";
import { createApp } from "vue";

import App from "@/app/App.vue";
import { router } from "@/app/router";
import { installSiteVisitTracker } from "@/features/analytics/siteVisitTracker";
import { queryClient } from "@/shared/api/queryClient";
import { runWhenBrowserIdle } from "@/shared/lib/loadWhenIdle";
import "@/shared/styles/base.scss";
import { registerPwaServiceWorker } from "@/shared/pwa/register";
import { injectBoardPalette } from "@/shared/theme/boardPalette";
import { applyStoredInterfaceTheme } from "@/shared/theme/interfaceTheme";

import "@/shared/styles/tokens.scss";
import "@/shared/styles/button-surfaces.scss";
import "@/shared/styles/tone-utilities.scss";

injectBoardPalette();
applyStoredInterfaceTheme();
installSiteVisitTracker(router);

createApp(App)
  .use(createPinia())
  .use(VueQueryPlugin, { queryClient })
  .use(router)
  .mount("#app");

void runWhenBrowserIdle(4_000).then(registerPwaServiceWorker);

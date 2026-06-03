import { VueQueryPlugin } from "@tanstack/vue-query";
import "ant-design-vue/dist/reset.css";
import { createPinia } from "pinia";
import { createApp } from "vue";

import App from "@/app/App.vue";
import { router } from "@/app/router";
import { queryClient } from "@/shared/api/queryClient";
import "@/shared/styles/base.scss";
import { registerPwaServiceWorker } from "@/shared/pwa/register";
import { injectBoardPalette } from "@/shared/theme/boardPalette";

import "@/shared/styles/tokens.scss";
import "@/shared/styles/button-surfaces.scss";
import "@/shared/styles/tone-utilities.scss";

injectBoardPalette();
void registerPwaServiceWorker();

createApp(App)
  .use(createPinia())
  .use(VueQueryPlugin, { queryClient })
  .use(router)
  .mount("#app");

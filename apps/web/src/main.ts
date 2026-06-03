import { VueQueryPlugin } from "@tanstack/vue-query";
import {
  Avatar,
  Badge,
  Button,
  Card,
  ConfigProvider,
  Empty,
  Input,
  Skeleton,
  Tabs,
  Tag,
} from "ant-design-vue";
import "ant-design-vue/dist/reset.css";
import { createPinia } from "pinia";
import { createApp } from "vue";

import App from "@/app/App.vue";
import { router } from "@/app/router";
import { queryClient } from "@/shared/api/queryClient";
import "md-editor-v3/lib/style.css";
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
  .use(ConfigProvider)
  .use(Button)
  .use(Input)
  .use(Card)
  .use(Avatar)
  .use(Tag)
  .use(Tabs)
  .use(Skeleton)
  .use(Empty)
  .use(Badge)
  .mount("#app");

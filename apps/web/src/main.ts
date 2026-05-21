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
import "@/shared/styles/base.scss";
import { injectBoardPalette } from "@/shared/theme/boardPalette";

import "@/shared/styles/tokens.scss";
import "@/shared/styles/tone-utilities.scss";

injectBoardPalette();

createApp(App)
  .use(createPinia())
  .use(VueQueryPlugin)
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

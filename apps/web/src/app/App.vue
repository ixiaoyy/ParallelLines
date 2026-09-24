<script setup lang="ts">
import { ConfigProvider } from "ant-design-vue";
import zhCN from "ant-design-vue/es/locale/zh_CN";
import { computed } from "vue";
import { useRoute } from "vue-router";

import { resolveRouteSeoMeta, useSeoMeta } from "@/shared/seo/meta";

const route = useRoute();
// 新站公开页面使用固定目录文案，保留管理员路由的 noindex 元信息。
useSeoMeta(
  computed(() =>
    resolveRouteSeoMeta(route.meta.seo, {
      routePath: route.path,
      siteTitle: "平行线",
      siteName: "平行线 ParallelLines",
      siteTagline: "发现有趣的游戏与互动项目",
    }),
  ),
);

/** 须与 tokens.scss / button-surfaces.scss 一致，见 AGENTS.md */
const theme = {
  token: {
    colorPrimary: "#409EFF",
    colorPrimaryHover: "#66B1FF",
    colorPrimaryActive: "#3A8EE6",
    colorSuccess: "#22C55E",
    colorWarning: "#FBBF24",
    colorError: "#F87171",
    colorTextHeading: "#334155",
    colorText: "#475569",
    colorBgLayout: "#F8FAFC",
    colorBgContainer: "#FFFFFF",
    colorBorder: "#E2E8F0",
    colorLink: "#409EFF",
    colorLinkHover: "#66B1FF",
    borderRadius: 16,
    fontFamily:
      '"LXGW WenKai Screen", "Noto Serif SC", ui-serif, Georgia, "Times New Roman", serif',
  },
  components: {
    Button: {
      colorPrimary: "#409EFF",
      colorPrimaryHover: "#66B1FF",
      colorPrimaryActive: "#3A8EE6",
      colorTextLightSolid: "#FFFFFF",
      borderRadius: 999,
      controlHeight: 40,
      fontWeight: 760,
    },
    Card: {
      borderRadiusLG: 16,
      boxShadowTertiary: "0 12px 24px rgba(61, 78, 94, 0.08)",
    },
  },
};
</script>

<template>
  <ConfigProvider :locale="zhCN" :theme="theme">
    <RouterView />
  </ConfigProvider>
</template>

<script setup lang="ts">
import { ConfigProvider } from "ant-design-vue";
import zhCN from "ant-design-vue/es/locale/zh_CN";
import { computed, defineAsyncComponent } from "vue";
import { useRoute } from "vue-router";

import { resolveRouteSeoMeta, useSeoMeta } from "@/shared/seo/meta";

const route = useRoute();
// 论坛外壳按需加载；目录首页及原目录后台不增加论坛导航或初始化请求。
const AppShell = defineAsyncComponent(() => import("@/app/layouts/AppShell.vue"));
const usesForumShell = computed(() => {
  const redirect = route.query.redirect;
  const isAdminLogin = route.name === "auth" && typeof redirect === "string" &&
    (redirect === "/admin" || redirect.startsWith("/admin/"));
  return route.meta.forumShell === true && !isAdminLogin;
});
// 论坛的动态品牌和页面 SEO 由旧外壳接管；其他页面继续使用目录文案。
useSeoMeta(
  computed(() => usesForumShell.value ? undefined :
    resolveRouteSeoMeta(route.name === "auth" ? {
      title: "后台登录 · {siteTitle}",
      description: "登录平行线后台管理项目目录与访问统计。",
      canonicalPath: "/auth",
      robots: "noindex,nofollow",
    } : route.meta.seo, {
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
    <RouterView v-slot="{ Component }">
      <AppShell v-if="usesForumShell">
        <component :is="Component" />
      </AppShell>
      <component :is="Component" v-else />
    </RouterView>
  </ConfigProvider>
</template>

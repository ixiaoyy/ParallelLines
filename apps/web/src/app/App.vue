<script setup lang="ts">
import { ConfigProvider } from "ant-design-vue";
import zhCN from "ant-design-vue/es/locale/zh_CN";
import { computed, defineAsyncComponent, shallowRef } from "vue";
import { useRoute } from "vue-router";

import { isChatSsoContinuation } from "@/shared/router/authReturn";
import { resolveRouteSeoMeta, useSeoMeta } from "@/shared/seo/meta";
import {
  buildSeoSiteDescription,
  buildSiteStructuredData,
  readServerSiteStructuredData,
  SEO_SITE_STRUCTURED_DATA_ID,
  SEO_SITE_TAGLINE,
  useStructuredData,
} from "@/shared/seo/structuredData";
import type { JsonLdObject } from "@/shared/seo/structuredData";

const route = useRoute();
// 论坛外壳按需加载；目录首页及原目录后台不增加论坛导航或初始化请求。
const AppShell = defineAsyncComponent(() => import("@/app/layouts/AppShell.vue"));
const usesForumShell = computed(() => {
  const redirect = route.query.redirect;
  const isAdminLogin = route.name === "auth" && typeof redirect === "string" &&
    (redirect === "/admin" || redirect.startsWith("/admin/"));
  const isChatLogin = route.name === "auth" && isChatSsoContinuation(redirect, window.location.origin);
  return route.meta.forumShell === true && !isAdminLogin && !isChatLogin;
});
// 根应用唯一维护站点图谱；先接续服务端品牌，静态壳才使用既有默认值，不新增初始化请求。
const siteGraph = shallowRef(readServerSiteStructuredData() ?? buildSiteStructuredData({
  siteUrl: window.location.origin,
  title: "平行线",
  description: buildSeoSiteDescription("平行线 ParallelLines"),
  logoUrl: "/logo-lines-mark.png",
}));
useStructuredData(SEO_SITE_STRUCTURED_DATA_ID, computed(() => {
  // 登录、后台及其他明确禁止索引的页面不新增公开图谱；品牌快照保留供返回公开页恢复。
  if (route.meta.seo?.robots?.split(",").includes("noindex")) return null;
  if (usesForumShell.value) return siteGraph.value;
  const graph = siteGraph.value["@graph"];
  if (!Array.isArray(graph)) return siteGraph.value;
  // 离开论坛只还原整站介绍，不重建自定义品牌、规范地址、别名或 Logo。
  return {
    ...siteGraph.value,
    "@graph": graph.map((node) => node !== null && typeof node === "object" && !Array.isArray(node)
      && node["@type"] === "WebSite" && typeof node.name === "string"
      ? { ...node, description: buildSeoSiteDescription(node.name) }
      : node),
  };
}));

/** 接收仍在展示的论坛外壳的公开品牌图谱；离页后的延迟结果不覆盖当前站点状态。 */
function receiveForumSiteGraph(graph: JsonLdObject): void {
  if (usesForumShell.value) siteGraph.value = graph;
}

// 论坛的动态品牌和页面 SEO 由旧外壳接管；其他页面沿用通用主站定位。
useSeoMeta(
  computed(() => usesForumShell.value ? undefined :
    resolveRouteSeoMeta(route.name === "auth" && !isChatSsoContinuation(route.query.redirect, window.location.origin) ? {
      title: "后台登录 · {siteTitle}",
      description: "登录平行线后台管理项目目录与访问统计。",
      canonicalPath: "/auth",
      robots: "noindex,nofollow",
    } : route.meta.seo, {
      routePath: route.path,
      siteTitle: "平行线",
      siteName: "平行线 ParallelLines",
      siteTagline: SEO_SITE_TAGLINE,
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
      <AppShell v-if="usesForumShell" @site-structured-data="receiveForumSiteGraph">
        <component :is="Component" />
      </AppShell>
      <component :is="Component" v-else />
    </RouterView>
  </ConfigProvider>
</template>

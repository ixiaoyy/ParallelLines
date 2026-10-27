<script setup lang="ts">
import { ConfigProvider } from "ant-design-vue";
import zhCN from "ant-design-vue/es/locale/zh_CN";
import { computed, defineAsyncComponent, shallowRef } from "vue";
import { useRoute, useRouter } from "vue-router";

import { resolveRouteSeoMeta, useSeoMeta } from "@/shared/seo/meta";
import {
  browserSeoOrigin,
  buildSeoSiteName,
  buildSiteStructuredData,
  readSiteStructuredData,
  SEO_INITIAL_SITE_TITLE,
  SEO_SITE_STRUCTURED_DATA_ID,
  useStructuredData,
} from "@/shared/seo/structuredData";
import type { JsonLdObject } from "@/shared/seo/structuredData";

const route = useRoute();
const router = useRouter();
const PUBLIC_STANDALONE_ROUTES = new Set([
  "home", "tools", "tool-excel-formulas", "tool-bead-pattern",
  "play-generals-soldiers", "play-snake-escape", "play-flappy-dunk",
]);
const isPublicStandaloneRoute = computed(() => PUBLIC_STANDALONE_ROUTES.has(String(route.name)));
// App 唯一拥有站点槽；首屏身份和论坛已获取的公开设置跨页面保留，不增加目录初始化请求。
const siteIdentity = shallowRef(readSiteStructuredData());
const publicSiteTitle = shallowRef(SEO_INITIAL_SITE_TITLE);
const siteBrand = computed(() => {
  const graph = siteIdentity.value?.["@graph"];
  const website = Array.isArray(graph) ? graph.find((node) =>
    node !== null && typeof node === "object" && !Array.isArray(node) && node["@type"] === "WebSite",
  ) : undefined;
  const fallbackTitle = publicSiteTitle.value ?? "平行线";
  const fallback = { siteTitle: fallbackTitle, siteName: buildSeoSiteName(fallbackTitle), siteUrl: browserSeoOrigin() };
  if (!website || typeof website !== "object" || Array.isArray(website) || typeof website.name !== "string") return fallback;
  let siteUrl = fallback.siteUrl;
  if (typeof website.url === "string") {
    try {
      const parsed = new URL(website.url);
      if (parsed.protocol === "https:" || parsed.protocol === "http:") siteUrl = parsed.origin;
    } catch { /* 无效规范地址不覆盖浏览器已完成跳转的地址。 */ }
  }
  return { siteTitle: publicSiteTitle.value ?? website.name, siteName: website.name, siteUrl };
});

/** 接收论坛既有查询确认的完整图谱与原站名；保留真实配置供后续公开页面使用，不推断品牌简称。 */
function updateSiteIdentity(schema: JsonLdObject, siteTitle: string): void {
  siteIdentity.value = schema;
  publicSiteTitle.value = siteTitle;
}
// 论坛外壳按需加载；目录首页及原目录后台不增加论坛导航或初始化请求。
const AppShell = defineAsyncComponent(() => import("@/app/layouts/AppShell.vue"));
const usesForumShell = computed(() => {
  const redirect = route.query.redirect;
  const isAdminLogin = route.name === "auth" && typeof redirect === "string" &&
    (redirect === "/admin" || redirect.startsWith("/admin/"));
  return route.meta.forumShell === true && !isAdminLogin;
});
// 论坛页面 meta 仍由旧外壳接管；七个公开入口复用首屏品牌，后台及私有路由沿用原默认值。
useSeoMeta(computed(() => {
  if (usesForumShell.value) return undefined;
  const brand = isPublicStandaloneRoute.value ? siteBrand.value : { siteTitle: "平行线", siteName: "平行线 ParallelLines" };
  const meta = resolveRouteSeoMeta(route.name === "auth" ? {
    title: "后台登录 · {siteTitle}",
    description: "登录平行线后台管理项目目录与访问统计。",
    canonicalPath: "/auth",
    robots: "noindex,nofollow",
  } : route.meta.seo, {
    routePath: route.path,
    siteTitle: brand.siteTitle,
    siteName: brand.siteName,
    siteTagline: "发现有趣的游戏与互动项目",
  });
  if (isPublicStandaloneRoute.value && siteBrand.value.siteUrl) {
    meta.canonicalPath = new URL(meta.canonicalPath, siteBrand.value.siteUrl).toString();
  }
  return meta;
}));
useStructuredData(SEO_SITE_STRUCTURED_DATA_ID, computed(() => {
  if (usesForumShell.value) return siteIdentity.value;
  if (!isPublicStandaloneRoute.value || !siteBrand.value.siteUrl) return null;
  const schema = siteIdentity.value ?? buildSiteStructuredData({
    siteUrl: siteBrand.value.siteUrl,
    title: siteBrand.value.siteTitle,
    description: "",
    logoUrl: "/logo-lines-mark.png",
  });
  const graph = schema["@graph"];
  if (!Array.isArray(graph)) return schema;
  // 站点图谱描述整个目录；切出论坛时只恢复此描述，保留服务端身份、Logo 和全部稳定引用。
  const description = resolveRouteSeoMeta(router.resolve({ name: "home" }).meta.seo, {
    routePath: "/", ...siteBrand.value, siteTagline: "发现有趣的游戏与互动项目",
  }).description;
  return { ...schema, "@graph": graph.map((node) =>
    node !== null && typeof node === "object" && !Array.isArray(node) && node["@type"] === "WebSite"
      ? { ...node, description } : node,
  ) };
}));

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
      <AppShell v-if="usesForumShell" :site-origin="siteBrand.siteUrl" @site-structured-data="updateSiteIdentity">
        <component :is="Component" />
      </AppShell>
      <component :is="Component" v-else />
    </RouterView>
  </ConfigProvider>
</template>

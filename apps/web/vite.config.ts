import { fileURLToPath, URL } from "node:url";

import vue from "@vitejs/plugin-vue";
import { defineConfig, type Plugin } from "vite";

const devApiProxyTarget = process.env.VITE_DEV_API_PROXY_TARGET;

/** 按实际静态资源配置预连 CDN；相对路径保持同源，不额外建立第三方连接。 */
function staticAssetPreconnect(): Plugin {
  let origin: string | undefined;
  return {
    name: "static-asset-preconnect",
    configResolved(config) {
      const base = config.env.VITE_STATIC_ASSET_BASE_URL?.trim()
        || "https://img.pingxingxian.space/static/web";
      if (/^https?:\/\//.test(base)) origin = new URL(base).origin;
    },
    transformIndexHtml() {
      return origin ? [{ tag: "link", attrs: { rel: "preconnect", href: origin }, injectTo: "head" }] : [];
    },
  };
}

/** 论坛独立构建使用自己的首个 HTML 元信息，保留服务端注入标记与正式品牌资源。 */
function forumEntryHtml(): Plugin {
  return {
    name: "forum-entry-html",
    transformIndexHtml(html) {
      const title = "平行线 ParallelLines · 圈子";
      const description = "平行线圈子：浏览公开版块，发布主题、回复讨论，与成员交流。";
      const origin = "https://forum.pingxingxian.space/";
      return html.replace(
        /<!-- parallellines-seo-head-start -->[\s\S]*?<!-- parallellines-seo-head-end -->/,
        `<!-- parallellines-seo-head-start -->
    <meta name="description" content="${description}" />
    <meta name="robots" content="index,follow" />
    <link rel="canonical" href="${origin}" />
    <meta property="og:type" content="website" />
    <meta property="og:title" content="${title}" />
    <meta property="og:site_name" content="平行线 ParallelLines" />
    <meta property="og:description" content="${description}" />
    <meta property="og:url" content="${origin}" />
    <meta property="og:locale" content="zh_CN" />
    <meta name="twitter:card" content="summary" />
    <meta name="twitter:title" content="${title}" />
    <meta name="twitter:description" content="${description}" />
    <title>${title}</title>
    <!-- parallellines-seo-head-end -->`,
      );
    },
  };
}

export default defineConfig(({ mode }) => ({
  // 游戏与论坛可同时本地预览，不能互相覆盖依赖预构建状态。
  cacheDir: mode === "forum" ? "node_modules/.vite-forum" : "node_modules/.vite",
  plugins: [vue(), staticAssetPreconnect(), ...(mode === "forum" ? [forumEntryHtml()] : [])],
  // 同一业务源码分别发布两个前端，运行时不会按任意 Host 猜测产品或共享浏览器令牌。
  define: { "import.meta.env.VITE_SITE_MODE": JSON.stringify(mode === "forum" ? "forum" : "games") },
  build: {
    rollupOptions: {
      output: {
        // Splits large third-party packages into stable cacheable chunks.
        // Key parameter `id` is Rollup's resolved module path; return value names the target chunk.
        // Side effect: only changes production bundle grouping, not application runtime logic.
        manualChunks(id) {
          // Keep Vite's shared preload helper in an entry-loaded chunk so a lazy editor cannot claim it.
          if (id === "\0vite/preload-helper.js") {
            return "vendor-vue";
          }

          const normalizedId = id.replace(/\\/g, "/");

          if (!normalizedId.includes("/node_modules/")) {
            return;
          }

          if (normalizedId.includes("/node_modules/md-editor-v3/")) {
            return "vendor-markdown-editor";
          }

          if (
            normalizedId.includes("/node_modules/ant-design-vue/") ||
            normalizedId.includes("/node_modules/@ant-design/icons-vue/")
          ) {
            return "vendor-ant-design";
          }

          if (normalizedId.includes("/node_modules/@tanstack/")) {
            return "vendor-query";
          }

          if (
            normalizedId.includes("/node_modules/echarts/") ||
            normalizedId.includes("/node_modules/zrender/")
          ) {
            return "vendor-echarts";
          }

          if (
            normalizedId.includes("/node_modules/vue/") ||
            normalizedId.includes("/node_modules/vue-router/") ||
            normalizedId.includes("/node_modules/pinia/") ||
            normalizedId.includes("/node_modules/@vue/")
          ) {
            return "vendor-vue";
          }

          if (
            normalizedId.includes("/node_modules/dompurify/") ||
            normalizedId.includes("/node_modules/xss/")
          ) {
            return "vendor-sanitizer";
          }
        },
      },
    },
  },
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
  server: {
    port: 5174,
    // 两套发布产物都不是开发输入，构建另一站时不触发当前页面热重载。
    watch: { ignored: ["**/dist/**", "**/dist-forum/**"] },
    proxy: devApiProxyTarget
      ? {
          "/api": {
            target: devApiProxyTarget,
            changeOrigin: true,
            secure: true,
          },
        }
      : undefined,
  },
}));

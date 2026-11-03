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

export default defineConfig({
  plugins: [vue(), staticAssetPreconnect()],
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
});

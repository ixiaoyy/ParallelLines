import { fileURLToPath, URL } from "node:url";

import vue from "@vitejs/plugin-vue";
import { defineConfig } from "vite";

const devApiProxyTarget = process.env.VITE_DEV_API_PROXY_TARGET;

export default defineConfig({
  plugins: [vue()],
  build: {
    rollupOptions: {
      output: {
        // Splits large third-party packages into stable cacheable chunks.
        // Key parameter `id` is Rollup's resolved module path; return value names the target chunk.
        // Side effect: only changes production bundle grouping, not application runtime logic.
        manualChunks(id) {
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

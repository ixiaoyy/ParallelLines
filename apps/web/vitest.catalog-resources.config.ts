import { fileURLToPath, URL } from "node:url";

import vue from "@vitejs/plugin-vue";
import { defineConfig } from "vitest/config";

// 本组只验证真实组件的图片加载属性，公开图片路径保持 URL 字符串。
// 禁止 SSR 单测将 /catalog/... 转成 Windows file URL；生产构建仍使用 vite.config.ts。
export default defineConfig({
  root: fileURLToPath(new URL(".", import.meta.url)),
  plugins: [vue({ template: { transformAssetUrls: false } })],
  resolve: {
    alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) },
  },
  test: {
    include: ["src/pages/catalog/catalogResourcePriority.test.ts"],
  },
});

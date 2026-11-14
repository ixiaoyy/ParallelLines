import { fileURLToPath, URL } from "node:url";
import { defineConfig } from "vitest/config";

// 仅隔离验证浏览器协议和账号响应隔离；不访问业务API、数据库或模型。
export default defineConfig({
  root: fileURLToPath(new URL(".", import.meta.url)),
  resolve: { alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) } },
  test: { include: ["src/features/auth/unified/*.test.ts"] },
});

import { fileURLToPath, URL } from "node:url";
import { defineConfig } from "vitest/config";

// 仅用内存存储和请求替身验证个人记录保存/同步，不访问业务接口或数据库。
export default defineConfig({
  root: fileURLToPath(new URL(".", import.meta.url)),
  resolve: { alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) } },
  test: { include: ["src/features/space/api.test.ts"] },
});

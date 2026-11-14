import { defineConfig } from "@playwright/test";

const env = {
  VITE_UNIFIED_AUTH_ENABLED: "true", VITE_API_BASE_URL: "/api/v1",
  VITE_UNIFIED_MAIN_ORIGIN: "http://127.0.0.1:4183", VITE_UNIFIED_CIRCLE_ORIGIN: "http://127.0.0.1:4184",
  VITE_STATIC_ASSET_BASE_URL: "/static/web",
};
export default defineConfig({
  testDir: "./tests/smoke", testMatch: "unified-login.spec.ts", workers: 1, timeout: 45_000,
  use: { headless: true, launchOptions: { executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH }, trace: "retain-on-failure" },
  webServer: [
    { command: "pnpm exec vite --host 127.0.0.1 --port 4183 --strictPort", url: "http://127.0.0.1:4183", env, reuseExistingServer: false },
    { command: "pnpm exec vite --mode forum --host 127.0.0.1 --port 4184 --strictPort", url: "http://127.0.0.1:4184", env, reuseExistingServer: false },
  ],
});

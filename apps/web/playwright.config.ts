import { defineConfig } from "@playwright/test";

const WEB_PORT = 3100;
const API_PORT = 8100;
const AUTH_PORT = 54399;

/**
 * End-to-end tests of the whole product on a local rig: the real API, real Postgres and
 * real browser sessions, with Supabase Auth and the AI providers replaced by stand-ins.
 * See apps/api/tests/e2e_rig.py.
 */
export default defineConfig({
  testDir: "./e2e",
  timeout: 120_000,
  expect: { timeout: 20_000 },
  workers: 1,
  reporter: "list",
  use: {
    baseURL: `http://localhost:${WEB_PORT}`,
    trace: "retain-on-failure",
    // Uses an installed Chrome locally; CI installs Chromium.
    channel: process.env.CI ? undefined : "chrome",
  },
  webServer: [
    {
      command: "uv run python tests/e2e_rig.py",
      cwd: "../api",
      url: `http://localhost:${API_PORT}/health/ready`,
      timeout: 120_000,
      reuseExistingServer: false,
      // Lets the rig stop its database, rather than leaving it running.
      gracefulShutdown: { signal: "SIGTERM", timeout: 8000 },
      env: {
        PYTHONPATH: ".",
        RIG_API_PORT: String(API_PORT),
        RIG_AUTH_PORT: String(AUTH_PORT),
        CORS_ORIGINS: `http://localhost:${WEB_PORT}`,
      },
    },
    {
      command: `npx next dev -p ${WEB_PORT}`,
      url: `http://localhost:${WEB_PORT}`,
      timeout: 180_000,
      reuseExistingServer: false,
      env: {
        NEXT_PUBLIC_SUPABASE_URL: `http://localhost:${AUTH_PORT}`,
        NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY: "e2e-local-only",
        NEXT_PUBLIC_API_URL: `http://localhost:${API_PORT}`,
        DEMO_EMAIL: "demo@example.com",
        DEMO_PASSWORD: "e2e-demo-password",
      },
    },
  ],
});

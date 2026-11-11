import path from "node:path";

import { defineConfig, devices } from "@playwright/test";

function serverEnv(overrides: Record<string, string>): Record<string, string> {
  return Object.fromEntries(
    Object.entries({ ...process.env, ...overrides }).filter(
      (entry): entry is [string, string] => entry[1] !== undefined,
    ),
  );
}

export default defineConfig({
  testDir: "./tests/e2e-real",
  fullyParallel: false,
  workers: 1,
  timeout: 60_000,
  expect: {
    timeout: 15_000,
  },
  reporter: [["list"]],
  use: {
    baseURL: "http://localhost:3100",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [
    {
      name: "chromium-real",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
  webServer: [
    {
      name: "backend",
      command: "uv run python scripts/run_e2e_server.py",
      cwd: path.resolve(process.cwd(), "../backend"),
      url: "http://127.0.0.1:8000/api/v1/health",
      timeout: 120_000,
      reuseExistingServer: false,
      env: serverEnv({
        APP_ENV: "test",
        DATABASE_URL:
          "sqlite+pysqlite:///./tmp/e2e-real/phase3-e2e.sqlite3",
        JWT_SECRET: "e2e-test-secret-at-least-32-characters",
        TEMP_ROOT: "./tmp/e2e-real",
        HISTORY_ROOT: "./tmp/e2e-real/history",
        LOG_DIR: "./tmp/e2e-real/logs",
        RUNTIME_LOG_DIR: "./tmp/e2e-real/logs/runtime-errors",
        CLEANUP_INTERVAL_SECONDS: "3600",
        RATE_LIMIT_PER_MINUTE: "1000",
        EXCEL_RATE_LIMIT_PER_MINUTE: "1000",
        E2E_BACKEND_PORT: "8000",
      }),
    },
    {
      name: "frontend-real",
      command: "pnpm dev --port 3100",
      url: "http://localhost:3100",
      timeout: 120_000,
      reuseExistingServer: !process.env.CI,
      env: serverEnv({
        NEXT_PUBLIC_DEMO_MODE: "false",
        API_INTERNAL_URL: "http://127.0.0.1:8000",
      }),
    },
  ],
});

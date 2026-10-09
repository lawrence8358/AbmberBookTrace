import { defineConfig, devices } from "@playwright/test";
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const e2ePort = process.env.E2E_PORT ?? process.env.PLAYWRIGHT_PORT ?? "5080";
const testData = mkdtempSync(join(tmpdir(), "booktrace-e2e-"));

export default defineConfig({
  testDir: "./tests/e2e",
  fullyParallel: false,
  workers: 1,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  reporter: "list",
  use: {
    baseURL: `http://127.0.0.1:${e2ePort}`,
    trace: "on-first-retry",
    launchOptions: {
      executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE
        ?? (process.platform === "win32" ? "C:/Program Files/Google/Chrome/Application/chrome.exe" : "/usr/bin/google-chrome"),
    },
  },
  webServer: {
    command:
      `pnpm --dir src/booktrace-client exec vue-tsc --noEmit && pnpm --dir src/booktrace-client exec vite build && dotnet run --project src/BookTrace.Api --no-launch-profile --urls http://127.0.0.1:${e2ePort}`,
    url: `http://127.0.0.1:${e2ePort}/health`,
    env: {
      ASPNETCORE_ENVIRONMENT: "Playwright",
      ConnectionStrings__BookTrace: `Data Source=${join(testData, "test.db")}`,
      CoverStorage__Path: join(testData, "covers"),
      BOOKTRACE_NOW_UTC: process.env.BOOKTRACE_NOW_UTC ?? "2026-09-20T09:00:00.000Z",
    },
    reuseExistingServer: false,
    timeout: 120_000,
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
    {
      name: "mobile",
      testMatch: ["**/auth.spec.ts", "**/book-cover.spec.ts", "**/responsive-acceptance.spec.ts"],
      use: {
        ...devices["Desktop Chrome"],
        viewport: { width: 390, height: 844 },
        hasTouch: true,
        isMobile: false,
      },
    },
  ],
});

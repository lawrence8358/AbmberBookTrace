import { defineConfig, devices } from "@playwright/test";

const e2ePort = process.env.E2E_PORT ?? "5080";

export default defineConfig({
  testDir: "./tests/e2e",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  reporter: "list",
  use: {
    baseURL: `http://127.0.0.1:${e2ePort}`,
    trace: "on-first-retry",
    launchOptions: {
      executablePath: "/usr/bin/google-chrome",
    },
  },
  webServer: {
    command:
      `cd src/booktrace-client && node_modules/.bin/vue-tsc --noEmit && node_modules/.bin/vite build && cd ../.. && dotnet run --project src/BookTrace.Api --no-launch-profile --urls http://127.0.0.1:${e2ePort}`,
    url: `http://127.0.0.1:${e2ePort}/health`,
    env: {
      ASPNETCORE_ENVIRONMENT: "Playwright",
    },
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
});

import { defineConfig, devices } from "@playwright/test";

/*
 * Browser tests for the whole app (frontend + Django API in demo mode).
 *
 * Before running, the API must be up on :8000 with a Celery worker, and
 * E2E_MANAGE must say how to run manage.py (used to make invite codes):
 *   local:  E2E_MANAGE="docker compose exec -T web python manage.py"
 *   CI:     E2E_MANAGE="uv run python manage.py"
 * The frontend is built and started by Playwright (webServer below).
 *
 * Firefox is the browser the app is checked in. To use a Firefox build that
 * is already on your computer instead of downloading Playwright's, set
 * E2E_FIREFOX_PATH to its executable.
 */
// E2E_PORT runs the tests' own server on another port (5173 is also allowed
// by the API's CORS settings), so a dev server already on 3000 is left alone.
const PORT = process.env.E2E_PORT ?? "3000";

export default defineConfig({
  testDir: "./e2e",
  timeout: 120_000,
  expect: { timeout: 15_000 },
  // The journey test signs up and logs in; the API allows 10 logins a
  // minute per address, so tests run one at a time.
  workers: 1,
  fullyParallel: false,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["list"], ["html", { open: "never" }]] : "list",
  use: {
    baseURL: `http://localhost:${PORT}`,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [
    {
      name: "firefox",
      use: {
        ...devices["Desktop Firefox"],
        launchOptions: process.env.E2E_FIREFOX_PATH ? { executablePath: process.env.E2E_FIREFOX_PATH } : {},
      },
    },
  ],
  webServer: {
    command: `npm run start -- -p ${PORT}`,
    url: `http://localhost:${PORT}`,
    reuseExistingServer: !process.env.CI,
    timeout: 60_000,
  },
});

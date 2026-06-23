import { defineConfig, devices } from "@playwright/test";

/**
 * Playwright e2e config for Axiom Finance frontend.
 * Boots the Next.js dev server and runs specs in tests/e2e.
 * Backend is expected at http://localhost:8000 (set NEXT_PUBLIC_API_BASE
 * or run docker-compose for full-stack flows).
 */
export default defineConfig({
  testDir: "./tests/e2e",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  reporter: "list",
  use: {
    baseURL: "http://localhost:3000",
    trace: "on-first-retry",
  },
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] } },
  ],
  webServer: {
    command: "npm run dev",
    url: "http://localhost:3000",
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },
});

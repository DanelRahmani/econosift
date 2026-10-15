import { defineConfig, devices } from "@playwright/test";

/**
 * Playwright e2e config for EconoSift frontend.
 * Boots the Next.js dev server and runs specs in tests/e2e.
 * Backend is expected at http://localhost:8000 (set NEXT_PUBLIC_API_BASE
 * or run docker-compose for full-stack flows).
 */
// PLAYWRIGHT_BASE_URL points the suite at an already-running stack (e.g. the
// docker-compose stack on :80, which is what CI uses). Left unset, the config
// keeps its original behaviour of booting `next dev` on :3000, so local runs
// are unchanged.
// PW_MOCK_API=1 (CI's smoke job) runs the suite against the static export with /api answered
// from recorded fixtures by tests/e2e/mock-server.mjs: no backend, no live sources. The gate
// still runs the suite against live Docker (PLAYWRIGHT_BASE_URL=http://localhost).
const mockApi = !!process.env.PW_MOCK_API;
const baseURL = process.env.PLAYWRIGHT_BASE_URL ?? (mockApi ? "http://localhost:4100" : "http://localhost:3000");
const useExternalServer = !!process.env.PLAYWRIGHT_BASE_URL;

export default defineConfig({
  testDir: "./tests/e2e",
  fullyParallel: true,
  // The backend is a single uvicorn process and every page fans out to many
  // uncached endpoints. Five parallel workers saturate it and the suite starts
  // failing on its own load rather than on real defects — capping workers is
  // the fix, not longer timeouts.
  workers: 2,
  forbidOnly: !!process.env.CI,
  ...(mockApi && !process.env.PLAYWRIGHT_BASE_URL ? { globalTeardown: "./tests/e2e/mock-teardown.mjs" } : {}),
  retries: process.env.CI ? 2 : 0,
  reporter: "list",
  // Pages fan out to many uncached upstream endpoints on a cold backend.
  timeout: 90_000,
  expect: { timeout: 30_000 },
  use: {
    baseURL,
    trace: "on-first-retry",
  },
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] } },
  ],
  ...(useExternalServer
    ? {}
    : mockApi
    ? {
        webServer: {
          command: "node tests/e2e/mock-server.mjs",
          url: "http://localhost:4100/api/health",
          reuseExistingServer: !process.env.CI,
          timeout: 30_000,
        },
      }
    : {
        webServer: {
          command: "npm run dev",
          url: "http://localhost:3000",
          reuseExistingServer: true,
          timeout: 120_000,
        },
      }),
});

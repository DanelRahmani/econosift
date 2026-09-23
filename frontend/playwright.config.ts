import { defineConfig, devices } from "@playwright/test";

/**
 * Playwright e2e config for Axiom Finance frontend.
 * Boots the Next.js dev server and runs specs in tests/e2e.
 * Backend is expected at http://localhost:8000 (set NEXT_PUBLIC_API_BASE
 * or run docker-compose for full-stack flows).
 */
// PLAYWRIGHT_BASE_URL points the suite at an already-running stack (e.g. the
// docker-compose stack on :80, which is what CI uses). Left unset, the config
// keeps its original behaviour of booting `next dev` on :3000, so local runs
// are unchanged.
const baseURL = process.env.PLAYWRIGHT_BASE_URL ?? "http://localhost:3000";
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
    : {
        webServer: {
          command: "npm run dev",
          url: "http://localhost:3000",
          reuseExistingServer: true,
          timeout: 120_000,
        },
      }),
});

import { test, expect, type Page, type ConsoleMessage } from "@playwright/test";

/**
 * Page-level smoke tests — Phase 40 (task A5).
 *
 * These catch the failure this app is most prone to: an endpoint changes shape
 * or an upstream source dies, the page still returns HTTP 200 because the shell
 * is server-rendered, and the panel silently renders empty. A 200 proves
 * nothing here; only real content does.
 *
 * Each page names its own landmark rather than assuming a generic <h1> —
 * /dashboard and /markets have no h1 at all, they open straight into panels.
 *
 * Timeouts are deliberately generous. Every panel is compute-tier "green" and
 * fetches on load, so on a cold cache a page can legitimately take tens of
 * seconds; the app also holds a startup splash until /api/health answers.
 * These tests assert the app works, not that it is fast.
 */

/** Console errors that are environmental rather than app defects. */
const IGNORED_CONSOLE = [
  /favicon\.ico/i,          // no favicon is served; unrelated to page health
  /ResizeObserver loop/i,   // benign Recharts resize chatter
  /Download the React DevTools/i,
];

function collectConsoleErrors(page: Page): string[] {
  const errors: string[] = [];
  page.on("console", (msg: ConsoleMessage) => {
    if (msg.type() !== "error") return;
    const text = msg.text();
    if (IGNORED_CONSOLE.some((re) => re.test(text))) return;
    errors.push(text);
  });
  page.on("pageerror", (err) => errors.push(`uncaught: ${err.message}`));
  return errors;
}

/**
 * A landmark that only appears once the page has actually rendered content,
 * plus a value pattern proving real data arrived rather than placeholders.
 */
const PAGES: { path: string; landmark: RegExp; value: RegExp }[] = [
  { path: "/dashboard", landmark: /US Treasury Yield Curve/i, value: /\d/ },
  { path: "/markets", landmark: /Normalised Price|Latest News/i, value: /\d/ },
  { path: "/macro", landmark: /Macro Intelligence/i, value: /\d/ },
  { path: "/portfolio", landmark: /Portfolio Analytics/i, value: /\d/ },
  { path: "/screener", landmark: /Stock Screener/i, value: /\d/ },
  { path: "/yield", landmark: /Rates & Policy/i, value: /\d/ },
  { path: "/risk", landmark: /Risk & Rolling Metrics/i, value: /\d/ },
  { path: "/options", landmark: /Options Analytics/i, value: /\d/ },
];

for (const { path, landmark, value } of PAGES) {
  test(`${path} renders content without console errors`, async ({ page }) => {
    const errors = collectConsoleErrors(page);

    const response = await page.goto(path, { waitUntil: "domcontentloaded" });
    expect(response?.status(), `${path} should return 2xx`).toBeLessThan(400);

    await expect(
      page.getByText(landmark).first(),
      `${path} never rendered its landmark`,
    ).toBeVisible({ timeout: 100_000 });

    const body = await page.locator("body").innerText();
    expect(value.test(body), `${path} rendered no numeric content`).toBe(true);

    expect(errors, `${path} logged console errors`).toEqual([]);
  });
}

test("navigation between pages preserves the shell", async ({ page }) => {
  await page.goto("/macro", { waitUntil: "domcontentloaded" });
  await expect(page.getByText(/Macro Intelligence/i).first()).toBeVisible({ timeout: 100_000 });

  await page.goto("/portfolio", { waitUntil: "domcontentloaded" });
  await expect(page.getByText(/Portfolio Analytics/i).first()).toBeVisible({ timeout: 100_000 });

  // Global nav survives client-side transitions.
  await expect(page.getByRole("link", { name: /Macro/i }).first()).toBeVisible();
});

test("an unknown route does not crash the app shell", async ({ page }) => {
  await page.goto("/definitely-not-a-real-page", { waitUntil: "domcontentloaded" });
  const body = await page.locator("body").innerText();
  expect(body.trim()).not.toBe("");
});

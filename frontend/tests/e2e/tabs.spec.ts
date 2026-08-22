import { test, expect, type Page } from "@playwright/test";

/**
 * Tab-level regression tests — Phase 40 (task A5).
 *
 * Deep-linked tabs are the most fragile surface in the app: they fetch their own
 * data client-side, so a changed response shape leaves the tab blank while the
 * page still returns 200. The Phase 39 additions (credit conditions, oil shock
 * decomposition, Treasury curve noise) are the newest and likeliest to regress.
 *
 * Each tab must reach one of exactly two coherent states:
 *   1. data rendered, or
 *   2. an explicit "unavailable" message.
 * A blank panel is neither, and that is the bug being guarded against.
 *
 * Asserting only the data state would make these fail in CI, which runs with no
 * API keys and therefore legitimately renders state 2.
 */

const TAB_TIMEOUT = 90_000;

/** Assert the panel mounted and settled into a coherent state. */
async function expectCoherentPanel(
  page: Page,
  heading: RegExp,
  dataMarkers: RegExp[],
) {
  // The heading renders in both the data and the unavailable state.
  await expect(page.getByRole("heading", { name: heading })).toBeVisible({
    timeout: TAB_TIMEOUT,
  });

  const body = await page.locator("body").innerText();
  const hasData = dataMarkers.every((re) => re.test(body));
  const hasExplicitFailure =
    /unavailable|FRED API key is required|did not return data/i.test(body);

  expect(
    hasData || hasExplicitFailure,
    "panel rendered neither data nor an explicit unavailable message",
  ).toBe(true);
}

test("macro financial tab renders the credit conditions panel", async ({ page }) => {
  await page.goto("/macro?tab=financial", { waitUntil: "domcontentloaded" });
  await expectCoherentPanel(page, /Credit & Funding Conditions/i, [
    /Excess Bond Premium/i,
    /SOFR .{1,3} IORB/i,
    /SLOOS/i,
  ]);
});

test("macro commodities tab renders the oil shock decomposition", async ({ page }) => {
  await page.goto("/macro?tab=commodities", { waitUntil: "domcontentloaded" });
  await expectCoherentPanel(page, /Oil Shock Decomposition/i, [
    /Demand component/i,
    /Oil-specific component/i,
    // The method caveat is what keeps the proxy honest — it must not be dropped.
    /not the structural VAR/i,
  ]);
});

test("yield curve noise tab renders with its limitation stated", async ({ page }) => {
  await page.goto("/yield?tab=Curve+Noise", { waitUntil: "domcontentloaded" });
  await expectCoherentPanel(page, /Treasury Curve-Fit Noise/i, [
    /Current noise/i,
    // The March-2020 caveat is a deliberate honesty feature, not decoration.
    /March 2020/i,
  ]);
});

test("yield real & breakeven tab shows the 5y5y forward", async ({ page }) => {
  await page.goto("/yield?tab=Real+%26+Breakeven", { waitUntil: "domcontentloaded" });

  // This tab has no unavailable state — it renders from the shared curve payload.
  await expect(page.getByText(/5y5y Forward Breakeven/i).first()).toBeVisible({
    timeout: TAB_TIMEOUT,
  });
});

test("macro tab selection survives a reload", async ({ page }) => {
  await page.goto("/macro?tab=financial", { waitUntil: "domcontentloaded" });
  await expect(
    page.getByRole("heading", { name: /Credit & Funding Conditions/i }),
  ).toBeVisible({ timeout: TAB_TIMEOUT });

  await page.reload({ waitUntil: "domcontentloaded" });
  await expect(
    page.getByRole("heading", { name: /Credit & Funding Conditions/i }),
  ).toBeVisible({ timeout: TAB_TIMEOUT });
});

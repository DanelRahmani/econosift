import { test, expect } from "@playwright/test";

/**
 * Phase 69 item 4: one panel that throws while rendering must not blank the page.
 * /dashboard/movers answers with a body of the wrong shape, so Top Movers throws on render;
 * the panel shows its own error card and every other Dashboard panel still renders.
 */
test("a panel that throws shows its own error and the rest of the page renders", async ({ page }) => {
  await page.route("**/api/dashboard/movers**", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ asOf: "2026-10-14", gainers: "not-a-list", losers: "not-a-list" }),
    }),
  );
  await page.goto("/dashboard", { waitUntil: "domcontentloaded" });

  await expect(page.getByTestId("panel-error").filter({ hasText: "Top movers" })).toBeVisible();
  // The neighbouring panels are untouched.
  await expect(page.getByText("US Treasury Yield Curve")).toBeVisible();
  await expect(page.getByText(/Market Breadth/)).toBeVisible();
  await expect(page.getByText("Global Indices")).toBeVisible();
});

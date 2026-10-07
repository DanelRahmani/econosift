import { test, expect } from "@playwright/test";

/**
 * P2-37 — the 13F panel shows % of shares outstanding and, once the previous
 * quarter's data set is stored, the quarter-on-quarter change. That ~100 MB
 * download runs only when the user asks. The API is mocked: the spec checks the
 * panel's states, not the SEC download.
 */
const base = {
  ticker: "AAPL", asOf: "2026-06-30", reportingLag: "45-day reporting lag", filers: 3, totalShares: 40000,
  holders: [{ name: "Fund Two LLC", shares: 20000, value: 4_000_000, pctFloat: 2.0, changeShares: null, changePct: null }],
};
const missing = { available: false, previousAsOf: null, previousDataset: "01dec2025-28feb2026",
  reason: "The previous quarter's 13F data set (01dec2025-28feb2026, a ~100 MB download) has not been loaded.",
  canLoad: true, loading: false };
const loaded = {
  ...base,
  holders: [{ ...base.holders[0], changeShares: -5000, changePct: -20.0 }],
  change: { ...missing, available: true, previousAsOf: "2026-03-31", reason: null, canLoad: false },
};

test("13F panel loads the previous quarter on request and shows the QoQ change", async ({ page }) => {
  let posted = 0;
  await page.route("**/api/market/13f/previous", (route) => {
    posted += 1;
    return route.fulfill({ json: { started: true, window: "01dec2025-28feb2026", error: null } });
  });
  await page.route("**/api/market/13f?**", (route) =>
    route.fulfill({ json: posted ? loaded : { ...base, change: missing } }));

  await page.goto("/markets?t=AAPL&tab=News+%26+Events", { waitUntil: "domcontentloaded" });
  // The card is the panel's source-scope root (it also names the ticker for the Source menu).
  const panel = page.locator('[data-prov-scope][data-prov-ctx="AAPL"]', {
    has: page.getByRole("heading", { name: "Institutional Holders (13F)" }),
  });
  await expect(panel.getByText("% Shs Out")).toBeVisible({ timeout: 60_000 });
  await expect(panel.getByText("2.00%")).toBeVisible();
  await expect(panel.getByText(/QoQ change: n\/a/)).toBeVisible();

  await panel.getByRole("button", { name: /Load previous quarter/ }).click();
  await expect(panel.getByText("QoQ change vs the quarter ending 2026-03-31")).toBeVisible();
  await expect(panel.getByText(/▼ 5K \(-20\.0%\)/)).toBeVisible();
  expect(posted).toBe(1);
});

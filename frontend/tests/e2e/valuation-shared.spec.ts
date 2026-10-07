import { test, expect } from "@playwright/test";

/**
 * P3-34 / P2-39 — the Valuation tab's engine and DCF panel share one /valuation/full request, and a
 * degraded bundle shows "Partial data, refreshing…" until a re-request brings the full one.
 * The first response is the live one with `degraded` forced on; later ones pass through.
 */
test("valuation panels share one request and refresh a degraded bundle", async ({ page }) => {
  test.setTimeout(150_000);
  let calls = 0;
  await page.route("**/api/valuation/full**", async (route) => {
    calls += 1;
    const res = await route.fetch();
    const body = await res.json();
    if (calls === 1) {
      body.degraded = true;
      body.degradedReason = "Yahoo returned partial company data (test).";
    }
    await route.fulfill({ response: res, json: body });
  });

  await page.goto("/markets?t=AAPL&tab=Valuation");
  const banner = page.getByRole("status").filter({ hasText: "Partial data, refreshing" });
  await expect(banner).toBeVisible({ timeout: 90_000 });
  // Engine grid and DCF panel both rendered from the same single response.
  expect(calls).toBe(1);

  // The 15 s re-request returns the full bundle and the notice goes away.
  await expect(banner).toBeHidden({ timeout: 45_000 });
  expect(calls).toBe(2);
});

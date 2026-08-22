import { test, expect } from "@playwright/test";

/**
 * Tab-level regression tests — Phase 40 (task A5).
 *
 * Deep-linked tabs are the most fragile surface in the app: they fetch their
 * own data client-side, so a changed response shape leaves the tab blank while
 * the page still returns 200. The Phase 39 additions (credit conditions, oil
 * shock decomposition, Treasury curve noise) are the newest and therefore the
 * likeliest to regress unnoticed.
 */

test("macro financial tab renders the credit conditions panel", async ({ page }) => {
  await page.goto("/macro?tab=financial", { waitUntil: "domcontentloaded" });

  await expect(page.getByRole("heading", { name: /Credit & Funding Conditions/i }))
    .toBeVisible({ timeout: 60_000 });

  // The four KPI labels, which only appear once the endpoint has returned.
  await expect(page.getByText("Excess Bond Premium").first()).toBeVisible();
  await expect(page.getByText(/SOFR . IORB/).first()).toBeVisible();
  await expect(page.getByText(/SLOOS/).first()).toBeVisible();

  // Evidence table renders its citations.
  await expect(page.getByText(/Gilchrist/).first()).toBeVisible();
});

test("macro commodities tab renders the oil shock decomposition", async ({ page }) => {
  await page.goto("/macro?tab=commodities", { waitUntil: "domcontentloaded" });

  await expect(page.getByRole("heading", { name: /Oil Shock Decomposition/i }))
    .toBeVisible({ timeout: 60_000 });

  await expect(page.getByText(/Demand component/i).first()).toBeVisible();
  await expect(page.getByText(/Oil-specific component/i).first()).toBeVisible();
  // The method note must stay visible — it is what keeps the proxy honest.
  await expect(page.getByText(/not the structural VAR/i)).toBeVisible();
});

test("yield curve noise tab renders with its limitation stated", async ({ page }) => {
  await page.goto("/yield?tab=Curve+Noise", { waitUntil: "domcontentloaded" });

  await expect(page.getByRole("heading", { name: /Treasury Curve-Fit Noise/i }))
    .toBeVisible({ timeout: 60_000 });

  await expect(page.getByText(/Current noise/i).first()).toBeVisible();
  // The March-2020 caveat is a deliberate honesty feature, not decoration.
  await expect(page.getByText(/March 2020/i)).toBeVisible();
});

test("yield real & breakeven tab shows the 5y5y forward", async ({ page }) => {
  await page.goto("/yield?tab=Real+%26+Breakeven", { waitUntil: "domcontentloaded" });

  await expect(page.getByText(/5y5y Forward Breakeven/i).first())
    .toBeVisible({ timeout: 60_000 });
});

test("macro tab selection survives a reload", async ({ page }) => {
  await page.goto("/macro?tab=financial", { waitUntil: "domcontentloaded" });
  await expect(page.getByRole("heading", { name: /Credit & Funding Conditions/i }))
    .toBeVisible({ timeout: 60_000 });

  await page.reload({ waitUntil: "domcontentloaded" });
  await expect(page.getByRole("heading", { name: /Credit & Funding Conditions/i }))
    .toBeVisible({ timeout: 60_000 });
});

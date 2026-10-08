import { test, expect } from "@playwright/test";
import { readFileSync } from "node:fs";
import { join } from "node:path";

/**
 * P2-10 — the nav no longer lists pages that duplicate another page's tabs:
 * "Policy & Sovereign" (its tabs live on Yield) and "Scenario Lab" (the same
 * ScenarioTab as Portfolio → Scenario). Old links still land on the right place.
 */

test("nav and command palette drop the duplicate pages", () => {
  const root = join(__dirname, "..", "..");
  for (const file of ["components/Navbar.tsx", "components/MobileNav.tsx", "lib/commandRegistry.ts"]) {
    const src = readFileSync(join(root, file), "utf8");
    expect(src, file).not.toMatch(/href: "\/policy"|href: "\/scenario"/);
  }
});

test("old /scenario and /policy links redirect to their tabs", async ({ page }) => {
  await page.goto("/scenario", { waitUntil: "domcontentloaded" });
  await expect(page).toHaveURL(/\/portfolio\?tab=Scenario/);
  await page.goto("/policy", { waitUntil: "domcontentloaded" });
  await expect(page).toHaveURL(/\/yield/);
});

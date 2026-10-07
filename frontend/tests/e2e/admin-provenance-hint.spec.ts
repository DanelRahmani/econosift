import { test, expect } from "@playwright/test";

/**
 * P2-33 — entries cached before an upgrade added sources serve without them until
 * they expire. Admin says so and points at "Clear cache & re-warm"; with no such
 * entries it stays quiet. The health response is mocked so the spec needs no
 * particular cache state.
 */
async function mockHealth(page: import("@playwright/test").Page, gaps: number) {
  await page.route("**/api/admin/health", async (route) => {
    const res = await route.fetch();
    const body = await res.json();
    body.cache.provenanceGaps = { total: gaps, byName: gaps ? { quote: gaps } : {} };
    await route.fulfill({ response: res, json: body });
  });
}

test("Admin shows the clear-cache hint when cached entries lack sources", async ({ page }) => {
  await mockHealth(page, 3);
  await page.goto("/admin", { waitUntil: "domcontentloaded" });
  const hint = page.getByRole("status").filter({ hasText: "no source annotations" });
  await expect(hint).toBeVisible();
  await expect(hint).toContainText("3 cached entries were stored before this version");
  await expect(hint).toContainText("Clear cache & re-warm");
});

test("Admin shows no hint when every cached entry has sources", async ({ page }) => {
  await mockHealth(page, 0);
  await page.goto("/admin", { waitUntil: "domcontentloaded" });
  await expect(page.getByText("Cache Entries")).toBeVisible();
  await expect(page.getByText("no source annotations")).toHaveCount(0);
});

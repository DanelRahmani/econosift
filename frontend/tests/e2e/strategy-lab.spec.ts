import { test, expect } from "@playwright/test";

/**
 * Phase 70 item 6: the Strategy Lab says that uploads run code on this machine and
 * never runs anything on its own: a run starts only from the 🔴 Run Analysis button.
 */
test("the Strategy Lab warns about uploads and does not run on open", async ({ page }) => {
  const runs: string[] = [];
  page.on("request", (r) => {
    if (r.method() !== "GET" && r.url().includes("/api/research/strategies")) runs.push(r.url());
  });
  await page.goto("/research?tab=strategies", { waitUntil: "domcontentloaded" });

  await expect(page.getByRole("alert").filter({ hasText: "runs its Python code on this machine" })).toBeVisible();
  await expect(page.getByRole("button", { name: /Run Analysis/ })).toBeVisible();
  await expect(page.getByLabel("Strategy")).toContainText("example_momentum.py");
  await page.waitForTimeout(1500);
  expect(runs).toEqual([]);
});

import { test, expect, type Page } from "@playwright/test";

/**
 * P2-07 — number keys 1–9 pick the page's Nth tab; ←/→ step the period control
 * on pages that have one. Neither fires while typing in a field.
 */

/** Press `key` until `check` passes: a key pressed before React hydrates has no listener and is lost. */
async function pressUntil(page: Page, key: string, check: () => Promise<void>) {
  await expect(async () => {
    await page.keyboard.press(key);
    await check();
  }).toPass({ timeout: 30_000 });
}

const activeTab = (page: Page, name: string) =>
  page.locator('button[data-active="true"]', { hasText: name });

test("number keys switch Risk tabs and arrow keys step the period", async ({ page }) => {
  await page.goto("/risk", { waitUntil: "domcontentloaded" });
  await pressUntil(page, "2", async () => {
    await expect(page).toHaveURL(/tab=Extended/, { timeout: 1_000 });
  });
  await expect(activeTab(page, "Extended")).toBeVisible();

  // Periods are 1y · 2y · 3y (default 3y): ← steps back, → forward, both clamp at the ends.
  await page.keyboard.press("ArrowLeft");
  await expect(page).toHaveURL(/[?&]p=2y/);
  await page.keyboard.press("ArrowLeft");
  await page.keyboard.press("ArrowLeft");
  await expect(page).toHaveURL(/[?&]p=1y/);
  await page.keyboard.press("ArrowRight");
  await expect(page).toHaveURL(/[?&]p=2y/);

  // A key that has no tab (9 > 5 tabs) changes nothing.
  await page.keyboard.press("9");
  await expect(activeTab(page, "Extended")).toBeVisible();
});

test("keys typed into a field do not switch tabs or periods", async ({ page }) => {
  await page.goto("/risk?tab=Correlation", { waitUntil: "domcontentloaded" });
  await expect(activeTab(page, "Correlation")).toBeVisible();
  const field = page.getByRole("textbox").first();
  await field.click();
  await field.pressSequentially("1");
  await field.press("ArrowLeft");
  await expect(field).toHaveValue(/1/);
  await expect(activeTab(page, "Correlation")).toBeVisible();
  expect(page.url()).not.toMatch(/[?&]p=/);
});

test("number keys switch Macro tabs", async ({ page }) => {
  await page.goto("/macro", { waitUntil: "domcontentloaded" });
  await pressUntil(page, "2", async () => {
    await expect(page).toHaveURL(/tab=inflation/, { timeout: 1_000 });
  });
});

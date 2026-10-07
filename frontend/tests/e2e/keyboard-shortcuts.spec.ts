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

test("[ and ] step Macro tabs past the ninth, clamped at the ends (P2-42)", async ({ page }) => {
  // Macro has 16 tabs; keys 1–9 stop at "business" (9th). From it, ] reaches commodities (10th) and fx (11th).
  await page.goto("/macro?tab=business", { waitUntil: "domcontentloaded" });
  await pressUntil(page, "]", async () => {
    await expect(page).toHaveURL(/tab=commodities/, { timeout: 1_000 });
  });
  await page.keyboard.press("]");
  await expect(page).toHaveURL(/tab=fx/);
  await page.keyboard.press("[");
  await page.keyboard.press("[");
  await expect(page).toHaveURL(/tab=business/);

  // The last tab clamps: ] on "sovereign" (16th) stays there.
  await page.goto("/macro?tab=sovereign", { waitUntil: "domcontentloaded" });
  await pressUntil(page, "[", async () => {
    await expect(page).toHaveURL(/tab=policy/, { timeout: 1_000 });
  });
  await page.keyboard.press("]");
  await expect(page).toHaveURL(/tab=sovereign/);
  await page.keyboard.press("]");
  await expect(page).toHaveURL(/tab=sovereign/);
});

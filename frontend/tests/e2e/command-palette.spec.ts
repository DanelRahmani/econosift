import { test, expect, type Page } from "@playwright/test";

/**
 * P1-18 — global command palette (Ctrl/⌘+K or the navbar Search button).
 *
 * Page and tab entries are static, so these run with no API keys (CI). The Wiki
 * case uses the backend's static Wiki data, which also needs no key.
 */

/**
 * Press Ctrl+K until the palette shows: a key pressed before React hydrates the navbar
 * (pages load with `domcontentloaded`) has no listener yet and is lost.
 */
/** The palette's own search box and results (the page may have other comboboxes, e.g. a <select>). */
const palette = (page: Page) => page.getByRole("dialog", { name: "Command palette" });

async function openWithShortcut(page: Page) {
  const dialog = page.getByRole("dialog", { name: "Command palette" });
  await expect(async () => {
    if (!(await dialog.isVisible())) await page.keyboard.press("Control+K");
    await expect(dialog).toBeVisible({ timeout: 1_000 });
  }).toPass({ timeout: 30_000 });
}

test("Ctrl+K opens the palette and Enter jumps to a sub-tab on another page", async ({ page }) => {
  await page.goto("/dashboard", { waitUntil: "domcontentloaded" });
  await openWithShortcut(page);
  await palette(page).getByRole("combobox").fill("inflation");
  // the Macro › Inflation tab is the best match and is pre-selected
  const first = palette(page).getByRole("option").first();
  await expect(first).toContainText("Inflation");
  await expect(first).toContainText("Macro");
  await expect(first).toHaveAttribute("aria-selected", "true");
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/\/macro\?tab=inflation$/);
  await expect(page.getByRole("dialog", { name: "Command palette" })).toBeHidden();
});

test("the navbar button opens it, Escape closes it, and a page entry navigates", async ({ page }) => {
  await page.goto("/dashboard", { waitUntil: "domcontentloaded" });
  const dialog = page.getByRole("dialog", { name: "Command palette" });
  await expect(async () => {   // same hydration retry as openWithShortcut
    if (!(await dialog.isVisible())) await page.getByRole("button", { name: /Search pages, tabs, tickers and Wiki/ }).click();
    await expect(dialog).toBeVisible({ timeout: 1_000 });
  }).toPass({ timeout: 30_000 });
  await page.keyboard.press("Escape");
  await expect(dialog).toBeHidden();

  await openWithShortcut(page);
  await palette(page).getByRole("combobox").fill("corp health");   // fuzzy: two partial words
  await palette(page).getByRole("option", { name: /Corporate Health/ }).first().click();
  await expect(page).toHaveURL(/\/corporate$/);
});

test("jumping to another tab of the page already open switches the tab", async ({ page }) => {
  await page.goto("/research", { waitUntil: "domcontentloaded" });
  await expect(page.locator('button[data-active="true"]', { hasText: "Risk Parity" })).toBeVisible();
  await openWithShortcut(page);
  await palette(page).getByRole("combobox").fill("momentum");
  await palette(page).getByRole("option", { name: /Momentum.*Research/ }).first().click();
  await expect(page).toHaveURL(/\/research\?tab=momentum$/);
  await expect(page.locator('button[data-active="true"]', { hasText: "Momentum" })).toBeVisible();
});

test("a Wiki term opens the Wiki on that term", async ({ page }) => {
  await page.goto("/dashboard", { waitUntil: "domcontentloaded" });
  await openWithShortcut(page);
  await palette(page).getByRole("combobox").fill("sharpe ratio");
  const wikiOption = palette(page).getByRole("option", { name: /Sharpe Ratio.*Wiki/ }).first();
  await expect(wikiOption).toBeVisible({ timeout: 30_000 });
  await wikiOption.click();
  await expect(page).toHaveURL(/\/wiki\?q=Sharpe.*&term=sharpe-ratio/);
  await expect(page.locator("#wiki-term-sharpe-ratio")).toBeVisible({ timeout: 30_000 });
});

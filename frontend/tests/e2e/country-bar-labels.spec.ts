import { test, expect } from "@playwright/test";
import { categoryBarHeight } from "../../lib/format";

/**
 * P2-16 — Recharts drops category labels it thinks would collide, so a vertical
 * bar chart of 18+ countries at a fixed height showed only every other country.
 * Charts force every label (`interval={0}`) and grow with the row count.
 */

test("bar charts grow by 24 px per row above a 300 px floor", () => {
  expect(categoryBarHeight(5)).toBe(300);    // 5 × 24 = 120 < 300
  expect(categoryBarHeight(18)).toBe(432);   // 18 × 24
  expect(categoryBarHeight(40)).toBe(960);   // 40 × 24
});

test("every bar on the Trade page's exports chart has its country label", async ({ page }) => {
  await page.goto("/trade", { waitUntil: "domcontentloaded" });
  const heading = page.getByRole("heading", { name: /Exports of Goods & Services/ });
  const unavailable = page.getByText(/unavailable|did not return data/i).first();
  await expect(heading.or(unavailable)).toBeVisible({ timeout: 90_000 });
  test.skip(!(await heading.isVisible()), "trade data unavailable in this environment");

  const chart = page.locator("div", { has: heading }).last().locator(".recharts-wrapper").first();
  const bars = chart.locator(".recharts-bar-rectangle");
  await expect(bars.first()).toBeVisible({ timeout: 30_000 });
  const nBars = await bars.count();
  expect(nBars, "enough countries to trigger label thinning").toBeGreaterThanOrEqual(18);
  await expect(chart.locator(".recharts-yAxis .recharts-cartesian-axis-tick")).toHaveCount(nBars);
});

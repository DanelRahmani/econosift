import { test, expect } from "@playwright/test";
import { readFileSync } from "node:fs";
import { join } from "node:path";

/**
 * P2-34 (A2) — the CAPM "Alpha (ann.)" tile must show the annualised alpha or
 * "—". The response also carries `alpha`, the *daily* regression intercept
 * (portfolio.py: annAlpha = alpha × 252), so falling back to it would print a
 * daily figure ~252× too small under an annual label. No browser needed.
 */
test("CAPM tile never falls back to the daily alpha", () => {
  const src = readFileSync(join(__dirname, "..", "..", "components", "portfolio", "CAPMAttribution.tsx"), "utf8");
  expect(src).not.toMatch(/annAlpha\s*\?\?\s*data\.alpha\b/);
  expect(src).toMatch(/label="Alpha \(ann\.\)"/);
});

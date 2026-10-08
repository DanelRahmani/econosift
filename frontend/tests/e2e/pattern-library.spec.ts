import { test, expect } from "@playwright/test";
import { readFileSync } from "node:fs";
import { join } from "node:path";

/**
 * P2-15 (scoped) — the shared pattern-library pieces (KpiTile / KpiStrip / ControlBar)
 * live in components/ui.tsx and the pilot pages use them instead of hand-rolling the
 * inline KPI card markup. Static source checks, no browser needed.
 */

const root = join(__dirname, "..", "..");
const read = (rel: string) => readFileSync(join(root, rel), "utf8");

test("components/ui.tsx exports KpiTile, KpiStrip and ControlBar", () => {
  const ui = read("components/ui.tsx");
  for (const name of ["KpiTile", "KpiStrip", "ControlBar"]) {
    expect(ui, name).toMatch(new RegExp(`export function ${name}\\b`));
  }
});

test("ControlBar renders a toolbar", () => {
  expect(read("components/ui.tsx")).toMatch(/role="toolbar"/);
});

for (const page of ["app/mergers/page.tsx", "app/insider/page.tsx", "app/corporate/page.tsx"]) {
  test(`${page} uses the shared components, not the inline KPI markup`, () => {
    const src = read(page);
    const imp = src.match(/import\s*\{([^}]*)\}\s*from\s*"@\/components\/ui"/);
    expect(imp, "imports from @/components/ui").not.toBeNull();
    // corporate has no live KPI strip (its private KpiCard was dead code), so it adopts ControlBar instead
    expect(imp![1]).toMatch(/\b(KpiTile|KpiStrip|ControlBar)\b/);
    expect(src).not.toMatch(/text-2xl font-bold mt-1/);
  });
}

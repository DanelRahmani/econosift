import { test, expect } from "@playwright/test";
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { fmtPct, fmtPctFromFraction } from "../../lib/format";

/**
 * P2-20 — one convention for fractions: `fmtPctFromFraction` takes the fraction
 * (0.1234) and prints the percent ("12.34%"). `fmtPct` is only for values the API
 * already sends in percent units. Scaling a fraction by hand (`fmtPct(v * 100)`)
 * is the fragile double-scaling pattern this pins out. No browser needed.
 */

test("fractions format as percent, with the digits asked for", () => {
  expect(fmtPctFromFraction(0.1234)).toBe("12.34%");      // 0.1234 × 100 = 12.34
  expect(fmtPctFromFraction(-0.0567, 1)).toBe("-5.7%");   // −0.0567 × 100 = −5.67 → 1 dp
  expect(fmtPctFromFraction(0.5, 0)).toBe("50%");
  expect(fmtPctFromFraction(null)).toBe("—");
  expect(fmtPctFromFraction(Number.NaN)).toBe("—");
  expect(fmtPct(12.34)).toBe("12.34%");                   // already percent: printed as is
});

function sources(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const p = join(dir, name);
    if (statSync(p).isDirectory()) return sources(p);
    return /\.tsx?$/.test(name) ? [p] : [];
  });
}

test("no component scales a fraction by hand before fmtPct", () => {
  const root = join(__dirname, "..", "..");
  const offenders = ["app", "components", "lib"]
    .flatMap((d) => sources(join(root, d)))
    .flatMap((file) =>
      readFileSync(file, "utf8")
        .split("\n")
        .map((line, i) => ({ file, line: i + 1, text: line }))
        .filter(({ text }) => /fmtPct\([^;]*?\*\s*100\b/.test(text)),
    )
    .map(({ file, line }) => `${file.slice(root.length + 1)}:${line}`);
  expect(offenders).toEqual([]);
});

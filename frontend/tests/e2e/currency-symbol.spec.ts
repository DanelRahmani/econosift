import { test, expect } from "@playwright/test";
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { currencySymbol } from "../../lib/format";

/**
 * P2-34 (A2) — an unknown quote currency is shown without a symbol, never as "$". Chart axes
 * take the symbol from the response's currency instead of hard-coding it. No browser needed.
 */

test("an unknown currency has no symbol (never an assumed dollar)", () => {
  expect(currencySymbol(undefined)).toBe("");
  expect(currencySymbol(null as any)).toBe("");
  expect(currencySymbol("")).toBe("");
});

test("known currencies keep their symbol, others print the code", () => {
  expect(currencySymbol("USD")).toBe("$");
  expect(currencySymbol("EUR")).toBe("€");
  expect(currencySymbol("SEK")).toBe("SEK ");
});

function sources(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const p = join(dir, name);
    if (statSync(p).isDirectory()) return sources(p);
    return /\.tsx?$/.test(name) ? [p] : [];
  });
}

// Scoped to the per-ticker Markets charts, whose quote currency varies. Macro axes such as the
// central-bank balance sheets (`$${v}T`) are genuinely USD-only series.
test("no Markets tickFormatter hard-codes a $ price prefix", () => {
  const root = join(__dirname, "..", "..");
  const offenders = [join("components", "markets"), join("app", "dividends")]  // dividends: P3-41
    .flatMap((d) => sources(join(root, d)))
    .filter((file) => /tickFormatter=\{[^}]*`\$\$\{/.test(readFileSync(file, "utf8")))
    .map((file) => file.slice(root.length + 1));
  expect(offenders).toEqual([]);
});

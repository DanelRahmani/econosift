import { test, expect } from "@playwright/test";
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";

/**
 * P2-34 (A4) — colours come from the theme tokens defined in `app/globals.css`
 * (`--border`, `--text-muted`, `--primary`, …, used as `rgb(var(--x))`) or the
 * Tailwind classes mapped to them (`text-text-muted`). The old `var(--color-*)`
 * names and a bare `text-muted` class are defined nowhere, so they silently fell
 * back to the browser default colour. No browser needed.
 */

function sources(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const p = join(dir, name);
    if (statSync(p).isDirectory()) return sources(p);
    return /\.tsx?$/.test(name) ? [p] : [];
  });
}

function offenders(pattern: RegExp): string[] {
  const root = join(__dirname, "..", "..");
  return ["app", "components", "lib"]
    .flatMap((d) => sources(join(root, d)))
    .flatMap((file) =>
      readFileSync(file, "utf8")
        .split("\n")
        .map((line, i) => ({ file, line: i + 1, text: line }))
        .filter(({ text }) => pattern.test(text)),
    )
    .map(({ file, line }) => `${file.slice(root.length + 1)}:${line}`);
}

test("no undefined --color-* CSS variables", () => {
  expect(offenders(/var\(--color-/)).toEqual([]);
});

test("no bare text-muted class (the mapped class is text-text-muted)", () => {
  expect(offenders(/(?<![\w-])text-muted(?![\w-])/)).toEqual([]);
});

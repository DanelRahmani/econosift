import { test } from "node:test";
import assert from "node:assert/strict";
import { capPoints, MAX_CHART_POINTS } from "../../lib/series.ts";

const rows = (n) => Array.from({ length: n }, (_, i) => ({ date: `d${i}`, value: i }));

test("short series pass through untouched (same array)", () => {
  const r = rows(500);
  assert.equal(capPoints(r), r);
  assert.equal(MAX_CHART_POINTS, 500);
});

test("long series are thinned to at most the cap, keeping the first and last point", () => {
  for (const n of [501, 1260, 2700, 11_552]) {
    const out = capPoints(rows(n));
    assert.ok(out.length <= 500, `${n} -> ${out.length}`);
    assert.ok(out.length >= 450, `${n} -> ${out.length} keeps most of the budget`);
    assert.equal(out[0].value, 0);
    assert.equal(out.at(-1).value, n - 1);
    for (let i = 1; i < out.length; i++) assert.ok(out[i].value > out[i - 1].value, "order kept");
  }
});

test("points named in `keep` survive thinning (reference areas pinned to a date)", () => {
  const out = capPoints(rows(2000), 500, (p) => p.date === "d1001" || p.date === "d1337");
  assert.ok(out.length <= 500);
  assert.ok(out.some((p) => p.date === "d1001"));
  assert.ok(out.some((p) => p.date === "d1337"));
});

test("empty and missing input give an empty array", () => {
  assert.deepEqual(capPoints([]), []);
  assert.deepEqual(capPoints(undefined), []);
});

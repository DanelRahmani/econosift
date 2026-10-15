// Run with: node --test tests/unit  (Node >= 22.18 strips the TypeScript types itself)
import { test } from "node:test";
import assert from "node:assert/strict";
import { STALE_MS, staleTimeFor, retryFor } from "../../lib/queryPolicy.ts";

test("snapshot data goes stale after about a minute", () => {
  for (const name of ["quote", "breadth", "movers", "treemap", "indices", "fearGreed", "screener"]) {
    assert.equal(staleTimeFor(name), STALE_MS.snapshot, name);
  }
  assert.equal(STALE_MS.snapshot, 60_000);
});

test("fundamentals and macro stay fresh longer than snapshots", () => {
  for (const name of ["valuationFull", "ratios", "corporateHealth", "dividendAnalysis", "researchDupont"]) {
    assert.equal(staleTimeFor(name), STALE_MS.fundamentals, name);
  }
  for (const name of ["macroInflation", "macroCentralBanks", "atlasSnapshot", "yieldCurves", "stabilityBanking", "wikiTerms"]) {
    assert.equal(staleTimeFor(name), STALE_MS.macro, name);
  }
  assert.ok(STALE_MS.fundamentals > STALE_MS.snapshot);
  assert.ok(STALE_MS.macro >= STALE_MS.fundamentals);
});

test("admin status is always refetched; anything unlisted gets the default", () => {
  assert.equal(staleTimeFor("health"), 0);
  assert.equal(staleTimeFor("adminErrors"), 0);
  assert.equal(staleTimeFor("somethingNew"), STALE_MS.default);
});

test("one retry, long retries only while the desktop backend is starting", () => {
  assert.equal(retryFor(0, false), true);
  assert.equal(retryFor(1, false), false);
  assert.equal(retryFor(5, true), true);
  assert.equal(retryFor(6, true), false);
});

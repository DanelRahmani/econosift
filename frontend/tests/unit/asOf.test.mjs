import { test } from "node:test";
import assert from "node:assert/strict";
import { asOfLabel, isPending, pendingRefetchInterval, PENDING_POLL_MS, PENDING_MAX_POLLS } from "../../lib/asOf.ts";

const NOW = new Date("2026-10-15T19:00:00Z"); // 15:00 ET

test("a timestamp from today reads as an ET clock time", () => {
  assert.equal(asOfLabel({ fetchedAt: "2026-10-15T18:45:00Z" }, NOW), "14:45 ET");
});

test("a timestamp from an earlier day keeps its date", () => {
  assert.equal(asOfLabel({ fetchedAt: "2026-10-14T20:00:00Z" }, NOW), "Oct 14, 16:00 ET");
});

test("a stored date stays a date, never shifted by the viewer's time zone", () => {
  assert.equal(asOfLabel({ asOf: "2026-10-14" }, NOW), "Oct 14, 2026");
});

test("fetchedAt wins over asOf; the provenance stamp is the last resort", () => {
  assert.equal(asOfLabel({ asOf: "2026-10-14", fetchedAt: "2026-10-15T18:45:00Z" }, NOW), "14:45 ET");
  assert.equal(asOfLabel({ provenance: { "*": { fetchedAt: "2026-10-15T18:30:00Z" } } }, NOW), "14:30 ET");
  assert.equal(asOfLabel({ provenance: { "*": [{ fetchedAt: "2026-10-15T18:15:00Z" }] } }, NOW), "14:15 ET");
});

test("nothing usable gives null instead of an invented time", () => {
  assert.equal(asOfLabel(null, NOW), null);
  assert.equal(asOfLabel({ asOf: null }, NOW), null);
  assert.equal(asOfLabel({ asOf: "not a date" }, NOW), null);
});

test("pending is the top-level status or a nested panel's", () => {
  assert.equal(isPending({ status: "pending" }), true);
  assert.equal(isPending({ analyst: { status: "pending" } }), true);
  assert.equal(isPending({ status: "ok" }), false);
  assert.equal(isPending(null), false);
  assert.equal(isPending([{ status: "pending" }]), false);
});

test("poll only while pending, and give up after a bounded number of polls", () => {
  assert.equal(pendingRefetchInterval({ status: "pending" }, 1), PENDING_POLL_MS);
  assert.equal(pendingRefetchInterval({ status: "pending" }, PENDING_MAX_POLLS + 1), false);
  assert.equal(pendingRefetchInterval({ price: 1 }, 1), false);
  assert.equal(pendingRefetchInterval(undefined, 0), false);
});

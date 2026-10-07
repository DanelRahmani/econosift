# Phase 63: status note (stopped at 98% weekly usage, 2026-10-03)

Work is on `DEV` and was committed item by item. **The phase gate has not run yet.** That means no spec-verifier
review, no Docker rebuild, no container pytest, no live checks, no full Playwright run, and no
ACTIVE_ISSUES/CHANGELOG updates. Resume by running the gate (steps 1–7 of `docs/plans/2026-10-open-issues-prompt.md`)
over `3a967f1..HEAD`, then continue with items 6–9.

## Done (committed, tested locally)

| ID | Commit | Change | Test |
|----|--------|--------|------|
| P2-36 | 726c1f8 | `tests/conftest.py` sets `DATABASE_URL` to `<tmp>/econosift_pytest.db` before any backend import and overrides any inherited value. The container gate no longer needs `-e DATABASE_URL`. | `test_test_db_pinned.py` passes with and without an inherited `DATABASE_URL`. |
| P2-18 | 84c06e8 | nginx: `/_next/static/` gets `public, max-age=31536000, immutable`; everything else under `/` gets `no-cache`. Before, HTML was `s-maxage=31536000, stale-while-revalidate`. | `cache-headers.spec.ts` passed against a reloaded nginx. **Still to do:** rebuild, then a normal page load picks up the new chunk names. |
| P3-35 | 921dec1 | `pv.stamp` / `pv.file_time` added. `fetchedAt` now comes from the snapshot build time for 13F holders (meta `builtAt`), the insider aggregate (data-set meta mtime), the country profile (countries.json and factbook file mtimes) and stored AI summaries (`created_at`). | `test_snapshot_fetched_at.py` (5 tests) |
| P2-20 | 3d225d0 | 27 `fmtPct(x * 100)` sites changed to `fmtPctFromFraction(x)`, with the same output. The Monte Carlo VaR tiles no longer turn a missing value into `0.00%`. | `percent-format.spec.ts` checks known values and scans the sources for the pattern. |
| P2-32 | e38262b | Nine endpoints now return objects with their own provenance map: options expiries, termstructure and smile (`{ticker, expiries/points}`); sector fundamentals (`{sectors}`) and drill (`{sector, industries}`); portfolio risk-contribution and kelly (`{holdings}`) and stress (`{scenarios}`); snowflake batch (`{scores}`). This is an **API change**. All frontend consumers were updated and tsc is clean. The sector drill and snowflake batch are dated by the screener snapshot. | `test_list_endpoint_provenance.py` (10 tests) |
| P2-33 | e38262b | `cache.provenance_gaps()` counts dict entries without a map in caches whose other entries have one. The count is exposed as `/admin/health` `cache.provenanceGaps`, and Admin shows the "Clear cache & re-warm" hint. | `test_cache_provenance_gaps.py`; `admin-provenance-hint.spec.ts` has not run yet because it needs the rebuilt frontend. |

## Not started

- P2-16: country labels on vertical bar charts with 18+ bars.
- P2-07: number keys for tabs, ←/→ for the period, via `useKeyboardShortcuts`, plus a Playwright test.
- P2-37: 13F quarter-on-quarter change and % float. `thirteenf_service.write_reduced` currently deletes every older window, so it must keep the previous quarter.
- DESK-02: Windows Job Object in `desktop/src-tauri/src/lib.rs`.

## Open decisions for the owner

- **P2-20 scope.** Fractions now always go through `fmtPctFromFraction`. `fmtPct` is kept for values the API already
  sends in percent (~43 sites). Making `fmtPct` itself fraction-in would mean auditing the units of every one of
  those sites. Decide whether that is wanted.
- **P2-32** is a breaking API change for the nine endpoints above. Any external script that used them needs updating.

## New issues found

- **P3-35 remainder:** data from bulk parquet files (World Bank / IMF / Fama-French through the source waterfall and
  Atlas, plus `regime_service`) is served inside `@cached`. It is therefore dated by when the cache entry was
  written, not when the file was downloaded. The bundled curated JSON (cb_meetings, doing_business, damodaran) is
  dated by the request time.
- The snowflake batch dates its data by `screener_cache.last_refresh` (the newest row). The sector drill uses the
  oldest row. "Data as of" should probably use the oldest row everywhere.
- `/ai/history` lists past summaries with `fetchedAt` set to the request time. Each item carries its own
  `created_at`, so it was left unchanged.

## Update 2026-10-07 (second session)

All nine items are implemented and committed: P2-16, P2-07, P2-37 and DESK-02 were added in this session.

- **Gate done:** spec-verifier review, with its two PARTIAL findings fixed (World Bank bulk files now date `fetchedAt`; snowflake batch uses its oldest row; `load_previous` reports honestly). Docker rebuild; container pytest passes in full **without** the `DATABASE_URL` override (pinned DB at `/tmp/econosift_pytest.db`; live cache grew 84 → 116). P2-18 confirmed: after the rebuild a normal load revalidated the HTML and matched the new scripts. Playwright: 32/33, and the 13F spec passes after fixing its locator and a real `▼ -5K` display bug.
- **DESK-02:** verified on a local release build. Force-kill before the fix: 1 orphaned backend. After: 0, port 8000 closed. A normal close still exits.
- **Still to do:** after the background backend rebuild, live-check the snowflake `fetchedAt` and regime endpoint. Mark rows resolved in `ACTIVE_ISSUES.md` (plus Recently Fixed rows) and add the CHANGELOG line. Then ask the owner about the PR.
- **New issues:** stale screener rows (e.g. ZS, last updated 2026-06-26) still appear in the sector drill. IMF/Fama-French bulk data in the source waterfall is still dated by the cache time. Macro has 16 tabs, but keys 1–9 reach only the first 9. A local `cargo build` uses a stale backend copy in `target/release/binaries` (Sep 29) that ignores `ECONOSIFT_DATA_DIR`.

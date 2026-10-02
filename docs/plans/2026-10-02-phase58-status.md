# Phase 58 status (checkpoint 2026-10-02, usage limit)

Plan: `docs/plans/2026-10-open-issues-prompt.md`. Owner chose for P1-15: **curated sourced JSON + SNB iCal feed**.

## Committed (unit-tested locally, NOT yet through the Docker gate / spec-verifier / live checks)
- **P1-15**: `backend/data/cb_meetings.json` rebuilt for 2026+2027 from each bank's official schedule
  (source URL + retrieved date per row). The old 2026 rows were wrong (e.g. Fed May 6/Nov 4/Dec 16 vs the
  Fed's Apr 29/Oct 28/Dec 9; ECB, RBA, BoJ, SNB Sep 24 off too). New `services/cb_meetings.py` (SNB yearly
  iCal overrides bundled SNB rows; `schedule_end`). Calendar response `cbScheduleEnds`, centralbanks
  `schedule_ends`; notes on Calendar page and Macro → Central Banks. Test `test_cb_meetings.py` fails 60 days
  before any bank's data runs out.
- **P2-31**: Treemap 1w/1m/3m/1y, sector chart 1Y (now 2y download) and the Sectors heatmap
  (1mo/3mo/6mo/1y, also first-of-window before) all use `session_base` 5/21/63/126/252.
  Tests in `test_sector_returns_m07_m08.py` (TestSessionBaseEverywhere).
- **P2-38**: `/corporate` Altman x4 converts liabilities via `dcf_engine.to_price_currency`'s FX; dividend
  FCF payout converts FCF. Tests `test_adr_currency_p2_38.py`.

## In flight (uncommitted in the working tree)
- **P2-39 / P3-34**: backend done + tested (`_INFO_RETRY_DELAYS` spaced 3rd attempt in `get_info`;
  `/valuation/full` returns `degraded` + `degradedReason`; tests in `test_yf_info_partial.py`).
  Frontend: `lib/useValuationFull.ts` (shared react-query key, refetch every 15 s while degraded, ≤8 times);
  `ValuationEngine.tsx` switched to it + "Partial data, refreshing…" banner. **TODO**: `DcfPanel.tsx` seed effect
  (lines ~122-148) must use `useValuationFull(selectedTicker)` and reseed when `full.data` identity changes,
  instead of its own `api.valuationFull` call; then `npx tsc --noEmit`.

## Remaining in Phase 58
- Item 0 docs: P2-28 → resolved by P1-19; P2-07 trimmed to number keys/arrows (`useKeyboardShortcuts.ts` unused);
  P3-04 resolved (Transactions tab + `/portfolio/transactions`, `/transactions/pnl` live).
- P2-40: user pointed to https://ai.google.dev/gemini-api/docs/google-search — check our `google_search` tool
  config against it, then regenerate one summary on gemini-2.5-flash.
- Gate: spec-verifier, Docker rebuild, container pytest, tsc, live checks (TSM Z ≈ 20.3 on /corporate, NVO FCF
  coverage, treemap = sector chart), Playwright, ACTIVE_ISSUES + CHANGELOG, commit + push.

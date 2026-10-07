# Prompt: work down the open issues (Phases 58–61)

Paste everything below the line into a fresh Claude Code session in `C:\Users\danel\Coding\axiomfinance`.
Run one phase per session (or two if usage allows); each phase ends verified, documented, committed
and pushed, so the next session can start cold.

---

Work down the open items in `ACTIVE_ISSUES.md` for EconoSift (FastAPI + Next.js 14, Docker Compose),
in the phases below, **one phase at a time, in order**. Read `CLAUDE.md`, `ACTIVE_ISSUES.md` and the
"Phase 51+" section of `CHANGELOG.md` first. Work on `DEV`.

## Why phased

The items differ in kind. Wrong numbers on used pages come first (Phase 58). The Markets audit's Low
leftovers are many small, independent, test-first fixes, so they parallelise well (Phase 59). Plumbing
and UX items share the frontend and the test harness (Phase 60). Model-quality items need owner choices
before any code (Phase 61). Feature ideas and permanent data limits are out of scope: list them, don't
build them.

## Ground rules (every phase, every sub-agent)

- **Reproduce first.** Confirm each item against the live stack (`http://localhost/api/...`) or by a direct
  computation before changing anything. If it does not reproduce, mark it **rejected** with the evidence.
- **Known-value test first.** Write a failing test with a hand-computable fixture (arithmetic in a comment),
  see it fail, fix, see it pass. No network in tests. Frontend behaviour gets a Playwright test.
- **Never fabricate data and never scrape HTML.** Use APIs, direct CSV/Excel/ZIP/ICS downloads or the MediaWiki
  API. When a value can't be computed honestly, return `null` plus a reason; the UI shows "n/a — reason".
- yfinance: always `.get()` with fallbacks. Every external call goes through `@cached` / `@async_cached`.
- Surgical changes only; match the surrounding style. Remove only the orphans your change creates.
- Files are CRLF. Edit with the Edit tool, or with a script that keeps the file's line endings.
- Sub-agents (Backend/Frontend/Math = sonnet, Data = haiku) only on **disjoint file sets**. The orchestrator
  alone runs git and edits shared files (`main.py`, `frontend/lib/api.ts`, `frontend/lib/types.ts`, routers
  outside a group's list).

## Gate (end of every phase)

1. Fresh-context review: `subagent_type: spec-verifier`, given only the raw phase diff, the verbatim issue rows
   and the test commands. Fix what it confirms, each with a test.
2. If Docker is not running, start Docker Desktop and wait for the engine. On any Docker build error run
   `powershell -c "[console]::beep(880,600)"` and stop.
3. `docker compose build backend frontend && docker compose up -d --force-recreate`, then the container tests
   (after the rebuild):
   `MSYS_NO_PATHCONV=1 docker compose exec -T -e DATABASE_URL=sqlite:////tmp/pytest.db backend python -m pytest -q -p no:warnings`.
   Then `cd frontend && npx tsc --noEmit`.
4. `POST /api/admin/cache/clear`, then live checks one ticker at a time. If Yahoo returns a degraded `info`
   (no sector/ROE), wait about 20 s and retry. Page checks in the browser.
5. Playwright against the stack: `cd frontend && PLAYWRIGHT_BASE_URL=http://localhost npx playwright test`.
   A cold-start timeout right after a restart is not a failure: rerun that spec once. Retry key presses until
   React has hydrated.
6. Docs: mark items fixed in `ACTIVE_ISSUES.md` (row → "✅ … RESOLVED (Phase N)" plus a "✅ Recently Fixed"
   row with before → after (live) and the test name). Add one CHANGELOG line under "Phase 51+".
7. Commit (message about the why) and push `DEV`. Watch plan usage (`get_usage`); near the 5-hour limit,
   commit finished work and write a status note under `docs/plans/` before stopping.

## Phase 58 — wrong numbers and stale rows

0. **Stale rows**, docs only:
   - **P2-28** is resolved by P1-19 (Phase 56); mark it so.
   - **P2-07** keeps only "number keys for tabs, arrow keys for periods". Ctrl+K shipped as P1-18;
     `lib/useKeyboardShortcuts.ts` is unused.
   - **P3-04**: check whether the Portfolio "Transactions" tab already covers buy/sell dates, cost basis and
     realized P&L. If it does, mark it resolved with the evidence.
1. **P1-15 — central-bank meetings end 2026-12-31.** `cb_meetings.json` has 52 unsourced 2026 rows.
   - Find honest sources for the 2027 schedules (Fed, ECB, BoE, BoJ, BoC, RBA, SNB, …). Prefer machine-readable
     files the banks publish (ICS/CSV/JSON); no HTML scraping.
   - Where only a published PDF or press release exists, propose a curated JSON with a source URL and a
     retrieved date per row, plus a visible "schedule ends <date>" note and a test that fails when the data
     runs out within 60 days.
   - **Ask the owner** to choose between the sourced options before writing them.
2. **P2-31 — Treemap 1W/1M/3M/1Y returns use the wrong base.** Use the session base the sector table and
   chart share (`sector_service.session_base`; 5/21/63/252 sessions) and the prior year-end for YTD. The Treemap
   must equal the sector chart for the same ETF and period.
3. **P2-38 — ADR currency mix on other pages.** `corporate_health_service._altman_z` and `dividend_service` FCF
   coverage divide statement-currency figures by USD values. Route them through
   `dcf_engine.to_price_currency` (no second FX path).
   - Known values: TSM Altman Z ≈ 20.3 on `/corporate` (Markets already shows it); NVO dividend FCF coverage
     in DKK→USD.
4. **P2-39 + P3-34 — degraded Yahoo `info` and the second `/valuation/full` fetch.** A half-failed `info`
   (no sector, ROE or EBITDA; net debt 0) still reaches users on a first load. In the Phase 54 gate it made
   the ASML grid DCF €847.74 while the panel showed €659.26.
   - Add a spaced retry or a background refetch for such bundles, and flag the response as degraded so the UI
     says "partial data, refreshing".
   - Make `DcfPanel` reuse the Valuation tab's data instead of fetching again.
5. **P2-40**: regenerate one AI summary on `gemini-2.5-flash`. If it is search-grounded, confirm the source
   links and the suggestion widget render, then close P2-40. If not, record the status code and leave it open.

## Phase 59 — Markets audit Low leftovers (parallel, disjoint files)

| Group | Items | Owns |
|---|---|---|
| Technicals | P3-29 Ichimoku forward cloud (emit the 26 projected Senkou bars from `ichimoku(append=False)`'s span frame), P3-30 Chikou displaced 26, P3-32 pivots stale when the market is closed (daily pivot from the last *completed* session; weekly/monthly holiday edge, using a trading calendar only if one is already a dependency, otherwise document it), P3-18 Fibonacci direction and intraday highs/lows | `technicals_service.py` + its tests (the pandas_ta tests run in the container only) |
| Ratios | P3-20 net debt minus short-term investments, P3-21 one ROE basis and one tax rate for ROIC vs WACC, P3-22 `debtToEquity` percent fallback, P3-26 a TTM label that is really the annual figure | `metrics.py`, `ratios.py` |
| Fundamentals | P3-33 Piotroski: current ratio, gross margin and asset turnover → None for banks, so they drop out of `maxScore` | `fundamentals.py` |
| Misc | P3-19 one 52-week-range definition across tabs, P3-23 EPS-surprise fallback as a percent, P3-24 Fama-French `asOf` = last data date, P3-25 short-interest universe = the real S&P 500 constituents or relabelled | `analyst_service.py`, `fama_french.py`, short-interest service; the frontend label only if needed |

## Phase 60 — plumbing and UX

- **P2-36**: `tests/conftest.py` must pin its own throwaway SQLite DB, so pytest can never wipe the live cache
  even without the `DATABASE_URL` override. Add a test that asserts the path.
- **P2-18**: stale JS after a redeploy. Set cache headers in nginx for HTML vs hashed `/_next/static`, and
  verify with a redeploy plus a page load without a hard refresh.
- **P2-20**: one percent formatter and one convention (fraction in, percent out). Remove the `fmtPct(v * 100)`
  double-scaling call sites and pin it with a unit-style test or a Playwright assertion on a known value.
- **P2-32 / P2-33**: provenance maps for the bare-list endpoints listed in the row. After the next upgrade, show
  the "Clear cache & re-warm" hint in Admin when cached entries lack provenance.
- **P2-16**: country labels on vertical bar charts with 18+ bars (explicit `interval={0}` plus height scaling).
- **P2-37**: 13F quarter-on-quarter change (keep the previous quarter's reduced data set; download only on
  request, it is about 100 MB) and % of float (shares outstanding from cached `info`).
- **P2-07 (remainder)**: number keys switch tabs and ←/→ change the period on pages with those controls, wired
  through `useKeyboardShortcuts` (never while typing in an input). Add a Playwright test.
- **DESK-02**: a Windows Job Object with `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE` in `desktop/src-tauri/src/lib.rs`, so
  a force-kill also ends `econosift-backend.exe`. Verify with `Stop-Process -Force` on a local Windows build.
  Skip it if a desktop build is not possible this session and say so.

## Phase 61 — model quality (owner decisions first)

For each item, present the options with their trade-offs and a recommendation, wait for the owner's choice,
then implement it test-first:

- **P2-29**: policy tracker mixes policy rates with money-market proxies. Options: label each row with the
  rate's true nature; source official policy rates (e.g. BIS policy-rate CSV); or both.
- **P2-30**: sovereign default probability calibration (training window vs pre-2000 defaults, hand-picked
  non-defaults). Options: re-estimate on a sourced default list, show it as a rank instead of a probability,
  or drop the probability.
- **P2-35**: breadth survivorship. Apply point-in-time membership, or label it "today's members".
- **P2-26**: new 52-week highs/lows vs the cited count. Document the definition difference or align it.
- **P2-27**: M&A tracker built from parsed headlines. Find a structured deal source, or relabel it as
  "merger news".
- **P2-34**: the low-severity bundle (IV30 in total variance, Calmar, Garman-Klass overnight gap, DDM double
  growth). Mostly mechanical once confirmed; fix each with a test.

## Out of scope (list them in the final report, don't build them)

- **Features:** P3-01 price alerts, P3-02 compare mode, P3-05 custom screener formulas, P3-07 EM sovereign
  watch, P3-08 regime overlays, P3-10 Econometric Lab extras, P3-11 Taylor rule.
- **Big refactors and UX decisions:** P2-15 pattern library, P2-10 nav redundancy.
- **Permanent limits:** P3-09 OECD SDMX, P3-13 Linux AppImage, P3-14 point-in-time fundamentals.

## Ask the owner before

- the P1-15 source choice;
- every Phase 61 option;
- merging `DEV` → `main` (open the PR only when asked);
- anything outward-facing.

Finish each phase with a table `ID | before → after (live) | test | commit`, plus the rejected items and the
open decisions, and remind the owner to run /compact.

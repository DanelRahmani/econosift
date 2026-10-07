# Prompt: Phase 64 — remaining P2/P3 issues (model quality + cleanup), delegated

Paste everything below the line into a fresh Claude Code session in `C:\Users\danel\Coding\axiomfinance`.
This merges the former "Phase 64 (model quality)" and "Phase 65 (cleanup)" into one phase. Feature ideas
(P3-01, P3-02, P3-05, P3-07, P3-08, P3-09, P3-10, P3-11) are **on hold**; do not build them.

---

Run **Phase 64** for EconoSift (FastAPI + Next.js 14, Docker Compose) on `DEV`. Read `CLAUDE.md`,
`ACTIVE_ISSUES.md`, the "Phase 51+" section of `CHANGELOG.md`, `docs/plans/2026-10-phase63-status.md`, and the
**Ground rules** and **Gate** sections of `docs/plans/2026-10-open-issues-prompt.md` first. They apply unchanged:
reproduce first, a failing known-value test before each fix, never fabricate data or scrape HTML (null + reason
instead), surgical changes, compute tiers (never auto-trigger 🟡/🔴).

## How this phase works: you orchestrate, cheaper agents implement

You (the main session) **do not write the fixes yourself**. You reproduce, get the owner's decisions, cut each
change into a work packet, dispatch it to a cheaper sub-agent, review what comes back, and commit. Use the
`agent-dispatch-packet` skill to write each packet and the `packet-executor` agent type (or `general-purpose`
with an explicit `model`) to run it.

**Your job (orchestrator):**
1. Reproduce each item against the live stack (`http://localhost/api/...`) or by direct computation. Record the
   evidence (numbers, file:line). Items that don't reproduce are **rejected** with that evidence; no packet.
2. Get the owner's decisions (Step 0) before any packet for a decision item.
3. Write one packet per change (see the template below) and dispatch it.
4. Review each returned diff yourself (`git diff`). Check it against the packet: scope respected, test written
   first, no fabricated values, style matched. Send it back with concrete notes, or accept it.
5. Edit the shared files yourself: `backend/backend/main.py`, `frontend/lib/api.ts`, `frontend/lib/types.ts`,
   `frontend/app/**/page.tsx`, `ACTIVE_ISSUES.md`, `CHANGELOG.md`. Packets must not touch them; if one needs a
   shared-file change, the packet says exactly what, and you apply it.
6. Run git: one commit per item (message about the why), push `DEV`.
7. Run the gate.

**Model routing** (cheapest that fits; escalate one step only after a failed review):

| Work | Agent | Model |
|------|-------|-------|
| Mechanical fix with an exact spec (rename, CSS token, guard, label, delete dead code) | `packet-executor` | haiku |
| Backend/frontend logic, a new test fixture, a provenance map | `packet-executor` / `general-purpose` | sonnet |
| Quant/math correctness (variance interpolation, estimators, calibration) | `general-purpose` | sonnet |
| Read-only searches ("where is X used") | `repo-scout` / `Explore` | haiku |
| Running Playwright / the container suite and reporting failures | `general-purpose` | sonnet |
| Fresh-context review of the phase diff (gate step 1) | `spec-verifier` | sonnet |

**Concurrency:** at most 3 packets at once, and only on **disjoint file sets** (list the files in each packet;
two packets never share a file). Don't edit a file yourself while a packet that owns it is running: a Phase 63
agent's edits collided with the orchestrator's. Run long checks in the background and wait for the
notification; don't poll.

### Packet template (fill every field; the agent sees nothing else)

```
Task: <ID> — <one-line goal>
Repo: C:\Users\danel\Coding\axiomfinance, branch DEV. Do NOT run git. Do NOT edit files outside "Files".
Issue row (verbatim): <paste the ACTIVE_ISSUES.md row>
Owner decision: <the option chosen in Step 0, verbatim> (or "none needed")
Reproduction: <what you observed: endpoint/command, actual vs expected, file:line>
Files (only these): <exact paths, including the test file>
Contract: <inputs/outputs, response shape, units, null + reason when not computable>
Test first: <the known-value test to write, with the hand arithmetic in a comment>; run it, see it FAIL, then fix.
Done when: <exact command(s)>, e.g. `cd backend && python -m pytest tests/<file>.py -q -p no:warnings`
           and/or `cd frontend && npx tsc --noEmit`
Rules: files may be CRLF — use the Edit tool, or Python with encoding="utf-8", newline="" keeping line endings;
never sed with regex backslashes. Never fabricate data. Match surrounding style. Theme tokens / shared UI
classes only (`.card`, `.btn`, `TabButton`, `ToggleChip`), no hard-coded colours.
Report back: one line per change (file: what), the test names, and the final test output tail.
```

## Step 0 — decisions (owner), before any packet for these items

Reproduce each first, then ask with `AskUserQuestion` (up to 4 questions per call; recommended option first,
marked "(Recommended)"; each option's description states its trade-off and rough cost). Record every answer
verbatim in `ACTIVE_ISSUES.md` (the row's details) when you commit that item.

- **P2-29** policy tracker mixes official policy rates with money-market proxies (BoE/BoJ/BoC/RBA/SNB OECD
  interbank, monthly effective FEDFUNDS, ECB MRO vs the deposit facility rate). Options: (a) label each row's
  rate type in the table and switch the ECB to the deposit facility rate; (b) source official policy rates (e.g.
  the BIS central-bank policy-rate CSV) for all banks, keeping proxies only as a labelled fallback; (c) both.
- **P2-30** sovereign default probability is weakly calibrated. Options: (a) present it as a risk **rank/score**
  and drop the "probability" wording; (b) re-estimate on a sourced default list with predictors that cover the
  episodes; (c) remove the probability column.
- **P2-35** breadth/Fear & Greed use today's S&P 500 members. Options: (a) apply the point-in-time membership the
  backtests already have; (b) keep it and label "today's members (survivorship)".
- **P2-26** 52-week highs/lows differ from a cited count. Options: (a) document the app's definition on the
  panel and in the Wiki, no code change; (b) offer a closing-price variant beside the intraday one.
- **P2-27** M&A tracker presents parsed headlines as deals. Options: (a) relabel the page and columns as
  "merger news" (no acquirer/target/value claims unless parsed with certainty); (b) find a free structured deal
  source (e.g. SEC 8-K/SC TO filings via EDGAR) and rebuild on it.
- **P2-34 (unmounted components)**: PositioningTab, FundingLiquidityTab, RankingsTab, RiskMetricsTable,
  PortfolioTab, ScreenerTab, FxRatesPanel. Options: (a) delete them after a `repo-scout` confirms no imports;
  (b) mount the ones whose data is still served; (c) leave them.
- **P2-41** stale screener rows (e.g. ZS, last updated 2026-06-26). Options: (a) the nightly rebuild deletes rows
  for symbols no longer in any tracked index; (b) keep them but exclude rows older than N days from the drill,
  snowflake batch and universe; (c) flag them as stale in the UI.
- **P2-42** number keys reach only 9 tabs (Macro 16, Yield 10). Options: (a) accept and show a "1–9" hint in the
  tab bar; (b) add `[` / `]` for previous/next tab on every tabbed page.
- **P2-10** main nav overlaps Markets sub-tabs; **P2-15** no shared KPI-strip/tab-bar/control-bar components.
  Options: (a) skip both this phase; (b) a scoped pass: a shared `KpiStrip` + `ControlBar` used on 2–3 pages
  only, and remove the nav duplicates the owner names; (c) a full pattern-library pass (large).

## Items and packets, in this order

### A. No decision needed (start these while waiting for Step 0 answers)

1. **P2-34 — low-severity audit bundle.** Confirm each finding first; a finding that doesn't reproduce is
   rejected with evidence. One packet per group, each with its own tests (known values):
   - **A1 Options/risk math (sonnet, math):** IV30 interpolated in total variance (σ²·t), not vol; risk Calmar from
     the arithmetic CAGR, not log-mean×252; Garman-Klass including the overnight gap (Yang-Zhang or the
     documented GK-with-open term); options Monte Carlo seeded (a `seed` parameter, deterministic tests).
   - **A2 Valuation (sonnet):** DDM grows the forward dividend once, not twice; unknown quote currency → null +
     reason instead of defaulting to USD; CAPM tile shows annualised alpha or "n/a", never daily alpha as annual.
   - **A3 Macro/stability data (sonnet):** foreign real yields use the latest monthly CPI where available (else
     label the annual vintage); banking NPL >5% and >10% get distinct flags; `capitalAdequacy` relabelled
     capital-to-assets; `domesticCreditGrowth` computed as growth (or relabelled as a level); currency-crisis
     reserves change notes valuation effects; credit-pulse funding spread labels the TEDRATE→SOFR−DTB3 splice
     with its date; an ongoing recession's period ends "ongoing", not today's date; remove or fetch the
     never-fetched `TOTCI` fallback; sector-rotation confidence computed (or dropped) instead of always 100%.
   - **A4 Frontend mechanical (haiku):** undefined `--color-*` variables / `text-muted` class in ~20 files →
     the defined theme tokens (`repo-scout` lists them first); Technicals uses `currencySymbol()` instead of `$`;
     short-interest average shows "—" instead of `NaN%`.
   - The unmounted-components part waits for its Step 0 answer.
2. **P3-36 (sonnet):** date data served from the downloaded IMF WEO and Fama-French files by the file's write
   time, the way Phase 63 did for World Bank (`bulk_data_service.worldbank_path`, `pv.file_time`): add
   `imf_path` / `famafrench_path`, stamp the refs in the source waterfall and its consumers. Bundled curated
   JSON (cb_meetings, doing_business, damodaran): stamp with the file's own `retrieved`/as-of date if it has
   one, else note "bundled with the app". One test per path.
3. **P3-37 (haiku):** make local desktop testing safe. `desktop/build-windows.ps1` (and `desktop/README.md`)
   refresh `src-tauri/target/release/binaries/econosift-backend` from `src-tauri/binaries/` before a release
   build, or document deleting it. Verify by building and checking the backend honours `ECONOSIFT_DATA_DIR`
   (no `data/` folder created in the working directory). **Never** start the desktop backend from the repo
   root: its CWD fallback would open the live Docker `./data/axiomfinance.db`.

### B. After the owner's choice (one packet per item unless noted)

4. **P2-41** per decision (backend, sonnet; tests on a temp screener DB via `SCREENER_DB_PATH` +
   `screener_cache.reset_connection()`).
5. **P2-35** per decision (math, sonnet; reuse the backtests' point-in-time membership; known-value test with a
   member that joined/left mid-window).
6. **P2-29** per decision (backend data + frontend label; you wire `types.ts`/page changes).
7. **P2-30** per decision (math, sonnet).
8. **P2-27** per decision (relabel = haiku frontend packet; EDGAR rebuild = sonnet backend packet, no scraping —
   EDGAR full-text/JSON APIs only).
9. **P2-26** per decision (docs/Wiki = haiku; variant = sonnet).
10. **P2-42** per decision (frontend, haiku; extend `lib/useKeyboardShortcuts.ts`; extend
    `tests/e2e/keyboard-shortcuts.spec.ts`).
11. **P2-34 unmounted components** per decision (haiku; delete only what `repo-scout` proves unused).
12. **P2-10 / P2-15** per decision (frontend, sonnet; you edit the pages).

### C. Verification only

13. **DESK-01-V:** if a full local installer build is possible (`desktop/build-windows.ps1`), install it, launch
    it, and confirm `%APPDATA%/AxiomFinance/backend.log` (or `EconoSift/`) is created and receives uvicorn
    startup lines; then uninstall. If not possible this session, say so and leave it open. Do not trigger
    `build-desktop.yml` (it is part of the gated release flow, outward-facing).

### Not in this phase

- On hold (feature ideas): P3-01, P3-02, P3-05, P3-07, P3-08, P3-09, P3-10, P3-11.
- Permanent limits, list only: P3-13 (Linux AppImage), P3-14 (point-in-time fundamentals).

## Lessons from Phase 63 (follow them)

- **Playwright must target Docker**: `cd frontend && PLAYWRIGHT_BASE_URL=http://localhost npx playwright test`.
  Delegate full runs to a sonnet agent; a cold-start timeout right after a restart is rerun once, not a failure.
  Scope locators to a panel by its source-scope root (`[data-prov-scope]`), not `locator("div").last()`.
- **pytest pins its own DB now** (`<tmp>/econosift_pytest.db`): no `DATABASE_URL` override is needed locally or
  in the container. A test that needs tables calls `backend.database.init_db()`. Container gate:
  `MSYS_NO_PATHCONV=1 docker compose exec -T backend python -m pytest -p no:warnings` (the doubled `-q` hides the
  summary line; read the exit code). Locally `fredapi` is missing: two cointegration tests and the FRED-retry/
  vintage tests fail; they pass in the container.
- **Provenance:** stored data is dated by its build/write time (`pv.stamp`, `pv.file_time`); the Navbar's "Data
  as of" is the **oldest** `fetchedAt` on the page, so date a snapshot by its oldest row. Bare lists can't carry
  a map: return objects.
- **Percent formatting (owner decision, P2-20):** fractions go through `fmtPctFromFraction`; `fmtPct` is for
  values already sent in percent. Never write `fmtPct(x * 100)` (a spec fails on it).
- **API changes** to response shapes are acceptable when nothing external consumes them (owner, P2-32), but
  update every consumer and grep both backend and frontend.
- **Caches:** a finished background build must clear the `@cached`/`@async_cached` entries that reported its
  "preparing" state (`cache.clear_all(name)`), or the UI waits an hour.
- **Python edit scripts on Windows:** `encoding="utf-8", newline=""`, keep the file's own line endings; write
  long scripts to the scratchpad and run them (inline heredocs with quotes broke bash). Never `sed` regex
  backslashes.
- **Refresh button (P1-20):** new on-load panels add `useRefreshNonce()` to their effect deps; Calculate/Run
  Analysis effects must not.
- **Don't spend the owner's Gemini quota**: use the fake client in `tests/test_ai_grounding.py`.
- **The Screener universe is a nightly snapshot**: screener metric changes show only after its rebuild; say so.

## Finish

- **Gate** (steps 1–7 of the plan): fresh-context `spec-verifier` (sonnet) on the raw phase diff + verbatim rows
  + the owner's decisions; fix what it confirms, each via a packet with a test. Docker rebuild + recreate;
  container pytest; `tsc`; live checks one ticker at a time; Playwright (delegated); docs (rows → "✅ …
  RESOLVED (Phase 64)", "✅ Recently Fixed" rows with before → after (live) and the test, one CHANGELOG line);
  commit and push `DEV`.
- **Report**: a table `ID | decision | before → after (live) | test | agent/model | commit`, the rejected items
  with evidence, open decisions, new issues, and a one-line cost note (how many packets per model).
- Watch `get_usage`. Near the 5-hour limit: stop dispatching, let running packets finish, review and commit
  what is done, and write a status note under `docs/plans/`.
- Ask the owner before merging `DEV` → `main` (PR only when asked) and before anything outward-facing.
- Remind the owner to run /compact.

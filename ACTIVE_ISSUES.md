# Active Issues — EconoSift

> Rebrand note: older issue descriptions retain the app-data path that was current when those issues were recorded. EconoSift continues to recognize that path for existing installs.

> **Generated:** 2026-06-30 · **Last audit:** 2026-10-01 (data & calculation audit, Phases 45–50 — see [`docs/audit/2026-10-econosift-data-audit.md`](./docs/audit/2026-10-econosift-data-audit.md)) · **Test status:** 892 backend tests passing
> Single source of truth for all known issues, consolidated from QA audits, deferred items, and the issue tracker.

---

## 🔴 P0 — Broken / Critical

*(No active P0 issues — all previously tracked P0 items have been resolved in earlier phases. See ✅ Recently Fixed below.)*

---

## 🟡 P1 — Important / Feature Gaps

| ID | Issue | Source | Details |
|----|-------|--------|---------|
| P1-17 | **Insider aggregate takes 1–2 hours** | Phase 52b | `/api/insider/aggregate` fetches every Form 4 of the last 90 days for ~500 S&P 500 members one SEC request at a time (AAPL alone: 14 filings, ~13 s), so the 🟡 Calculate run far exceeds nginx's 180 s and the user sees a timeout while it keeps running in a worker thread (no longer freezing the server). Options: build it from the SEC's quarterly insider-transaction data sets (one ZIP, like 13F) plus recent daily filings, or run it as a background job with progress. |
| P1-15 | **Central-bank meetings data ends 2026-12-31** | Audit (calendar) | `cb_meetings.json` lists 2026 meetings only (52 rows, no source). Central-bank events disappear from the calendar in January 2027 unless the file is extended or replaced by a sourced feed. |

---

## 🟢 P2 — Polish / UX

| ID | Issue | Source | Details |
|----|-------|--------|---------|
| P2-07 | **Keyboard shortcuts** | `ISSUES.md` | No keyboard nav. Ctrl+K search, number keys for tabs, arrow keys for periods. |
| P2-10 | **Markets sub-tab redundancy** | CLAUDE.md (Phase 19/22) | Main nav items overlap with Markets page sub-tabs (cosmetic). Also tracked in `UX_Reshuffle.md`. |
| P2-15 | **Pattern Library** | CLAUDE.md (Phase 23) | No shared component library for KPI strips, tab bars, control bars. Every page hand-rolls these. |
| P2-16 | **Bar chart Y-axis labels suppressed** | CLAUDE.md (Phase 25) | Recharts auto-suppresses labels for vertical BarChart with 18+ countries. `shortCountryName()` + `width={90}` partial mitigation. |
| P2-18 | **Browser refresh needed after redeploy** | CLAUDE.md (Phase 25) | Stale JS bundles served after `docker compose up -d`. Hard-refresh required. |
| P2-20 | **Percent formatting inconsistency** | `FACT_CHECK.md`, audit | `fmtPct(v * 100)` used in `ValuationKpiPanel` and `ExtendedRiskTable.tsx` (line 13) — fragile double-scaling pattern. Standardize percent formatting. |
| P2-26 | **New 52-week highs/lows differ from a cited count** | Audit L-14 / P2-24 | For 2026-09-29 the app counts 9 highs / 34 lows (S&P 500, session-aligned, intraday highs/lows of prices as traded, trailing 252 sessions); a report cited 4 / 29. The external report's definition (window, universe, tie handling) is unknown, so the gap is unexplained rather than a known bug. |
| P2-27 | **M&A tracker shows parsed news headlines as deals** | Audit (mergers) | "Acquirer/target" are the first two upper-case words of a Finnhub merger-news headline and values are regex-matched; the Source panel says so, but the page still presents them as deals. Needs a real deal source or a relabel to "merger news". |
| P2-28 | **AI summaries are not grounded in app data** | Audit (AI) | No EconoSift data is sent to Gemini; figures come from the model's training knowledge. The UI now says so, but a grounded prompt (send the page's own numbers) would make them usable. |
| P2-29 | **Policy tracker mixes policy rates with proxies** | Audit (policy) | Non-Fed rates for BoE/BoJ/BoC/RBA/SNB are OECD money-market/interbank rates; the Fed is monthly effective FEDFUNDS; the ECB uses the MRO rate while its operative rate is the deposit facility rate. Carry differentials inherit the mix. Labelled in provenance, not in the table. |
| P2-30 | **Sovereign default probability is weakly calibrated** | Audit (sovereign) | Predictors start in 2000 but most default episodes in the bundled training set predate it and are dropped; non-default rows are hand-picked; prob5y assumes a constant hazard. Treat outputs as a ranking, not a probability. |
| P2-31 | **Treemap multi-period returns use the wrong base** | Audit (markets) | For 1W/1M/3M/1Y the base is the first close of a longer download window, so the labelled period is not the real one. |
| P2-32 | **Endpoints without a provenance map** | Phase 49 | Bare-list responses (options expiries/term structure/smile, sector drill/fundamentals, portfolio risk-contribution/Kelly/stress) and the snowflake batch (keyed by ticker) cannot carry the map; their panels fall back to the enclosing section's source or say "Source not annotated". Wrapping them in objects is an API change. |
| P2-33 | **Cached responses from before an upgrade lack provenance** | Phase 49 | Entries cached before Phase 49 carry no map until they expire (≤60 min). Use Admin → "Clear cache & re-warm" after upgrading. |
| P2-34 | **Low-severity audit findings** | Audit C-34…C-40, D-30, D-40 | IV30 interpolated in vol not total variance; risk Calmar uses log-mean×252; Garman-Klass ignores overnight gaps; DDM grows the forward dividend twice; options Monte Carlo unseeded; foreign real yields use a year-old annual CPI; unknown quote currency defaults to USD; undefined `--color-*` CSS variables / `text-muted` class in ~20 files; banking NPL >5% and >10% add the same single flag, `capitalAdequacy` is capital-to-assets and `domesticCreditGrowth` is a level; currency-crisis reserves change includes valuation effects; credit-pulse funding spread splices TEDRATE with SOFR−DTB3; an ongoing recession's period ends "today"; the `TOTCI` fallback in financial conditions is never fetched; Technicals hard-codes `$`; short-interest average can print NaN%; sector-rotation confidence is always 100%; CAPM tile falls back from annualised to daily alpha; several components are not mounted (PositioningTab, FundingLiquidityTab, RankingsTab, RiskMetricsTable, PortfolioTab, ScreenerTab, FxRatesPanel). |
| P2-35 | **Breadth uses today's index members (survivorship)** | Audit C-23 | Breadth and Fear & Greed count today's S&P 500 constituents over the 2-year window; point-in-time membership exists for backtests but is not applied here. |
| P2-36 | **Running pytest inside the backend container wipes the live cache** | Phase 52 | `tests/conftest.py` calls `cache.clear_all()` before every test against whatever `DATABASE_URL` points at — in the container that is the live `./data` DB. Run container tests with `-e DATABASE_URL=sqlite:////tmp/pytest.db` until conftest pins a test DB itself. |
| P2-37 | **13F panel: % float and quarter-on-quarter change are blank** | Phase 52b | Holders now come from the SEC 13F data sets, one quarter at a time. QoQ change needs the previous quarter's data set as well (a second ~100 MB download); % float needs shares outstanding. The newest data set also lags: the Jun–Aug 2026 filings window was not yet published on 2026-10-01, so the panel shows the quarter ending 2026-03-31. |

---

## 🔵 P3 — Future Features / Speculative

| ID | Feature | Source | Rationale |
|----|---------|--------|-----------|
| P3-01 | **Price alerts** | `ISSUES.md` | Set target prices, RSI thresholds, earnings dates — in-app notifications. No notification system exists. |
| P3-02 | **Compare mode on Markets** | `ISSUES.md` | Side-by-side metric comparison (P/E, EV/EBITDA, Beta) for selected tickers. |
| P3-04 | **Portfolio transaction log** | `ISSUES.md` | Add buy/sell dates, cost basis, realized P&L. Currently theoretical allocations only. |
| P3-05 | **Custom screener formulas** | `ISSUES.md` | Let users type `pe < 15 && roe > 0.15` instead of only presets. |
| P3-07 | **EM sovereign risk watch** | CLAUDE.md (Phase 18A) | Extend sovereign risk panel to emerging markets. |
| P3-08 | **Regime overlays on Atlas/Macro** | CLAUDE.md (Phase 18A) | Overlay macro regime quadrant on Atlas map and Macro charts. |
| P3-09 | **OECD SDMX integration** | CLAUDE.md (Phase 24) | API too complex for bulk download; deferred. |
| P3-10 | **Econometric Lab enhancements** | CLAUDE.md (Phase 18A) | Additional regression diagnostics (fixed effects, lag selection). |
| P3-11 | **Taylor Rule calculator revival** | CLAUDE.md (Phase 18A) | Phase 18B stub removed in Phase 19E. If revived, use `fetch_fred_series()` from `macro_expansion_service.py`. |
| ✅ P3-12 | **Reinhart-Rogoff bulk source URL is dead (404)** | Admin bulk data | RESOLVED: the sovereign-default model already ships the R&R training data bundled in `sovereign_default_service.py`, and the downloaded parquet was never read anywhere. Removed the dead `RR_URL` / `_download_reinhart_rogoff` bulk step and its status row — no more 404 on bulk refresh. |
| P3-14 | **Fundamentals are latest-restatement, not point-in-time (permanent free-data limit)** | Phase 42 (C3) | yfinance returns fundamentals *as they stand now*, including restatements — there is no as-reported-then view. Any backtest using P/E, ROE, accruals, Piotroski, Altman, Beneish or DuPont is therefore contaminated by look-ahead: the numbers were not knowable at the simulated decision date. Affected services: `fundamentals.py`, `corporate_health_service.py`, `dupont_service.py`, `dividend_service.py`, `valuation_engine.py`, `dcf_engine.py`, `snowflake_service.py`, `screener_service.py` (fundamental presets). **Not fixable with free data** — point-in-time fundamentals require a paid vendor (Compustat PIT, Sharadar SF1). Mitigation: `backtest_engine.run_backtest` rejects fundamental signals unless `allow_lookahead=True` is passed explicitly, and surfaces a warning when it is. Price-derived signals (momentum, technicals, realized moments, short interest, macro overlays) are unaffected. |
| ✅ P3-15 | **Nasdaq-100 and Dow universes were silently empty** | Phase 44 | RESOLVED: Wikipedia moved both membership tables onto dedicated articles ("List of NASDAQ-100 companies", "List of Dow Jones Industrial Average companies"); the parent pages now carry only history/milestone tables, so `_parse_constituents` found nothing and `get_constituents` returned `[]` without erroring. Only the page titles in `_PAGES` were stale — the parser itself was fine. Dow and NDX point-in-time reconstruction remains unsupported (no parseable change log exists for either) and now degrades with an explicit `complete: false` note. |
| P3-13 | **Linux desktop ships as `.deb` only (no AppImage)** | CI build | Tauri's AppImage bundling fails on GitHub's `ubuntu-latest` runners (`failed to run linuxdeploy`) — linuxdeploy is itself an AppImage needing FUSE, and `APPIMAGE_EXTRACT_AND_RUN=1` / `NO_STRIP=true` didn't clear it (likely a WebKitGTK-4.1 / Ubuntu-24.04 plugin incompatibility). The `.deb` builds reliably, so `appimage` was dropped from `tauri.conf.json` targets. Revisit if a universal AppImage is needed (e.g. build in an older container or via `tauri-action`). |

---

## 🖥️ Desktop (Tauri / Windows) — v1.0.0

| ID | Issue | Severity | Details |
|----|-------|----------|---------|
| DESK-01-V | **Verify the DESK-01 fix in a real desktop build** | P3 | The `run.py` frozen-mode log redirect (see ✅ DESK-01 below) is verified by code-read and a simulated-frozen run only — Phase 37 shipped no desktop build. On the next `build-desktop.yml` run (the gated main→PRODUCTION release flow, not triggered automatically), launch the installed app and confirm `%APPDATA%/AxiomFinance/backend.log` is created and receives uvicorn startup lines. |
| DESK-02 | **Backend still orphaned if the app is force-killed** | P3 | Force-killing `econosift.exe` (`Stop-Process -Force` / Task Manager "End task") leaves the child `econosift-backend.exe` running on port 8000 — dropping a `CommandChild` handle doesn't send a kill signal, only a normal exit does. Normal window close is now fixed (see ✅ Recently Fixed below): `lib.rs` kills the child on `RunEvent::ExitRequested`. The force-kill case is unfixable from inside the app itself; it needs an OS-level parent-death mechanism (Windows Job Object with `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`) to have the OS kill the child automatically when the parent dies, regardless of how. Lower priority — force-kill is a rare user action, not the normal quit path. |

---

## ✅ Recently Fixed (Desktop)

| ID | Issue | Details |
|----|-------|---------|
| ✅ DESK-01 | **`backend.log` not written under `console=False`** | Root cause was not a broken stdout but a piped one: the Tauri shell spawns the backend with stdout/stderr **piped** (and the pipe receiver discarded in `lib.rs`), so `run.py`'s `sys.stdout is None` check never fired in the frozen app and the redirect to `%APPDATA%/AxiomFinance/backend.log` was skipped. `run.py` now redirects both streams whenever `sys.frozen` is set (keeping the `None` fallback for non-frozen edge cases). Logic verified with a simulated-frozen run; full end-to-end verification needs the next desktop build. |
| ✅ DESK-03 | **API keys saved in Admin never took effect, even after restart** | The Admin "save API keys" endpoint (`routers/admin.py`) wrote to a project-root-relative `.env` path (`os.path.dirname(__file__)/../../../.env`), which under the frozen desktop exe resolves inside the PyInstaller bundle, not `%APPDATA%/AxiomFinance`. Meanwhile `config.py`'s `load_dotenv()` searched the CWD, an unrelated and unpredictable directory in the frozen app. The two never pointed at the same file, so keys were written to disk (as the user could see) but never read back, even on restart. Fixed: both now target `config.DATA_DIR/.env` — the same app-data directory the DB and settings already use. |
| ✅ DESK-04 | **`econosift-backend.exe` kept running after closing `econosift.exe` normally** | `lib.rs` spawned the backend child process but discarded the handle (`let (_rx, _child) = ...`) — dropping a `CommandChild` doesn't terminate the OS process it represents, so it kept running after the window closed. Fixed: the child is now stored in managed app state and killed on `RunEvent::ExitRequested`. Force-kill of the parent still orphans the backend (see DESK-02). |
| ✅ DESK-05 | **Bulk data downloads (Admin panel) silently failed on desktop** | `bulk_data_service.py` hardcoded its storage dir to `/app/data/bulk` (the Docker volume mount path), which on Windows resolves to `C:\app\data\bulk` — typically not writable without admin rights, causing every download to fail. Also had no guard against a second "Refresh" click starting a concurrent run (interleaved writes could corrupt `_status.json`), and only saved status once at the very end, so a crash mid-run silently discarded all progress with no visible error. Fixed: falls back to `config.DATA_DIR/bulk` when `/app/data` isn't present (preserves existing Docker behavior via `/app/data`), added a lock to make concurrent triggers a no-op, and status is now always saved in `finally`. The Admin page also now polls status while a refresh is running instead of checking once. |

---

## ✅ Recently Fixed (App bugs)

| ID | Issue | Details |
|----|-------|---------|
| ✅ P1-14 | **Cold-start timeouts** | Phase 51: per-key cache single-flight (was per function), SQLite cache I/O and BIS/probit/curve-fit work moved off the event loop, FRED limiter holds a real 110/min window with one retry on rate limit. Cold 6-concurrent burst 940 s → 247 s, worst endpoint 128 s, no 504s, no loop stalls. Remaining: ~110 s floor from FRED's 120/min quota on a fully cold start — addressed next by stale-while-revalidate and the setup wizard's background warm (`docs/plans/2026-10-setup-wizard.md`). |
| ✅ P1-16 | **Cache writes dropped while jobs held SQLite's write lock** | Phase 52c: `refresh_daily_quotes` kept its write transaction open across ~50 Yahoo round trips (~14 min per run), so every cache write and Admin "Clear cache" failed with `database is locked`; it now fetches first and writes in one short transaction. `refresh_daily_prices` commits per ticker instead of one 25k-row transaction (run 53 s → 28 s). Live: a cache clear during the startup jobs now succeeds first time (failed for 60+ s before). |
| ✅ P1-13 | **SEC EDGAR identity / insider and 13F data** | Phase 52b: identity set in the owner's `.env` (not committed). That exposed two broken features. Form 4: the parser used the pre-5.x edgartools table API, so every filing was skipped and every ticker showed 0 transactions (AAPL now lists its open-market sales, e.g. 2,399 sh at $340.06 on 2026-09-22); edgartools pinned to 5.x. 13F: holders were read from the ticker's own filings, which never contain 13F-HRs; now built from the SEC's quarterly Form 13F data sets (AAPL: 6,010 filers, BlackRock 1.14 bn shares, quarter ending 2026-03-31); VALUE is in dollars (the old ×1000 was wrong) and filings still reporting thousands are detected and rescaled. The insider aggregate ran on the event loop and now runs in a worker thread. |
| ✅ P2-24 | **Fear & Greed sub-scores need date-aligned validation** | Phases 46/49: breadth and every signal are aligned to the last completed session, each signal carries its own `asOf`/`stale`, highs/lows use intraday extremes of prices as traded, the headline equals the last history point, put/call is ranked against its own recorded history (it was pinned at 0), and right-click → Source shows each signal's series and date. The residual highs/lows count gap is tracked as P2-26. |
| ✅ P2-25 | **Macro current-year GDP/CPI mislabeled as annual** | Phase 47: annual values use complete years only (the running year is never averaged), completed-year GDP uses `A191RL1A225NBEA`, q/q SAAR is labelled as such, IMF projections carry an `estimate` flag, and the macro regime's "current" reading is the latest period with both GDP and CPI. Fix to the annualisation helper itself in `28d63bb`. |
| ✅ P2-05 | **No React error boundaries** | Added `components/ErrorBoundary.tsx` (class boundary with "Try again" reset) wrapping `{children}` inside `<main>` in `app/layout.tsx` — a page crash now shows a retry card while Navbar/Footer/MobileNav stay alive — plus `app/error.tsx` as the App Router segment boundary. Pure client-runtime, unaffected by the static export. |
| ✅ P2-04 | **Mobile bottom nav cramped** | `MobileNav.tsx` bottom bar reduced from 7 to 6 items: Learning + Theme toggles moved into the "More" drawer as a controls row; tap targets widened (`min-w 3rem→3.5rem`, labels 10px→11px). |
| ✅ P2-06 | **Data freshness badges** | `DataFreshnessBadge` wired up starting with the Screener (replacing the hand-rolled "as of" span). Dashboard skipped deliberately — the page composes child components and has no `asOf` in scope. Further rollout is incremental as pages get touched. |
| ✅ P2-11 | **Active tab styling inconsistency** | Shared `TabButton` (underline) and `ToggleChip` (soft outline) added to `components/ui.tsx`; swapped into MacroTabShell, ScenarioTab, PriceChart and the options/portfolio/policy/yield/risk/stability tab bars (~9 hand-rolled copies removed). Research's main tab bar intentionally left (deliberate design deviation). Bonus: yield/stability tab bars used nonexistent Tailwind tokens (`text-muted`, `hover:text-foreground`) — fixed by the swap. |
| ✅ P2-12 | **Options ~15min delay badge restyle** | Restyled to the canonical badge look (`rounded-md text-xs font-semibold bg-warning/20 text-warning`), matching `SignalBadge`. |
| ✅ P2-13 | **Compute-tier indicator consistency** | Unified to `<emoji> <phrase>` prefix format (e.g. `🔴 Monte Carlo`); research tabs already conformed. |
| ✅ P2-21 | **Raw ISO timestamps shown to users** | The one genuine case was Screener's `asOf` (a real datetime from `screener_cache.last_refresh()`), now rendered via `DataFreshnessBadge`. Audit of all other raw `asOf` renders confirmed they are date-only strings (`YYYY-MM-DD`), which read fine raw. |
| ✅ P3-06 | **`datetime.utcnow()` deprecation** | All backend `datetime.utcnow()` call sites migrated. Sites persisting to or comparing against naive DB datetimes (`cache.py`, `db_models.py` column defaults, `admin.py`, `ai.py`) use a naive-UTC helper (`datetime.now(timezone.utc).replace(tzinfo=None)`) to avoid aware-vs-naive `TypeError` against existing rows; isolated sites use aware `datetime.now(timezone.utc)`. Tests updated to match. |
| ✅ P2-22 | **COT/Positioning tab data unreliable** | Root cause: CFTC's `deafut.txt` returns HTTP 200 but has **no header row**, so pandas used the first data row as column names; the old success check (`not df.empty`) accepted the garbage, parsing silently yielded nothing, and the fallback URLs were never tried (one was 404-dead). Fixed in `cot_service.py`: CFTC's Socrata JSON API (`publicreporting.cftc.gov/resource/6dca-aqww.json`, exact `cftc_contract_market_code` match — S&P E-mini is `13874A`; the old `13874+` prefix also matched E-mini S&P *sector* futures) is now the primary source with parse-validation before any source is accepted, year-aware `deacot{YYYY}.zip` legacy fallbacks, and `skip_if` on `@async_cached` so failure envelopes are never cached for 60 min. Also fixed a latent `itertuples()` underscore-rename crash in history building. `PositioningTab.tsx` now shows the unavailable card on empty `contracts` and a stale-data warning past 14 days. Covered by `backend/tests/test_cot_service.py` (8 tests) and live-verified (all 6 contracts, 104-week history). |
| ✅ P2-19 | **`@async_cached` persistent cache trap** | Verified fixed in commit `6b9e2a5`: `skip_if` (default = empty-container check) guards writes to **both** tiers in both `@cached` and `@async_cached`; the SQLite tier now enforces TTL on read; `cache.clear_all()` flushes both tiers and is wired at `POST /api/admin/cache/clear`. Covered by `backend/tests/test_cache.py`. Residual gap (non-empty *error envelopes* bypassing the default check) closed for COT in the P2-22 fix via a custom `skip_if` — other services returning `{"error": ...}` envelopes should adopt the same pattern when touched. |
| ✅ BUG-A1 | **Atlas / cache warming: all 6 timeline endpoints 500 with `{"detail":"'id'"}`** | `atlas_service._country_universe()` returned country dicts without the ISO-numeric `id` field after commit `cf2d1a0` switched it to a static JSON that only stores `{iso3, name, regions}`. `get_timeline()` reads `country["id"]` → `KeyError: 'id'` → HTTP 500, breaking GDP growth, inflation, unemployment, debt/GDP, current account and GDP-per-capita warming (and the Atlas map / Macro panels downstream). Fixed: re-derive the numeric `id` via `pycountry` (matching the pre-regression behaviour) when loading the static JSON and in the wbgapi fallback. |
| ✅ BUG-A2 | **Dividend yield shown ~100× too high (MSFT "98%")** | `dividend_service.py` multiplied yfinance's `dividendYield` by 100, but current yfinance returns it already in percent units (0.98 = 0.98%) — as `metrics.compute_ratios`, the frontend RatiosTab and the dividends page all assume. Fixed: removed the `× 100`. Also corrected the screener `high_dividend` preset threshold (`0.03` → `3.0`) which assumed the old fraction convention. |
| ✅ BUG-A3 | **Stock Screener flickered / reloaded in an infinite loop** | `activePresets` was rebuilt as a `new Set(...)` on every render and used in the data-fetch `useEffect` dependency array, so the effect re-ran every render → fetch → setState → re-render → fetch… Fixed: memoised the Set on `urlState.presets`. |
| ✅ BUG-A4 | **Clicking a country sent the user to the Dashboard** | The site is a static export; `/country/[iso2]` only pre-generated 20 hardcoded countries, so any other code 404s and the static server falls back to `index.html` → root redirect to `/dashboard`. Fixed: `generateStaticParams` now emits the full ISO 3166-1 alpha-2 set (`lib/iso2Codes.ts`). |
| ✅ BUG-A5 | **Admin: IMF WEO showed no size; bulk-data failures showed only "⚠ Failed"** | IMF WEO is stored as per-indicator `imf_*.parquet` files, but the size lookup pointed at a non-existent single `imf_weo.parquet`. Fixed to sum the directory (`_dir_size(DATA_DIR, "imf_")`). The bulk-data table now prints the actual error message instead of hiding it in a hover tooltip (surfaces the R&R 404 — see P3-12). |

---

## ✅ Recently Fixed

These items are verified as fixed in shipped phases. Listed here for reference to avoid re-reporting.

| ID | Issue | Fixed In |
|----|-------|----------|
| ✅ | Color system: beige → true white, reddish-black → greyish-black | Phase 22 |
| ✅ | Fear & Greed gauge redesign with tick marks | Phase 22 |
| ✅ | Admin nav link added | Phase 23 |
| ✅ | Screener remembers universe choice | Phase 23 |
| ✅ | Sticky sub-tab bars on all pages | Phase 23 |
| ✅ | Mobile nav collapse to 5 primary | Phase 23 |
| ✅ | Yield + Policy merge → "Rates & Policy" | Phase 23 |
| ✅ | Country search in Econometric Lab (200 countries) | Phase 23 |
| ✅ | Live FRED risk-free rates (13 countries) | Phase 23 |
| ✅ | Live Damodaran ERP (ctryprem.xlsx auto-download) | Phase 23 |
| ✅ | DCF discount rate selector with regional rates | Phase 23 |
| ✅ | Research Hub ticker SearchBar | Phase 23 |
| ✅ | Dark-mode Technicals Y-axis fix | Phase 19 |
| ✅ | Dividend yield double-scaling fix | Phase 19 |
| ✅ | Macro: Funding, Commodities, FX, PPP, Financial Conditions, NFP, ISLMPC, Quantity Theory, Central Banks, EPU, RegimeClock all fixed | Phase 20 |
| ✅ | Nav overflow scroll (desktop) | Phase 19 |
| ✅ | Mobile nav + Treemap/Calendar/Sectors/Theme | Phase 19 |
| ✅ | Treemap spinner + text contrast | Phase 19 |
| ✅ | Dashboard null-safety | Phase 19 |
| ✅ | Options IV clamp ≤500% | Phase 19 |
| ✅ | Portfolio "AAPL" → "Ticker" placeholder | Phase 19 |
| ✅ | yfinance 401 retry (2 retries) | Phase 19 |
| ✅ | Docker DNS (8.8.8.8/8.8.4.4) | Phase 19 |
| ✅ | Nginx healthcheck + proxy_next_upstream | Phase 24 |
| ✅ | BIS CPI matches World Bank exactly (US 2023: 4.12%) | Phase 24 |
| ✅ | Admin API keys management | Phase 24 |
| ✅ | Scheduler cron expression fixed (P0-01) | Pre-Phase 36 (verified 2026-06-30) |
| ✅ | Backend 502 on restart — healthcheck + nginx retry (P0-02) | Phase 24 |
| ✅ | Wiki returns terms correctly (P0-03) | Pre-Phase 36 (verified 2026-06-30) |
| ✅ | Calendar FRED noise removed — dropped in Phase 19 (P0-04) | Phase 19 |
| ✅ | yfinance missing keys — Fix 1–6 injected in `get_info()` (P0-06) | Pre-Phase 36 (verified 2026-06-30) |
| ✅ | Options IV30 backsolve via `iv_backsolve()` Brent solver (P1-01) | Pre-Phase 36 (verified 2026-06-30) |
| ✅ | Fama-French CSV parser no longer truncates (P1-10) | Pre-Phase 36 (verified 2026-06-30) |
| ✅ | Beta computed & injected in `get_info()` KPI fix (P1-15) | Pre-Phase 36 (verified 2026-06-30) |
| ✅ | **P1-03**: Atlas map — added error state, key prop, improved geojson fetch | Phase 36 |
| ✅ | **P1-04**: Yahoo rate-limit batching — BATCH_SIZE 5→10, progressive backoff | Phase 36 |
| ✅ | **P1-05**: Multi-country macro — World Bank fallback for non-US inflation/employment | Phase 36 |
| ✅ | **P1-06**: CountrySelector typeahead — timeoutRef cleared on pick to prevent stale dropdown | Phase 36 |
| ✅ | **P1-07**: Dashboard React error #425 — defensive `String()` wrapping in FearGreedGauge/BreadthBar | Phase 36 |
| ✅ | **P1-08**: 30Y breakeven — DGS30−DFII30 fallback when T30YIE FRED series empty | Phase 36 |
| ✅ | **P1-09**: Scenario Lab — dedicated `/scenario` page created + nav entries | Phase 36 |
| ✅ | **P1-10**: Econometric Lab — error handling added to runRegression(), TaylorRuleWidget wrapped | Phase 36 |
| ✅ | **P1-11**: BIS Credit-to-GDP gaps — wired into `BIS_DATASETS` bulk refresh | Phase 36 |
| ✅ | **P1-12**: DCF share count — marketCap/price cross-validation heuristic added | Phase 36 |
| ✅ | **P1-13**: Piotroski F-Score — prior-year data via `_prior_val()` with quarterly fallback (AAPL: 8/9, was 4/9) | Phase 36 |
| ✅ | **P1-14**: Beneish M-Score — same fix as P1-13 (AAPL: −2.00, 7/8 components, was null) | Phase 36 |
| ✅ | **P2-17**: BIS Credit-to-GDP gaps — wired into `BIS_DATASETS` bulk refresh (was P1-11) | Phase 36 |
| ✅ | **P2-01**: PageSkeleton rollout — no bare `animate-pulse` found in Treemap or Risk sub-components | P2 audit 2026-06-30 |
| ✅ | **P2-02**: Sub-tab scroll arrows — `ScrollableTabBar` with chevron arrows in `ui.tsx:57-103`, used on Macro + Markets | P2 audit 2026-06-30 |
| ✅ | **P2-03**: Taylor Rule frontend wiring — backend `/macro/taylor-rule` + `api.macroTaylorRule()` + `TaylorRuleWidget.tsx` all connected | P2 audit 2026-06-30 |
| ✅ | **P2-08**: Export PDF button — `ExportPdfButton` component in `ui.tsx:107-123`, used on Markets page | P2 audit 2026-06-30 |
| ✅ | **P2-09**: Fear & Greed per-signal explanations — `FearGreedGauge.tsx:67-80` renders score + `label_text` per signal | P2 audit 2026-06-30 |
| ✅ | **P2-14**: Calendar FRED noise — feed dropped in Phase 19, confirmed in `calendar_service.py:85-89` | Phase 19 |
| ✅ | **P2-23**: Dark mode chart hardcoded colors — no `stroke="#333"` found; all charts use `chartPalette()` | P2 audit 2026-06-30 |

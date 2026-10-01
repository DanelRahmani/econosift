# Changelog — EconoSift

## Phase 51+ — Responsiveness and first-run setup (2026-10)

- **Phase 51 — cold-start latency (P1-14).** Measured on a cold backend with the startup jobs running and 6 concurrent requests, like a browser: the 45-endpoint burst took 940 s (one endpoint never answered in 10 min); now 247 s, worst endpoint 128 s (under nginx's 180 s), zero event-loop stalls. Causes fixed: the cache's single-flight lock was per function, so every cold FRED / World Bank / yfinance fetch app-wide queued behind one another (now per key); SQLite cache reads/writes ran on the event loop and froze the server for up to 229 s while warm-up jobs held the write lock; BIS bulk downloads/parses and the recession probit, curve-noise and oil-shock fits ran on the loop; `/valuation/full` fetched in series. FRED's limiter only spaced requests (peaked at 159/min against FRED's 120/min cap, 28 failures cached as silent gaps): it now holds a 110/minute window and retries a rate-limited series once. Remaining floor: ~200 FRED calls at 120/min on a truly cold start.

## Phase 45–50 — Data & calculation audit, and right-click → Source (2026-10-01)

Full audit of how data is pulled and computed, with the findings fixed and recorded in [`docs/audit/2026-10-econosift-data-audit.md`](./docs/audit/2026-10-econosift-data-audit.md); open and low-severity items are in `ACTIVE_ISSUES.md`.

- **Phase 45 — missing is not zero, and dates are real.** Failure envelopes are no longer cached; country charts no longer draw missing values as zero bars; payloads are dated by their data (World Bank comparisons were stamped "today" while showing 2021–2024 data). Archived World Bank codes replaced (CO₂, time-to-start-a-business), bank Z-score read from the database that holds it, poverty lines relabelled to the 2021-PPP $3.00/$4.20/$8.30 lines, Atlas year keys restored after a cache round-trip.
- **Phase 46 — Fear & Greed and breadth (P2-24).** Session-aligned to the last completed session, intraday 52-week highs/lows of prices as traded, McClellan warm-up, headline equals its history, per-signal `asOf`/`stale`. Put/call (pinned at 0) is ranked against its own recorded history; a weekday job records it and IV30.
- **Phase 47 — macro pipeline (P2-25).** Complete years only in every annual figure; trade balance no longer shown as current account % GDP; index levels no longer shown as growth; FX heatmap no longer double-inverted (USD/JPY ≈ 0.006) with CNY/CHF/SEK mislabels fixed; IMF ISO3 truncation (China read Switzerland's data) fixed; dead FRED/World Bank/BIS series replaced or reported unavailable (commodities, PPP, term premium, Japan CPI, euro-area HICP, LEI/ISM, cross-border claims, real effective exchange rates); macro regime "current" reading fixed for the US and restored for Japan and the euro area; 10-year yields for country risk-free rates with fallbacks flagged.
- **Phase 48 — calculations.** Dividend payout/TTM/DDM, snowflake coverage units, risk-parity CAGR, carry backtest look-ahead, IV Rank over real history, Black-Scholes dividend yield, Kelly, Black-Litterman, Sortino, portfolio return aggregation, Piotroski/Beneish/Ohlson/Altman, valuation growth input and ADR currency conversion — each with a known-value test.
- **Phase 49 — provenance backend.** Every data endpoint returns a `provenance` map (provider, series id, units, frequency, observation date, true fetch time from the cache, flags; formula and inputs for computed values). Also fixed: an annualisation bug that sent monthly FRED/ECB/DB.nomics/Frankfurter series to annual fallbacks and emptied the FX indicator (`28d63bb`).
- **Phase 50 — right-click → Source.** Right-click any value for its source panel (or "Copy value"); the Atlas map names country, year and indicator; desktop opens https source links in the browser. Wiring every value surfaced more wrong numbers, fixed: charts paired series by array position instead of date, FX–commodity lead/lag compared the same days at every lag, analyst upside printed a fraction as a percent, the quantity-theory chart never drew, COT net commercial was hard-coded to 0, plus mislabels (Michigan "5Y" is 1-year, industrial production is an index, option "VaR" is a payoff percentile, the DDM rate was not 9.5%). AI summaries now state that no app data is sent to the model.
- **Primary-source spot checks** (FRED, World Bank, IMF, BIS, retrieved 2026-10-01) match for GDP, current account, FX, Atlas values, government debt and cross-border claims; they caught two more errors, fixed: year-over-year changes used a row-count lag that spanned 13 months across FRED's missing October-2025 CPI (3.71% shown vs 3.35%), and the debt series switched definitions mid-line.

## 2026-09-30 — Apple Silicon desktop release builds

- Added a native Apple Silicon macOS DMG build to the desktop release workflow and attach it alongside the Windows and Linux installers on GitHub Releases.
- Updated desktop release documentation and linked the repository landing page directly to published installers.
- The macOS DMG is unsigned and not notarized, so it may require Gatekeeper approval on first launch.

## 2026-09-29 — EconoSift rebrand

- Updated the product name, interface identity, logos, app theme, documentation, desktop/package identifiers, and release workflow artifact labels to EconoSift.
- Kept API route paths, request parameters, and response keys unchanged, including the legacy `axiomFairValue` and `axiomIndex` keys.
- Added browser-storage compatibility migration and preserved existing desktop app-data directories and the `axiomfinance.db` filename for upgrades.
- Historical entries below describe the app and artifacts as they existed before the rebrand.

> Concise build history. See commits for details.
> All phases shipped via Docker Compose on a self-hosted Windows machine.

---

## Phase 44 — Empty index universes fixed, ESLint wired into CI (2026-08-22)

- **🐛 Nasdaq-100 and Dow universes were silently empty.** Wikipedia moved both membership tables onto dedicated "List of ..." articles; the parent pages now carry only history and milestone tables, so the parser found nothing and `get_constituents` returned `[]` without raising — the screener and backtester universes for `ndx`/`dow` were blank rather than broken-looking. Only the page titles were stale. Now: sp500 503, ndx 102, dow 30, all verified end-to-end through the backtester.
- Point-in-time reconstruction stays S&P-500-only and says so: the Dow's historical article is ~64 wide period tables with no date column and the Nasdaq-100 has no change article, so `_CHANGES_PAGES` lists only sp500 and the others degrade with an explicit `complete: false` note rather than being listed-but-broken.
- **ESLint wired into CI.** It had never been initialised, so `next lint` prompted interactively and would hang a runner. Now committed with `eslint@8` and `eslint-config-next@14` pinned to match Next 14 (9.x and 16.x both break `next lint` on this version). All 13 pre-existing errors fixed — 11 unescaped JSX entities plus two `eslint-disable` comments referencing a rule the config never loaded, resolved by registering the plugin rather than deleting the suppressions.

## Phase 42-43 — Point-in-time data, out-of-sample scoring, and a backtester (2026-08-22)

- **Survivorship bias removed** (`constituents.members_as_of`): reconstructs index membership on any past date by walking Wikipedia's change log backwards. The log moved to its own article since it was last looked at, and coverage is only reliable from ~2010 (20-27 changes/yr, vs under 2/yr before 2005) — earlier dates return `complete: false` rather than a confidently wrong roster. Verified against known events: TSLA absent before Dec 2020, and ATVI/FISV/DISCA/XLNX correctly restored to the 2018 roster despite being gone today.
- **FRED vintages** (`vintage` / `first_release` on `fetch_fred_series`): 45 of 46 quarterly GDP observations differ between first release and latest, so anything scored on revised data flatters itself.
- **🐛 Recession model scored out of sample:** the probit was fitted over the whole history then applied back across it. `_walk_forward_probit` refits monthly on data available at the time. The paths diverge sharply — in late 2000 the in-sample model reads 24% where the real-time model reads 97%. Both are charted. (What was *not* wrong: T10Y3M is never revised and the service already used SAHMREALTIME.)
- **P3-14 logged:** fundamentals are latest-restatement on yfinance and cannot be honestly backtested on free data. The backtester refuses fundamental signals unless `allow_lookahead=True`.
- **Vectorized backtester** (`backtest_engine.py`, `POST /api/research/backtest`, Research → Backtester, 🔴 tier): quantile sorts with turnover-based costs, gross and net side by side, optional point-in-time universe. Two alignment sentinels pin that positions formed at *t* earn the return from *t* to *t+1* — writing them caught a double-lag in the first draft that would have understated every signal. Six price-derived signals wired up. First result is unflattering and honest: S&P 500 momentum nets **-2.6% CAGR** over 108 months with the survivorship correction on.
- **Composite risk dial** (`composite_signal_service.py`, `/api/macro/risk-dial`, Macro → Financial Conditions): blends EBP, ANFCI, SLOOS, HY OAS, term spread and SOFR-IORB into one exposure multiplier, shrunk 50% toward zero (Campbell-Thompson), clipped to [0.4×, 1.2×] — a dial, never a binary call. **Ships with its own walk-forward self-test published beside it:** over 403 months (1993-2026) it returns Sharpe 0.82 vs 0.74 buy-and-hold with max drawdown -40.6% vs -50.8%, net of costs, at ~1.0× average exposure. A losing result would be displayed the same way.
- **Exposure & ops:** loopback binding, explicit CORS allowlist, FRED/Finnhub outbound throttling, and a live error feed on Admin (Phase 41 items shipped alongside).

## Phase 40-41 — Test safety net, two maths fixes, and exposure hardening (2026-08-22)

- **CI now runs the tests** (`.github/workflows/ci.yml`): pytest + `tsc --noEmit` on every push to `DEV`/`main` and every PR into `main`, plus a Playwright job that boots the docker stack. Nothing previously gated the `DEV` → `main` PR. The backend suite was verified genuinely offline (no API keys, throwaway `AXIOM_DATA_DIR`), so no network markers were needed. `next lint` is deliberately excluded — ESLint has never been initialised here and would hang a runner.
- **Options engine tested** (32 tests): put-call parity, the textbook 10.4506 reference, Greeks against finite differences, IV round-trips, CRR converging to Black-Scholes for American calls and exceeding it for deep-ITM puts. No defects found.
- **Portfolio engine tested** (35 tests): a helper builds prices whose log returns have *exactly* a specified mean and covariance, making the checks algebraic — Kelly is exactly μ/σ², risk contributions sum exactly to portfolio vol (Euler), Black-Litterman equilibrium matches δΣw, and a view equal to equilibrium leaves the posterior unchanged. No defects found.
- **🐛 Hurst exponent fixed:** R/S ran on price *levels* instead of increments, returning ~1.0 for random-walk, trending and mean-reverting series alike — the Risk page reported "Trending" for essentially every ticker. Now differences internally with the Anis-Lloyd small-sample correction; measured unbiased (mean 0.502–0.510), and the existing 0.4/0.6 bands turn out to be its 95% null interval, so they were kept. AAPL/KO/TLT now read 0.50–0.56.
- **🐛 RSI fallback fixed:** it replaced a zero average loss with NaN, blanking RSI exactly when it should read 100 (an unbroken advance).
- **Playwright smoke suite** (15 specs): 8 pages + the 5 Phase 39 tabs. Tabs assert a *coherent state* — data or an explicit unavailable message — because CI runs keyless and legitimately renders the latter; a blank panel is the regression being caught.
- **Exposure hardened:** nginx binds `127.0.0.1:80`; CORS moved from `allow_origins=["*"]` to an explicit allowlist (tauri origins kept for the desktop build), verified by a rejected `evil.com` preflight against `PUT /api/admin/config`. New `ratelimit.py` throttles FRED (120/min) and Finnhub (60/min) at their call sites.
- **Live-ops error feed:** `errorlog.py` keeps the last 200 WARNING+ records in memory, exposed at `/api/admin/errors` and surfaced as "Recent Failures" on the Admin page — services degrade quietly by design, which previously made a broken source indistinguishable from an empty one.

## Phase 39 — High-evidence credit, oil, and rates indicators (2026-08-22)

Adds the indicators with the strongest out-of-sample evidence in the literature that the platform did not already carry, each with a documented causal channel rather than a bare correlation.

- **Credit & funding conditions** (`credit_conditions_service.py`, `/api/macro/credit-conditions`, Macro → Financial & Funding Conditions): SOFR−IORB reserve scarcity (IOER spliced pre-2021-07-29), SLOOS net C&I tightening (`DRTSCILM` — Lown & Morgan 2006), the Gilchrist-Zakrajšek **Excess Bond Premium** with its GZ spread and recession probability (direct Fed CSV, not on FRED), and NFCI/ANFCI. 12 tests incl. source-failure and schema-drift paths.
- **Oil shock decomposition** (`oil_shock_service.py`, `/api/macro/oil-shocks`, Macro → Commodities): splits real WTI monthly returns into a global-demand component (ΔIGREA + real copper) and an oil-specific residual, so a price move is interpretable per Kilian (2009) instead of directionless. Labelled throughout as a reduced-form proxy, **not** the structural VAR. 10 tests on synthetic fixtures with a known generating beta.
- **Treasury curve-fit noise** (`treasury_noise_service.py`, `/api/yield/noise`, new Yield → Curve Noise tab): daily Nelson-Siegel RMSE across the CMT tenors, an HPW-style (2013) arbitrage-capital gauge. Verified against history and **documented as limited**: it reaches ~20bps in 2008 vs ~7bps in calm 2017 but stays ~10bps in March 2020, because CMT is already an official smoothed curve and cannot show on-the-run dislocation. Shipped with that caveat surfaced in the UI. 9 tests.
- **5y5y forward breakeven** (`T5YIFR`) added to `yield_curve_service` as a separate field (a forward, not a spot tenor) and charted on Yield → Real & Breakeven.
- **Bug fix:** `credit_market.py` requested `BAMLC0A4CBBBOAS`, which does not exist on FRED — the BBB spread KPI had been silently `null`. Corrected to `BAMLC0A4CBBB`.
- Credit conditions mounted as a sibling of `FinancialConditions` in `MacroTabShell` rather than a child, so the two panels fetch independently and neither blanks the other while loading.

## Phase 38b — Five analyst features: net liquidity, recession model, earnings quality, event study, factor regime (2026-07-03)

- **F1 Fed Plumbing & Net Liquidity** (`liquidity_service.py`, `/api/macro/net-liquidity`, Funding & Liquidity tab): net liquidity = WALCL − RRP − TGA on the weekly H.4.1 Wednesday grid + bank reserves + SPX overlay. FRED unit scales verified against live magnitudes (WALCL/WTREGEN/WRESBAL millions, RRPONTSYD billions — the live curl gate caught a wrong initial assumption). 5-KPI row, dual-axis SPX chart, components chart, 26-week WoW table. 5 pure-compute tests.
- **F5 Recession Probability** (`recession_service.py`, `/api/macro/recession-probability`, Leading Indicators tab): NY-Fed-style 12-month-ahead probit on the 10y–3m spread fit by scipy MLE (no statsmodels dep), plus Sahm rule, FRED smoothed probability cross-check, months-inverted counter, NBER episode shading. 9 tests.
- **F3 Earnings Quality & Accruals** (`corporate_health_service.py` additions, `/api/corporate/earnings-quality?universe=`, Corporate page): Sloan balance-sheet accruals, CFO/NI cash conversion, NOA growth, composite 0–100 quality score, worst-decile flagging over dow/ndx/sp500 — completes the forensic triad (Altman/Piotroski/Beneish) with earnings persistence. 7 tests.
- **F2 Event Study Lab** (`event_study_service.py`, `POST /api/research/event-study`, Research tab #10, 🟡 tier): market-model CAR/AAR around earnings dates (yfinance) or FOMC decisions (bundled public Fed calendar 2015–2025), OLS estimation window, mean/median CAR, hit rate, t-stat, day-relative CAR path chart + per-event table. 4 tests on a zero-noise synthetic fixture.
- **F4 Factor Regime Monitor** (`fama_french.py` additions, `/api/research/factor-regime`, Research tab #11): monthly F-F 5-factor + momentum via pandas-datareader, trailing 1/3/12-mo compounded returns, factor-momentum ranks, regime label (Risk-On/Off × style leader), cumulative growth-of-$1 chart. 8 tests.
- Backend work parallelised across four subagents on disjoint files; orchestrator wired shared files (`api.ts`, `types.ts`, `macro.py`, `research.py`, page registrations) and ran the Docker/pytest/tsc/curl gate.

## Phase 38a — Event-loop hygiene: threadpool offloading + cache single-flight (2026-07-02)

- **Event-loop blocking fixed:** sync yfinance/pandas/SQLite work in `async def` routes now runs via `asyncio.to_thread` — `research.py` (all 6 sync quant endpoints), `sector.py` (all 4), `portfolio.py` (11 heavy `port.*` computations incl. frontier/Monte Carlo/Black-Litterman/Fama-French download), `ai.py` (SQLite lookups + `_save` retry loop that could `time.sleep` up to ~15s on the loop). One slow upstream call no longer stalls every concurrent request. `macro.py`/`atlas.py` audited — already clean (async services or pure in-memory).
- **Sync `cached()` single-flight:** per-cache `threading.Lock` with double-checked locking (mirrors `async_cached`) — cold-cache thundering herd against rate-limited APIs eliminated.

## Phase 37 — Fix-it sprint: COT data, error boundaries, UI consistency, desktop logging (2026-07-02)

- **P2-22 COT/Positioning fixed:** CFTC Socrata API primary source with exact contract codes + parse-validated source waterfall (headerless `deafut.txt` no longer accepted as "success"); failure envelopes never cached (`skip_if`); PositioningTab empty/stale states. 8 new tests. **P2-19 closed** (verified fixed in the prior cache-poisoning commit).
- **Docker frontend build repaired:** unbuildable since Phase 36 (`output:"export"` vs standalone Dockerfile) — output mode now env-driven (`NEXT_OUTPUT_MODE`).
- **P2-05/P2-06/P2-21:** global `ErrorBoundary` + `app/error.tsx` (crashes show a retry card, nav survives); `DataFreshnessBadge` live on Screener; raw-timestamp audit.
- **P2-04/P2-11/P2-12/P2-13:** mobile nav decongested (toggles → More drawer); shared `TabButton`/`ToggleChip` in `ui.tsx` replacing ~9 hand-rolled tab bars; Options delay badge + compute-tier labels normalized.
- **DESK-01:** frozen backend now writes `%APPDATA%/AxiomFinance/backend.log` (redirect keyed on `sys.frozen`; Tauri pipes stdout so the old `is None` check never fired). **P3-06:** all `datetime.utcnow()` migrated (naive-UTC helper where DB rows are naive).
- **Test suite isolation:** autouse fixture resets both cache tiers per test — the persistent SQLite tier was cross-polluting ~20 tests.

## Cache poisoning fix + macro/Atlas data resilience + theming (2026-07-02)

- **Cache poisoning fixed (root cause of missing Atlas GDP + blank macro tabs):** the SQLite cache tier ignored TTL and served empty/failed payloads forever. `HybridCache._get_from_db` now enforces `ttl_sec` (expired rows deleted → re-fetch), and `cached`/`async_cached` never persist empty results (new `skip_if` guard, defaults to an empty-container check). Existing poisoned entries self-heal on next run.
- **Atlas hardened:** `atlas_service` WB fetch is now bulk-first (parquet) with a live `wbgapi` fallback; `get_timeline` skips caching all-null results; prefetch kicks a background bulk download if none is present.
- **Admin:** new `POST /admin/cache/clear` + "Clear cache & re-warm" button; saving API keys now purges caches. `macro_regime` returns an explicit `available:false` (with reason) instead of fabricating a "Deflationary" regime on missing FRED data; `RegimeOverlay` shows a clear degraded state.
- **UI fixes:** country-name labels on all horizontal bar charts now render in full (`interval={0}` on the category axis — Housing, Fiscal, Labor, Energy, Inequality, Business, Financial Conditions, Banking Stability, Short Interest); Recharts tooltips/axes/legends themed via CSS variables so they're readable in dark mode.
- **Custom theme maker:** Admin → Appearance lets users pick Primary + Accent brand colours on top of the light/dark base themes, applied via CSS variables, persisted in localStorage, and applied pre-paint (no flash). `ThemeProvider` extended with `colors`/`setColors`/`resetColors`.
- **P3-12 resolved:** removed the dead Reinhart-Rogoff bulk download (404); the sovereign model already uses bundled R&R data.

## Gated desktop release flow — main → PRODUCTION (2026-07-01)

- `main` is now feature-development only: `build-desktop.yml` no longer builds on `main`/PRs — it triggers on `PRODUCTION` pushes, `v*` tags, and manual dispatch.
- New `promote-to-production.yml` (manual "Promote main → PRODUCTION"): merges `main` into `PRODUCTION`, pushes, then dispatches the 3-OS build (needed because a `GITHUB_TOKEN` push doesn't trigger other workflows).
- New `TAURI_BUILD.md` documents the four contracts a `main` feature must respect to stay Tauri-packageable (`config.DATA_DIR` for all writes, static export + full `generateStaticParams`, 127.0.0.1:8000 backend + health gate, PyInstaller `collect_all`) and the release steps.

## Cross-platform desktop builds — Windows · macOS · Linux (2026-07-01)

`build-desktop.yml` now builds on a 3-OS matrix (`windows-latest` / `macos-latest` / `ubuntu-latest`), each freezing its own PyInstaller backend and running `tauri build`:

- **Windows** → NSIS `*-setup.exe`, **macOS** → `*.dmg` (Apple Silicon, unsigned), **Linux** → `*.deb`.
- Linux `tauri.conf.json` originally also targeted **AppImage**, but it can't be bundled on GitHub's runners (`linuxdeploy` needs FUSE; `APPIMAGE_EXTRACT_AND_RUN`/`NO_STRIP` didn't clear it — likely a WebKitGTK-4.1 plugin issue). Dropped `appimage` and ship `.deb` only (tracked as P3-13).
- CI actions bumped to Node-24-native versions; broken duplicate `build-desktop.yml` removed; path triggers widened.

## Bug-fix batch — Atlas, Screener, Dividends, Country pages, Admin (2026-07-01)

User-reported defects fixed (see `ACTIVE_ISSUES.md` BUG-A1…A5):

- **Atlas / cache warming:** re-derive the ISO-numeric `id` (via `pycountry`) in `atlas_service._country_universe()` — a regression from the static-JSON switch (`cf2d1a0`) that made all 6 Atlas timeline endpoints 500 with `{"detail":"'id'"}` and cascaded into the Macro/Atlas panels.
- **Dividend yield:** stop multiplying yfinance's `dividendYield` by 100 (it's already percent units) — MSFT no longer shows "98%". Screener `high_dividend` threshold corrected to `3.0`.
- **Stock Screener:** memoise `activePresets` so the fetch effect no longer loops (flicker/reload).
- **Country pages:** pre-generate the full ISO 3166-1 alpha-2 set so clicking any country resolves instead of falling back to `/dashboard` (static-export 404).
- **Admin bulk data:** IMF WEO size now sums its per-indicator parquet files; the status table prints the real error message (surfaces the dead Reinhart-Rogoff source URL, tracked as P3-12) instead of a bare "⚠ Failed".

---

## Desktop v1.0.0 — Working Windows Build (2026-07-01)

Supersedes the original Phase 37 desktop scaffolding, which built but failed to launch (silent backend crash on missing imports). Root causes fixed:

- **Backend freeze:** rewrote `backend/build.spec` to PyInstaller **onedir** with `collect_all()` over the whole dependency stack (numpy/scipy/pandas/pyarrow/arch/statsmodels/yfinance/… + certifi, pycountry, financedatabase, edgar data) — captures the lazy/dynamic imports and data files the hand-listed `hiddenimports` missed.
- **Tauri wiring:** dropped the sidecar/updater approach; the backend folder is bundled via `bundle.resources` and spawned from `src-tauri/src/lib.rs` using a resource-resolved path, with `AXIOM_DATA_DIR` passed on the command.
- **Data dir:** `database.py` now resolves the SQLite path from `config.DATA_DIR` (`%APPDATA%/AxiomFinance`) instead of a CWD-relative `./data`, so the DB no longer scatters based on launch directory.
- **Cold-start race:** health-gate splash in `providers.tsx` polls `/api/health` before mounting; React Query retry bumped.
- **Windows-only, local build**, production windowless (`console=False`). NSIS installer (165 MB) published via **Git LFS** under `releases/`; GitHub Actions `build-desktop.yml` builds on `windows-latest`.
- **Verified:** clean install launched from a neutral CWD serves live data (`/api/health`, `/api/search` → 200); DB + WAL/SHM land in `%APPDATA%/AxiomFinance` with no stray copies.
- **Known caveats:** DESK-01 (`backend.log` not written under `console=False`), DESK-02 (backend orphaned on force-kill) — tracked in `ACTIVE_ISSUES.md`.

Commit `441f938`.

## Phase 37: Tauri Desktop App (2026-06-30)

- **Frontend:** Switched to `output: "export"` (static HTML); API client uses configurable base URL (`NEXT_PUBLIC_API_URL`); added `generateStaticParams` for `country/[iso2]` dynamic routes
- **Desktop:** New `desktop/` Tauri v2 Rust project; Rust sidecar manager spawns Python backend binary, polls health check, shows error dialog on failure; placeholder icons generated
- **Backend:** PyInstaller `build.spec` to compile Python into `axiom-backend` binary; data directory resolves via `AXIOM_DATA_DIR` env var with OS-standard fallback; settings.json read for API keys
- **Settings UI:** New `SettingsPanel.tsx` modal for FRED/Finnhub/Gemini API keys; saves via Tauri FS plugin (Docker admin API fallback); gear icon in navbar
- **CI/CD:** GitHub Actions matrix build on `windows-latest`, `macos-latest`, `ubuntu-latest`; pipeline: PyInstaller → Next.js static export → Tauri build → GitHub Release on tag
- **Auto-update:** Tauri updater via GitHub Releases; signing keys generated with pubkey in `tauri.conf.json`

## Phase 36 — P1 Bug Fixes (2026-06-30)

| ID | Description |
|----|-------------|
| P1-03 | Atlas map — added error state, key prop on ComposableMap, improved geojson fetch |
| P1-04 | Rate-limit batching — BATCH_SIZE 5→10, progressive backoff in `yfinance_service.py` |
| P1-05 | Multi-country macro — World Bank fallback for non-US `/macro/inflation` and `/macro/employment` |
| P1-06 | CountrySelector — `timeoutRef` cleared on `pick()` to prevent stale dropdown reopen |
| P1-07 | Dashboard React #425 — defensive `String()` wrapping in `FearGreedGauge` and `BreadthBar` |
| P1-08 | 30Y breakeven — `DGS30 − DFII30` fallback when `T30YIE` FRED series empty |
| P1-09 | Scenario Lab — dedicated `/scenario` page with Suspense boundary, nav entries in Navbar + MobileNav |
| P1-10 | Econometric Lab — error handling in `runRegression()`, surfaces failures to UI |
| P1-11 | BIS credit gaps — `bis_credit_gap` added to `BIS_DATASETS` and download URL map |
| P1-12 | DCF share count — `marketCap / currentPrice` cross-validation heuristic in `dcf_engine.py` + `valuation_engine.py` |
| P1-13 | Piotroski F-Score — `_prior_val()` with quarterly fallback for prior-year data (AAPL: 8/9, was 4/9) |
| P1-14 | Beneish M-Score — same fix as P1-13 (AAPL: −2.00, 7/8 components, was null) |

All 12 P1 issues resolved. 85 DCF/valuation tests pass. TypeScript compiles clean.

| Phase | Date | Description | Commit |
|-------|------|-------------|--------|
| Setup | — | Deps, pytest + Playwright harness, Finnhub config | `02f5028` |
| Phase 0 | — | DCF engine, FX rates panel, regime clock | `390438b` |
| Phase 1 | — | Valuation engine (8-model), extended fundamentals, analyst data, Fama-French | `4b21fae` |
| UI Polish | — | Metrics colour coding, ratio guide, cleaner macro chart tooltips | `374a49a` |
| Phase 2 | — | Dashboard breadth, indices, Fear & Greed, top movers | `7937e9c` |
| Phase 3 | — | S&P 500 Treemap with sector/industry drill-down | `4bd7393` |
| Phase 4 | — | Calendar: macro, earnings, dividends, IPOs, CB meetings | `06c613a` |
| Phase 5 | — | Screener: cached universe, presets, 9 result tabs, sparkline gallery | `a9dbb8b` |
| Phase 6 | — | Risk: rolling metrics, GARCH/Hurst/cointegration, stress/Monte Carlo | `dccc5f5` |
| Phase 7 | — | Options: IV analytics, Greeks, term structure, OI, binomial/MC pricing | `4c7f01a` |
| Phase 8 | — | Macro expansion (10 tabs), 13F/Form 4 panels | `1815c9e` |
| Phase 9 | — | Snowflake composite score: 5-axis radar + batch endpoint | `9ec9d71` |
| Phase 10 | — | Sectors: SPDR ETF KPIs, return charts, rotation clock, industry drill-down | `10e9c0b` |
| Phase 11 | — | Portfolio: efficient frontier, Black-Litterman, Monte Carlo, Fama-French, stress | `aee9c35` |
| Phase 12 | — | Advanced technicals: MACD/BB/Ichimoku/Fibonacci/Pivots on Markets + Screener | `c061511` |

---

## Phase 13–24: Expansion

| Phase | Date | Description | Commit |
|-------|------|-------------|--------|
| Phase 13 | 2026-06-25 | Atlas: world choropleth, 6 indicators, year slider, regional blocs WB/IMF data | `34148aa` |
| Phase 14 | 2026-06-25 | Research Hub: Risk Parity (ERC/inverse-vol), FX Carry (G10), Momentum (decile backtests) | `ae01e35` |
| Phase 15 | 2026-06-26 | Realized Moments (GK variance, skew, cross-section) + Econometric Lab (pooled OLS, no statsmodels) | `49048c4` |
| Phase 16 | 2026-06-26 | Country Risk (6-KPI traffic-light) + Central Bank Tracker (7 CBs, IRSTCI01/IR3TIB01) | `8003fa8` |
| Phase 17 | 2026-06-27 | SQLite persistence (6 ORM tables), APScheduler jobs, React Query v5, HybridCache, composite endpoint, admin performance, Nginx gzip, progressive tab loading | `466be45` |
| Phase 18A | 2026-06-27 | Macro-Financial Intelligence: credit_market, yield_curve, policy, sovereign_risk, macro_regime services. /yield, /policy, /sovereign pages | `ebe152d` |
| Phase 19 | 2026-06-27 | UI & Data Quality fixes (5 sub-phases, 21 fixes): dividend yield scaling, dark chart Y-axis, calendar FRED filter, nav overflow, treemap UX, dashboard null-safety, options IV clamp, yfinance 401 retry, Docker DNS | `72477bd` |
| Phase 20 | 2026-06-26 | Macro Policy Pages: funding_service fix, commodities→FRED, FX→FRED, PPP rewrite, COT fallbacks, CentralBanksTab, FinancialConditions, LeadingIndicators, RegimeClock | `6ba3a5e` |
| Phase 21 | 2026-06-26 | Wiki: 410 financial terms, 26 categories, debounced search, category sidebar, expandable cards, related-term cross-linking | `6403132` |
| Phase 22 | 2026-06-27 | UI Theming: neutral grey palette, PageSkeleton + EmptyState components, Fear & Greed SVG gauge, maroon accent | `5644c34` |
| Phase 23 | 2026-06-27 | UI Polish: PageSkeleton rollout, sticky tab bars, mobile nav collapse, screener persistence, Yield+Policy merge, country search in EconLab, live FRED risk-free rates | `07ca909` |
| Phase 24 | 2026-06-28 | Bulk Data Pipeline (WB/IMF/BIS/Fama-French parquet), BIS integration (CPI/policy/FX/credit gaps), macro regime overhaul, prefetch system (95 tasks), Docker healthcheck | `d5eb553` |

---

## Phase 25–36: IDEA_LIST Delivery

| Phase | Date | Description | Commit |
|-------|------|-------------|--------|
| Phase 25 | 2026-06-29 | Fiscal Sustainability tab (/macro), BIS Property Prices → Housing tab, BIS Credit Gaps → Financial Conditions tab | `9ec9e91` |
| Phase 26 | 2026-06-29 | Trade Flows & Globalization page (/trade): exports/imports, trade balances, openness indices, BIS effective FX | `9ec9e91` |
| Phase 27 | 2026-06-29 | Corporate Health Monitor (/corporate): Altman Z, Piotroski 9-pt, Beneish M. Dividend Analysis (/dividends): yield, growth, payout, aristocrats. Insider Trading Aggregator. Sector DuPont Analysis. Inflation Expectations → Inflation tab | `9ec9e91` |
| Phase 30 | 2026-06-29 | Business Dynamism tab, M&A/Corporate Actions tracker, Demographics→Atlas overlay, Short Interest→Markets panel | `df7dae8` |
| Phase 31 | 2026-06-29 | Banking & Financial Stability (/stability): NPL, capital adequacy, Z-scores, BIS credit gaps. Cross-Border Finance (/crossborder): BIS locational banking stats, debt securities. Sovereign Default Probability Model | `282703f` |
| Phase 32 | 2026-06-29 | Wired 3 macro tabs that were built but missing router endpoints: Labor Market Deep Dive (/macro?tab=labor), Energy Transition & Climate (/macro?tab=energy), Inequality & Development (/macro?tab=inequality) | `9a6a297` |
| Phase 33 | 2026-06-29 | Currency Crisis Early Warning: upgraded to 6-signal KLR model with reserves decline + FX overvaluation signals | `78ae75b` |
| Phase 34 | 2026-06-29 | Supply Chain Vulnerability Atlas layer: 13th indicator — choropleth map. IDEA_LIST: 22/22 complete 🎉 | `b496559` |
| Phase 35 | 2026-06-29 | AI-Powered Summaries: Google Gemini — company/macro/dashboard summaries with SQLite caching, model selector, clickable chips, source attribution | `5875bbb` |
| Phase 36 | 2026-06-29 | Shareable URLs / Deep Linking + Configurable Benchmark Override on Markets + Risk pages | `e14ee06` |

---

## Phase 37–40: Remaining P3 Features

| Phase | Date | Description |
|-------|------|-------------|
| Phase 37 | 2026-06-30 | Portfolio Transaction Log: buy/sell tracking with cost basis, realized P&L (FIFO lot matching), localStorage + optional SQLite sync. New Transactions tab on /portfolio. | `b661e68` |
| Phase 38 | 2026-06-30 | Learning Layers: beginner/expert mode toggle, 60+ metric tooltips with explanations, page walkthrough banners on Dashboard/Markets/Portfolio. | `fdbae7c` |
| Phase 39 | 2026-06-30 | Cross-Asset & Factor Analytics: 3 new Research Hub tabs — Cross-Asset Correlation (stocks/bonds/commodities/FX matrix), FX-Macro Link (6 commodity pairs with lead/lag), Multi-Country Portfolio (FX-adjusted returns, currency exposure). | `ace186b` |
| Phase 40 | 2026-06-30 | Navigation Reshuffle: grouped More dropdown with 5 section headers (Discover/Analyze/Markets & Data/Global/Reference). Renamed "M&A" → "Mergers & Acquisitions", "Rates & Policy" → "Yield". Primary bar unchanged per user direction. IDEA_LIST: all 3 P3 items complete. | `6e4a752` |

---

## Legend

- All phases have verified commit references from git history
- Phases 13–40 were shipped via the per-phase Docker gate workflow (build → recreate → curl → browser check)

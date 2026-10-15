# EconoSift — Performance & Architecture Refactor Proposals (Phase 65+)

_Date: 2026-10-15. Basis: five read-only analysis agents (backend, frontend, Rust feasibility,
data sources, backtesting) plus orchestrator spot-checks of the key claims against the code.
Nothing in the app was changed to produce this document._

---

## 1. Diagnosis — why EconoSift is slow and why things break

The core finding is the same from every angle: **neither the language (Python) nor the UI
framework (Next.js/React) is the bottleneck. The architecture is.** Every page load fans out
live to Yahoo/FRED/BIS/World Bank, results live in a 60-minute blob cache, and one Python
process serves users, runs the scheduler and warms caches at the same time. The cache layer
itself (single-flight locks, stale-while-revalidate) is well engineered; the problem is what it
wraps.

### Verified root causes (✔ = orchestrator checked in code)

| # | Root cause | Evidence |
|---|---|---|
| 1 | ✔ **No market-data store is ever read.** `DailyPrice`/`DailyQuote`/`DailyMacro`/`DailyFX` are written by `jobs.py` but only read by the admin row-count. Every page re-downloads. `refresh_daily_prices` only covers `tickers[:100]` of a sorted list. | `services/jobs.py:137,149`, `routers/admin.py:36` |
| 2 | **Per-ticker Yahoo fan-out.** `get_info` = ~5–10 HTTP calls/ticker; the screener refresh runs it over ~500 names (~3–5k Yahoo requests) at every container start. Yahoo throttles → partial/empty data → "things break". | `yfinance_service.py:314,412`, `screener_service.py:729,859`, `main.py:56` |
| 3 | ✔ **One uvicorn process, blocking calls inside `async def`.** ~25 async routes call sync Yahoo/SQLite code without `to_thread`; while one cold fetch runs, the whole app (incl. `/health`) freezes. | `backend/Dockerfile` CMD (no workers), `routers/technicals.py:14-23`, also snowflake, scenario, atlas, corporate, dividend, research, macro |
| 4 | ✔ **Nginx re-sends timed-out requests up to 3×** to the same single backend, tripling load on an already saturated process. | `nginx/default.conf:20-21,31-32` |
| 5 | **Startup stampede.** Screener warm-up + 4 immediate scheduler jobs + the user's first page all compete for the same Yahoo budget, GIL and SQLite write lock. Crons run during US market hours. | `main.py:56`, `jobs.py` ~428 |
| 6 | ✔ **Empty DataFrames are cached.** `_is_empty_result` handles None/dict/list/str but not `pd.DataFrame`; `get_close_frame`/`get_volume_frame` return `pd.DataFrame()` on failure → one Yahoo hiccup blanks treemap/breadth/sector/risk for an hour. | `cache.py:363-379`, `yfinance_service.py:38-91` |
| 7 | **DataFrames never reach the persistent cache tier** (`json.dumps` TypeError is silently swallowed) → every restart / desktop launch is a full cold start. | `cache.py:753-760` |
| 8 | **Duplicate downloads & memory growth.** Treemap, breadth, screener and sector each download the same S&P 500 prices with different periods; stale-refresh spawns unbounded threads. | `cache.py:19,442` |
| 9 | **Silent failure handling.** ~200 broad `except` sites, ~110 of which return empty → users see blanks, not errors. No per-source circuit breaker; a dead host costs its full 45–180 s timeout on every miss. | e.g. `screener_service.py:757,870` |
| 10 | ✔ **Frontend amplifies backend latency.** `retry: 6` globally, no client timeout, ~240 hand-rolled `useEffect` fetches that bypass react-query's cache (only ~10 `useQuery` calls in the app) → refetch on every tab switch, 15–20 s spinners on errors. | `frontend/lib/queryClient.ts:11`, `lib/api.ts:60-75` |
| 11 | **Breakage → blank pages.** One root ErrorBoundary; hand-written `types.ts` (no OpenAPI codegen, `response_model` on 1 route) with 47 `as any` casts → a shape drift crashes the whole page. | `app/layout.tsx:29`, `lib/types.ts` |
| 12 | **Charts:** Recharts SVG with animation on and no downsampling for long daily series; eager imports of all tabs on Macro/Research/Portfolio. | 227 `<Line` vs 108 `dot={false}` |

The project's own history agrees: ACTIVE_ISSUES P1-14 records a cold 6-request burst taking
940 s (cut to 247 s), with a ~110 s floor from the FRED quota alone.

### What a language switch would and would not fix

- **Rust backend:** most latency is network-bound; the heavy maths (GARCH, SLSQP, Monte Carlo,
  covariance) already runs in compiled numpy/scipy/arch code. A Rust port would speed up
  Python-level loops 10–50×, but barely move user-perceived latency. Hard to port:
  scipy SLSQP (efficient frontier, risk parity), `arch` GARCH, statsmodels cointegration,
  `edgartools` Form 4/13F parsing, and pandas semantics across 59 files. Yahoo access is the
  most fragile piece in *either* language (Rust `yfinance-rs` is a small one-person crate).
- **Python strategy import** (your requirement) needs a Python runtime in the product under
  every option. That cancels Rust's main packaging win (dropping the PyInstaller-frozen backend).
- **Svelte/Solid frontend:** ~30–50 % less JS and faster reactivity, i.e. tens of milliseconds.
  But pages wait seconds on the network, and that wait stays the same. Rewriting ~40k lines of TSX
  (21 pages, heavy charting, Recharts has no Svelte equivalent) means 3–5 months of risk to the
  current look for little measurable gain.

---

## 2. Proposals

### Proposal A — "Stabilise in place" (quick wins only)
Python + Next.js unchanged; fix the verified defects.

- Backend: empty-DataFrame `skip_if` (#6); `to_thread`/plain `def` for the ~25 blocking async
  routes (#3); drop `timeout` from nginx `proxy_next_upstream` (#4); stagger/serialise startup
  jobs and move crons out of US hours (#5); lazy/batched beta in `get_info`, drop quarterly
  statements from the screener path (#2); per-source circuit breaker (#9); per-function TTLs
  (daily bars until next close, quotes shorter); one shared S&P 500 price download sliced by
  all consumers (#8).
- Frontend: `retry` 6 → 1–2 (keep long retry only for desktop cold start, gated on `/health`);
  20–30 s `AbortSignal` timeout in `get()`; per-tab/per-panel ErrorBoundaries; lazy-load tabs
  and `wikiData`; `isAnimationActive={false}` + downsample to ≤500 points; mock `/api` in the
  Playwright smoke tests.

| Effort | Risk | Gain | Backtesting / strategy import | Data sources |
|---|---|---|---|---|
| ~2–3 weeks | Low | Fewer freezes and blank pages; cold start still slow | Unchanged (live 120-ticker download) | Unchanged |

### Proposal B — "Local-first data platform" ⭐ RECOMMENDED
Proposal A, plus re-architect around a persisted data store and a separate ingest worker.
Python stays as the backend language and React stays, so all 21 pages keep their current look.

1. **Market-data store.** Daily OHLCV (raw + adjusted), splits, dividends and fundamentals,
   stored in Parquet partitioned by ticker/year and queried with **DuckDB** (or SQLite tables
   for small series). Ingestion is incremental: append only new bars. Every analytics service
   reads local data; Yahoo is hit by **one** ingest job, never by a page request.
2. **Separate worker process/container** for the scheduler, warm-up and ingestion (and later
   the backtests), so user requests never share a GIL, thread pool or Yahoo budget with refresh
   jobs. Once the cache is no longer process-local, you can then run several uvicorn workers.
3. **Polars in the hot paths** (breadth, screener indicators, cross-sectional backtests).
   Polars is written in Rust, so this gets Rust speed with no rewrite.
4. **Typed API contract.** Add `response_model` to the routers and generate `types.ts` with
   `openapi-typescript`; add a zod (or similar) check at the API boundary for critical pages.
5. **Frontend data layer.** Mechanically convert the ~240 `useEffect` fetches to `useQuery`.
   The `api.x()` functions already exist, so each conversion is ~5 lines and gives cache,
   dedup and cancellation. Add aggregate "one call per tab" endpoints where a tab fires many
   requests. Add `lightweight-charts` (candles/technicals) or `uPlot` (long series) for price
   charts, and keep Recharts for small panels.
6. **Backtesting on the store** (see §3), plus the data-source upgrades (see §4).
7. *Optional, later:* move from Next.js to **Vite + React** (+ TanStack/React Router): 1–2 weeks,
   ~95 % code reuse (all components, Tailwind, theme tokens, `ui.tsx` and Recharts carry over).
   This removes the dual `export`/`standalone` build, the hydration races behind the flaky
   e2e tests, and slow dev builds, and it is the cleanest fit for Tauri.
8. *Optional, only where profiling proves it:* PyO3/maturin Rust kernels for a measured hot
   loop (e.g. Monte Carlo).

| Effort | Risk | Gain | Backtesting / strategy import | Data sources |
|---|---|---|---|---|
| ~8–12 weeks, in phases; each phase shippable | Low–medium | **High**: pages read local data and cold starts disappear; Yahoo outages degrade to "data as of last night" instead of blanks | First-class: store-backed, survivorship-aware, sandboxed Python strategies | SEC fundamentals, Stooq/Tiingo fallback, nightly options snapshots |

### Proposal C — "Rust core + Python sidecar"
Axum + Tokio + Polars serve the API, cache and ingestion. A Python worker pool (over Arrow IPC)
runs arch/scipy/statsmodels/edgartools and user strategies. SvelteKit or Vite + React frontend.

| Effort | Risk | Gain | Backtesting / strategy import | Data sources |
|---|---|---|---|---|
| ~4–7 months | High: two runtimes and an IPC contract, ~265 routes to port, numerical revalidation, and Python must still be frozen for the desktop app | Medium-high on serving; roughly the same as B on user-perceived latency, because B already removes the network from the request path | Works (strategies run in the Python worker), but more moving parts than B | Same as B |

Only worth it as a later step **after** B, if profiling shows the Python serving layer is still
the bottleneck, which none of the evidence suggests today.

### Proposal D — "Full rewrite: Rust backend + SvelteKit frontend"

| Effort | Risk | Gain | Backtesting / strategy import | Data sources |
|---|---|---|---|---|
| ~9–18 months | Very high: a feature freeze, scipy/arch/statsmodels/edgartools to reimplement without reference tests, Yahoo crumb handling in a small crate, and the visual polish to rebuild | Largest on paper; little user-visible gain on network-bound pages | **Fails your requirement** unless you embed a Python interpreter, which brings the packaging problem back | Same as B |

**Not recommended.**

---

## 2b. Database — split it by workload

**Today** there are three storage mechanisms, all of them row- or blob-oriented:

| Store | What lives there | Problem |
|---|---|---|
| `axiomfinance.db` (SQLite WAL, SQLAlchemy; `database.py`, `db_models.py`) | User state (`portfolio_transaction`, `ai_summary`, `job_execution`), the persistent cache tier (`cache_entry`: JSON text blobs), and time series (`daily_price`, `daily_macro`, `daily_fx`, `metric_snapshot`) | One file with one write lock, shared by user writes, cache writes on the request path, and ingest jobs. Time series are stored one row per value and loaded with ~25k `session.merge()` calls (each a SELECT). `daily_price` is never read. No migrations tool. |
| `screener_cache.db` (raw `sqlite3`) | Screener fundamentals and shares | A second hand-rolled schema with separate code |
| Ad hoc Parquet (`bulk_data_service.py`) | World Bank bulk downloads | Fine, but a one-off |

SQLite isn't the problem for user state. The problem is using one OLTP file for three very
different workloads, and storing analytics data in row or JSON form that has to be re-parsed
into pandas on every read.

**Recommended target (embedded, so it still works in the Tauri desktop app with no server to
install):**

1. **Analytical store = Parquet files + DuckDB** for prices, corporate actions, fundamentals,
   macro series, FX and metric snapshots.
   - Columnar and vectorised; reads straight into pandas/Polars via Arrow with zero parsing.
   - A 500-ticker × 10-year panel is a sub-second query.
   - The ingest worker is the **only writer**. It writes new Parquet partitions and swaps them
     in with an atomic rename. The API opens them read-only through an in-memory DuckDB
     connection. This sidesteps DuckDB's single-writer-process rule, which would otherwise
     clash with a separate worker.
   - Every ingest gets a snapshot ID, so backtests can be reproduced.
   - Folds in `screener_cache.db` and the World Bank Parquet files.
2. **App state = SQLite stays** (transactions, settings, AI summaries, job log, strategy
   metadata), with the SQLAlchemy models kept and **Alembic** added for migrations. It's small,
   transactional, and backs up as a single file.
3. **Cache = its own SQLite file (or `diskcache`)**, separate from user data, storing DataFrames
   as Arrow/Parquet bytes instead of JSON. That fixes causes #7 and the write-lock contention.
   Once pages read from the analytical store, most of this cache becomes unnecessary and can
   shrink to API-response caching for slow non-price sources.

**Considered and not recommended:**
- **PostgreSQL + TimescaleDB:** excellent for the Docker deployment, but it is a server, so the
  desktop app would have to bundle and manage a Postgres process. It also adds operations work
  for a single-user app.
- **ClickHouse / QuestDB:** same server issue, and overkill for this data volume (tens of
  millions of rows at most).
- **Polars-only on Parquet, without DuckDB:** viable and simpler. DuckDB is preferred because
  SQL over Parquet makes the cross-sectional/universe queries and ad hoc admin checks much easier.

This slots into **Phase 66**. The SQLite/cache split is low risk and could even go into Phase 65.

---

## 3. Backtesting & importing Python strategies (fits Proposal B)

**Today:** `backtest_engine.py` is a decent vectorized, cross-sectional quantile backtester. It
has correct t→t+1 alignment (tests pin it), a `LookaheadError` gate on fundamentals, costs in
bps, and an optional point-in-time S&P 500 universe. But each run downloads 10y of prices live
for at most **120 of today's constituents** (`backtest_signals.py:30,119`). Delisted names have
no price data, so the point-in-time universe is largely cosmetic. There is no walk-forward
testing, no slippage model and no user strategies.

**Plan:**
1. The data store comes first (§2-B.1): adjusted and raw bars, a corporate-actions table,
   delisted tickers kept, and a snapshot ID recorded on every backtest run so it can be reproduced.
2. Keep the in-house engine as the core. Add a **weights-based runner** and a strategy plugin
   interface:

   ```python
   class Strategy:
       name = "my_momo"
       params = {"lookback": 126, "top_n": 20}
       universe = "sp500"        # point-in-time membership applied by the harness
       frequency = "M"

       def generate_weights(self, ctx) -> "pd.Series":
           # ctx.prices is trimmed to rows <= ctx.asof BY THE HARNESS (structural no-lookahead)
           px = ctx.prices[ctx.members]
           score = px.iloc[-1] / px.iloc[-self.params["lookback"]] - 1
           w = score.nlargest(self.params["top_n"])
           return w / w.sum()
   ```
   Add adapters for `generate_signals(df)`, a vectorbt-style signal function that feeds the
   existing quantile path, and a thin backtesting.py-style `init/next` shim for single-asset
   strategies. Reimplement that shim rather than embedding the library, to avoid AGPL in the
   desktop build.
3. **Sandboxing:** imported code is arbitrary code execution. Run it in a separate `python -I`
   worker with CPU/memory limits and a wall-clock timeout, a scrubbed environment (no API
   keys), and data passed in as Arrow/Parquet files. In Docker, run it in a no-network worker
   container. Upload is off by default and enabled in Admin, and every run is shown with the
   file hash. On the desktop app this isolation is crash and resource containment only, not a
   security boundary; the UI should say so.
4. Add walk-forward / out-of-sample splits, a slippage model and short-borrow costs.
5. **External engines:** optionally use vectorbt (open-source edition) only as a backend for
   parameter sweeps. Look at NautilusTrader (Rust core, Python strategies) only if intraday,
   order-book or live trading becomes a goal (v2.0 was still at release candidate in Sept 2026).
   Skip Backtrader (unmaintained), LEAN (.NET) and Freqtrade (crypto-only).

This design keeps strategies in a Python worker, so it carries over unchanged if you ever
move to Proposal C.

---

## 4. Data sources (Yahoo stays primary for prices)

_Note: the research agent could not reach provider websites directly. Rate limits and terms
below come from secondary sources and must be checked before building on them._

| Data | Primary | Fallback(s) | Action |
|---|---|---|---|
| Equity EOD | Yahoo | **Stooq** bulk (nightly), Tiingo free (single symbols) | Add a circuit-breaker fallback so a Yahoo outage no longer empties the screener |
| Quotes / delayed intraday | Yahoo | Alpaca Basic (free account, IEX feed, batch snapshots), Tiingo IEX | Optional |
| US fundamentals | **SEC EDGAR companyfacts / frames** (official, free, nightly bulk zip, 10 req/s, User-Agent only) | Yahoo, SimFin | **Highest value**: replaces ~3–5k Yahoo `.info`/statement calls; SEC Financial Statement Data Sets give point-in-time fundamentals for backtests |
| Options | Yahoo | Own nightly chain snapshot | No reliable free source found; Tradier sandbox, CBOE delayed and Alpaca indicative are worth a hands-on test |
| US macro | FRED (+ ALFRED vintages) | BLS v2, BEA, Treasury FiscalData | Get CPI/jobs/GDP directly from the source on release day; cross-check yields |
| Global macro | World Bank, ECB, Eurostat, BIS, DBnomics | **OECD new SDMX API** (20 req/min, run from a nightly job only) | Update API_suggestions.md (still lists the retired OECD.Stat) |
| IMF | `imfp` | — | **Test it:** the IMF retired its old JSON service and IFS codes were split into new dataflows |
| FX | Frankfurter / ECB | — | Keep (exchangerate.host now needs a key; avoid it) |
| Crypto (if wanted) | Coinbase public REST | CoinGecko Demo | Optional |
| News | Finnhub | GDELT, SEC RSS | Optional |

Licence note: free price tiers (Stooq, Tiingo, Alpaca) allow personal, non-redistributed use.
That is fine for a self-hosted app, but would need revisiting if EconoSift were ever hosted for
others. SEC, Treasury, BLS and BEA data are public domain.

---

## 5. Recommendation & suggested phasing

**Recommend Proposal B.** Keep Python, keep React, re-architect around a local data store and
a separate worker, and decide on Vite later.

| Phase | Content | Done when |
|---|---|---|
| 65 | Proposal A quick wins (backend + frontend) | Cold Dashboard/Markets load with no app-wide freeze; no cached empty frames; e2e smoke tests mocked and green |
| 66 | Database split (§2b): Parquet + DuckDB analytical store written by an incremental ingest worker; SQLite + Alembic for app state; separate Arrow-based cache file. Screener, breadth, treemap, sector and risk read from the store | No Yahoo call on any page request for daily data; a restart is warm |
| 67 | SEC companyfacts fundamentals + Stooq/Tiingo fallback + per-source circuit breakers; test imfp | Screener refresh no longer calls `.info` per ticker |
| 68 | Typed contract (`response_model` + openapi-typescript) + `useQuery` migration + per-panel error boundaries | `as any` count → ~0; one failing panel never blanks a page |
| 69 | Backtesting v2: weights runner, strategy plugins, sandboxed worker, walk-forward | A user `.py` strategy uploads and backtests against PIT S&P 500 data |
| 70 (opt.) | Next.js → Vite + React; canvas charts for price series | Same visuals; single static build for Docker and Tauri |
| later (opt.) | Profile; PyO3 kernels or Proposal C only if a measured bottleneck remains | — |

Phase 65 alone should make the app feel noticeably more stable. Phase 66 is the step that
makes it fast.

### Orchestrator corrections to agent findings
- The Rust study listed `finnhub-python` as unused. It is not: it is imported in
  `services/finnhub_service.py` and `services/calendar_service.py`. Don't remove it.
- No `next build`, profiler or live timing was run in this analysis (the dependencies weren't
  installed in the analysis environment). Size and effort figures are estimates; Phase 65
  should start by profiling the 5 slowest endpoints to confirm the ranking.

# EconoSift — Performance Refactor Plan (Phase 65+) — v2

_v1 (2026-10-15) compared four options, from fixing in place up to a full Rust + Svelte rewrite.
v2 (2026-10-15) is the chosen direction after the owner's review: fix the loading problem at its
root and keep the stack._

## 0. Decisions (owner, 2026-10-15)

| Topic | Decision | Why |
|---|---|---|
| Language / frameworks | **Keep Python (FastAPI) and TypeScript (Next.js/React).** No Rust, no Svelte, no Vite move. | The slowness comes from how data is fetched and stored, not from the language. |
| Database | **One database: SQLite**, one file, for everything: prices, fundamentals, macro, portfolio, settings, AI summaries and cache. | Already used and built into Python, so no new dependency. Public domain, the most widely deployed database, with support pledged to 2050. Embedded, so it works unchanged in Docker and the desktop app. |
| Freshness | **S&P 500 / Nasdaq 100 / Dow snapshot every ~15 min** during US market hours; end-of-day bars stored permanently. | A few bulk requests per snapshot instead of hundreds of per-ticker calls. |
| Fetching | **One throttled fetcher inside the backend process.** It is the only code allowed to call Yahoo or other market-data sources. Pages only read the database. | Lowest memory and CPU use; same in Docker and on the desktop. |
| Data sources | **Keyless by default; free keys optional** (a user can paste them in Admin). Nothing paid, nothing mandatory. | If a user would have to pay for data Yahoo gives away free, there is no point to the app. |

**Dependency rule:** no new dependency unless it replaces an old one. This plan adds **none**.
It can likely **remove** `pyarrow`: its only direct use is the Parquet files in
`bulk_data_service.py`, which move into SQLite. Check that nothing else needs it before dropping it.

---

## 1. The problem in one sentence

Every page asks Yahoo (and FRED, BIS, World Bank…) for data live, per ticker, at the moment you
open it. With hundreds of tickers, Yahoo rate-limits us; the failures get cached or retried
(making it worse), and one backend process freezes while it waits.

Verified evidence (file:line, checked in code):

| # | Problem | Where |
|---|---|---|
| 1 | A `daily_price` table exists and is filled, but **nothing ever reads it**. Pages re-download instead. The filler only covers `tickers[:100]`. | `services/jobs.py:137,149`, `routers/admin.py:36` |
| 2 | **Per-ticker Yahoo fan-out.** `get_info` ≈ 5–10 requests per ticker; the screener refresh runs it over ~500 names (≈3–5k Yahoo requests) **at every container start**. `yf.download` itself makes one request per ticker. | `yfinance_service.py:314,412`, `screener_service.py:729,859`, `main.py:56` |
| 3 | **Empty results are cached.** A failed price download returns an empty DataFrame, which the cache doesn't treat as "empty" → treemap/breadth/sector/risk stay blank for an hour. | `cache.py:363-379`, `yfinance_service.py:38-91` |
| 4 | **Retries multiply the load.** Nginx re-sends timed-out requests up to 3×; the frontend retries 6× with no timeout. | `nginx/default.conf:20-21,31-32`, `frontend/lib/queryClient.ts:11` |
| 5 | **One backend process, blocking calls inside `async` routes** (~25 routes) → one slow Yahoo call freezes every page, including `/health`. | `backend/Dockerfile` CMD, e.g. `routers/technicals.py:14-23` |
| 6 | **Startup stampede.** Screener warm-up + 4 immediate jobs + the user's first page all hit Yahoo at once. | `main.py:56`, `jobs.py` ~428 |
| 7 | **Data scattered over 3 stores:** `axiomfinance.db`, `screener_cache.db`, and ~10 Parquet files; price DataFrames never reach the persistent cache, so every restart is a cold start. | `database.py`, `screener_cache.py:27`, `bulk_data_service.py`, `cache.py:753-760` |
| 8 | **Frontend bypasses its own cache.** ~240 hand-written `useEffect` fetches vs ~10 `useQuery` → refetch on every tab switch; one failing panel blanks the page. | `frontend/components/**`, `app/layout.tsx:29` |

---

## 2. Target architecture — "local-first"

```
                 ┌──────────────────────── backend process ────────────────────────┐
 Yahoo / SEC /   │  Fetcher (1 thread, global rate limit, backoff, circuit breaker) │
 FRED / BIS … ──►│        │ writes in batched transactions                          │
                 │        ▼                                                         │
                 │  econosift.db  (SQLite, WAL)  ◄──── read-only queries ──── API   │◄── Next.js
                 └──────────────────────────────────────────────────────────────────┘
```

**Rule:** an API request never calls an external market-data source. It reads the database
and returns the data with an `asOf` timestamp. If something is missing (a ticker never seen
before), it queues a fetch and returns `status: "pending"`; the frontend shows "loading data…"
and polls. Yahoo going down means "prices as of 14:45", not blank pages.

### 2.1 One SQLite database

One file (`econosift.db`, in the existing data directory). It replaces `axiomfinance.db`,
`screener_cache.db` and the Parquet files, with a one-time migration that keeps your
portfolio, AI summaries and settings.

| Table | Contents | Key |
|---|---|---|
| `security` | symbol, name, CIK, exchange, sector, industry, shares outstanding, listed/delisted dates | symbol |
| `index_membership` | S&P 500 / NDX / Dow membership intervals (point-in-time, for backtests) | index, symbol, start |
| `price_daily` | open, high, low, close, adj_close, volume | **(symbol, date) `WITHOUT ROWID`** |
| `corporate_action` | splits, dividends | symbol, date, type |
| `quote_latest` | latest 15-min snapshot: price, change, day OHLC, volume, market cap, P/E… | symbol |
| `quote_intraday` | 15-min snapshots, kept ~10 days for intraday charts | (symbol, ts) |
| `fundamental` | concept, period end, **filed date**, value, source (point-in-time) | (symbol, concept, period_end, filed) |
| `macro_series` / `fx_daily` | FRED/BIS/WB/IMF/ECB series values | (series, country, date) |
| `source_health` | last success, failure count, circuit-open-until per source | source |
| `fetch_queue` | pending on-demand fetches | id |
| `api_cache` | non-tabular API responses for slow sources (news, AI context) only | (name, key) |
| existing app tables | `portfolio_transaction`, `ai_summary`, `job_execution`, settings, later `strategy` | — |

**Why SQLite is fast enough here:**
- **Data volume is small.** ~520 symbols × 10 years ≈ 1.3M daily rows (~100 MB). With a
  `(symbol, date)` primary key, loading 500 tickers × 2 years for breadth is a single indexed
  range scan that should take well under a second.
- **Writes are batched.** `executemany` inside one transaction per batch replaces today's
  ~25k one-row `session.merge()` calls, each of which runs a SELECT first.
- **Settings:** WAL mode (already on), `synchronous=NORMAL`, `mmap_size`, `cache_size`, and
  `temp_store=MEMORY`. WAL means readers never block on the single writer, which is the fetcher.
- **Schema migrations:** a small `schema_version` table and numbered SQL scripts. Alembic would
  be a new dependency, so it is not used.

### 2.2 The fetcher — how we stop flooding Yahoo

A single scheduler thread owns all external calls, with a **global token bucket per source**
(start: Yahoo ≤ 1 request/s with jitter; SEC ≤ 5/s, below its 10/s limit). It slows down
exponentially on HTTP 429 and opens a **circuit breaker** after repeated failures, so a source
that is down is skipped for N minutes instead of being retried on every page.

**Yahoo budget, before vs after:**

| | Today | After |
|---|---|---|
| Container start | ≈3–5k requests (screener warm-up + jobs) | 0 (data already in the DB) |
| First-ever install | same | One-time backfill: ~520 history requests at ≤1/s ≈ 10 min, resumable, with progress in Admin |
| Each page open | 0–hundreds (on any cache miss) | **0** |
| Intraday | — | Bulk snapshot every 15 min ≈ 3–5 requests each → ~80–130/day |
| End of day | — | Today's bar built from the last snapshot, plus one confirmation pass |
| Fundamentals | `.info` + statements per ticker, on demand | **SEC** in bulk (keyless; see §3); Yahoo only for fields SEC lacks (forward P/E, analyst targets), rotating ~75 tickers/day → full refresh weekly |
| **Total** | thousands per session | **~200–300 per day** |

**Bulk snapshot mechanism.** This needs a spike in Phase 66 to confirm; this environment couldn't
reach Yahoo to test. Candidates, in order:
1. **`yf.screen()`**: a public yfinance function that returns up to 250 quotes per call,
   including price, day high/low, volume, market cap and P/E. A US large-cap query (sorted by
   market cap) covers the S&P 500 in ~3 calls; any missing index members are filled
   individually.
2. **yfinance `WebSocket`** (built into yfinance 1.x, no key): one connection subscribed to all
   ~520 symbols during market hours, written to the DB every 15 min.
3. Fallback: throttled `yf.download(period="1d", interval="15m")` in chunks. This is slower but
   always works.

### 2.3 What changes on the read side

- Every service that today calls `yfinance_service.get_close_frame`/`get_volume_frame`/`get_ohlc_frame`
  reads `price_daily` instead. There is one shared helper (`store.prices(symbols, start, end)`),
  so treemap, breadth, sector, screener, risk, portfolio and backtests all share one copy of the data.
- The screener reads `quote_latest` + `fundamental`. That is one SQL query instead of 500 `.info` calls.
- Uncached compute endpoints (risk, options, Monte Carlo) remain compute-on-demand, but read
  their inputs from the DB.
- Macro/BIS/World Bank/IMF jobs keep their current sources and write to `macro_series`.

---

## 3. Data sources (keyless first)

| Data | Primary (keyless) | Optional free-key fallback | Notes |
|---|---|---|---|
| US equity prices & snapshots | **Yahoo** (yfinance), throttled + bulk | Tiingo (free key), Alpaca (free account, IEX feed), Stooq (free key via CAPTCHA since spring 2026) | Stooq without a key is now broken, which also affects `pandas-datareader`'s Stooq reader |
| US fundamentals | **SEC EDGAR**: `frames` API (one call = one figure for *every* company), `companyfacts` per company, nightly `companyfacts.zip`. Keyless, needs a User-Agent with contact info, ≤10 req/s | — | Point-in-time via the filing date → usable in backtests. Market cap = price × SEC shares; P/E etc. computed locally |
| Forward estimates, analyst targets | Yahoo (rotating weekly refresh) | — | SEC doesn't have these |
| Options chains | Yahoo, on demand per ticker (only when the user opens Options) + nightly snapshot for SPY/QQQ | — | No free bulk source found |
| Insider / 13F | SEC (already via edgartools) | — | Keyless |
| US macro | FRED (free key, already set) | BLS / BEA (free keys), Treasury FiscalData (keyless) | Treasury FiscalData is the keyless backup for yields |
| Global macro / policy rates | World Bank, ECB, Eurostat, BIS, DBnomics, IMF (keyless) | — | **Test `imfp`**: IMF retired its old API |
| FX | Frankfurter / ECB (keyless) | — | — |
| News | Finnhub (free key, already) | — | Optional: GDELT (keyless) |

Licence note: Yahoo/Stooq/Tiingo/Alpaca data is for personal use only and must not be
redistributed. That is fine for a self-hosted app; don't host it publicly for others.

---

## 4. Frontend (TypeScript stays)

Only the data-loading layer changes; the look doesn't.
- Global react-query defaults: `retry` 6 → 1 (keep the long retry only for the desktop
  "backend starting" state, gated on `/health`), plus a 20–30 s timeout in `api.ts get()`.
- Convert the ~240 `useEffect` fetches to `useQuery`. The `api.x()` functions already exist,
  so each conversion is ~5 lines and gives caching across tab switches, deduplication and
  cancellation.
- Show the `asOf` timestamp from the backend ("prices as of 14:45 ET") and a "loading data…"
  state for `pending`.
- Per-tab/per-panel error boundaries so one broken panel never blanks a page.
- Lazy-load the tabs on Macro/Research/Portfolio/Yield; chart animation off and ≤500 points
  per series.
- Mock `/api` in the Playwright smoke tests (this fixes the flaky CI job).

---

## 5. Backtesting & Python strategies (on top of the store)

Today each backtest downloads 10 years of prices live for at most 120 of *today's* S&P 500
members (`backtest_signals.py:30,119`), so it suffers from survivorship bias.

With the store:
- Backtests read `price_daily` + `index_membership` and run over the full point-in-time universe,
  including delisted names where Yahoo still has history.
- A strategy plugin is a `.py` file with a `generate_weights(ctx)` method. The harness slices data
  so a strategy can't see the future.
- It runs in a separate, short-lived Python subprocess with a timeout, memory limit, no API keys
  and (in Docker) no network, because uploaded code is arbitrary code. Uploads are off by default.
- Every run records the strategy file hash and data snapshot, so results are reproducible.

No new dependencies: subprocess, resource limits and SQLite are all in the standard library.

---

## 6. Phases

| Phase | Content | Done when |
|---|---|---|
| **65 — Stop the bleeding** | Empty-DataFrame cache guard; fix the ~25 blocking `async` routes; nginx: no retry on timeout; frontend `retry: 1` + request timeout; stagger startup (no screener warm-up at boot); a global Yahoo rate limiter + circuit breaker wrapped around the existing yfinance calls | No app-wide freezes; no Yahoo 429 storms in the logs on a cold start; blank panels show an error instead |
| **66 — One database + fetcher** | Consolidated `econosift.db` with the schema above + migration of existing data; fetcher thread; spike → bulk 15-min snapshot; one-time backfill with progress in Admin; `store.prices()` helper | Restart is instant and warm; one Yahoo request log shows ≤ a few hundred calls/day |
| **67 — Read from the store** | Move treemap, breadth, sector, screener, risk, portfolio, technicals, markets to DB reads; `asOf` on responses; remove the old per-ticker paths and the now-unused cache code | **Zero** Yahoo calls on any page open for daily/snapshot data |
| **68 — SEC fundamentals** | SEC frames/companyfacts ingest → `fundamental`; screener/valuation/ratios read from it; weekly rotating Yahoo refresh for estimates; optional free-key fallbacks in Admin | Screener refresh makes no per-ticker `.info` calls |
| **69 — Frontend data layer** | `useQuery` migration, `asOf`/pending UI, per-panel error boundaries, lazy tabs, mocked e2e | Tab switches don't refetch; CI e2e green |
| **70 — Backtesting v2** | Store-backed point-in-time backtests, strategy plugins, sandboxed runner, walk-forward | A user `.py` strategy uploads and backtests on PIT S&P 500 data |

Phase 65 is small (days) and gives immediate relief. Phases 66–67 are what make the app fast.

## 7. Open items to verify (spikes, not assumptions)
- Bulk snapshot: does `yf.screen()` reliably cover all S&P 500 / NDX members, and how does Yahoo
  respond to ~3 calls every 15 min? Compare with the WebSocket option. (Phase 66, day 1)
- SEC `frames` coverage for the concepts the screener needs (EPS, revenue, net income, shares,
  equity, debt, cash flow) and how to handle odd fiscal years.
- `imfp` against the new IMF API.
- Whether `pyarrow` can be dropped once Parquet is gone.
- None of the Yahoo/SEC/Stooq endpoints could be reached from the analysis environment, so all
  request counts above are estimates until Phase 65/66 measures them.

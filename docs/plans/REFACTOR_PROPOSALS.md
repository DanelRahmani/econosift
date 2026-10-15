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

**Goal: the app feels snappy.** Measurable targets, checked in the Docker gate of each phase:
- Any page API call served from the DB: **p95 < 300 ms** (measure with `curl -w '%{time_total}'`
  over the main endpoints of each page).
- Page shows real content **< 1.5 s** after navigation on a warm app; tab switches show cached
  data instantly.
- **Zero** external market-data calls triggered by opening a page; no Yahoo 429s in the logs
  during normal use.
- A backend restart shows data immediately; nothing waits for a warm-up.

**Dependency rule:** no new dependency unless it replaces an old one. This plan adds **none**.
~~It can likely remove `pyarrow`.~~ **Verified in 65.0: `pyarrow` stays.** `edgartools` 5.x
lists it as a hard requirement, so it is installed either way. The Parquet files still move into
SQLite (one store), but dropping the package itself would mean dropping edgartools (§8.6).

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
`screener_cache.db` and the Parquet files. **No data migration:** there are no users yet, so the
old files are dropped and the new database is built fresh by the backfill. Tables are created
with `CREATE TABLE IF NOT EXISTS` at startup, and there is no migration tooling.

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

### 2.2 The fetcher — how we stop flooding Yahoo

A single scheduler thread owns all external calls, with a **global token bucket per source**
(set from the 65.0 measurements, §8.2: **Yahoo 2 requests/s, burst 4, with jitter**. 100 chart
calls ran clean at 3/s, so this leaves a third of headroom. **SEC 5/s**, half its 10/s limit).
It slows down
exponentially on HTTP 429 and opens a **circuit breaker** after repeated failures, so a source
that is down is skipped for N minutes instead of being retried on every page.

**Yahoo budget, before vs after:**

| | Today | After |
|---|---|---|
| Container start | ≈3–5k requests (screener warm-up + jobs) | 0 (data already in the DB) |
| First-ever install | same | One-time backfill: ~520 `period="max"` history requests (one each, ~0.7 s) ≈ 5–7 min, resumable, with progress in Admin |
| Each page open | 0–hundreds (on any cache miss) | **0** |
| Intraday | — | Bulk snapshot every 15 min = 5 `screen` calls each → ~130/day (measured, §8.1) |
| End of day | — | Today's bar built from the last snapshot, plus one confirmation pass |
| Fundamentals | `.info` + statements per ticker, on demand | **SEC** in bulk (keyless; see §3); Yahoo only for fields SEC lacks (forward P/E, analyst targets), rotating ~75 tickers/day → full refresh weekly |
| **Total** | thousands per session | **~200–300 per day** |

**Bulk snapshot mechanism. Decided in 65.0 (§8.1): `yf.screen()`.**
- Query: `exchange is-in [NMS, NYQ, NGM, NCM, ASE, BTS, PCX]` and `intradaymarketcap > 4e9`,
  sorted by market cap, 250 per page. **5 calls covered 518/518** S&P 500 + NDX + Dow members,
  with price, change, open, day high/low, volume, previous close, market cap, shares, P/E (485/518
  have trailing P/E), forward P/E, 52-week range and 3-month average volume. Each call took ~0.5 s.
- Don't use `region = us`: it took 10 calls and still missed 7 members.
- A member that drops under the cap floor (or out of the result) is filled by a throttled
  per-ticker chart call.
- Fallback when `screen` fails: throttled `yf.download(period="1d", interval="15m")` in chunks
  (50 tickers took 13.5 s, so ~1 request per ticker).
- ~~yfinance `WebSocket`~~: dropped as a snapshot source. It connects and streams, but its
  messages carry only price/change/time (no OHLC or volume), and `screen` already does the job.

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
| US fundamentals | **SEC EDGAR**: `companyfacts` per company (has the `filed` date) for the backfill and for changed companies; `frames` nightly to detect new filings (frame rows have `accn` but **no `filed` date**). ~~nightly `companyfacts.zip`~~ (1.4 GB, dropped). Keyless, needs a User-Agent with contact info, ≤10 req/s | — | Point-in-time via the filing date → usable in backtests. Market cap = price × SEC shares; P/E etc. computed locally. Concept fallback chains in §8.3 |
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

**Branch:** all of this work happens on **`refactor/data-layer`** (branched from `DEV`). Commit
one item per commit and push after each one. Open a PR to `DEV` only when the owner asks.

| Phase | Content | Done when |
|---|---|---|
| **65.0 — Verify sources live** | Before writing code, run quick throwaway checks from the owner's machine against every endpoint in §7. Don't commit probe scripts or add tests for this. Record the results (works / limits / response shape) in a new §8 of this file, and adjust the plan where something doesn't work | Every source in §3 is marked ✅ verified or ❌ dropped, with a replacement |
| **65 — Stop the bleeding** | Empty-DataFrame cache guard; fix the ~25 blocking `async` routes; nginx: no retry on timeout; frontend `retry: 1` + request timeout; stagger startup (no screener warm-up at boot); a global Yahoo rate limiter + circuit breaker wrapped around the existing yfinance calls | No app-wide freezes; no Yahoo 429 storms in the logs on a cold start; blank panels show an error instead |
| **66 — One database + fetcher** | Consolidated `econosift.db` with the schema above, built fresh with no data migration; fetcher thread; bulk 15-min snapshot via `yf.screen` (decided in §8.1, no spike needed); one-time backfill with progress in Admin; `store.prices()` helper | Restart is instant and warm; one Yahoo request log shows ≤ a few hundred calls/day |
| **67 — Read from the store** | Move treemap, breadth, sector, screener, risk, portfolio, technicals, markets to DB reads; `asOf` on responses; remove the old per-ticker paths and the now-unused cache code | **Zero** Yahoo calls on any page open for daily/snapshot data |
| **68 — SEC fundamentals** | SEC companyfacts backfill + nightly frames change-detection → `fundamental`, with the §8.3 concept fallbacks; screener/valuation/ratios read from it; weekly rotating Yahoo refresh for estimates; optional free-key fallbacks in Admin | Screener refresh makes no per-ticker `.info` calls |
| **69 — Frontend data layer** | `useQuery` migration, `asOf`/pending UI, per-panel error boundaries, lazy tabs, mocked e2e | Tab switches don't refetch; CI e2e green |
| **70 — Backtesting v2** | Store-backed point-in-time backtests, strategy plugins, sandboxed runner, walk-forward | A user `.py` strategy uploads and backtests on PIT S&P 500 data |

Phase 65 is small (days) and gives immediate relief. Phases 66–67 are what make the app fast.

## 7. Phase 65.0 checklist — verify these live before building on them

None of these could be reached from the cloud analysis environment, so every request count and
limit above is an estimate until this checklist is done. Use throwaway snippets in a Python REPL
or `curl`; don't commit them.

| # | Source / call | What to confirm |
|---|---|---|
| 1 | `yf.screen(EquityQuery(...), size=250, sortField="intradaymarketcap")` | Returns 250 quotes per call with price, day high/low, open, volume, market cap, trailing P/E; how many calls cover all S&P 500 + NDX + Dow members; which members are missing |
| 2 | yfinance `WebSocket` (or `AsyncWebSocket`) subscribed to ~520 symbols for 2–3 min during market hours | Messages arrive for most symbols; fields; any disconnects |
| 3 | `yf.download(<50 tickers>, period="1d", interval="15m", threads=False)` | Works as the fallback; time taken; any 429s |
| 4 | `yf.download(<1 ticker>, period="max", auto_adjust=False, actions=True)` | Backfill shape: raw + adj close, splits, dividends |
| 5 | Yahoo rate behaviour | Run ~100 sequential chart calls at 1/s, then at 3/s: when do 429 / `YFRateLimitError` start? Use this to set the token-bucket rate |
| 6 | SEC `https://www.sec.gov/files/company_tickers.json` (with a `User-Agent: EconoSift <contact>` header) | Ticker → CIK map |
| 7 | SEC `https://data.sec.gov/api/xbrl/frames/us-gaap/{concept}/USD/CY2025Q2I.json` for Revenues, NetIncomeLoss, EarningsPerShareDiluted (unit `USD-per-shares`), StockholdersEquity, Assets, Liabilities, CashAndCashEquivalentsAtCarryingValue, plus `dei/EntityCommonStockSharesOutstanding` (unit `shares`) | Coverage of S&P 500 CIKs per concept; which concepts need fallbacks (e.g. `RevenueFromContractWithCustomerExcludingAssessedTax`) |
| 8 | SEC `https://data.sec.gov/api/xbrl/companyfacts/CIK##########.json` | Per-company fallback; includes the `filed` date (point-in-time) |
| 9 | SEC nightly `https://www.sec.gov/Archives/edgar/daily-index/xbrl/companyfacts.zip` | Size and download time; whether frames make it unnecessary |
| 10 | Treasury FiscalData `https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v2/accounting/od/avg_interest_rates?page[size]=1` and the daily par yield curve CSV at `https://home.treasury.gov/resource-center/data-chart-center/interest-rates/` | Keyless; same-day yields |
| 11 | BLS `https://api.bls.gov/publicAPI/v2/timeseries/data/CUUR0000SA0` (no key) | Keyless daily limit and response |
| 12 | Frankfurter, World Bank (`wbgapi`), ECB (`ecbdata`), BIS WS_CBPOL bulk CSV, DBnomics, Eurostat | Still working as currently used |
| 13 | IMF via `imfp` (WEO dataflow and indicator codes) | Still resolves after IMF's API change |
| 14 | OECD `https://sdmx.oecd.org/public/rest/...` | Only if a feature needs it; note the 20/hour download limit |
| 15 | Stooq `https://stooq.com/q/d/l/?s=aapl.us&i=d` with and without `&apikey=` | Confirms keyless access is gone and the free key works (optional fallback) |
| 16 | Tiingo / Alpaca free tiers | Only if the owner creates free keys; otherwise mark "optional, unverified" |

Also check whether `pyarrow` can be dropped once the Parquet files are gone.

## 8. Verification results

_Phase 65.0, run 2026-10-15 between 05:20 and 06:10 UTC (01:20–02:10 ET, US market closed) from the
owner's machine. yfinance 1.5.1 (local; `requirements.txt` only pins `>=0.2.40`, so Phase 66 raises
the floor to the tested version). Universe = 503 S&P 500 + 101 NDX + 30 Dow = **518 unique
symbols** (the app's own `constituents.py`). Throwaway scripts; nothing committed._

### 8.0 Summary

| # | Check | Result |
|---|---|---|
| 1 | `yf.screen` bulk quotes | ✅ **5 calls → 518/518** with an exchange filter (§8.1). Chosen snapshot mechanism |
| 2 | yfinance `WebSocket` | ⚠️ connects and streams (17 symbols in 90 s, overnight session); price/change/time only, no OHLC/volume. Not tested in regular hours. **Dropped**: not needed |
| 3 | `yf.download` 15m × 50 | ✅ 13.5 s, 26 bars × 50 tickers, NY tz, no 429. Kept as the fallback |
| 4 | `yf.download` `period="max"`, `actions=True` | ✅ AAPL 0.7 s, 11,552 rows from 1980-12-12; Open/High/Low/Close/Adj Close/Volume/Dividends/Stock Splits; splits 2005/2014/2020 present. 20 tickers × 10y = 5.5 s |
| 5 | Yahoo rate | ✅ 100 chart calls at 1/s **and** 100 at 3/s: no 429; latency p50 0.14 s, p95 0.32 s. 20 `.info` calls at 1 per 1.5 s: clean, p50 0.29 s, 184 keys. → bucket **2/s, burst 4** |
| 6 | SEC `company_tickers.json` | ✅ 10,451 tickers, 0.7 s; **503/503 S&P 500 resolve** (dash form, e.g. `BRK-B`) |
| 7 | SEC `frames` | ✅ ~0.4 s, 300–800 KB per call; coverage per concept below; **rows have no `filed` date** |
| 8 | SEC `companyfacts` | ✅ 0.3–0.9 s, 3.7–4.8 MB per company; facts carry `start, end, val, accn, fy, fp, form, filed, frame` |
| 9 | SEC `companyfacts.zip` | ❌ **1.4 GB**: dropped. Frames + per-company facts cover the need |
| 10 | Treasury | ✅ keyless. Par yield CSV and real yield CSV (`daily-treasury-rates.csv/2026/all?type=daily_treasury_yield_curve` / `…real_yield_curve`) had 10/14 data at 01:20 ET on 10/15. FiscalData `avg_interest_rates` works (monthly, last 2026-09-30) |
| 11 | BLS v2 keyless | ✅ `CUUR0000SA0` to 2026-M09. Limits are BLS's documented unregistered caps (25 queries/day); not measured |
| 12 | Frankfurter, World Bank, ECB, BIS, Eurostat, DBnomics | ✅ Frankfurter (`.app` and `.dev/v1`), `wbgapi`, `ecbdata`, BIS WS_CBPOL CSV and Eurostat all work. ⚠️ DBnomics works, but the app's paths are stale (§8.5) |
| 13 | IMF via `imfp` | ✅ resolves (`WEO`, plus `WEO_2026_APR_VINTAGE`), but **28 s per call**, and `start_year`/`end_year` didn't trim (data came back through 2031). DataMapper `/indicators/{code}` (used by `bulk_data_service`) ✅ 200; the per-country `?periods=` path gives 403 |
| 14 | OECD SDMX | ✅ reachable (dataflow query). Not used by any planned feature |
| 15 | Stooq | ❌ keyless now returns a JavaScript bot-check page. Keyed access unverified (no key). Not used by the app |
| 16 | Tiingo / Alpaca | ⏸ optional, unverified (no keys) |
| — | `pyarrow` drop | ❌ not possible: `edgartools` requires it (§8.6) |

### 8.1 Snapshot: `yf.screen`

- `EquityQuery("and", [is-in exchange NMS,NYQ,NGM,NCM,ASE,BTS,PCX], gt intradaymarketcap 4e9)`,
  `sortField="intradaymarketcap"`, `size=250`: total 1,598 matches; members covered after each page
  178 → 335 → 457 → 507 → **518**. The smallest member cap was $9.1B (APTV), so the floor has room.
- `region = us` with a $5B floor: 3,471 matches, 10 calls, still missing AOS, ARE, MGM, MOS, NCLH,
  PNR and WYNN. Don't use it.
- Fields on all 518 covered rows: `regularMarketPrice, regularMarketOpen, regularMarketDayHigh,
  regularMarketDayLow, regularMarketVolume, marketCap`; `trailingPE` 485/518. Also present:
  `regularMarketChange(Percent), regularMarketPreviousClose, regularMarketTime` (epoch s),
  `sharesOutstanding, forwardPE, epsTrailingTwelveMonths, priceToBook, dividendYield,
  fiftyTwoWeekHigh/Low, averageDailyVolume3Month/10Day, fiftyDayAverage, earningsTimestamp,
  averageAnalystRating, exchange, currency, marketState`. 89 keys per row. Treat each as optional.
- `EquityQuery` has no `ticker` field, so a list of symbols can't be screened directly. The fill-in
  for a missing member is a per-ticker chart call.

### 8.2 Rate limits (Yahoo, SEC)

- Yahoo: no 429 in 200 sequential chart calls up to 3/s, nor in 20 `.info` calls. The 429 storms the
  app sees come from volume (thousands of `.info` calls at boot), not from per-second rate. Set the
  bucket to **2/s, burst 4**, with exponential backoff and the circuit breaker on any 429. Don't
  probe higher rates: the first 429 can lead to a long IP block.
- SEC: ~35 calls at ≤5/s with the owner's `EDGAR_IDENTITY` as the User-Agent: no throttling. Keep 5/s.

### 8.3 SEC coverage (S&P 500, 503 CIKs)

Frames coverage per concept (duration `CY2025Q2`, instant `CY2025Q2I`):

| Concept | S&P 500 hits | Fallback chain |
|---|---|---|
| Revenue | 217 `Revenues` | + `RevenueFromContractWithCustomerExcludingAssessedTax` → 433, + `RevenuesNetOfInterestExpense` → 437, + `InterestAndDividendIncomeOperating` → 441, + `RevenueFromContractWithCustomerIncludingAssessedTax` → 460, + `InterestIncomeExpenseNet` → 461, + `RegulatedAndUnregulatedOperatingRevenue` → **463** |
| NetIncomeLoss | 431 | — |
| EarningsPerShareDiluted (`USD-per-shares`) | 447 | — |
| StockholdersEquity | 462 | — |
| Assets | 494 | — |
| Liabilities | **355** | derive `LiabilitiesAndStockholdersEquity` (494) − `StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest` (or `StockholdersEquity`), and label it derived |
| CashAndCashEquivalentsAtCarryingValue | 416 | `CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents` 467 |
| dei `EntityCommonStockSharesOutstanding` | 445 | + us-gaap `CommonStockSharesOutstanding` → 456; then Yahoo `sharesOutstanding` from the snapshot |

- **The remaining ~37 revenue misses are mostly off-calendar fiscal years** (MSFT, ORCL, COST,
  CSCO, PG, NKE, FDX, ADP, INTU…). Their fiscal Q4 is only reported inside the 10-K's annual
  figure, so no quarterly frame exists. Fix: from `companyfacts`, Q4 = FY − (Q1+Q2+Q3), or use
  TTM/annual values. That is a computation from filed numbers, not an estimate.
- Frames lag filings. `NetIncomeLoss` had 439 hits for CY2026Q1 but only 404 for CY2026Q2 (late
  filers), and 108 for CY2025Q4 (Q4 sits inside 10-Ks). So read the latest *available* fact per
  company rather than one fixed frame.
- **Ingest design (replaces the plan's "frames for everything"):**
  1. Backfill: `companyfacts` for every CIK. ~520 calls at 5/s ≈ 2–4 min, ~2 GB uncompressed,
     with `filed` dates (point-in-time).
  2. Nightly: ~10 frames calls for the latest periods. Any CIK whose `accn` changed gets its
     `companyfacts` re-fetched. Usually a handful a night; ~100 per day in earnings season.

### 8.4 Treasury / BLS (keyless backups)

- Treasury's daily par and real yield CSVs are a usable keyless backup for FRED yields (FRED keeps
  working with the owner's key). The previous trading day's row is there by early morning ET.
- BLS keyless works, but 25 queries/day is too tight for routine use. Keep FRED as primary.

### 8.5 Pre-existing data issues found (not part of this refactor)

- `sources/source_dbnomics.py` paths are stale. `OECD/MEI/…LRHUTTTT` ends **2024-01**,
  `OECD/QNA/…B1_GE` ends **2023-Q4** (OECD retired MEI/QNA), and `BIS/cbpol/{iso2}:PP:M` → **404**.
  This is only a fallback tier (BIS is fetched directly first), but it serves 2–3-year-old data
  when reached. Flagged for `ACTIVE_ISSUES.md`. Phase 66 writes whatever the macro jobs fetch into
  `macro_series` with its real date, so stale points show their true `asOf`.
- `imfp` takes 28 s per call. Fetching it in a background job into `macro_series` (Phase 66) takes
  it off the request path.

### 8.6 `pyarrow`

`pip show edgartools` (5.62.0) lists `pyarrow` in `Requires`. Direct uses in the app are wider than
§0 assumed: `bulk_data_service.py` (WB/IMF/FF Parquet), `regime_service.py`, `insider_dataset.py`
(Form 4 trades) and `thirteenf_service.py` (13F holders, read with `filters=` predicate pushdown).
**Plan change:** the price and macro Parquet files still move into `econosift.db` (Phase 66). The
insider and 13F datasets move too, as indexed tables keyed on cusip/quarter, so the "one database"
decision holds. `pyarrow` stays in `requirements.txt` because edgartools needs it.

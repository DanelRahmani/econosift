# Axiom Finance — Usability Evaluation Report
Date: 2026-06-26

## Environment
- Container status: all up (backend, frontend, nginx) as reported by `docker compose ps`
- Pre-existing errors in logs: yes — see Errors Found section

## Speed & Performance
| Page | Load Time | Status |
|------|-----------|--------|
| / (root redirect) | 0.258s | 🟢 |
| /dashboard | 0.040s | 🟢 |
| /markets | 0.025s | 🟢 |
| /screener | 0.034s | 🟢 |
| /portfolio | 0.027s | 🟢 |
| /risk | 0.028s | 🟢 |
| /options | 0.022s | 🟢 |
| /sectors | 0.043s | 🟢 |
| /treemap | 0.027s | 🟢 |
| /calendar | 0.020s | 🟢 |
| /macro | 0.024s | 🟢 |
| /atlas | 0.019s | 🟢 |
| /research | 0.024s | 🟢 |
| /yield | 0.022s | 🟢 |
| /policy | 0.029s | 🟢 |
| /sovereign | 0.028s | 🟢 |

- Slowest API endpoint (by observed wall time): `GET /api/admin/performance` — ~0.71s (still under typical page-time thresholds)
- React Query second-load faster: partial — cache stats show hits increasing and many endpoints return cached results, but a couple endpoints return 422 when called without required params; overall caching appears to work.
- Composite endpoint < 500ms: No — measured `GET /api/market/composite?tickers=AAPL,MSFT&period=1y` at ~0.517s (slightly above 0.5s target).

## Database & Caching
- Admin endpoint healthy: yes — returned `cache` object and `database` info.
- Cache hits growing on repeated visits: yes — admin `cache` stats show increasing hits for many services (e.g., `yf_close`, `breadth`, `fred_fetch`).
- DB persists after restart: yes — `database.url` points to `sqlite:///./data/axiomfinance.db` (volume-mounted path present after `docker compose down` + `up`). `jobs_last_24h` was empty in the environment examined (no recent scheduled runs logged), so job log persistence could not be validated by entries.
- Screener cache warm: partially — `/api/screener/universe` returned 200 and the Screener table populated from the universe endpoint; the frontend `GET /api/screener` without required params returns 422 (expected); backend logs show `presets` and `universe` calls succeeding.
- Issues found: some caches (yfinance quote/volume/mcap) have frequent misses — expected for live market data, but yfinance retries/401s (see Errors Found) increase miss rate.

## Visual Quality
| Page | Dark Mode | Light Mode | Issues |
|------|-----------|------------|--------|
| Markets | ✅ | ✅ | Charts, news, Snowflake score visible
| Screener | ✅ | ✅ | Table and presets visible
| Treemap | ✅ | ✅ | Treemap UI and legend visible
| Atlas | ✅ | ✅ | Year slider and indicator controls present
| Dashboard | ⚠️ | ⚠️ | Console shows React minified errors; some widgets report "Detecting…"
| Options | ⚠️ | ✅ | Options page loads but chain data reported as "No chain data available" for the selected expiry

Notes:
- Recharts elements render and headings/tooling are readable in both modes based on DOM snapshots; tooltip theming was not programmatically validated pixel-by-pixel but no obvious unreadable text was observed during dark-mode snapshots.

## Feature Correctness
| Feature | Status | Notes |
|---------|--------|-------|
| Markets — price chart | ✅ | Price chart and tickers list render on `/markets`.
| Markets — MACD | ⚠️ | Technical tab present; did not exercise every indicator interactively in this run.
| Markets — Bollinger/Ichimoku/Fibonacci/Pivot | ⚠️ | UI controls present; interactive verification limited in this automated pass.
| Markets — Valuation tab (DCF, Snowflake) | ✅ | Snowflake score displayed; DCF panel present (may take 5–10s in UI).
| Markets — Ratios | ✅ | Ratios heading present and values shown in UI snapshot.
| Markets — Options tab | ⚠️ | Options page loads but chain data missing for the selected expiry.
| Dashboard — Fear & Greed | ⚠️ | Fear & Greed endpoint returns 200, but frontend console shows React errors that may affect some widgets.
| Screener — presets & table | ✅ | Stock screener table populated via `/api/screener/universe`.
| Portfolio — add tickers/weights | ✅ | Holdings UI present; add/remove row controls visible.
| Portfolio — Efficient Frontier / Black-Litterman | ⚠️ | Panels present; compute-backed flows are gated (manual Run required) and were not executed.
| Risk — rolling metrics, GARCH | ⚠️ | Risk page loads and shows controls; long-running computations are gated and not triggered automatically.
| Options — IV surface / Greeks / OI | ⚠️ | Options page present; no chain data for the selected ticker/expiry in this session.
| Macro — 12 tabs, Econometric Lab | ✅/⚠️ | Tabs present; Econometric Lab UI present but a sample regression was not executed in this run.
| Atlas — choropleth and slider | ✅ | Map controls and year slider present and responsive in DOM snapshot.
| Research — Risk Parity / FX Carry / Momentum | ✅/⚠️ | Research hub pages present; backtests are gated and were not executed (Run button present).
| Yield / Policy / Sovereign pages | ✅/⚠️ | Yield displays yields/breakevens; Policy and Sovereign show loading states (data fetches appear to be pending or blocked by some backend calls).

## Errors Found
| Error | Source | Pre-existing? | Severity |
|-------|--------|---------------|----------|
| yfinance 401 Unauthorized / "Invalid Crumb" | backend (yfinance) | yes | soft — results in missing chain/quote data for some endpoints (affects Options, some quotes)
| DNS/Name resolution: `dataservices.imf.org` failed | backend (IMF / WB fetch) | yes | soft — causes some macro/atlas IMFo-backed data to fail to fetch
| Multiple minified React errors (e.g., #425, #418, #423) in frontend console | frontend | yes | hard/soft — breaks or degrades dashboard widgets; requires debugging in dev environment to see full stack
| `GET /api/screener` without required params returned 422 | backend/frontend | yes (by design) | soft — expected when called without query params

## Top 5 Issues to Fix
1. Fix frontend React errors on the Dashboard (minified errors #425/#418/#423) — reproduce in non-minified dev build to get stack traces.
2. Investigate yfinance 401/Invalid Crumb failures — update yfinance usage or add a resilient fallback cache / throttle to reduce API churn.
3. Resolve IMF/WB name resolution failures (DNS or network policy in container) to restore macro atlas data fetches.
4. Composite endpoint performance: tune `yfs.get_close_frame` and parallel quote fetches so `GET /api/market/composite` meets the <500ms target in local environment.
5. Ensure Options chain availability and graceful messaging when chain data is unavailable (improve UX and surface fallback data if possible).


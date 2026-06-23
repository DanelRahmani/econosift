# Axiom Finance — Claude Code Execution Plan

## Stack
- **Backend**: Python FastAPI
- **Frontend**: Next.js (TypeScript, React)
- **Data**: All free — yfinance (primary), FRED (fredapi), Eurostat, World Bank, OECD, IMF WEO, Finnhub (free tier), FinanceDatabase, Wikipedia MediaWiki API, CFTC (direct file download), SEC EDGAR (edgartools), NY Fed (direct file download)
- **Cost**: $0 — no paid APIs, no web scraping
- **Rule**: Only use free APIs, pip-installable libraries, or direct structured file downloads (CSV/Excel/ZIP from stable government/institutional URLs). No HTML scraping of any kind.

---

## Phase Map
Execute phases in order. Phase 0 unblocks user trust; Phases 1–10 build out the platform.

| Phase | Feature | Priority |
|---|---|---|
| 0 | Critical Bug Fixes | Immediate |
| 1 | Valuation Engine (8 models) | High |
| 2 | Market Breadth & Dashboard | High |
| 3 | S&P 500 Treemap | High |
| 4 | Economic Calendar | Medium |
| 5 | Screener Overhaul | Medium |
| 6 | Rolling Quantitative Metrics | Medium |
| 7 | Options & IV Module | Medium |
| 8 | Macro Expansion | Medium |
| 9 | Snowflake Composite Score | Low |
| 10 | Sector Performance Charts | Low |

---

## Index Constituent Lists — Wikipedia MediaWiki API

All index constituent lists (S&P 500, Nasdaq 100, Dow 30) are fetched via the **Wikipedia MediaWiki Action API** — a free, structured JSON API, not HTML scraping.

**Method**:
1. Call the MediaWiki API with `action=parse&prop=wikitext&page=<page_title>&format=json` to retrieve raw wikitext for the relevant Wikipedia article.
2. Parse the wikitext tables using `wikitextparser` (`pip install wikitextparser`) to extract structured rows (ticker, company name, sector, industry, date added etc.).
3. Cache results weekly — index compositions change infrequently (~4× per year for S&P 500, less for others).

**Wikipedia page titles**:
- S&P 500: `"List of S&P 500 companies"`
- Nasdaq 100: `"Nasdaq-100"`
- Dow 30: `"Dow Jones Industrial Average"`

**API endpoint**: `https://en.wikipedia.org/w/api.php?action=parse&prop=wikitext&page={title}&format=json`

**Example** (Python):
```python
import requests, wikitextparser as wtp

def fetch_sp500_constituents():
    url = "https://en.wikipedia.org/w/api.php"
    params = {"action": "parse", "prop": "wikitext", "page": "List of S&P 500 companies", "format": "json"}
    r = requests.get(url, params=params, headers={"User-Agent": "AxiomFinance/1.0"})
    wikitext = r.json()["parse"]["wikitext"]["*"]
    parsed = wtp.parse(wikitext)
    table = parsed.tables[0]  # first table = current constituents
    return table.data()  # list of lists
```

This is a **JSON API call** — `requests` fetches JSON, `wikitextparser` parses wikitext syntax. No HTML is parsed at any point.

---

## Phase 0 — Bug Fixes (Do First)

**0.1 Valuation Tab — DCF panel is blank**
Two-stage DCF using slider inputs (Risk-Free Rate, Market Premium, FCF Growth, Terminal Growth). Fetch TTM FCF and shares outstanding from `yfinance`. Output: intrinsic value per share, Bear/Base/Bull scenario table, 7×7 sensitivity heatmap (FCF Growth vs WACC), colour-coded by upside/downside vs current price.

**0.2 Macro Tab — FX Rates panel empty**
Fetch 15+ major currency pairs via yfinance (`EURUSD=X` format). Show current rate, 1D/1W/1M/1Y change %, 30-day sparkline per pair. Add base currency switcher (USD/EUR/GBP).

**0.3 Macro Tab — Regime Classifier stuck on "Detecting..."**
Implement 2×2 Goldilocks matrix: GDP trend (FRED `GDPC1`) × CPI trend (FRED `CPIAUCSL`) → Goldilocks / Reflation / Stagflation / Recession. Also for Eurozone (Eurostat API) and Japan (OECD.Stat API). Output: 4-quadrant scatter, animated dot, regime badge, time scrubber from 2000.

**Data lag note**: Eurozone and Japan GDP/CPI are released 6–8 weeks after the reference period. The animated dot always reflects the latest *available* data period — label it "as of [latest available quarter/month]", never imply live data for non-US regions.

---

## Phase 1 — Valuation Engine

**Architecture**: Single `CountrySelector` at top of Valuation tab auto-detects stock's listing country from Yahoo exchange code, fetches live 10Y government bond yield (FRED), applies Damodaran Jan 2026 ERP (store in `backend/data/damodaran_erp_2026.json`), computes WACC. All 8 models share these rates.

**8 Valuation Models** (each as an expandable card in a 2×4 grid):

1. **DCF (Two-Stage)** — 10-year FCF projection + terminal value. Heatmap + scenario table.
2. **DDM (Gordon Growth)** — `P₀ = D₁ / (r − g)`. Only render if `dividendRate > 0`, else grey locked card.
3. **Graham Formula** — `V* = EPS × (8.5 + 2g) × 4.4 / Y`. Y = live AAA yield from FRED series `AAA`. `g` is a whole number (e.g. 8 for 8% growth).
4. **Graham Number** — `√(22.5 × EPS × BVPS)`. Requires EPS > 0 and BVPS > 0. 22.5 = Graham's max P/E (15) × max P/B (1.5).
5. **Peter Lynch / PEG** — Fair value = `EPS × growth_rate` where `growth_rate` is a whole number (e.g. 15 for 15%). Cap at 20. PEG = `(P/E) / growth_rate`. PEG verdict badge.
6. **EV/EBITDA Comps** — Static `sector_multiples.json` (Damodaran-sourced) is the **primary** source for sector median multiples. Live peer fetch via FinanceDatabase is an optional enhancement only — never block rendering on it. Not applicable for Financials sector.
7. **Residual Income (RIM)** — `Intrinsic Value = BVPS + PV(RI stream)`. ROE sourced first from `Ticker.info["returnOnEquity"]`; if `None`, compute manually as `net_income / avg(equity_t, equity_t-1)` from `Ticker.financials` and `Ticker.balance_sheet`. If neither available, lock the card with explanation. Best for banks/REITs.
8. **EPV (Earnings Power Value)** — `EPV (firm) = Adjusted NOPAT / WACC`. Per-share: `(EPV − net debt) / shares outstanding`. Net debt = total debt − cash.

**Axiom Fair Value** (Phase 1.9): Weighted composite of applicable models (DCF 30%, Comps 20%, RIM 15%, EPV 15%, Graham Formula 10%, Lynch 5%, DDM 5%). Verdict: Significantly Under/Modestly Under/Fair/Modestly Over/Significantly Overvalued. Gauge + needle at top of tab.

**Stock page KPI additions** (alongside price/market cap row):
- **EV/FCF** — `Ticker.info["enterpriseValue"]` / TTM FCF from `Ticker.cashflow`.
- **FCF Yield** — `(TTM FCF / shares outstanding) / price`. Display as %.
- **Short Float %** — `Ticker.info["shortPercentOfFloat"]`. Colour: >20% red, 10–20% orange, <10% neutral. `N/A` if `None` (common for non-US).
- **Short Ratio** — `Ticker.info["shortRatio"]` (days to cover). `N/A` if `None`.
- **Earnings Revision** — `Ticker.earnings_forecasts` (yfinance ≥0.2.28). Guard with `hasattr` + version check. Compare current EPS mean estimate to 30/60/90 days ago; display ↑ / ↓ / ↔ badge. `N/A` if unavailable.
- **ROIC** — `NOPAT / (total equity + total debt − cash)`. NOPAT = `EBIT × (1 − effective_tax_rate)`. From `Ticker.financials` and `Ticker.balance_sheet`. `N/A` if any input is missing.

**Key files to create:**
- `backend/routes/valuation.py`
- `backend/services/valuation_engine.py`
- `backend/services/discount_rates.py`
- `backend/services/peer_fetcher.py`
- `backend/data/damodaran_erp_2026.json`
- `backend/data/sector_multiples.json`
- `frontend/app/markets/tabs/Valuation.tsx`
- `frontend/components/valuation/` (CountrySelector, CompositePanel, ValuationGauge, ModelCard, SensitivityHeatmap, ScenarioTable, WarningFlags)

---

## Phase 2 — Market Breadth & Dashboard

**2.1 Breadth Bar** — S&P 500 constituent list fetched via the Wikipedia MediaWiki API (see "Index Constituent Lists" section above), cached weekly. Batch-download 1Y daily prices via `yf.download()` in chunks of 100. Compute: Advancing/Declining, New Highs/Lows, % Above SMA50, % Above SMA200, McClellan Oscillator, Cumulative A/D Line. Display as segmented bars, sticky at top of Markets page.

**McClellan Oscillator formula** — Ratio-adjusted version:
- RANA = `(Advances − Declines) / (Advances + Declines)`
- McClellan Oscillator = `19-day EMA of RANA − 39-day EMA of RANA`
- 19-day EMA multiplier = 0.10; 39-day EMA multiplier = 0.05

**Cumulative A/D Line** — Running cumulative sum of daily (Advances − Declines), 3-year lookback. Plot as time-series overlaid with S&P 500 price. Divergence (index new high but A/D not confirming) is a warning signal. Computed entirely from the existing constituent price cache — no additional data source.

**2.2 Global Indices Table** — ~25 indices via yfinance (`^GSPC`, `^GDAXI`, `^N225` etc.). Price, 1D%, 5-day sparkline, 1M%, YTD%. Region tabs, sortable columns.

**2.3 Fear & Greed Index** — 7 signals scored 0–100, averaged:
1. S&P 500 vs 125-day SMA (z-score normalised)
2. New 52W Highs vs Lows ratio (from constituent cache)
3. **McClellan Summation Index** (cumulative sum of ratio-adjusted McClellan Oscillator, percentile-ranked over 2Y lookback)
4. Put/Call Ratio — SPY options chain from yfinance (`yf.Ticker("SPY").option_chain(nearest_expiry)`), aggregate put OI / call OI. Secondary: FRED `CBOE/PUTCALL` if available. Inverted.
5. VIX (`^VIX`, inverted percentile over 2Y lookback)
6. Stocks vs Bonds relative return (`^GSPC` vs `TLT`, 20-day rolling)
7. HY Credit Spread (FRED `BAMLH0A0HYM2`, inverted)

Verdicts: 0–20 Extreme Fear → 80–100 Extreme Greed. Speedometer gauge, 90-day history chart, signal breakdown panel.

**2.4 Dashboard Page** — New route `/dashboard` as default landing page. Layout: Breadth Bar → 3-column header (Fear&Greed / Session status / Regime badge) → Global Indices Table → Yield Curve + Top Movers → Sector bars → Mini calendar strip.

**2.5 Top Movers** — From constituent cache: Top 5 Gainers, Losers, Unusual Volume (>2× avg), 52W Highs/Lows. Tabbed compact table on dashboard.

---

## Phase 3 — S&P 500 Treemap

Hierarchical JSON: S&P 500 → Sector → Industry → Stock. Constituent list fetched via Wikipedia MediaWiki API (cached weekly). Rectangle area = log(market cap), colour = daily return % on red-white-green diverging scale (−5% deep red, 0% white, +5% deep green).

Rendering: `d3-hierarchy` squarified treemap for layout; React renders SVG rects. Hover tooltip (name, price, 1D%, mkt cap, P/E, 52W range). Click stock → navigate to Markets tab. Click sector → drill down.

Controls: Period selector (1D/1W/1M/3M/YTD/1Y), Index selector (S&P 500/Nasdaq 100/Dow 30), Group by (Sector/Industry), Colour by (Return/Mkt Cap/Volume).

Replace existing Sectors tab heatmap with treemap as primary view. Embed compact non-interactive version on Dashboard.

---

## Phase 4 — Economic Calendar

Route `/calendar`. Sub-tabs: Economic / Earnings / Dividends / IPO.

**Data sources:**
- **Macro events**: Finnhub `/calendar/economic` (primary — returns event name, date, actual, forecast, previous for all major economies). Supplement with FRED release calendar for US-specific events.
- **Central bank meeting dates**: Store in `backend/data/cb_meetings.json` (FOMC, ECB, BOE, BOJ etc.), updated manually twice a year.
- **Earnings**: `yf.Ticker(t).calendar` + Finnhub `/calendar/earnings`. Run as overnight background cron with `ThreadPoolExecutor(max_workers=10)` — never on-demand.
- **Dividends**: `yf.Ticker(t).info["exDividendDate"]` batch computed in same overnight cron.
- **IPO**: Finnhub `/calendar/ipo`.

**UX**: Weekly grid Mon–Sun, today highlighted. Filter by impact (★★★/★★/★), country, category, timezone. Actual vs Consensus colouring (green = beat, red = miss). Countdown timers for events within 24h.

**High-impact events** (hardcode impact=3 in `event_impact.json`):
- US: NFP, CPI, Core PCE, GDP advance, Retail Sales, FOMC Decision, ISM PMI (via Finnhub calendar), Weekly Jobless Claims
- EU: ECB Rate Decision, Eurozone CPI Flash, Eurozone GDP
- UK: BOE Decision, UK CPI, UK GDP
- JP: BOJ Decision, Japan CPI

---

## Phase 5 — Screener Overhaul

**Universes**:
- S&P 500 — Wikipedia MediaWiki API (`"List of S&P 500 companies"`) parsed with `wikitextparser`, cached weekly
- Nasdaq 100 — Wikipedia MediaWiki API (`"Nasdaq-100"`) parsed with `wikitextparser`, cached weekly
- Dow 30 — Wikipedia MediaWiki API (`"Dow Jones Industrial Average"`) parsed with `wikitextparser`, cached weekly
- Small-Cap proxy — FinanceDatabase `Equities().select(country="United States")` filtered by market cap <$2B. Label as "Small-Cap Universe (~3,000–5,000 tickers)", **not** "Russell 2000", as results include OTC stocks and are approximate.
- Custom — manual ticker entry.

**Pipeline**: Overnight cron — fetch constituent list via Wikipedia MediaWiki API → batch-fetch fundamentals from yfinance → cache in Parquet/SQLite. Price metrics refresh daily; fundamentals weekly. Run with `ThreadPoolExecutor(max_workers=10)`.

**Screener columns** (in addition to standard P/E, P/B, EV/EBITDA):
- Short Float % — `Ticker.info["shortPercentOfFloat"]` (US only; `None` for most non-US)
- Short Ratio — `Ticker.info["shortRatio"]`
- ROIC — computed (see Phase 1 definition); `N/A` if inputs missing
- FCF Yield — computed
- EV/FCF — computed
- Earnings Revision 30D — `Ticker.earnings_forecasts` (guarded with `hasattr`)

**Preset Signal Pills**:
- Price Action: Top Gainers, Biggest Losers, New 52W High/Low, Above/Below SMA200, Golden/Death Cross
- Volume: Unusual Volume (>2× avg), Overbought (RSI>70), Oversold (RSI<30), High Beta
- Fundamentals: Undervalued, High Dividend, High ROIC, Quality Growth, Deep Value, High Short Interest (>20% float)
- Situations: Earnings This Week, Post-Earnings, Pre-Earnings Dip, Insider Buying (Form 4 code-P transactions in last 30 days)

**Result View Tabs**: Overview | Performance | Technicals | Valuation | Profitability | Dividends | Financials | Balance Sheet | All Columns. Sortable, CSV-exportable.

**Charts View**: Gallery of 200×120px sparkline thumbnails (last 3M closes + SMA50). Canvas-based rendering.

---

## Phase 6 — Rolling Quantitative Metrics

Rolling Metrics section on Risk tab. Window selector: 20D / 60D (default) / 120D / 252D.

**Metrics** (3Y history):
- Rolling Sharpe Ratio (annualised, FRED `DGS10` as risk-free rate)
- Rolling Volatility (stddev × √252)
- Rolling Beta (vs `^GSPC`)
- Rolling Sortino Ratio
- Rolling Max Drawdown (filled area)
- Rolling Correlation (between selected ticker pairs)
- Rolling VaR 95% and 99%

Two views: Overlay (all tickers, metric selector) and Grid (2×3).

---

## Phase 7 — Options Tab

**KPI Cards**: IV30, IV Rank, IV Percentile, Put/Call OI Ratio, Max Pain, Implied Earnings Move.

**IV Rank formula**: `(current_IV − min_IV_52w) / (max_IV_52w − min_IV_52w) × 100`

**IV30 interpolation**: Find the two expiries bracketing 30 DTE and linearly interpolate ATM IV. If fewer than 2 expiries bracket 30 DTE, fall back to nearest single expiry ATM IV and label as "nearest expiry IV" not "IV30".

**Charts**: IV Term Structure (ATM IV vs DTE, annotate earnings date) + IV Smile (IV vs moneyness 0.70–1.30).

**Chain Table**: Calls | strikes | puts. ITM rows tinted. OTM-only toggle. Synced expiry selector.

**OI Profile**: Horizontal bar chart, calls (green) right, puts (red) left. Max pain line annotated.

All data from `yf.Ticker(t).option_chain(expiry)`. IV is decimal (0.34 = 34%) — multiply by 100 for display. Label data as "delayed ~15min".

---

## Phase 8 — Macro Expansion

Reorganise Macro tab: Overview | Rates & Yields | Inflation | Growth & Employment | Commodities | FX | Leading Indicators | Positioning.

**Commodities**: ~25 via yfinance futures (CL=F, GC=F, HG=F, ZC=F etc.). Dr. Copper vs World Bank GDP, Gold/Oil ratio with FRED recession shading (`USREC`), Axiom Commodity Index.

**Rates & Yields sub-tab**:
- CB policy rates, yield curve spreads (2Y10Y, 3M10Y)
- TIPS/breakeven: FRED `T5YIE`, `T10YIE`
- Real yields: FRED `DFII10`
- **SOFR** (FRED `SOFR`) — benchmark overnight rate. Chart vs Fed Funds Rate (`FEDFUNDS`).
- **IG Credit Spread** (FRED `BAMLC0A0CM`) alongside HY spread (`BAMLH0A0HYM2`).
- **TED Spread proxy** — FRED `DTB3` minus FRED `SOFR`. Spikes = interbank funding stress.
- **Corporate bond yields by rating** — FRED BofA series: AAA (`BAMLC0A1CAAA`), AA (`BAMLC0A2CAA`), A (`BAMLC0A3CA`), BBB (`BAMLC0A4CBBB`), BB (`BAMLH0A1HYBB`), B (`BAMLH0A2HYB`). All on one chart.

**Growth & Employment sub-tab**:
- GDP, unemployment rate, NFP
- **Weekly Initial Jobless Claims** (FRED `ICSA`) — most frequent US labour signal. Chart with 4-week MA + recession shading.
- **Continuing Claims** (FRED `CCSA`)
- **M2 Money Supply** (FRED `M2SL`) — YoY growth rate, overlaid with CPI.
- **Sahm Rule** (FRED `SAHMREALTIME`) — threshold 0.50. Shade chart red when ≥ 0.50.

**Inflation sub-tab**:
- CPI (FRED `CPIAUCSL`), Core CPI (`CPILFESL`)
- **PCE** (FRED `PCEPI`) and Core PCE (`PCEPILFE`) — Fed's preferred gauge.
- **PPI** (FRED `PPIACO`)
- **5Y5Y Forward Inflation** (FRED `T5YIFR`)
- Breakeven: 5Y (`T5YIE`), 10Y (`T10YIE`)

**Leading Indicators sub-tab**:
- **Conference Board LEI** (FRED `USSLIND`) — flag when YoY change turns negative.
- **OECD CLI** — multi-country via OECD.Stat HTTP REST API (no key required). G7 + major EMs.
- **GSCPI** (NY Fed) — monthly Excel file downloaded directly from `https://www.newyorkfed.org/medialibrary/research/interactives/gscpi/downloads/gscpi_data.xlsx` via `pandas.read_excel`. Direct structured file download from a stable institutional URL. Values above 0 = above-average supply chain pressure. If URL returns 404, log warning and serve last cached value.
- **CFNAI** (FRED `CFNAI`) — values below −0.70 historically precede recessions.
- **ISM PMI** — historical data via FRED series `NAPM` (available through 2023); live/upcoming ISM Manufacturing and Services PMI readings via Finnhub `/calendar/economic` (provides actual, forecast, previous). Display as time series with 50-line expansion/contraction threshold; annotate the 2023 FRED data cutoff.

**FX sub-tab**: DXY (`DX-Y.NYB`), currency heatmap (grid of crosses, 1D change %), EM FX emphasis.

**Positioning sub-tab**:

**COT Report (Commitment of Traders)**
- Source: CFTC direct ZIP file downloads — `https://www.cftc.gov/dcom/files/dcotnoc.zip` (current year) and `https://www.cftc.gov/files/dea/history/deacot_1986_2016.zip` (historical). Direct structured file downloads from a US government URL — no scraping.
- Parse with `pandas.read_csv(skipinitialspace=True)`. Always `.strip()` all column names and string values — trailing spaces are endemic in CFTC files.
- Key contracts: S&P 500 E-mini (code 13874+), Nasdaq 100 E-mini (209742), EUR/USD (099741), Gold (088691), WTI Crude (067651), 10Y Treasury Note (043602).
- For each: chart net Non-Commercial (speculator) positioning over time.
- **COT Index** = `(current_net_spec − min_52w) / (max_52w − min_52w) × 100`. >80% = extreme speculator longs (contrarian bearish).

**SEC Form 4 Insider Trades**
- Source: SEC EDGAR REST API (free, no key required): `https://efts.sec.gov/LATEST/search-index?q="{ticker}"&forms=4&dateRange=custom&startdt={start}&enddt={end}`. JSON response — no HTML parsing.
- Filter: code `P` = open-market buy, code `S` = open-market sell. Exclude code `A` (RSU award — not discretionary).
- On stock pages: timeline chart overlaid on price (green arrow = buy, red = sell). Insider Buy/Sell ratio last 90 days as badge.
- In screener: "Insider Buying" preset = tickers with at least one code-P transaction in last 30 days.
- Rate limit: `time.sleep(0.15)` between EDGAR calls.

**SEC 13F Institutional Holdings**
- Source: `edgartools` library (`pip install edgartools`, free, no key). Queries SEC EDGAR JSON APIs under the hood — no HTML parsing. Usage: `from edgar import Company; Company(ticker).get_filings(form="13F-HR")`.
- For stock pages: top 10 institutional holders — fund name | shares | % of float | QoQ change | filing date.
- Label: "as of [quarter end] — 45-day reporting lag."
- Rate limit: `time.sleep(0.1)` between calls.

---

## Phase 9 — Snowflake Composite Score

Pentagon radar chart, 0–10 per axis, sector-normalised (percentile rank within sector peers from Phase 5 cache):

1. **Value** — P/E, EV/EBITDA, EV/FCF, FCF Yield, P/B, PEG
2. **Future Growth** — EPS growth estimate, revenue growth YoY, earnings revision 30D, R&D intensity
3. **Past Performance** — 3Y revenue CAGR, 3Y EPS CAGR, ROE avg, gross margin trend, price alpha vs sector
4. **Financial Health** — Altman Z-Score (>3.0 safe, 1.8–3.0 grey, <1.8 distress), ROIC vs WACC spread, interest coverage, current ratio, net cash, debt/equity
5. **Dividend** — Yield vs peers, payout ratio, 5Y CAGR, consistency, FCF coverage. Score 0 if no dividend.

Invert percentile for "lower = better" metrics. Fallback to industry → market-wide if <10 sector peers.

**Placement**: Overview tab (alongside price chart), screener Charts view thumbnail, Valuation tab next to Axiom Fair Value.

**Additional**: Rules-based verdict text + top 3 Rewards (✓) and top 3 Risks (⚠) from sub-metric scores.

Rendering: `recharts RadarChart`. Click axis → navigate to relevant tab.

---

## Phase 10 — Sector Performance Charts

11 SPDR ETFs (XLF, XLK, XLE, XLV, XLI, XLY, XLP, XLB, XLRE, XLC, XLU) from yfinance.

**Bar Charts**: 6 horizontal bar charts (1D, 1W, 1M, 3M, YTD, 1Y). Sorted by return per chart. S&P 500 reference line.

**Fundamentals Table**: Overview / Valuation / Performance / Volatility tabs. ETF prices + median constituent fundamentals from Phase 5 cache.

**Industry Drill-Down**: Click sector → industries (top-3 stocks by mkt cap per industry). Breadcrumb navigation → Screener filtered to industry.

**Sector Rotation Clock**: Sam Stovall 4-quadrant framework (Early/Mid/Late/Recession). Sectors placed canonically, sized/coloured by relative performance vs S&P 500. Implied phase from 3M ETF returns. Cross-validate with Phase 0.3 Regime Clock.

---

## Data Source Quick Reference

| Source | Install / Access | Key | Used For |
|---|---|---|---|
| yfinance | `pip install yfinance` | None | Prices, fundamentals, options, FX, commodities, short interest |
| FRED | `pip install fredapi` | Free key required | All macro series: yields, inflation, employment, credit, M2, Sahm, LEI etc. |
| Eurostat | `pip install eurostat` | None | EU GDP, HICP, unemployment |
| World Bank | `pip install wbdata` | None | Global GDP, debt, current account |
| OECD.Stat | HTTP REST API (no install) | None | CLI, MEI, Japan macro |
| IMF WEO | Direct Excel download (stable URL) | None | 190-country forecasts, debt (Apr/Oct) |
| Finnhub | `pip install finnhub-python` | Free key required | Earnings/IPO calendar, live ISM PMI event data |
| FinanceDatabase | `pip install financedatabase` | None | Small-cap universe construction, sector classification |
| Wikipedia MediaWiki API | `pip install wikitextparser` + `requests` | None | S&P 500, Nasdaq 100, Dow 30 constituent lists (JSON API + wikitext parse) |
| Damodaran | Direct Excel download (annual) | None | Country ERP, sector multiples |
| CFTC | Direct ZIP download (`cftc.gov`) | None | COT positioning data |
| SEC EDGAR | `pip install edgartools` | None | 13F institutional holdings, Form 4 insider trades |
| NY Fed | Direct Excel download (stable URL) | None | GSCPI (supply chain pressure) |

---

## Caching Strategy

| Frequency | What |
|---|---|
| Every 15min (market hours), hourly (off-hours) | Index prices, FX, commodities, VIX, S&P 500 constituent prices |
| Daily (11pm UTC) | Screener metrics, Fear & Greed, breadth stats + cumulative A/D, movers, options chains, sector ETFs, rolling risk, Snowflake scores |
| Weekly (Friday after 6pm ET) | COT report (CFTC releases Fridays), earnings calendar, constituent lists (Wikipedia MediaWiki API) |
| Weekly (Thursday) | Initial jobless claims (FRED `ICSA`) |
| Monthly | OECD CLI, Eurostat, FRED monthly series, World Bank, GSCPI (NY Fed Excel), M2, LEI, CFNAI |
| Quarterly | 13F institutional holdings (edgartools, 45-day lag) |
| Annually (Jan) | Damodaran ERP + multiples |
| Biannually (Apr/Oct) | IMF WEO |

Use `cachetools` for development, Redis for production. Cache key must include all relevant parameters (ticker, period, country). Expose `/api/admin/cache/clear` for manual invalidation.

---

## Notes for Claude Code
- **No web scraping** — never use `BeautifulSoup`, `requests` to parse HTML, `Selenium`, or any HTML parsing to extract data. All data must come from structured APIs, pip libraries, or direct file downloads (CSV/Excel/ZIP).
- **Wikipedia constituent lists** — use the MediaWiki Action API (`action=parse&prop=wikitext`) + `wikitextparser` to extract tables as structured data. This is a JSON API call, not HTML scraping.
- Always implement safe `.get()` with fallbacks on `yf.Ticker(t).info` — fields can return `None`
- Use `yf.download()` for batch price requests; never loop individual `Ticker()` calls for large universes
- Phase 9 (Snowflake) depends on Phase 5 universe cache — implement Phase 5 first
- For inapplicable valuation models, render a grey locked card with explanation — never hide it
- Sector normalisation in Phase 9: percentile rank within sector peers; invert for "lower = better" metrics
- yfinance IV is always decimal (0.34 = 34%) — multiply by 100 before displaying
- Peter Lynch growth rate and Graham Formula `g` are whole numbers (15 = 15%), not decimals
- EPV produces a firm-level value — subtract net debt and divide by shares outstanding for per-share output
- McClellan Oscillator: use ratio-adjusted net advances (RANA), not raw advances − declines
- Form 4 codes: `P` = open-market buy, `S` = open-market sell, `A` = award (exclude)
- edgartools calls: `time.sleep(0.1)` between requests
- CFTC COT CSV: always `.strip()` all column names and string values on load
- GSCPI: direct Excel URL `https://www.newyorkfed.org/medialibrary/research/interactives/gscpi/downloads/gscpi_data.xlsx` — use `pandas.read_excel`; if 404, log and serve last cached value
- ISM PMI: use FRED `NAPM` for historical data through 2023; live readings via Finnhub calendar only
- Sahm Rule: shade chart red when `SAHMREALTIME ≥ 0.50`
- EV/EBITDA Comps: static `sector_multiples.json` is primary; live FinanceDatabase peer fetch is optional only
- RIM: if `Ticker.info["returnOnEquity"]` is `None`, compute from financials; if still unavailable, lock the card
- `Ticker.earnings_forecasts` requires yfinance ≥0.2.28 — guard with `hasattr` and version check
- Small-cap screener universe: label "Small-Cap Universe (~3,000–5,000 tickers)", not "Russell 2000"
- Eurozone/Japan macro data lags 6–8 weeks — label "as of [latest available period]"
- 13F holdings: label "as of [quarter end] — 45-day reporting lag"
- All financial data must display its "as of" date
- Options data: label "delayed ~15min"

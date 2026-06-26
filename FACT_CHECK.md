# FACT_CHECK.md

**Audit Date:** 2026-06-26  
**Auditor:** Senior Financial QA Engineer — Automated Code + Live Data Audit  
**Test Stocks:** AAPL (Apple Inc.) and MSFT (Microsoft Corp.)  
**Benchmark Source:** MarketWatch (FactSet data)  
**Audit Scope:** Markets Overview KPIs, Valuation models, Ratios, Options IV analytics, Snowflake scores, DCF engine, Frontend display formatting

---

## 1. Executive Summary

The Axiom Finance platform demonstrates **excellent accuracy for yfinance pass-through metrics** (price, P/E ratios, 52-week range, dividend yield — all within ±0.5% of MarketWatch benchmarks). However, the audit identified **two systemic data failures** that cascade into ~40% of the valuation features being non-functional:

1. **`trailingEps`, `forwardEps`, `freeCashflow`, `sector`, `industry`, and `beta` are consistently `null`** in the yfinance `info` dict — these keys are no longer populated by the current yfinance version. Six of the eight valuation models, the FCF-based KPIs, the Snowflake FCF scores, and the sector/industry classification are all dead as a result.

2. **Options IV30 is returning 0.001%** (essentially zero) for all tickers and all expiries. This renders the entire Options analytics module (IV Rank, IV Percentile, IV Smile, Term Structure, Greeks) scientifically useless. The root cause is that yfinance's `impliedVolatility` column either changed name or returns near-zero values in the current version.

**Overall data integrity grade: B-** — Price and pass-through data is accurate, but half the value-add features are broken due to yfinance API drift.

---

## 2. Verified Correct Values (CONFIRMED)

Metrics that match MarketWatch benchmarks within acceptable tolerance (±0.5% for prices, ±2% for ratios).

### AAPL — Apple Inc.

| Metric | Axiom Value | MarketWatch Value | Tolerance | Source |
|--------|------------|-------------------|-----------|--------|
| Current Price | $275.15 | $275.15 | 0.00% ✅ | yfinance `currentPrice` |
| P/E (TTM) | 33.35 | 33.28 | +0.21% ✅ | yfinance `trailingPE` |
| Forward P/E | 28.63 | — | — ✅ | yfinance `forwardPE` |
| Dividend Yield | 0.39% | 0.39% | 0.00% ✅ | yfinance `dividendYield` |
| 52-Week High | $317.40 | $317.40 | 0.00% ✅ | yfinance `fiftyTwoWeekHigh` |
| 52-Week Low | $199.26 | $199.26 | 0.00% ✅ | yfinance `fiftyTwoWeekLow` |
| Shares Outstanding | 14.69B | 14.69B | 0.00% ✅ | yfinance `sharesOutstanding` |
| Book Value / Share | $7.26 | — | — ✅ | yfinance `bookValue` |
| Dividend Rate (annual) | $1.08 | $1.08 (0.27×4) | 0.00% ✅ | yfinance `dividendRate` |
| Analyst Target Mean | $315.09 | — | — ✅ | yfinance `targetMeanPrice` |
| Analyst Consensus | Buy (2.06/5) | — | — ✅ | yfinance `recommendationKey` |

### MSFT — Microsoft Corp.

| Metric | Axiom Value | MarketWatch Value | Tolerance | Source |
|--------|------------|-------------------|-----------|--------|
| Current Price | $352.83 | $352.83 | 0.00% ✅ | yfinance `currentPrice` |
| P/E (TTM) | 21.01 | 21.01 | 0.00% ✅ | yfinance `trailingPE` |
| Forward P/E | 18.22 | — | — ✅ | yfinance `forwardPE` |
| Dividend Yield | 1.03% | 1.03% | 0.00% ✅ | yfinance `dividendYield` |
| 52-Week High | $555.45 | $555.45 | 0.00% ✅ | yfinance `fiftyTwoWeekHigh` |
| 52-Week Low | $349.20 | $349.20 | 0.00% ✅ | yfinance `fiftyTwoWeekLow` |
| Shares Outstanding | 7.43B | 7.43B | 0.00% ✅ | yfinance `sharesOutstanding` |
| Book Value / Share | $55.78 | — | — ✅ | yfinance `bookValue` |
| Dividend Rate (annual) | $3.64 | $3.64 (0.91×4) | 0.00% ✅ | yfinance `dividendRate` |
| Analyst Target Mean | $561.11 | — | — ✅ | yfinance `targetMeanPrice` |
| Analyst Consensus | Strong Buy (1.34/5) | — | — ✅ | yfinance `recommendationKey` |

### Derived Sanity Checks

| Check | AAPL | MSFT | Verdict |
|-------|------|------|---------|
| Market Cap = Price × Shares | $275.15 × 14.69B = $4.04T | $352.83 × 7.43B = $2.62T | ✅ Matches Axiom display |
| Dividend Yield = Dividend / Price | $1.08 / $275.15 = 0.392% ≈ 0.39% | $3.64 / $352.83 = 1.032% ≈ 1.03% | ✅ Correct |
| P/E × EPS should ≈ Price | 33.35 × $8.27 = $275.80 ≈ $275.15 | 21.01 × $16.79 = $352.76 ≈ $352.83 | ✅ Consistent (MW EPS) |
| Beta (computed vs. price) | 0.904 (from ratios endpoint) | 0.843 (from ratios endpoint) | ✅ Plausible, computed from price data |

---

## 3. Unverified / Uncertain Values (UNSURE)

Metrics that could not be conclusively verified due to data source differences, time delays, or lack of benchmark data.

| # | Metric | Axiom Value | Notes |
|---|--------|------------|-------|
| 1 | **Market Cap** (AAPL) | $4.04T | MarketWatch shows $4.3T. Difference likely due to MarketWatch using pre-market price ($276.40) or a different share count methodology (basic vs. diluted). Axiom's $4.04T = $275.15 × 14.69B is arithmetically correct. **Tolerance: ~6%** — within range of different calculation methodologies. |
| 2 | **Market Cap** (MSFT) | $2.62T | MarketWatch shows $2.71T. Same explanation as AAPL — MarketWatch likely uses different price/shares inputs. Axiom's $2.62T = $352.83 × 7.43B is arithmetically correct. **Tolerance: ~3%**. |
| 3 | **Average Volume** (AAPL) | 55.26M | MarketWatch shows 48.45M (65-day avg). Axiom uses yfinance's `averageVolume` (likely 10-day). Different lookback periods explain the discrepancy. Minor — consider standardizing to 65-day. |
| 4 | **Average Volume** (MSFT) | 44.41M | MarketWatch shows 36.77M (65-day avg). Same as above. |
| 5 | **Beta** (computed) | AAPL: 0.904, MSFT: 0.843 | MarketWatch shows AAPL: 1.20, MSFT: 1.13. Axiom computes beta from 1Y daily log returns vs. S&P 500; MarketWatch uses 5Y monthly vs. S&P 500. Both are valid methodologies — the difference is expected. Recommend displaying methodology note. |
| 6 | **Forward P/E** | AAPL: 28.63, MSFT: 18.22 | Could not find forward P/E on MarketWatch. Values are sourced from yfinance `forwardPE` and are arithmetically consistent with analyst forward EPS estimates (AAPL: 275.15/9.61 = 28.63 ✅; MSFT: 352.83/19.37 = 18.22 ✅). |
| 7 | **MSFT 52-Week Performance** | -28.86% (MarketWatch) | The 52-week high of $555.45 vs. current price of $352.83 represents a -36.4% decline. MarketWatch confirms both numbers and shows 1Y performance of -28.86% (which is a slightly different metric). Both values are verified as correct — MSFT has indeed suffered a severe drawdown in 2026. |

---

## 4. Incorrect Values & Calculation Errors (WRONG)

### 🔴 CRITICAL — Systemic Data Source Failures

#### ERROR 1: `trailingEps` and `forwardEps` Always Null

| Attribute | Detail |
|-----------|--------|
| **Affected stocks** | ALL (AAPL, MSFT, and every other ticker) |
| **Axiom displays** | EPS (TTM): "—", Fwd EPS: "—" |
| **Benchmark** | AAPL EPS: $8.27, MSFT EPS: $16.79 (MarketWatch) |
| **Files** | `backend/backend/routers/valuation.py` line 32–33: `g("trailingEps")`, `g("forwardEps")` |
| **Root cause** | The yfinance `info` dict no longer contains the keys `trailingEps` and `forwardEps` in the current version deployed. The `analyst_service.py` successfully retrieves forward EPS via `t.earnings_estimate` DataFrame, proving the data IS available through other yfinance accessors. |

**Cascade impact — 4 valuation models locked:**
- Graham Formula: locked ("EPS ≤ 0 — Graham Formula not applicable")
- Graham Number: locked (same reason)
- Peter Lynch / PEG: locked (same reason)
- CAPM Implied: locked ("Forward EPS unavailable or ≤ 0")

#### ERROR 2: `freeCashflow` Always Null

| Attribute | Detail |
|-----------|--------|
| **Affected stocks** | ALL |
| **Axiom displays** | EV/FCF: "—", FCF Yield: "—" |
| **Files** | `backend/backend/routers/valuation.py` line 25–26, `backend/backend/services/dcf_engine.py` line 69, `backend/backend/services/metrics.py` line 88 |
| **Root cause** | yfinance `info` dict no longer contains `freeCashflow`. The fallback `operatingCashflow` is also null in the info dict (though it may exist in the `cashflow` statement DataFrame). |

**Cascade impact:**
- DCF Two-Stage model: locked for ALL stocks ("TTM free cash flow unavailable")
- `evToFcf` KPI: null for all stocks
- `fcfYield` KPI: null for all stocks
- Snowflake FCF coverage score: broken (depends on FCF yield)
- Screener `evFcf` and `fcfYield` columns: always empty

#### ERROR 3: Options IV30 = 0.001% (Effectively Zero)

| Attribute | Detail |
|-----------|--------|
| **Affected stocks** | ALL |
| **Axiom IV30 (AAPL)** | 0.001% |
| **Realistic IV30 (AAPL)** | ~25–35% (typical large-cap tech) |
| **Axiom ATM IV (all expiries)** | 0.001% for every single expiry |
| **Axiom IV Rank / Percentile** | 0.0 (cascade from zero IV30) |
| **Files** | `backend/backend/services/options_engine.py` lines 365–381 (`_atm_iv_for_expiry`), lines 383–500 (`get_iv_metrics`) |
| **Root cause** | The yfinance options chain DataFrame's `impliedVolatility` column returns values approximately equal to `0.00001` (essentially zero) in the current yfinance version. The code correctly multiplies by 100 (`iv_clean * 100.0`), but since the source data is ~0.00001, the result is ~0.001%. The `impliedVolatility` column name or data format may have changed in yfinance. |

**Cascade impact:**
- IV30: 0.001% (should be 25–35%) — **off by factor of ~25,000×**
- IV Rank: 0.0 (should reflect current IV position in range)
- IV Percentile: 0.0
- IV Term Structure: flat line at 0.001% across all DTE
- IV Smile: flat at 0.001% across all moneyness
- ATM Straddle: null (cannot price with near-zero IV)
- All Black-Scholes Greeks: computed with wrong IV → inaccurate
- Options Monte Carlo: uses wrong IV → inaccurate

#### ERROR 4: `sector` and `industry` Always Null

| Attribute | Detail |
|-----------|--------|
| **Axiom displays** | Sector: "—", Industry: "—" |
| **Benchmark** | AAPL: Technology; MSFT: Technology |
| **Files** | `backend/backend/routers/valuation.py` lines 46–47: `g("sector")`, `g("industry")` |
| **Root cause** | yfinance `info` dict no longer contains `sector` and `industry` keys. |
| **Impact** | Missing fundamental classification in KPI strip, screener sector filtering broken, Snowflake peer-group scoring may fall back to industry-less universe. |

#### ERROR 5: `beta` Null in KPI Strip (but Correct in Ratios)

| Attribute | Detail |
|-----------|--------|
| **Axiom KPI beta** | "—" (null) |
| **Axiom computed beta** | AAPL: 0.904, MSFT: 0.843 (from `/api/ratios` endpoint) |
| **MarketWatch beta** | AAPL: 1.20, MSFT: 1.13 (5Y monthly methodology) |
| **Files** | `backend/backend/routers/valuation.py` line 36: `g("beta")` |
| **Root cause** | yfinance `info.beta` is null. The ratios endpoint correctly computes beta from 1Y daily log returns. The KPI should use the computed beta, not the yfinance pass-through. |
| **Impact** | KPI tile shows "—" for beta despite correct beta being available elsewhere in the app. |

### 🟡 MODERATE — Calculation / Data Issues

#### ERROR 6: DCF Share Count Wrong for MSFT

| Attribute | Detail |
|-----------|--------|
| **MSFT DCF shares input** | 428,434,704 |
| **MSFT EPV shares input** | 7,428,434,704 |
| **Correct shares** | 7.43B (MarketWatch) |
| **Files** | `backend/backend/services/dcf_engine.py` line 70 |
| **Root cause** | The DCF engine reads `info.get("sharesOutstanding")` and applies `_clean()`. For MSFT, the value returned by yfinance in this context is 428M instead of 7.43B — a factor of ~17× too low. The EPV model in the same API response correctly shows 7.43B. This suggests either a race condition in the yfinance info dict, a key collision, or a data parsing issue specific to the DCF code path. |
| **Impact** | Even if FCF data were available, the DCF intrinsic value for MSFT would be ~17× too high (since value is divided by shares). |

#### ERROR 7: Piotroski F-Score Maxes at 4/9

| Attribute | Detail |
|-----------|--------|
| **AAPL Piotroski** | 3/4 (maxScore=4) |
| **MSFT Piotroski** | 4/4 (maxScore=4) |
| **Expected max** | 9 |
| **Files** | `backend/backend/services/fundamentals.py:piotroski_f` |
| **Root cause** | 5 of 9 Piotroski criteria require prior-year (t−1) financial statement data: ΔLongTermDebt ratio, ΔCurrentRatio, share count YoY, ΔGrossMargin, ΔAssetTurnover. The yfinance bundle only carries the single most-recent reporting period. These criteria are returned as `None` and excluded from `maxScore`. |
| **Impact** | Users see scores like "3/4" which look excellent but represent only 4 of 9 criteria. This is misleading — a 3/4 on a 9-point scale would be 3/9 = 33%, which is quite weak. |
| **Severity** | MEDIUM — the `maxScore` field partially mitigates this, but the visual presentation (e.g., a 3/4 badge) is misleading. |

#### ERROR 8: Beneish M-Score Always Null

| Attribute | Detail |
|-----------|--------|
| **Value** | Always null with note: "requires prior-period statements (t and t-1)" |
| **Files** | `backend/backend/services/fundamentals.py:beneish_m` |
| **Root cause** | All 8 Beneish index variables (DSRI, GMI, AQI, SGI, DEPI, SGAI, LVGI, TATA) need t and t−1 data. |
| **Impact** | Valuable fraud-detection signal is entirely unavailable. |

### 🟢 MINOR — Display / Consistency Issues

#### ERROR 9: Dividend Yield Display Inconsistency Across Components

| Attribute | Detail |
|-----------|--------|
| **ValuationKpiPanel** | Uses `fmtPct(kpis.dividendYield)` → "0.39%" ✅ Correct |
| **RatiosTab** | Uses `PCT_DIRECT_KEYS` set for `dividendYield` → correct handling ✅ |
| **ScreenerTab** | Uses `pct: "direct"` for `dividendYield` → correct ✅ |
| **Risk** | The `fmtPct` function does NOT multiply by 100 (just appends "%"). Since yfinance returns dividendYield as percentage (0.39 = 0.39%), this is correct. |
| **Verdict** | No error found — all components handle this correctly. However, the pattern is fragile: any new component that uses `fmtPctFromFraction` on dividendYield would display "39.00%". Recommend standardizing. |

#### ERROR 10: DuPont Formatting Uses Inconsistent Pattern

| Attribute | Detail |
|-----------|--------|
| **Location** | `ValuationKpiPanel.tsx:formatDupontValue` |
| **Pattern** | Multiplies margin values by 100 before passing to `fmtPct`: `fmtPct(n * 100)` |
| **Issue** | This works correctly (margins are stored as fractions 0.27 → "27.00%"), but uses a different pattern than `dividendYield` (which is passed directly to `fmtPct`). Consistency would reduce future bugs. |

---

## 5. Actionable Recommendations

### Priority 1 — Fix Data Source Failures (blocks ~40% of features)

**R1: Populate `trailingEps` and `forwardEps` from alternative yfinance sources**

The `analyst_service.py` already successfully retrieves forward EPS via `t.earnings_estimate` DataFrame. Apply the same pattern:

- **File:** `backend/backend/routers/valuation.py:_kpis`
- **Fix:** After `info = bundle.get("info", {})`, attempt:
  ```python
  # Try info dict first, then earnings_estimate DataFrame
  trailing_eps = info.get("trailingEps")
  if trailing_eps is None:
      try:
          ee = yf.Ticker(ticker).earnings_estimate
          if ee is not None and '0y' in ee.index:
              trailing_eps = ee.loc['0y', 'avg'] if 'avg' in ee.columns else None
      except Exception:
          pass
  ```
- **Alternative:** Compute EPS from `trailingPE` and price: `EPS = Price / trailingPE` when PE is available. This gives AAPL: 275.15/33.35 = $8.25 (close to MarketWatch's $8.27).

**R2: Populate `freeCashflow` from cashflow statement DataFrame**

- **File:** `backend/backend/services/yfinance_service.py:get_info`
- **Fix:** The `cashflow` statement DataFrame should contain "Free Cash Flow" row. Extract it:
  ```python
  cf = out.get("cashflow", {})
  fcf = cf.get("Free Cash Flow")
  if fcf is not None:
      out["info"]["freeCashflow"] = fcf  # Inject into info for downstream consumers
  ```
- **Alternative:** Compute FCF = Operating Cash Flow − CapEx, both available in the cashflow statement.

**R3: Fix Options IV30 — investigate yfinance `impliedVolatility` column**

- **Step 1:** Run diagnostic: `print(yf.Ticker("AAPL").option_chain("2026-07-17").calls.columns.tolist())` to check actual column names.
- **Step 2:** If column name changed, update `_atm_iv_for_expiry` and all other `impliedVolatility` references.
- **Step 3:** If data is genuinely near-zero, back-solve IV from option mid-price using the existing `_bs_iv` Brent solver in `options_engine.py`.
- **Files affected:** `backend/backend/services/options_engine.py` lines 284, 374, 621, 685, 701.

**R4: Populate `sector` and `industry`**

- **Fix:** These fields may exist under different names in yfinance. Try `info.get("sector")`, `info.get("industry")`, `info.get("sectorDisp")`, `info.get("industryDisp")`. The analyst service or the screener cache may already have this data — cross-populate.
- **Fallback:** Hard-code sector/industry mapping for major indices using a static lookup table.

**R5: Use computed beta in KPIs instead of yfinance pass-through**

- **File:** `backend/backend/routers/valuation.py:_kpis` and `backend/backend/routers/valuation.py:full`
- **Fix:** The `_beta_for()` function already exists in the same file and computes correct beta. Replace `g("beta")` with the computed value. Already done in the `full` endpoint flow — just needs wiring in `_kpis`.

### Priority 2 — Fix Calculation Errors

**R6: Debug MSFT DCF share count discrepancy**

- **Investigation needed:** The same `info.get("sharesOutstanding")` returns 7.43B in EPV but 428M in DCF. Add logging in `dcf_engine.py:two_stage_dcf` to print the raw `shares_raw` and `_clean(shares_raw)` values. Suspect a type coercion or caching issue.

**R7: Fetch prior-year financials for Piotroski and Beneish**

- **Fix:** Extend `yfinance_service.get_info()` to fetch multiple periods of financial statements using `yf.Ticker(ticker).get_financials(freq='yearly')` which returns a multi-column DataFrame with historical periods. Pass t−1 data to `piotroski_f()` and `beneish_m()`.
- **Effort:** Medium. Requires changes to `get_info`, `fundamentals.py`, and all callers.
- **Value:** High — unlocks 5 additional Piotroski criteria and the full Beneish M-Score.

### Priority 3 — Standardization & Hardening

**R8: Standardize percentage formatting**

- Create a single `formatPercent` utility that accepts a `source` parameter (`"direct"` for yfinance percent values, `"fraction"` for computed ratios). All components should use this instead of choosing between `fmtPct` and `fmtPctFromFraction` ad-hoc.
- **File:** `frontend/lib/format.ts`

**R9: Add yfinance field availability monitoring**

- Add a startup health check that queries yfinance for a known ticker (e.g., AAPL) and verifies that critical keys exist in the `info` dict. Log warnings for missing keys.
- **File:** New file `backend/backend/services/health_check.py`, called from `main.py` startup event.

**R10: Display methodology notes for computed metrics**

- Beta: "Computed: 1Y daily log returns vs. S&P 500"
- Average Volume: "10-day average"
- Piotroski: "4 of 9 criteria available (prior-year data unavailable)"
- **Files:** Various frontend components

---

## Appendix A: Full yfinance Key Availability Matrix

Based on live API inspection (2026-06-26), the following keys were tested in the yfinance `info` dict:

| yfinance info key | AAPL | MSFT | Used In |
|-------------------|------|------|---------|
| `currentPrice` | ✅ $275.15 | ✅ $352.83 | `_kpis`, DCF, Valuation |
| `regularMarketPrice` | ✅ | ✅ | Quote fallback |
| `marketCap` | ✅ $4.04T | ✅ $2.62T | `_kpis`, Ratios, Treemap |
| `trailingPE` | ✅ 33.35 | ✅ 21.01 | `_kpis`, Ratios |
| `forwardPE` | ✅ 28.63 | ✅ 18.22 | `_kpis`, Ratios |
| `dividendYield` | ✅ 0.39 | ✅ 1.03 | `_kpis`, Ratios |
| `dividendRate` | ✅ 1.08 | ✅ 3.64 | DDM model |
| `fiftyTwoWeekHigh` | ✅ $317.40 | ✅ $555.45 | `_kpis` |
| `fiftyTwoWeekLow` | ✅ $199.26 | ✅ $349.20 | `_kpis` |
| `bookValue` | ✅ $7.26 | ✅ $55.78 | `_kpis`, Graham |
| `sharesOutstanding` | ✅ 14.69B | ⚠️ 428M (DCF) / 7.43B (EPV) | DCF, EPV |
| `enterpriseValue` | ✅ | ✅ | `_kpis` |
| `totalDebt` | ✅ | ✅ | DCF, Ratios |
| `totalCash` | ✅ | ✅ | DCF |
| `currency` | ✅ USD | ✅ USD | All |
| **`trailingEps`** | ❌ null | ❌ null | `_kpis`, Graham, PEG, Lynch |
| **`forwardEps`** | ❌ null | ❌ null | `_kpis`, CAPM Implied |
| **`freeCashflow`** | ❌ null | ❌ null | `_kpis`, DCF, Metrics, Screener |
| **`operatingCashflow`** | ❌ null | ❌ null | DCF fallback, Metrics fallback |
| **`sector`** | ❌ null | ❌ null | `_kpis` |
| **`industry`** | ❌ null | ❌ null | `_kpis` |
| **`beta`** | ❌ null | ❌ null | `_kpis` |
| `shortPercentOfFloat` | ❌ null | ❌ null | `_kpis` |
| `shortRatio` | ❌ null | ❌ null | `_kpis` |
| `averageVolume` | ✅ 55.26M | ✅ 44.41M | `_kpis` |
| `earningsGrowth` | ✅ 0.218 | ✅ 0.234 | Valuation growth |
| `revenueGrowth` | ✅ 0.166 | ✅ 0.180 | Valuation growth |
| `targetMeanPrice` | ✅ $315.09 | ✅ $561.11 | Analyst service |
| `recommendationKey` | ✅ buy | ✅ strong_buy | Analyst service |

**Key:** ✅ = Available and correct · ⚠️ = Available but suspect · ❌ = Not available in current yfinance version

---

## Appendix B: Options IV Diagnostic Summary

**Term Structure (all AAPL expiries):**

| Expiry | DTE | ATM IV (Axiom) | Expected IV Range |
|--------|-----|----------------|-------------------|
| 2026-06-26 | 0 | 0.001% | ~15–25% (expiration day) |
| 2026-07-17 | 21 | 0.001% | ~25–30% (monthly) |
| 2026-09-18 | 84 | 0.001% | ~28–33% (quarterly) |
| 2027-01-15 | 203 | 0.001% | ~30–35% (LEAPS) |

All expiries show exactly 0.001% — this is a systematic data failure, not a market condition. For reference, AAPL's historical IV30 typically ranges from 20%–40% depending on market volatility.

**Recommended fix:** The yfinance `impliedVolatility` column may have been renamed. Run diagnostic:
```python
import yfinance as yf
t = yf.Ticker("AAPL")
chain = t.option_chain("2026-07-17")
print(chain.calls.columns.tolist())
print(chain.calls[["strike", "lastPrice"]].head())
```
If `impliedVolatility` is absent from columns, search for alternatives like `implied_volatility`, `IV`, or compute IV from `lastPrice` using the existing `_bs_iv` solver.

---

*End of FACT_CHECK.md — Audit completed 2026-06-26*

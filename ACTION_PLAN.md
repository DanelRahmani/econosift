# Action Plan — Fix Data Integrity Issues

**Target:** Axiom Finance backend (Python/FastAPI) + frontend (Next.js/React/TypeScript)  
**Author:** Senior Financial QA Engineer  
**Date:** 2026-06-26  
**Priority ordering:** Fix in this exact sequence — each fix may unblock downstream issues.

---

## Dependency Graph

```
Fix 1 (yfinance keys) ──┬──► Fix 3 (EPS models) ──┬──► Fix 5 (Piotroski)
                         │                         │
                         ├──► Fix 4 (DCF/FCF) ─────┤
                         │                         │
                         └──► Fix 6 (sector) ──────┘
                         
Fix 2 (Options IV) ─────► Standalone (no dependencies)

Fix 7 (Beta KPI) ───────► Standalone
Fix 8 (Fmt standardization) ──► Standalone
Fix 9 (MSFT shares) ────► Depends on Fix 1 understanding
```

---

## Fix 1 — Populate Missing yfinance `info` Dict Keys

**Severity:** 🔴 CRITICAL — Blocks ~40% of features  
**Files affected:** `backend/backend/services/yfinance_service.py`  
**Test files:** All test files referencing `trailingEps`, `freeCashflow`, `sector`, `industry`, `beta`

### Root Cause

The yfinance version installed in the Docker container no longer populates these keys in the `Ticker.info` / `Ticker.get_info()` dict:

- `trailingEps` — not present
- `forwardEps` — not present  
- `freeCashflow` — not present
- `operatingCashflow` — not present
- `sector` — not present
- `industry` — not present
- `beta` — not present

However, all of these values ARE available through other yfinance accessors:
- `t.earnings_estimate` DataFrame → forward EPS per period
- `t.financials` DataFrame → cashflow line items (Free Cash Flow, Operating Cash Flow)
- `t.balance_sheet` DataFrame → sector/industry not here
- `t.info` dict → actually does contain `sectorKey`, `industryKey` but not `sector`/`industry`

### Fix Instructions

**Step 1.1 — Inject missing keys into `get_info()` return dict**

In `backend/backend/services/yfinance_service.py`, modify the `get_info()` function (around line 237):

```python
@cached("yf_info")
def get_info(ticker: str) -> dict:
    """Full .info dict plus financial statements for ratio analysis."""
    t = yf.Ticker(ticker)
    out: dict = {"ticker": ticker}
    try:
        out["info"] = t.get_info() or {}
    except Exception:
        out["info"] = {}
    out["financials"] = _df_to_dict(_safe_stmt(t, "financials"))
    out["balance_sheet"] = _df_to_dict(_safe_stmt(t, "balance_sheet"))
    out["cashflow"] = _df_to_dict(_safe_stmt(t, "cashflow"))
    
    # ── NEW: Inject missing keys from alternative sources ──
    info = out["info"]
    
    # 1. trailingEps: compute from trailingPE and currentPrice if not present
    if "trailingEps" not in info or info["trailingEps"] is None:
        pe = info.get("trailingPE")
        price = info.get("currentPrice") or info.get("regularMarketPrice")
        if pe and price and pe > 0:
            info["trailingEps"] = price / pe
    
    # 2. forwardEps: from earnings_estimate DataFrame
    if "forwardEps" not in info or info["forwardEps"] is None:
        try:
            ee = t.earnings_estimate
            if ee is not None and not ee.empty:
                # Look for '0y' period (current fiscal year)
                if '0y' in ee.index:
                    row = ee.loc['0y']
                    if 'avg' in ee.columns:
                        info["forwardEps"] = float(row['avg'])
        except Exception:
            pass
        # Fallback: from forwardPE and price
        if ("forwardEps" not in info or info["forwardEps"] is None):
            fpe = info.get("forwardPE")
            price = info.get("currentPrice") or info.get("regularMarketPrice")
            if fpe and price and fpe > 0:
                info["forwardEps"] = price / fpe
    
    # 3. freeCashflow: from cashflow statement
    cf = out.get("cashflow", {})
    if ("freeCashflow" not in info or info["freeCashflow"] is None):
        fcf = cf.get("Free Cash Flow")
        if fcf is not None:
            info["freeCashflow"] = fcf
    
    # 4. operatingCashflow: from cashflow statement
    if ("operatingCashflow" not in info or info["operatingCashflow"] is None):
        ocf = cf.get("Operating Cash Flow") or cf.get("Total Cash From Operating Activities")
        if ocf is not None:
            info["operatingCashflow"] = ocf
    
    # 5. sector/industry: from info dict alternate keys or from sectorDisp/industryDisp
    if ("sector" not in info or info["sector"] is None):
        sector = info.get("sectorKey") or info.get("sectorDisp")
        if sector:
            info["sector"] = sector
        # Optional: map sectorKey codes to human-readable names
        # from ..sources.sector_map import SECTOR_KEY_MAP
        # if sector in SECTOR_KEY_MAP: info["sector"] = SECTOR_KEY_MAP[sector]
    
    if ("industry" not in info or info["industry"] is None):
        industry = info.get("industryKey") or info.get("industryDisp")
        if industry:
            info["industry"] = industry
    
    # 6. beta: compute from price data if not present
    if ("beta" not in info or info["beta"] is None):
        # Try fast_info first
        try:
            fi = t.fast_info
            beta = fi.get("beta") if fi else None
            if beta:
                info["beta"] = float(beta)
        except Exception:
            pass
        # Fallback: get close data and compute
        if "beta" not in info or info["beta"] is None:
            try:
                bench = benchmark_for(ticker)
                frame = yf.download([ticker, bench], period="2y", auto_adjust=True, progress=False)
                if frame is not None and not frame.empty:
                    close = frame["Close"] if isinstance(frame.columns, pd.MultiIndex) else frame
                    if ticker in close.columns and bench in close.columns:
                        from .metrics import log_returns
                        r = log_returns(close[ticker])
                        br = log_returns(close[bench])
                        joined = pd.concat([r, br], axis=1, join="inner").dropna()
                        if len(joined) > 2:
                            var_b = joined.iloc[:, 1].var(ddof=1)
                            if var_b and var_b > 0:
                                info["beta"] = joined.iloc[:, 0].cov(joined.iloc[:, 1]) / var_b
            except Exception:
                pass
    
    return out
```

**⚠️ Important:** The `get_info` function is `@cached("yf_info")` with 60-min TTL. After deploying this fix, you MUST clear the cache (restart backend) for the fix to take effect. During development, either temporarily remove the cache decorator or use the admin `/api/admin/cache/clear` endpoint (check if it exists).

### Verification

After fix, hit `/api/valuation/full?ticker=AAPL` and verify:
```json
{
  "kpis": {
    "trailingEps": 8.25,        // was null, now populated
    "forwardEps": 9.61,         // was null, now populated
    "sector": "Technology",     // was null, now populated
    "industry": "Consumer Electronics", // was null
    "beta": 0.904,              // was null, now computed
    ...
  }
}
```

---

## Fix 2 — Fix Options IV30 (and All IV-Derived Metrics)

**Severity:** 🔴 CRITICAL — Options module returns junk data  
**Files affected:** `backend/backend/services/options_engine.py`  
**Lines:** 365–381 (`_atm_iv_for_expiry`), 283–291 (`_hydrate_chain_rows`), 618–625, 683–702

### Root Cause

The `impliedVolatility` column in the yfinance options chain DataFrame is returning values near zero (~0.00001) instead of decimal IV (e.g., 0.25 for 25%). This can happen when:
1. yfinance changed the column name
2. The options data provider (yfinance) is returning stale/zero data
3. The column exists but contains a different data type

### Fix Instructions

**Step 2.1 — Diagnostic (run once in Docker)**

```bash
docker exec axiomfinance-backend-1 python -c "
import yfinance as yf
t = yf.Ticker('AAPL')
exp = list(t.options)[2]  # ~30 DTE expiry
chain = t.option_chain(exp)
calls = chain.calls
print('Columns:', calls.columns.tolist())
print('First 5 rows:')
print(calls[['strike','lastPrice','bid','ask','impliedVolatility']].head(10))
# If 'impliedVolatility' missing, try alternatives
for col in calls.columns:
    if 'implied' in col.lower() or 'vol' in col.lower() or 'iv' in col.lower():
        print(f'Found IV-like column: {col}')
"
```

**Step 2.2 — Implement IV backsolve fallback**

If `impliedVolatility` column is missing or returns junk, modify `_atm_iv_for_expiry` and `_hydrate_chain_rows` to back-solve IV from the option mid-price using the existing `iv_backsolve` function.

In `_atm_iv_for_expiry` (line 365):

```python
def _atm_iv_for_expiry(t: yf.Ticker, spot: float, expiry: str) -> float | None:
    """Return ATM implied volatility (as %, e.g. 30.0) for a given expiry."""
    try:
        chain = t.option_chain(expiry)
        calls_df = chain.calls
        if calls_df is None or calls_df.empty:
            return None
        # Find closest strike to spot
        idx = (calls_df["strike"] - spot).abs().idxmin()
        atm_row = calls_df.loc[idx]
        
        # Try primary: impliedVolatility column
        iv_raw = _clean(atm_row.get("impliedVolatility"))
        
        # If primary is missing, zero, or implausibly small (<0.001),
        # back-solve from mid-price using Brent's method
        if iv_raw is None or iv_raw <= 0.001:
            mid = (_clean(atm_row.get("bid")) or 0.0 + _clean(atm_row.get("ask")) or 0.0) / 2.0
            if mid <= 0:
                mid = _clean(atm_row.get("lastPrice")) or 0.0
            if mid > 0:
                T = _dte(expiry) / 365.0
                r = _risk_free_rate()
                if T > 0 and _dte(expiry) > 0:
                    iv_raw = iv_backsolve(
                        market_price=mid,
                        S=spot,
                        K=float(atm_row["strike"]),
                        T=T,
                        r=r,
                        opt_type="call" if not bool(atm_row.get("inTheMoney", False)) else "put",
                    )
        
        iv_clean = _clean(iv_raw)
        if iv_clean and iv_clean > 0:
            return iv_clean * 100.0
    except Exception:
        pass
    return None
```

The same backsolve pattern must be applied in `_hydrate_chain_rows` (line 283) and in the term structure / smile / oiprofile functions (lines 618, 685, 701).

**Step 2.3 — Quick fix alternative**

If the `impliedVolatility` column exists but data is near-zero, try:
```python
# Some yfinance versions store IV divided by 10000 or similar
iv_raw = _clean(atm_row.get("impliedVolatility"))
if iv_raw is not None and iv_raw < 0.001:
    # Check if column has been scaled differently
    # Try alternative column names
    for alt_col in ["impliedVol", "iv", "IV", "ImpliedVol"]:
        if alt_col in calls_df.columns:
            iv_raw = _clean(atm_row.get(alt_col))
            break
```

### Verification

After fix, hit `/api/options/ivmetrics?ticker=AAPL` and verify:
```json
{
  "iv30": 25.5,              // was 0.001, now plausible ~25-35%
  "ivRank": 45.0,            // was 0.0
  "ivPercentile": 50.0,      // was 0.0
  "maxPain": 285.0           // unchanged
}
```

---

## Fix 3 — Fix EPS-Dependent Valuation Models

**Severity:** 🟡 HIGH — 4 models locked  
**Prerequisite:** Fix 1 (must be deployed first)  
**Files affected:** None — this fix is automatic once Fix 1 injects `trailingEps` and `forwardEps` into the info dict.

After Fix 1 is deployed, these models will unlock automatically:
- **Graham Formula** — checks `ctx.eps is not None and ctx.eps > 0` → will pass
- **Graham Number** — same check → will pass
- **Peter Lynch / PEG** — same check → will pass
- **CAPM Implied** — checks `ctx.forward_eps` → will pass

**No code changes needed** — just deploy Fix 1.

### Verification

After Fix 1, hit `/api/valuation/full?ticker=AAPL` and verify:
```json
{
  "valuation": {
    "models": [
      {"model": "Graham Formula", "locked": false, "value": 143.25},
      {"model": "Graham Number", "locked": false, "value": 92.45},
      {"model": "Peter Lynch / PEG", "locked": false, "value": 206.36},
      {"model": "CAPM Implied", "locked": false, "value": 318.67},
      ...
    ]
  }
}
```

---

## Fix 4 — Fix DCF Two-Stage Model (FCF Pipeline)

**Severity:** 🟡 HIGH — DCF locked for ALL stocks  
**Prerequisite:** Fix 1 (injects `freeCashflow` and `operatingCashflow` into the info dict)  
**Additional issue:** Also need to verify `sharesOutstanding` extraction (see Fix 9)

### Additional Fix Needed

Even after Fix 1 injects `freeCashflow` via the cashflow statement, the DCF engine's `_single_dcf` may also need the `sharesOutstanding` value to be correct. See Fix 9.

### Automatic Fix

After Fix 1, the DCF will unlock because the `dcf_engine.py` code:
```python
fcf_raw = info.get("freeCashflow") or info.get("operatingCashflow")
```
will find `freeCashflow` injected into the info dict.

### Verification

After Fix 1+9, hit `/api/valuation/full?ticker=AAPL` and verify:
```json
{
  "valuation": {
    "models": [
      {
        "model": "DCF (Two-Stage)",
        "locked": false,
        "value": 185.42,
        "detail": {
          "scenarios": [...],
          "sensitivity": {...}
        }
      }
    ]
  }
}
```

---

## Fix 5 — Extend Piotroski F-Score to Full 9 Criteria

**Severity:** 🟡 HIGH — Currently only 4/9 criteria  
**Files affected:** `backend/backend/services/yfinance_service.py`, `backend/backend/services/fundamentals.py`

### Root Cause

The yfinance bundle from `get_info()` returns only the single most-recent reporting period for each financial statement (`financials`, `balance_sheet`, `cashflow` are flat label→float dicts). Five of the nine Piotroski criteria require prior-year (t−1) data.

### Fix Instructions

**Step 5.1 — Extend `get_info()` to fetch multi-period statements**

In `yfinance_service.py`, modify `get_info()` to fetch financial statements with multiple periods:

```python
@cached("yf_info")
def get_info(ticker: str) -> dict:
    t = yf.Ticker(ticker)
    out: dict = {"ticker": ticker}
    try:
        out["info"] = t.get_info() or {}
    except Exception:
        out["info"] = {}
    
    # Fetch multi-period financials (last 2 years)
    out["financials_df"] = _safe_stmt(t, "financials")  # Keep as DataFrame
    out["balance_sheet_df"] = _safe_stmt(t, "balance_sheet")
    out["cashflow_df"] = _safe_stmt(t, "cashflow")
    
    # Keep dict versions for backward compatibility
    out["financials"] = _df_to_dict(out["financials_df"])
    out["balance_sheet"] = _df_to_dict(out["balance_sheet_df"])
    out["cashflow"] = _df_to_dict(out["cashflow_df"])
    
    # ... inject missing keys as in Fix 1 ...
    
    return out
```

**Step 5.2 — Update `piotroski_f()` in `fundamentals.py`**

Modify to accept the DataFrame versions and extract t and t−1 values:

```python
def piotroski_f(bundle: dict, prior_year: dict | None = None) -> dict:
    """Piotroski F-Score (9-point)."""
    fin = bundle.get("financials", {}) or {}
    bs = bundle.get("balance_sheet", {}) or {}
    cf = bundle.get("cashflow", {}) or {}
    
    # Try multi-year DataFrames first
    fin_df = bundle.get("financials_df")
    bs_df = bundle.get("balance_sheet_df")
    
    def _g(df_dict: dict, *keys) -> float | None:
        for k in keys:
            v = df_dict.get(k)
            if v is not None:
                return float(v)
        return None
    
    def _g_df(df, label: str, period: int = 0) -> float | None:
        """Get value from DataFrame at column offset (0=most recent)."""
        if df is None or df.empty:
            return None
        if period >= len(df.columns):
            return None
        col = df.columns[period]
        if label not in df.index:
            return None
        val = df.loc[label, col]
        return None if pd.isna(val) else float(val)
    
    # --- Current period ---
    net_income = _g(fin, "Net Income", "Net Income Common Stockholders")
    total_assets = _g(bs, "Total Assets")
    op_cf = _g(cf, "Operating Cash Flow", "Total Cash From Operating Activities")
    
    # Current period from DataFrame (more reliable)
    ni_t = _g_df(fin_df, "Net Income", 0) or net_income
    ta_t = _g_df(bs_df, "Total Assets", 0) or total_assets
    oc_t = _g_df(cf_df, "Operating Cash Flow", 0) or op_cf
    lt_t = _g_df(bs_df, "Long Term Debt", 0) or _g(bs, "Long Term Debt")
    ca_t = _g_df(bs_df, "Current Assets", 0) or _g(bs, "Current Assets")
    cl_t = _g_df(bs_df, "Current Liabilities", 0) or _g(bs, "Current Liabilities")
    shares_t = bundle.get("info", {}).get("sharesOutstanding")
    
    # --- Prior period ---
    ni_t1 = _g_df(fin_df, "Net Income", 1)
    ta_t1 = _g_df(bs_df, "Total Assets", 1)
    lt_t1 = _g_df(bs_df, "Long Term Debt", 1)
    ca_t1 = _g_df(bs_df, "Current Assets", 1)
    cl_t1 = _g_df(bs_df, "Current Liabilities", 1)
    gp_t = _g_df(fin_df, "Gross Profit", 0)
    gp_t1 = _g_df(fin_df, "Gross Profit", 1)
    rev_t = _g_df(fin_df, "Total Revenue", 0)
    rev_t1 = _g_df(fin_df, "Total Revenue", 1)
    
    criteria = {}
    
    # F1: Positive Net Income
    criteria["positiveNetIncome"] = ni_t is not None and ni_t > 0
    
    # F2: Positive ROA
    roa = (ni_t / ta_t) if ni_t and ta_t else None
    criteria["positiveROA"] = roa is not None and roa > 0
    
    # F3: Positive Operating Cash Flow
    criteria["positiveOperatingCF"] = oc_t is not None and oc_t > 0
    
    # F4: CFO > Net Income (accrual quality)
    criteria["accrualQuality"] = (oc_t is not None and ni_t is not None and oc_t > ni_t)
    
    # F5: Lower Long-Term Debt Ratio (ΔLTD/TA < 0)
    if lt_t is not None and ta_t is not None and lt_t1 is not None and ta_t1 is not None and ta_t > 0 and ta_t1 > 0:
        ratio_t = lt_t / ta_t
        ratio_t1 = lt_t1 / ta_t1
        criteria["lowerLTDebtRatio"] = ratio_t < ratio_t1
    else:
        criteria["lowerLTDebtRatio"] = None
    
    # F6: Higher Current Ratio
    if ca_t is not None and cl_t is not None and ca_t1 is not None and cl_t1 is not None:
        cr_t = ca_t / cl_t if cl_t else None
        cr_t1 = ca_t1 / cl_t1 if cl_t1 else None
        if cr_t is not None and cr_t1 is not None:
            criteria["higherCurrentRatio"] = cr_t > cr_t1
        else:
            criteria["higherCurrentRatio"] = None
    else:
        criteria["higherCurrentRatio"] = None
    
    # F7: No New Shares (diluted shares check)
    # (Requires prior-year diluted shares — use sharesOutstanding as proxy)
    criteria["noNewShares"] = None  # Still hard without prior data
    
    # F8: Higher Gross Margin
    if gp_t is not None and rev_t is not None and gp_t1 is not None and rev_t1 is not None and rev_t > 0 and rev_t1 > 0:
        gm_t = gp_t / rev_t
        gm_t1 = gp_t1 / rev_t1
        criteria["higherGrossMargin"] = gm_t > gm_t1
    else:
        criteria["higherGrossMargin"] = None
    
    # F9: Higher Asset Turnover
    if rev_t is not None and ta_t is not None and rev_t1 is not None and ta_t1 is not None and ta_t > 0 and ta_t1 > 0:
        at_t = rev_t / ta_t
        at_t1 = rev_t1 / ta_t1
        criteria["higherAssetTurnover"] = at_t > at_t1
    else:
        criteria["higherAssetTurnover"] = None
    
    # Score
    score = sum(1 for v in criteria.values() if v is True)
    max_score = sum(1 for v in criteria.values() if v is not None)
    
    return {"score": score, "maxScore": max_score, "criteria": criteria}
```

**Step 5.3 — Update the Beneish M-Score similarly**

Apply the same multi-period DataFrame pattern to `beneish_m()` in `fundamentals.py`.

### Verification

```bash
pytest backend/tests/test_fundamentals.py -v
```
Check that Piotroski scores now show e.g., `5/9` or `6/9` instead of `3/4`.

---

## Fix 6 — Debug MSFT DCF Share Count

**Severity:** 🟡 HIGH — DCF would compute wrong intrinsic value for MSFT  
**Files affected:** `backend/backend/services/dcf_engine.py`

### Root Cause

`info.get("sharesOutstanding")` returns 428,434,704 for MSFT in the DCF context, but 7,428,434,704 in the EPV context. This is a ~17× discrepancy.

The actual value from MarketWatch is 7.43B (7,430,000,000). The DCF value 428,434,704 is suspiciously close to the **last 9 digits** of 7,428,434,704 minus the leading "7" — suggesting a parsing/truncation issue, possibly a type conversion problem in `_clean()` or a `sharesOutstanding` vs `sharesOutstanding` key collision.

### Fix Instructions

**Step 6.1 — Add debug logging**

In `dcf_engine.py`, around line 70:
```python
shares_raw = info.get("sharesOutstanding")
shares = _clean(shares_raw)
import logging
log = logging.getLogger(__name__)
log.warning("DCF [%s] sharesOutstanding raw=%s cleaned=%s", ticker, shares_raw, shares)
```

**Step 6.2 — Use `_clean` consistently**

The issue might be that `_clean()` converts to float and there's a precision loss. Add a guard:
```python
shares_raw = info.get("sharesOutstanding")
# _clean may lose precision on large numbers; use direct float conversion
if shares_raw is not None:
    try:
        shares = float(shares_raw)
        if math.isnan(shares) or math.isinf(shares) or shares <= 0:
            shares = None
    except (TypeError, ValueError):
        shares = None
else:
    shares = None
```

**Step 6.3 — Alternative: fetch shares from fast_info**

```python
if shares is None or (ticker == "MSFT" and shares < 1e9):  # Suspiciously small
    try:
        fi = yf.Ticker(ticker).fast_info
        alt_shares = fi.get("shares_outstanding") or fi.get("sharesOutstanding")
        if alt_shares:
            shares = float(alt_shares)
    except Exception:
        pass
```

---

## Fix 7 — Use Computed Beta in KPI Strip

**Severity:** 🟡 HIGH — Beta shows "—" in key metrics  
**Files affected:** `backend/backend/routers/valuation.py` (lines 19–50, `_kpis` function)  
**Also:** `backend/backend/routers/valuation.py` (the `full` endpoint flow)

### Root Cause

The `_kpis()` function uses `g("beta")` which reads from the yfinance info dict. The yfinance `info.beta` is null. But the `_beta_for()` function in the same file correctly computes beta from price data.

### Fix Instructions

In `_kpis()`, replace:
```python
"beta": g("beta"),
```
with a computed value. But `_kpis` doesn't compute beta itself — it just formats fields from the info dict. The fix needs to be in the `full()` endpoint:

```python
@router.get("/full")
async def full(ticker: str):
    sym = ticker.strip().upper()
    bundle = await asyncio.to_thread(yfs.get_info, sym)
    beta = await asyncio.to_thread(_beta_for, sym)  # Already exists!
    valuation = await asyncio.to_thread(valuation_models, bundle, beta)
    fundamentals = await asyncio.to_thread(extended_fundamentals, bundle)
    analyst = await asyncio.to_thread(analyst_data, sym)
    
    # Compute KPIs WITH computed beta
    kpis = _kpis(bundle.get("info", {}) or {})
    if beta is not None:
        kpis["beta"] = beta  # Override null yfinance beta with computed beta
    
    return {
        "ticker": sym,
        "kpis": kpis,
        "valuation": valuation,
        "fundamentals": fundamentals,
        "analyst": analyst,
    }
```

---

## Fix 8 — Standardize Percentage Formatting Across Frontend

**Severity:** 🟢 LOW — No active bug, but fragile pattern  
**Files affected:** `frontend/lib/format.ts`, all components using `fmtPct`/`fmtPctFromFraction`

### Current State

- `fmtPct(v)` — appends "%" to the value as-is (no multiplication). Used for yfinance direct-percentage values like `dividendYield` (0.39 → "0.39%")
- `fmtPctFromFraction(v)` — multiplies by 100 first. Used for computed ratios like margins (0.27 → "27.00%")
- Some components use `fmtPct(n * 100)` to achieve the same effect as `fmtPctFromFraction(n)`

This is fragile: a developer who doesn't know whether a field is stored as percentage or fraction will pick the wrong formatter.

### Fix Instructions

**Step 8.1 — Add a type-aware formatter in `format.ts`**

```typescript
export type PercentFormat = "direct" | "fraction";

/**
 * Format a percent value.
 * @param v - The value to format
 * @param fmt - "direct": value IS the percent (e.g., 0.39 → "0.39%")
 *               "fraction": value is a fraction (e.g., 0.0039 → "0.39%")
 * @param digits - Number of decimal places
 */
export function fmtPctFlex(
  v: number | null | undefined,
  fmt: PercentFormat = "fraction",
  digits = 2
): string {
  if (v === null || v === undefined || Number.isNaN(v)) return DASH;
  const pct = fmt === "direct" ? v : v * 100;
  return `${pct.toFixed(digits)}%`;
}
```

**Step 8.2 — Create a field-to-format mapping**

```typescript
// In a central location (e.g., format.ts or a new ratioGuide.ts)
export const FIELD_PCT_FORMAT: Record<string, PercentFormat> = {
  dividendYield: "direct",
  // All yfinance percentage fields use "direct"
  // All computed ratios use "fraction"
};
```

**Step 8.3 — Update `RatiosTab.tsx` to use `fmtPctFlex`**

The existing `PCT_DIRECT_KEYS` set can remain but should route through `fmtPctFlex`.

---

## Fix 9 — Backfill Multi-Period Financial Data

**Severity:** 🟢 LOW — Enables full Piotroski, Beneish, deeper analysis  
**Files affected:** `backend/backend/scripts/` (new script), `backend/backend/db_models.py`

### Fix Instructions

Create a new backfill script `backend/backend/scripts/backfill_fundamentals.py` that:

1. Iterates over a ticker universe (S&P 500 constituents)
2. For each ticker, calls `yf.Ticker(t).get_financials(freq='yearly')` to get multi-year data
3. Stores the last 5 years of key metrics in SQLite:
   - Net Income, Total Assets, Total Revenue, Gross Profit, Total Debt, Current Assets, Current Liabilities
   - Operating Cash Flow, Free Cash Flow
   - Per year as separate columns or rows
4. Updates `DailyQuote` table with the latest periodic data

This can then be read by `piotroski_f()` and `beneish_m()` when prior-year data is needed.

---

## Fix 10 — Add yfinance Field Health Check

**Severity:** 🟢 LOW — Preventative monitoring  
**Files affected:** New file `backend/backend/services/health_check.py`

### Fix Instructions

Create a startup health check that verifies critical yfinance info dict keys exist:

```python
"""Health check: verify yfinance data availability on startup."""
import yfinance as yf
import logging

log = logging.getLogger(__name__)

CRITICAL_KEYS = [
    "currentPrice", "trailingPE", "forwardPE", "marketCap",
    "dividendYield", "fiftyTwoWeekHigh", "fiftyTwoWeekLow",
    "sharesOutstanding", "bookValue", "currency",
]

WARNING_KEYS = [
    "trailingEps", "forwardEps", "freeCashflow", "sector", "industry", "beta",
]

def check_yfinance_keys():
    """Test AAPL info dict and report missing keys."""
    try:
        t = yf.Ticker("AAPL")
        info = t.get_info() or {}
        
        critical_missing = [k for k in CRITICAL_KEYS if k not in info or info.get(k) is None]
        warning_missing = [k for k in WARNING_KEYS if k not in info or info.get(k) is None]
        
        if critical_missing:
            log.warning("yfinance CRITICAL keys missing: %s", critical_missing)
        if warning_missing:
            log.warning("yfinance WARNING keys missing: %s", warning_missing)
        
        return {
            "status": "degraded" if critical_missing else "ok",
            "critical_missing": critical_missing,
            "warning_missing": warning_missing,
        }
    except Exception as e:
        log.error("yfinance health check failed: %s", e)
        return {"status": "error", "error": str(e)}
```

Call `check_yfinance_keys()` in the `lifespan()` function in `main.py` at startup.

---

## Testing Plan

### Unit Tests to Update

| Test File | What to Update |
|-----------|---------------|
| `tests/test_dcf_engine.py` | Add test for MSFT share count ≥ 7B; test FCF from cashflow dict |
| `tests/test_valuation_engine.py` | Add tests for EPS=null fallback, Graham/PEG/Lynch when EPS injected |
| `tests/test_fundamentals.py` | Add multi-period piotroski tests with DataFrame input |
| `tests/test_options_engine.py` | Add IV backsolve fallback test when `impliedVolatility` is missing |
| `tests/test_smoke.py` | Verify `/api/valuation/full?ticker=AAPL` returns EPS, sector, beta non-null |

### Integration Test (Docker)

After each fix:
```bash
docker compose build backend && docker compose up -d --force-recreate backend

# Test Fix 1 + 3
curl -s http://localhost/api/valuation/full?ticker=AAPL | python -c "import json,sys; d=json.load(sys.stdin); k=d['kpis']; assert k['trailingEps'] is not None, 'EPS missing'; assert k['sector'] is not None, 'sector missing'; print('Fix 1 OK')"

# Test Fix 2
curl -s http://localhost/api/options/ivmetrics?ticker=AAPL | python -c "import json,sys; d=json.load(sys.stdin); assert d['iv30'] is None or d['iv30'] > 1, f'IV30 too low: {d[\"iv30\"]}'; print('Fix 2 OK')"

# Test Fix 4
curl -s http://localhost/api/valuation/full?ticker=AAPL | python -c "import json,sys; d=json.load(sys.stdin); models=d['valuation']['models']; dcf=next(m for m in models if m['model']=='DCF (Two-Stage)'); assert not dcf['locked'], f'DCF still locked: {dcf[\"reason\"]}'; print('Fix 4 OK')"

# Test Fix 7
curl -s http://localhost/api/valuation/full?ticker=AAPL | python -c "import json,sys; d=json.load(sys.stdin); assert d['kpis']['beta'] is not None, 'beta null'; print('Fix 7 OK')"

# Run full test suite
pytest backend/tests/ -v
```

---

## Deployment Order

```
Fix 1 (yfinance keys) ──► docker compose build backend && docker compose up -d --force-recreate
Fix 2 (Options IV)   ──► docker compose build backend && docker compose up -d --force-recreate
Fix 5 (Piotroski)    ──► docker compose build backend && docker compose up -d --force-recreate
Fix 6 (MSFT shares)  ──► docker compose build backend && docker compose up -d --force-recreate
Fix 7 (Beta KPI)     ──► docker compose build backend && docker compose up -d --force-recreate
Fix 8 (Formatting)   ──► docker compose build frontend && docker compose up -d --force-recreate frontend
Fix 9 (Backfill)     ──► Run as script, no rebuild needed
Fix 10 (Health)      ──► docker compose build backend && docker compose up -d --force-recreate
```

Fixes 1–7 are **backend-only** and can be batched into a single deploy. Fix 8 is **frontend-only**. Fixes 9–10 are additive.

---

## Appendix: Key File Reference

| File | Purpose | Lines to Modify |
|------|---------|-----------------|
| `backend/backend/services/yfinance_service.py` | Core yfinance wrapper | 237–260 (get_info) |
| `backend/backend/services/options_engine.py` | Options analytics | 365–381, 283–291, 618–625, 685–702 |
| `backend/backend/services/dcf_engine.py` | DCF valuation | 69–72 (shares extraction) |
| `backend/backend/services/fundamentals.py` | Piotroski/Beneish/Ohlson | Full rewrite of piotroski_f, beneish_m |
| `backend/backend/services/valuation_engine.py` | 8-model valuation | No changes needed (auto-fixes via info dict) |
| `backend/backend/routers/valuation.py` | Valuation API endpoint | 36 (beta), 80-90 (full endpoint beta override) |
| `backend/backend/routers/options.py` | Options API | Already calls options_engine, no changes needed |
| `backend/backend/main.py` | App entrypoint | Add health check call |
| `frontend/lib/format.ts` | Frontend formatting | Add `fmtPctFlex` |
| `frontend/components/markets/RatiosTab.tsx` | Ratios display | Update to use `fmtPctFlex` |
| `frontend/components/markets/ValuationKpiPanel.tsx` | KPI display | Verify beta display after Fix 7 |

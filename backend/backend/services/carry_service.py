"""G10 FX Carry Analytics — Phase 14.

Computes:
  - Carry table: foreign policy rate − USD policy rate, FX vol, vol-adjusted carry
  - Carry backtest: long top-3 / short bottom-3 by carry, base-100 cumulative
"""
from __future__ import annotations

import logging
import math
from datetime import date, timedelta

import numpy as np
import pandas as pd

from .. import provenance as pv
from ..cache import cached
from . import rates_service
from . import yfinance_service as yfs

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# G10 currency config
# ---------------------------------------------------------------------------

# CCY → list of FRED series ids to try in order (first with recent data wins).
# Primary: OECD "Immediate Rates (<24h): Central Bank Rates" (IRSTCI01*) — current
# policy-rate proxies. Fallback: OECD 3-month interbank (IR3TIB01*) for currencies
# whose immediate-rate series has been discontinued. The legacy INTDSR* discount-rate
# series were dropped — they ended ~2021 and fail the staleness guard.
_POLICY_RATE_SERIES: dict[str, list[str]] = {
    "USD": ["FEDFUNDS"],
    "EUR": ["ECBMRRFR", "ECBDFR", "IRSTCI01EZM156N"],
    "GBP": ["IRSTCI01GBM156N", "IR3TIB01GBM156N"],
    "CAD": ["IRSTCI01CAM156N", "IR3TIB01CAM156N"],
    "AUD": ["IRSTCI01AUM156N", "IR3TIB01AUM156N"],
    "NZD": ["IRSTCI01NZM156N", "IR3TIB01NZM156N"],
    "CHF": ["IRSTCI01CHM156N", "IR3TIB01CHM156N"],
    "JPY": ["IRSTCI01JPM156N", "IR3TIB01JPM156N"],
}

# Non-USD G10 currencies (NOK/SEK omitted — no reliable FRED policy rate series)
_NON_USD_CCYS = ["EUR", "GBP", "CAD", "AUD", "NZD", "CHF", "JPY"]

# Yahoo Finance FX tickers: <CCY>USD=X  (USD per 1 unit foreign)
def _fx_ticker(ccy: str) -> str:
    return f"{ccy}USD=X"

# DXY proxy
_DXY_TICKERS = ("DX-Y.NYB", "UUP")

# Minimum days since last observation for a series to be considered "recent"
_MAX_STALE_DAYS = 120


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _clean(v) -> float | None:
    """Return float or None, never NaN/inf."""
    if v is None:
        return None
    try:
        f = float(v)
        return f if math.isfinite(f) else None
    except (TypeError, ValueError):
        return None


def _resolve_policy_rate_series(start: str) -> tuple[dict[str, pd.Series], dict[str, str]]:
    """Per currency, the full history of the first candidate FRED series whose
    latest observation is recent. Returns (CCY -> series in %, CCY -> id)."""
    all_series: list[str] = []
    for series_list in _POLICY_RATE_SERIES.values():
        all_series.extend(series_list)
    # Deduplicate while preserving order
    seen: set[str] = set()
    unique_series = [s for s in all_series if not (s in seen or seen.add(s))]

    fred_data = rates_service._fetch_many_fred_sync(unique_series, start)

    out: dict[str, pd.Series] = {}
    sources: dict[str, str] = {}
    cutoff = date.today() - timedelta(days=_MAX_STALE_DAYS)

    for ccy, candidates in _POLICY_RATE_SERIES.items():
        for sid in candidates:
            series = fred_data.get(sid)
            if series is None or series.empty:
                continue
            clean = series.dropna()
            if clean.empty:
                continue
            last_idx = clean.index[-1]
            last_date = last_idx.date() if hasattr(last_idx, "date") else date.fromisoformat(str(last_idx)[:10])
            if last_date < cutoff:
                log.debug("FRED %s for %s last obs %s is stale (>%d days)", sid, ccy, last_date, _MAX_STALE_DAYS)
                continue
            clean.index = pd.to_datetime(clean.index)
            out[ccy] = clean.sort_index()
            sources[ccy] = sid
            log.info("Carry: %s resolved via %s (last obs %s)", ccy, sid, last_date)
            break
        else:
            log.warning("Carry: could not resolve policy rate for %s", ccy)

    return out, sources


def _resolve_policy_rates(start: str, observed: dict[str, str] | None = None) -> tuple[dict[str, float], dict[str, str]]:
    """Latest policy rate per currency (%), and the FRED id that resolved.

    If ``observed`` is given it is filled with CCY -> date of the latest observation."""
    series, sources = _resolve_policy_rate_series(start)
    if observed is not None:
        observed.update({ccy: str(s.index[-1])[:10] for ccy, s in series.items()})
    return {ccy: round(float(s.iloc[-1]), 4) for ccy, s in series.items()}, sources


def _compute_fx_vol(close: pd.DataFrame, ticker: str, min_rows: int = 20) -> float | None:
    """Annualised FX vol (%) from daily log returns."""
    if ticker not in close.columns:
        return None
    series = close[ticker].dropna()
    if len(series) < min_rows:
        return None
    log_rets = np.log(series / series.shift(1)).dropna()
    if len(log_rets) < min_rows:
        return None
    vol = float(log_rets.std() * math.sqrt(252) * 100)
    return round(vol, 4) if math.isfinite(vol) else None


def _rate_ref(ccy: str, sid: str, observed: str | None) -> dict:
    """FRED ref for the rate series that resolved for ``ccy``."""
    interbank = sid.startswith("IR3TIB01")
    primary = _POLICY_RATE_SERIES[ccy][0]
    note = None
    if sid != primary:
        note = f"Primary series {primary} was missing or stale, so {sid} stood in."
    return pv.fred(
        sid, f"{ccy} short-term interest rate" + (" (3-month interbank, not a policy rate)" if interbank else ""),
        units="% p.a.", frequency="daily" if sid.startswith("ECB") else "monthly", observed=observed,
        flags=("proxy",) if interbank else (), note=note)


def _metrics_from_series(cum: pd.Series) -> dict:
    """Compute CAGR, vol, Sharpe, maxDrawdown from a base-100 cumulative series."""
    if cum.empty or len(cum) < 2:
        return {"cagr": None, "vol": None, "sharpe": None, "maxDrawdown": None}
    log_rets = np.log(cum / cum.shift(1)).dropna()
    n = len(log_rets)
    years = n / 252
    total_return = float(cum.iloc[-1] / cum.iloc[0]) - 1.0
    cagr = round(((1 + total_return) ** (1 / years) - 1) * 100, 4) if years > 0 else None
    ann_vol = round(float(log_rets.std() * math.sqrt(252) * 100), 4) if n > 1 else None
    # Sharpe (rf = 0): annualised mean daily return over annualised vol.
    ann_mean = float((cum / cum.shift(1) - 1).dropna().mean() * 252 * 100)
    sharpe = round(ann_mean / ann_vol, 4) if (ann_vol and ann_vol > 0) else None
    rolling_max = cum.cummax()
    dd = (cum - rolling_max) / rolling_max
    max_dd = round(float(dd.min() * 100), 4)
    return {
        "cagr": _clean(cagr),
        "vol": _clean(ann_vol),
        "sharpe": _clean(sharpe),
        "maxDrawdown": _clean(max_dd),
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

@cached("carry_table")
def get_carry_table(period: str = "3y") -> dict:
    """Build G10 FX carry table sorted by carry (desc).

    Returns:
    {
      "asOf": "YYYY-MM-DD",
      "usdRate": float,
      "rows": [
        {
          "ccy": "AUD",
          "pair": "AUD/USD",
          "spot": float,
          "foreignRate": float,
          "carry": float,
          "fxVol": float | None,
          "volAdjCarry": float | None,
          "rateSource": "INTDSRAUAM193N"
        },
        ...
      ]  # sorted by carry desc
    }
    """
    try:
        # 5-year start to ensure we have recent observations
        start = (date.today() - timedelta(days=5 * 365)).strftime("%Y-%m-%d")
        rate_obs: dict[str, str] = {}
        rates, sources = _resolve_policy_rates(start, rate_obs)

        usd_rate = rates.get("USD")
        if usd_rate is None:
            log.warning("Carry: could not resolve USD policy rate (FEDFUNDS)")
            return {"error": "USD policy rate unavailable", "asOf": str(date.today()), "usdRate": None, "rows": []}

        # Fetch FX spot data
        fx_tickers = tuple(_fx_ticker(ccy) for ccy in _NON_USD_CCYS)
        close = yfs.get_close_frame(fx_tickers, period)

        rows = []
        for ccy in _NON_USD_CCYS:
            if ccy not in rates:
                continue
            ticker = _fx_ticker(ccy)
            foreign_rate = rates[ccy]
            carry = round(foreign_rate - usd_rate, 4)

            # Spot price
            spot: float | None = None
            if ticker in close.columns:
                last_valid = close[ticker].dropna()
                if not last_valid.empty:
                    spot = round(float(last_valid.iloc[-1]), 6)

            fx_vol = _compute_fx_vol(close, ticker)
            vol_adj_carry: float | None = None
            if fx_vol is not None and fx_vol > 0:
                vol_adj_carry = round(carry / fx_vol, 4)

            rows.append({
                "ccy": ccy,
                "pair": f"{ccy}/USD",
                "spot": _clean(spot),
                "foreignRate": _clean(foreign_rate),
                "carry": _clean(carry),
                "fxVol": _clean(fx_vol),
                "volAdjCarry": _clean(vol_adj_carry),
                "rateSource": sources.get(ccy, "unknown"),
            })

        rows.sort(key=lambda r: r["carry"] if r["carry"] is not None else -999, reverse=True)

        # Determine asOf date from FX data
        as_of = str(date.today())
        if not close.empty:
            last_idx = close.dropna(how="all").index
            if len(last_idx):
                d = last_idx[-1]
                as_of = str(d.date()) if hasattr(d, "date") else str(d)[:10]

        fx_input = pv.ref("yahoo", None, "Daily adjusted close of the G10 pairs quoted as USD per unit of currency",
                          units="USD per unit", frequency="daily", observed=as_of if not close.empty else None)
        prov: dict = {
            "*": pv.derived("Carry = foreign short-term rate - US rate (percentage points), with FX spot and volatility "
                            "from Yahoo pairs", [fx_input, "usdRate"], title="G10 FX carry table", observed=as_of),
            "usdRate": _rate_ref("USD", sources["USD"], rate_obs.get("USD")),
        }
        for r in rows:
            c = r["ccy"]
            pair = _fx_ticker(c)
            prov[f"rows.{c}.foreignRate"] = _rate_ref(c, sources[c], rate_obs.get(c))
            prov[f"rows.{c}.spot"] = pv.yahoo(
                pair, f"{c}/USD spot (last close)", units="USD per unit", frequency="daily",
                observed=pv.last_date(close[pair]) if pair in close.columns else None)
            prov[f"rows.{c}.carry"] = pv.derived("foreignRate - usdRate (percentage points)",
                                                 [f"rows.{c}.foreignRate", "usdRate"], title="Carry")
            prov[f"rows.{c}.fxVol"] = pv.derived(
                f"sample std of daily log returns of {pair} over the requested period × √252 × 100 (percent)",
                [f"rows.{c}.spot"], title="FX volatility")
            prov[f"rows.{c}.volAdjCarry"] = pv.derived("carry ÷ fxVol", [f"rows.{c}.carry", f"rows.{c}.fxVol"],
                                                       title="Vol-adjusted carry")
        return pv.attach({
            "asOf": as_of,
            "usdRate": _clean(usd_rate),
            "rows": rows,
        }, prov)
    except Exception as exc:
        log.exception("get_carry_table failed: %s", exc)
        return {"error": str(exc), "asOf": str(date.today()), "usdRate": None, "rows": []}


@cached("carry_backtest")
def get_carry_backtest(period: str = "3y") -> dict:
    """Long top-3 / short bottom-3 carry strategy backtest.

    Returns:
    {
      "series": [{"date": "YYYY-MM-DD", "strategy": float, "benchmark": float}, ...],
      "legs": {"long": ["AUD", "NZD", "GBP"], "short": ["JPY", "CHF", "EUR"]},
      "metrics": {"cagr": float, "vol": float, "sharpe": float, "maxDrawdown": float}
    }
    """
    _EMPTY = {
        "series": [],
        "legs": {"long": [], "short": []},
        "metrics": {"cagr": None, "vol": None, "sharpe": None, "maxDrawdown": None},
    }
    try:
        # Walk-forward: at each month start, rank currencies by the carry
        # known *then* and hold long top-3 / short bottom-3 for the month.
        # Earlier versions ranked by today's carry and applied those legs to
        # the whole history (look-ahead), and earned FX moves only — never
        # the interest differential that is the point of a carry trade (C-06).
        start = (date.today() - timedelta(days=8 * 365)).strftime("%Y-%m-%d")
        rate_series, rate_sources = _resolve_policy_rate_series(start)
        if "USD" not in rate_series:
            return {**_EMPTY, "error": "USD policy rate unavailable"}
        ccys = [c for c in _NON_USD_CCYS if c in rate_series]
        if len(ccys) < 6:
            return {**_EMPTY, "error": f"not enough currencies with carry data (need 6, got {len(ccys)})"}

        close = yfs.get_close_frame(tuple(_fx_ticker(c) for c in ccys), period)
        if close.empty:
            return {**_EMPTY, "error": "no FX price data"}
        close.index = pd.to_datetime(close.index)
        # Daily return of holding each currency vs USD (tickers are USD per unit).
        fx_rets = close.ffill().pct_change().rename(columns={_fx_ticker(c): c for c in ccys})

        def _rate_known(ccy: str, when: pd.Timestamp) -> float | None:
            # Monthly FRED policy/interbank rates are averages dated the 1st of
            # the month and published after it ends: lag one month.
            s = rate_series[ccy].loc[: when - pd.DateOffset(months=1) - pd.Timedelta(days=1)]
            return float(s.iloc[-1]) if len(s) else None

        weight = 1.0 / 3.0
        strategy_parts: list[pd.Series] = []
        long_ccys: list[str] = []
        short_ccys: list[str] = []
        months = fx_rets.index.to_period("M")
        for month in months.unique():
            seg = fx_rets[months == month].dropna(how="all")
            if seg.empty:
                continue
            t0 = seg.index[0]
            usd = _rate_known("USD", t0)
            carry = {c: _rate_known(c, t0) - usd for c in ccys
                     if usd is not None and _rate_known(c, t0) is not None}
            if len(carry) < 6:
                continue
            ranked = sorted(carry, key=carry.get, reverse=True)
            long_ccys, short_ccys = ranked[:3], ranked[-3:]
            leg = pd.Series(0.0, index=seg.index)
            for c in long_ccys:
                leg += weight * (seg[c].fillna(0.0) + carry[c] / 100.0 / 252)
            for c in short_ccys:
                leg -= weight * (seg[c].fillna(0.0) + carry[c] / 100.0 / 252)
            strategy_parts.append(leg)

        strategy_rets = pd.concat(strategy_parts).dropna() if strategy_parts else pd.Series(dtype=float)
        if strategy_rets.empty:
            return {**_EMPTY, "error": "strategy returns are empty"}

        dxy_close: pd.Series | None = None
        for dxy_sym in _DXY_TICKERS:
            dxy_frame = yfs.get_close_frame((dxy_sym,), period)
            if dxy_sym in dxy_frame.columns and not dxy_frame[dxy_sym].dropna().empty:
                dxy_close = dxy_frame[dxy_sym].dropna()
                dxy_close.index = pd.to_datetime(dxy_close.index)
                break

        cum_strategy = (1 + strategy_rets).cumprod() * 100

        # Benchmark base-100
        bench_series: pd.Series | None = None
        if dxy_close is not None and not dxy_close.empty:
            dxy_rets = dxy_close.pct_change().dropna()
            bench_series = (1 + dxy_rets).cumprod() * 100
        else:
            bench_series = pd.Series(100.0, index=cum_strategy.index)

        # Align on common index
        common_idx = cum_strategy.index.intersection(bench_series.index)
        if common_idx.empty:
            # Reindex benchmark to strategy
            bench_aligned = bench_series.reindex(cum_strategy.index, method="ffill").fillna(100.0)
        else:
            cum_strategy = cum_strategy.reindex(common_idx)
            bench_aligned = bench_series.reindex(common_idx)

        # Build series output
        series_records = []
        for dt, strat_val in cum_strategy.items():
            bench_val = bench_aligned.get(dt, None) if hasattr(bench_aligned, "get") else bench_aligned.loc[dt] if dt in bench_aligned.index else None
            series_records.append({
                "date": str(dt.date()) if hasattr(dt, "date") else str(dt)[:10],
                "strategy": _clean(strat_val),
                "benchmark": _clean(bench_val),
            })

        metrics = _metrics_from_series(cum_strategy)

        obs = series_records[-1]["date"] if series_records else None
        fx_input = pv.ref("yahoo", None, "Daily adjusted close of the G10 pairs quoted as USD per unit of currency",
                          units="USD per unit", frequency="daily", observed=pv.last_date(close))
        rate_inputs = [_rate_ref(c, rate_sources[c], str(rate_series[c].index[-1])[:10]) for c in ["USD"] + ccys]
        if dxy_close is not None:
            bench_ref = pv.yahoo(dxy_sym, "US dollar index proxy, daily close", frequency="daily",
                                 observed=pv.last_date(dxy_close),
                                 flags=("proxy",) if dxy_sym == "UUP" else (),
                                 note="UUP (an ETF) stands in for the dollar index." if dxy_sym == "UUP" else None)
        else:
            bench_ref = pv.derived("flat 100 line: neither DX-Y.NYB nor UUP returned data, so there is no benchmark",
                                   [], title="Benchmark unavailable", flags=("fallback",))
        prov = {
            "*": pv.derived(
                "Walk-forward carry strategy: each month start, rank the 7 non-USD G10 currencies by (foreign - USD "
                "policy rate) known then (rates lagged one month), go long the top 3 and short the bottom 3 at 1/3 "
                "each; daily return = FX return ± carry ÷ 100 ÷ 252", rate_inputs + [fx_input],
                title="G10 carry backtest", observed=obs),
            "series": pv.derived("base-100 compounding of the daily strategy return", ["*"], title="Strategy value",
                                 observed=obs),
            "series.benchmark": bench_ref,
            "legs": pv.derived("the top-3 (long) and bottom-3 (short) currencies at the last month start", ["*"],
                               title="Current legs", observed=obs),
            "metrics": pv.derived(
                "in percent: cagr = (final ÷ first)^(252/n) - 1; vol = std of daily log returns × √252; sharpe = mean "
                "daily return × 252 ÷ vol (no risk-free deduction); maxDrawdown = worst value ÷ running peak - 1",
                ["series"], title="Strategy statistics", observed=obs),
        }
        return pv.attach({
            "series": series_records,
            "legs": {"long": long_ccys, "short": short_ccys},
            "metrics": metrics,
        }, prov)
    except Exception as exc:
        log.exception("get_carry_backtest failed: %s", exc)
        return {**_EMPTY, "error": str(exc)}

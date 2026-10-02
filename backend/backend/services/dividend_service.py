"""Dividend Analysis service — Phase 27.

Dividend yield, growth rates, payout ratio, sustainability score, and DDM fair value.
"""
from __future__ import annotations

import logging

import numpy as np
import pandas as pd
import yfinance as yf

from .. import provenance as pv
from ..cache import cached
from . import dcf_engine

logger = logging.getLogger(__name__)


def _latest_val(df, row_name: str) -> float | None:
    try:
        if df is None or df.empty or row_name not in df.index:
            return None
        v = float(df.loc[row_name].iloc[0])
        return v if np.isfinite(v) else None
    except Exception:
        return None


def _now() -> pd.Timestamp:
    return pd.Timestamp.now()


def _safe_div(a: float | None, b: float | None) -> float | None:
    if a is None or b is None or b == 0:
        return None
    return a / b


@cached("dividend_analysis")
def get_dividend_analysis(ticker: str) -> dict:
    """Return dividend yield, growth rates, payout ratio, sustainability, and DDM fair value."""
    ticker = ticker.strip().upper()
    try:
        stock = yf.Ticker(ticker)
        info = stock.info or {}
        dividends = stock.dividends
        cashflow = stock.cashflow

        price = info.get("currentPrice") or info.get("regularMarketPrice")
        name = info.get("shortName") or info.get("longName") or ticker
        sector = info.get("sector")

        # Current dividend yield — yfinance already returns this in percent
        # units (e.g. 0.98 = 0.98%), matching metrics.compute_ratios and the
        # frontend which format it directly. Do NOT multiply by 100.
        div_yield = info.get("dividendYield")
        if div_yield is not None:
            div_yield = round(float(div_yield), 2)

        # Annual dividend history (per share, sum by calendar year) — complete
        # years only. The running year is partial, and so is the first year of
        # the record; summing either as "annual" broke the CAGR, reset the
        # growth streak to 0 for most of every year and fed the DDM (C-02).
        annual_divs: dict[int, float] = {}
        ttm_div = None
        last_div_date = None
        if dividends is not None and not dividends.empty:
            divs = dividends.sort_index()
            idx = pd.DatetimeIndex(divs.index)
            if idx.tz is not None:
                idx = idx.tz_convert(None)
            divs.index = idx
            last_div_date = divs.index[-1]
            now = _now()
            this_year = now.year
            for dt, val in divs.items():
                y = dt.year
                if y < this_year:
                    annual_divs[y] = annual_divs.get(y, 0) + float(val)
            if len(annual_divs) > 1:
                annual_divs.pop(min(annual_divs))
            window = divs[divs.index > now - pd.Timedelta(days=365)]
            ttm_div = float(window.sum()) if len(window) else None

        years = sorted(annual_divs.keys())
        latest_year = years[-1] if years else None
        latest_annual_div = annual_divs.get(latest_year) if latest_year else None

        # Dividend growth rates (CAGR)
        def _cagr(years_back: int) -> float | None:
            if latest_year is None:
                return None
            target_year = latest_year - years_back
            # Find closest year ≤ target
            candidates = [y for y in years if y <= target_year]
            if not candidates:
                return None
            ref_year = max(candidates)
            ref_div = annual_divs[ref_year]
            cur_div = annual_divs[latest_year]
            if ref_div is None or ref_div <= 0 or cur_div is None or cur_div <= 0:
                return None
            n = latest_year - ref_year
            if n <= 0:
                return None
            cagr = (cur_div / ref_div) ** (1.0 / n) - 1.0
            if not np.isfinite(cagr):
                return None
            return round(cagr * 100, 2)

        cagr_5y = _cagr(5)
        cagr_10y = _cagr(10)

        # Consecutive years of dividend growth
        consecutive_growth = 0
        for i in range(len(years) - 1, 0, -1):
            if annual_divs[years[i]] > annual_divs[years[i - 1]]:
                consecutive_growth += 1
            else:
                break

        # Payout ratios. yfinance dividends are already *per share*: the old
        # code divided by the share count again (payout ≈ 1e-10 → "safe" for
        # every stock) and compared a per-share dividend with total operating
        # cash flow (C-01).
        shares = info.get("sharesOutstanding")
        eps = info.get("trailingEps")
        fcf = info.get("freeCashflow")
        if fcf is None:
            fcf = _latest_val(cashflow, "Free Cash Flow") if cashflow is not None else None
        # FCF is in the statement currency (DKK for NVO); the dividend is in the price currency (P2-38).
        fx_rate = dcf_engine.to_price_currency({"info": info})["_fx"]["rate"]
        fcf = fcf * fx_rate if fcf is not None and fx_rate is not None else None
        payout_ratio = _safe_div(ttm_div, eps) if ttm_div and eps and eps > 0 else None
        fcf_payout = (_safe_div(ttm_div * shares, fcf)
                      if ttm_div and shares and fcf and fcf > 0 else None)

        # Sustainability score (0-100)
        sus_score = 50.0
        components = 0
        if payout_ratio is not None:
            components += 1
            if 0 < payout_ratio < 0.5:
                sus_score += 15
            elif 0.5 <= payout_ratio < 0.7:
                sus_score += 5
            elif payout_ratio >= 0.7:
                sus_score -= 10
            if payout_ratio > 1.0:
                sus_score -= 20
        if fcf_payout is not None:
            components += 1
            if fcf_payout < 0.6:
                sus_score += 15
            elif fcf_payout < 0.8:
                sus_score += 5
            else:
                sus_score -= 10
        if cagr_5y is not None:
            components += 1
            if cagr_5y > 8:
                sus_score += 10
            elif cagr_5y > 3:
                sus_score += 5
            elif cagr_5y < 0:
                sus_score -= 10
        if consecutive_growth >= 10:
            sus_score += 10
        elif consecutive_growth >= 5:
            sus_score += 5
        sus_score = max(0, min(100, sus_score))

        sus_label = "Strong" if sus_score >= 70 else ("Adequate" if sus_score >= 40 else "Weak")

        # DDM: Gordon Growth Model
        ddm_value = None
        ddm_growth = None
        discount = None
        from .discount_rates import risk_free_rate
        risk_free = risk_free_rate()
        if ttm_div and cagr_5y is not None:
            ddm_growth = min(cagr_5y / 100, risk_free + 0.02)  # cap growth at risk-free + 2%
            ddm_growth = max(ddm_growth, 0.01)  # floor at 1%
            discount = risk_free + 0.05  # 5% equity risk premium
            if discount > ddm_growth:
                ddm_value = ttm_div * (1 + ddm_growth) / (discount - ddm_growth)
                ddm_value = round(ddm_value, 2)

        return pv.attach({
            "ticker": ticker,
            "name": name,
            "sector": sector or None,
            "price": price,
            "dividendYield": div_yield,
            "latestAnnualDividend": latest_annual_div,
            "latestYear": latest_year,
            "ttmDividend": round(ttm_div, 4) if ttm_div is not None else None,
            "cagr5y": cagr_5y,
            "cagr10y": cagr_10y,
            "consecutiveGrowthYears": consecutive_growth,
            "payoutRatio": round(payout_ratio, 4) if payout_ratio is not None else None,
            "fcfPayoutRatio": round(fcf_payout, 4) if fcf_payout is not None else None,
            "sustainabilityScore": round(sus_score, 0),
            "sustainabilityLabel": sus_label,
            "ddmFairValue": ddm_value,
            "ddmGrowthRate": round(ddm_growth * 100, 2) if ddm_growth is not None else None,
            "ddmDiscountRate": round(discount * 100, 2) if discount is not None else None,
            "ddmUpsidePct": round((ddm_value / price - 1) * 100, 1) if ddm_value and price else None,
            "annualDividends": {str(y): round(v, 4) for y, v in sorted(annual_divs.items())},
            "asOf": last_div_date.strftime("%Y-%m-%d") if last_div_date is not None else None,
        }, _provenance(ticker, last_div_date.strftime("%Y-%m-%d") if last_div_date is not None else None))
    except Exception as exc:
        logger.warning("dividend_analysis failed for %s: %s", ticker, exc)
        return {"ticker": ticker, "error": str(exc)}


def _provenance(ticker: str, last_div: str | None) -> dict:
    """Refs for /dividend/analysis: dividend history, TTM figures from Yahoo info, and the DDM inputs."""
    from .discount_rates import risk_free_rate_is_fallback

    hist = pv.yahoo(ticker, "Ticker.dividends: per-share dividend payments", frequency="event",
                    units="currency per share", observed=last_div)
    info = pv.yahoo(ticker, "Ticker.info: price, yield, EPS, shares, free cash flow")
    rf_fallback = risk_free_rate_is_fallback()

    def d(formula: str, inputs: list, title: str, **kw) -> dict:
        return pv.derived(formula, inputs, title=title, **kw)

    annual = "calendar-year sum of dividends; only complete years (the running year and the first year are dropped)"
    rf = pv.fred("DGS10", "US 10-year Treasury constant-maturity yield", frequency="daily",
                 flags=("fallback",) if rf_fallback else (),
                 note="Hard-coded 4% used because FRED could not be read." if rf_fallback else None)
    return {
        "*": hist,
        "price": pv.yahoo(ticker, "info.currentPrice (else regularMarketPrice)"),
        "name": pv.yahoo(ticker, "info.shortName (else longName)"),
        "sector": pv.yahoo(ticker, "info.sector"),
        "dividendYield": pv.yahoo(ticker, "info.dividendYield", units="percent (0.98 = 0.98%)"),
        "annualDividends": d(annual, [hist], title="Annual dividends per share"),
        "latestAnnualDividend": d(annual + ", latest complete year", [hist], title="Latest annual dividend"),
        "ttmDividend": d("sum of dividends paid in the last 365 days", [hist], title="Trailing-12-month dividend"),
        "cagr5y": d("(latest annual dividend / annual dividend 5 years earlier)^(1/years) − 1, in percent",
                    [hist], title="5-year dividend growth"),
        "cagr10y": d("(latest annual dividend / annual dividend 10 years earlier)^(1/years) − 1, in percent",
                     [hist], title="10-year dividend growth"),
        "consecutiveGrowthYears": d("number of consecutive most recent years in which the annual dividend rose",
                                    [hist], title="Consecutive years of dividend growth"),
        "payoutRatio": d("trailing-12-month dividend / info.trailingEps (only if EPS > 0)", [hist, info],
                         title="Payout ratio"),
        "fcfPayoutRatio": d("trailing-12-month dividend × shares outstanding / free cash flow (info.freeCashflow, "
                            "else the latest annual cash-flow statement; only if positive)", [hist, info],
                            title="FCF payout ratio"),
        "sustainabilityScore": d(
            "50 + points for payout ratio (<50% +15, 50-70% +5, ≥70% −10, >100% a further −20), FCF payout (<60% "
            "+15, <80% +5, else −10), 5-year growth (>8% +10, >3% +5, <0 −10) and streak (≥10 years +10, "
            "≥5 +5); clipped to 0-100", ["payoutRatio", "fcfPayoutRatio", "cagr5y", "consecutiveGrowthYears"],
            title="Dividend sustainability score"),
        "sustainabilityLabel": d("score ≥ 70 Strong; ≥ 40 Adequate; else Weak", ["sustainabilityScore"],
                                 title="Sustainability label"),
        "ddmGrowthRate": d("5-year dividend growth, capped at risk-free rate + 2% and floored at 1%", ["cagr5y", rf],
                           title="DDM growth rate"),
        "ddmDiscountRate": d("US 10-year Treasury yield + 5% (a hard-coded equity risk premium)", [rf],
                             title="DDM discount rate"),
        "ddmFairValue": d("TTM dividend × (1 + g) / (r − g), g = the DDM growth rate, r = US 10-year Treasury "
                          "yield + 5% (a hard-coded equity risk premium)", ["ttmDividend", "ddmGrowthRate", rf],
                          title="Dividend discount model value"),
        "ddmUpsidePct": d("(DDM fair value / price − 1) × 100", ["ddmFairValue", "price"], title="DDM upside"),
    }

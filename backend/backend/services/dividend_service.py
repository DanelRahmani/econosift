"""Dividend Analysis service — Phase 27.

Dividend yield, growth rates, payout ratio, sustainability score, and DDM fair value.
"""
from __future__ import annotations

import logging

import numpy as np
import yfinance as yf

from ..cache import cached

logger = logging.getLogger(__name__)


def _latest_val(df, row_name: str) -> float | None:
    try:
        if df is None or df.empty or row_name not in df.index:
            return None
        v = float(df.loc[row_name].iloc[0])
        return v if np.isfinite(v) else None
    except Exception:
        return None


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
        fin = stock.financials
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

        # Annual dividend history (sum by year)
        annual_divs: dict[int, float] = {}
        if dividends is not None and not dividends.empty:
            divs = dividends.sort_index()
            for dt, val in divs.items():
                y = dt.year
                annual_divs[y] = annual_divs.get(y, 0) + float(val)

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

        # Payout ratio
        net_income = _latest_val(fin, "Net Income")
        operating_cf = _latest_val(cashflow, "Operating Cash Flow") if cashflow is not None else None
        shares = info.get("sharesOutstanding")
        dps = _safe_div(latest_annual_div, shares) if latest_annual_div and shares else None
        eps = info.get("trailingEps")
        payout_ratio = _safe_div(dps, eps) if dps and eps else None
        fcf_payout = _safe_div(latest_annual_div, operating_cf) if latest_annual_div and operating_cf else None

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
        risk_free = 0.045  # approximate 10Y
        if latest_annual_div and cagr_5y is not None:
            ddm_growth = min(cagr_5y / 100, risk_free + 0.02)  # cap growth at risk-free + 2%
            ddm_growth = max(ddm_growth, 0.01)  # floor at 1%
            discount = risk_free + 0.05  # 5% equity risk premium
            if discount > ddm_growth:
                ddm_value = latest_annual_div * (1 + ddm_growth) / (discount - ddm_growth)
                ddm_value = round(ddm_value, 2)

        return {
            "ticker": ticker,
            "name": name,
            "sector": sector or None,
            "price": price,
            "dividendYield": div_yield,
            "latestAnnualDividend": latest_annual_div,
            "latestYear": latest_year,
            "cagr5y": cagr_5y,
            "cagr10y": cagr_10y,
            "consecutiveGrowthYears": consecutive_growth,
            "payoutRatio": round(payout_ratio, 4) if payout_ratio is not None else None,
            "fcfPayoutRatio": round(fcf_payout, 4) if fcf_payout is not None else None,
            "sustainabilityScore": round(sus_score, 0),
            "sustainabilityLabel": sus_label,
            "ddmFairValue": ddm_value,
            "ddmGrowthRate": round(ddm_growth * 100, 2) if ddm_growth is not None else None,
            "ddmUpsidePct": round((ddm_value / price - 1) * 100, 1) if ddm_value and price else None,
            "annualDividends": {str(y): round(v, 4) for y, v in sorted(annual_divs.items())},
            "asOf": None,
        }
    except Exception as exc:
        logger.warning("dividend_analysis failed for %s: %s", ticker, exc)
        return {"ticker": ticker, "error": str(exc)}

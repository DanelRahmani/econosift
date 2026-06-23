"""Two-stage DCF valuation engine with scenario analysis and sensitivity heatmap."""
from __future__ import annotations

import math
from datetime import date

from .metrics import _clean


def _single_dcf(
    fcf: float,
    fcf_growth: float,
    terminal_growth: float,
    wacc: float,
    stage1_years: int,
    net_debt: float,
    shares: float,
) -> float | None:
    """Compute per-share intrinsic value for one parameter set. Returns None if invalid."""
    if wacc <= terminal_growth:
        return None
    if wacc <= terminal_growth + 0.005:
        wacc = terminal_growth + 0.005

    pv1 = 0.0
    cf = fcf
    for year in range(1, stage1_years + 1):
        cf = cf * (1 + fcf_growth)
        pv1 += cf / ((1 + wacc) ** year)

    # Terminal value (Gordon Growth Model): FCF_N*(1+g)/(wacc-g)
    tv = cf * (1 + terminal_growth) / (wacc - terminal_growth)
    pv_tv = tv / ((1 + wacc) ** stage1_years)

    ev = pv1 + pv_tv
    equity = ev - net_debt
    intrinsic = equity / shares
    return _clean(intrinsic)


def two_stage_dcf(
    bundle: dict,
    *,
    fcf_growth: float,
    terminal_growth: float,
    wacc: float,
    stage1_years: int = 10,
) -> dict:
    """
    Two-stage DCF valuation returning base result, scenarios, and sensitivity heatmap.

    Parameters
    ----------
    bundle : dict
        Output from yfinance_service.get_info(ticker).
    fcf_growth : float
        Stage-1 FCF growth rate (e.g. 0.08 for 8%).
    terminal_growth : float
        Perpetuity growth rate for terminal value.
    wacc : float
        Weighted-average cost of capital discount rate.
    stage1_years : int
        Number of years in Stage 1 (default 10).
    """
    info: dict = bundle.get("info") or {}
    ticker: str = bundle.get("ticker") or ""

    # --- Extract inputs ---
    fcf_raw = info.get("freeCashflow") or info.get("operatingCashflow")
    shares_raw = info.get("sharesOutstanding")
    total_debt_raw = info.get("totalDebt") or 0
    total_cash_raw = info.get("totalCash") or 0
    currency = info.get("currency") or "USD"
    spot_raw = info.get("currentPrice") or info.get("regularMarketPrice")

    fcf = _clean(fcf_raw)
    shares = _clean(shares_raw)
    net_debt = (_clean(total_debt_raw) or 0.0) - (_clean(total_cash_raw) or 0.0)
    spot = _clean(spot_raw)
    as_of = date.today().isoformat()

    # --- Guard conditions ---
    def _locked(reason: str) -> dict:
        return {
            "ticker": ticker,
            "currency": currency,
            "spotPrice": spot,
            "intrinsicValue": None,
            "upsidePct": None,
            "locked": True,
            "reason": reason,
            "inputs": {
                "ttmFcf": fcf,
                "shares": shares,
                "netDebt": net_debt,
                "fcfGrowth": fcf_growth,
                "terminalGrowth": terminal_growth,
                "wacc": wacc,
                "stage1Years": stage1_years,
            },
            "scenarios": [],
            "sensitivity": {},
            "asOf": as_of,
        }

    if fcf is None:
        return _locked("TTM free cash flow unavailable")
    if shares is None:
        return _locked("Shares outstanding unavailable")
    if shares <= 0:
        return _locked("Shares outstanding is zero or negative")
    if wacc <= terminal_growth:
        return _locked(
            f"WACC ({wacc:.3f}) must be greater than terminal growth ({terminal_growth:.3f})"
        )

    # --- Base intrinsic value ---
    intrinsic = _single_dcf(fcf, fcf_growth, terminal_growth, wacc, stage1_years, net_debt, shares)

    upside_pct: float | None = None
    if intrinsic is not None and spot is not None and spot != 0:
        upside_pct = _clean((intrinsic - spot) / spot)

    # --- Scenario table ---
    bear_wacc = wacc + 0.01
    bear_growth = fcf_growth - 0.03
    bull_wacc = max(wacc - 0.01, terminal_growth + 0.005)
    bull_growth = fcf_growth + 0.03

    def _scenario_entry(label: str, sg: float, sw: float) -> dict:
        iv = _single_dcf(fcf, sg, terminal_growth, sw, stage1_years, net_debt, shares)
        up: float | None = None
        if iv is not None and spot is not None and spot != 0:
            up = _clean((iv - spot) / spot)
        return {
            "scenario": label,
            "fcfGrowth": round(sg, 4),
            "wacc": round(sw, 4),
            "intrinsicValue": iv,
            "upsidePct": up,
        }

    scenarios = [
        _scenario_entry("Bear", bear_growth, bear_wacc),
        _scenario_entry("Base", fcf_growth, wacc),
        _scenario_entry("Bull", bull_growth, bull_wacc),
    ]

    # --- Sensitivity heatmap 7×7 ---
    fcf_steps = [round(fcf_growth + (i - 3) * 0.01, 4) for i in range(7)]
    wacc_steps = [round(wacc + (i - 3) * 0.005, 4) for i in range(7)]

    grid: list[list[float | None]] = []
    for fg in fcf_steps:
        row: list[float | None] = []
        for wc in wacc_steps:
            if wc <= terminal_growth:
                row.append(None)
            else:
                row.append(_single_dcf(fcf, fg, terminal_growth, wc, stage1_years, net_debt, shares))
        grid.append(row)

    sensitivity = {
        "fcfGrowthAxis": fcf_steps,
        "waccAxis": wacc_steps,
        "grid": grid,
    }

    return {
        "ticker": ticker,
        "currency": currency,
        "spotPrice": spot,
        "intrinsicValue": intrinsic,
        "upsidePct": upside_pct,
        "locked": False,
        "inputs": {
            "ttmFcf": fcf,
            "shares": shares,
            "netDebt": net_debt,
            "fcfGrowth": fcf_growth,
            "terminalGrowth": terminal_growth,
            "wacc": wacc,
            "stage1Years": stage1_years,
        },
        "scenarios": scenarios,
        "sensitivity": sensitivity,
        "asOf": as_of,
    }

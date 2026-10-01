"""Audit M-18 (Sharpe/Sortino on simple returns, FRED rf) and M-23 (bank ratios), M-17 support fields.

No network: prices are synthetic, yfinance_service and the rf source are monkeypatched.
"""
from __future__ import annotations

import asyncio
import math

import pandas as pd
import pytest

from backend.routers import ratios as ratios_router
from backend.services import discount_rates, metrics

# Simple daily returns R = [+2%, -1%, +3%, 0%, -2%] compounded from 100.
_R = [0.02, -0.01, 0.03, 0.0, -0.02]


def _prices() -> pd.Series:
    p = [100.0]
    for r in _R:
        p.append(p[-1] * (1 + r))
    return pd.Series(p, index=pd.date_range("2024-01-01", periods=len(p)))


def test_sharpe_uses_simple_returns_and_arithmetic_mean():
    # mean R = 0.02/5 = 0.004 -> annual 0.004*252 = 1.008; rf = 0.0252
    # deviations from the mean: .016 -.014 .026 -.004 -.024 -> squares sum .00172 -> /4 = .00043
    # ann vol = sqrt(.00043 * 252) = 0.3291808; Sharpe = (1.008 - 0.0252) / 0.3291808 = 2.98559
    # (log returns would give 2.8641)
    m = metrics.risk_metrics(_prices(), None, 0.0252)
    assert m["sharpe"] == pytest.approx(2.985593, abs=1e-5)


def test_sortino_uses_simple_returns_vs_daily_rf():
    # R - rf/252 (rf/252 = 0.0001): .0199 -.0101 .0299 -.0001 -.0201 -> below-MAR squares:
    # .00010201 + .00000001 + .00040401 = .00050603; /5 = .000101206; sqrt = .0100601
    # downside dev = .0100601 * sqrt(252) = 0.1596994; Sortino = 0.9828 / 0.1596994 = 6.15406
    m = metrics.risk_metrics(_prices(), None, 0.0252)
    assert m["sortino"] == pytest.approx(6.154060, abs=1e-5)


def test_nobs_and_unchanged_log_fields():
    m = metrics.risk_metrics(_prices(), None, 0.0252)
    assert m["nObs"] == 5
    # dailyMeanReturn stays the mean *log* return (audit verified it)
    logs = [math.log(1 + r) for r in _R]
    assert m["dailyMeanReturn"] == pytest.approx(sum(logs) / 5, abs=1e-12)
    assert len(m["returns"]) == 5


def test_empty_case_has_nobs_zero():
    m = metrics.risk_metrics(pd.Series(dtype=float), None, 0.04)
    assert m["nObs"] == 0 and m["sharpe"] is None


# ── router: rf from FRED, riskFree / riskFreeSource / betaBasis ──

def _patch_router(monkeypatch, fallback: bool):
    frame = pd.DataFrame({"XYZ": _prices(), "SPY": _prices()})
    monkeypatch.setattr(ratios_router.yfs, "benchmark_for", lambda s: "SPY")
    monkeypatch.setattr(ratios_router.yfs, "get_info", lambda s: {"ticker": s, "info": {}})
    monkeypatch.setattr(ratios_router.yfs, "get_close_frame", lambda syms, period: frame)
    monkeypatch.setattr(discount_rates, "short_risk_free_rate", lambda: 0.0252, raising=False)
    monkeypatch.setattr(discount_rates, "short_risk_free_rate_is_fallback", lambda: fallback, raising=False)


def test_router_uses_short_rate_when_no_param(monkeypatch):
    _patch_router(monkeypatch, fallback=False)
    out = asyncio.run(ratios_router.ratios("xyz", "1y", None))
    assert out["riskFree"] == 0.0252 and out["riskFreeSource"] == "FRED DGS3MO"
    assert out["sharpe"] == pytest.approx(2.985593, abs=1e-5)
    assert out["betaBasis"] == {"period": "1y", "frequency": "daily", "benchmark": "SPY", "nObs": 5}


def test_router_reports_fallback_and_request_param(monkeypatch):
    _patch_router(monkeypatch, fallback=True)
    out = asyncio.run(ratios_router.ratios("xyz", "1y", None))
    assert out["riskFreeSource"] == "fallback 4%"
    out = asyncio.run(ratios_router.ratios("xyz", "1y", 0.0))
    assert out["riskFree"] == 0.0 and out["riskFreeSource"] == "request parameter"


# ── M-23: bank ratios that are meaningless are null with a reason ──

def _jpm_bundle():
    return {
        "ticker": "JPM",
        "info": {"currency": "USD", "financialCurrency": "USD", "industry": "Banks - Diversified",
                 "sector": "Financial Services"},
        "financials": {"Total Revenue": 1_000.0, "Net Income": 300.0},
        # receivables x 365 / revenue = 600 * 365 / 1000 = 219 days (meaningless for a bank)
        "balance_sheet": {"Total Assets": 20_000.0, "Accounts Receivable": 600.0, "Stockholders Equity": 2_000.0},
        "cashflow": {"Free Cash Flow": -800.0},   # -800 / 1000 = -80 % FCF margin
    }


def test_bank_dso_and_fcf_margin_are_null_with_reason():
    out = metrics.compute_ratios(_jpm_bundle())
    assert out["efficiency"]["dso"] is None
    assert out["profitability"]["fcfMargin"] is None
    assert "bank" in out["unavailable"]["efficiency.dso"].lower()
    assert "bank" in out["unavailable"]["profitability.fcfMargin"].lower()
    # ratios that stay meaningful are untouched: net margin 300 / 1000
    assert out["profitability"]["netMargin"] == pytest.approx(0.3)


def test_non_bank_dso_and_fcf_margin_unchanged():
    b = _jpm_bundle()
    b["info"]["industry"] = "Software - Application"
    out = metrics.compute_ratios(b)
    assert out["efficiency"]["dso"] == pytest.approx(219.0)
    assert out["profitability"]["fcfMargin"] == pytest.approx(-0.8)
    assert "efficiency.dso" not in out["unavailable"]


# ── P3-28: /capm-dcf's dcf_target must not return negative values ──

def test_dcf_target_is_null_for_negative_fcf_and_banks():
    info = {"freeCashflow": -100.0, "sharesOutstanding": 10.0}
    assert metrics.dcf_target(info, 0.05, 0.02, 0.09) is None            # FCF <= 0
    bank = {"freeCashflow": 100.0, "sharesOutstanding": 10.0, "industry": "Banks - Diversified"}
    assert metrics.dcf_target(bank, 0.05, 0.02, 0.09) is None            # not meaningful for banks
    # debt far above the PV of cash flows -> equity value <= 0 -> null, not a negative price
    levered = {"freeCashflow": 1.0, "sharesOutstanding": 10.0, "totalDebt": 1e6}
    assert metrics.dcf_target(levered, 0.05, 0.02, 0.09) is None

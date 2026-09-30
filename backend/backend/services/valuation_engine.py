"""
Valuation Engine — 8 models + CAPM implied + EconoSift Fair Value composite.

Each model returns:
  {"model": str, "value": float|None, "locked": bool,
   "reason": str|None, "detail": dict}

Top-level entry point:  valuation_models(bundle, beta=None, growth=None) -> dict
"""
from __future__ import annotations

import math
from datetime import date
from typing import Any

from .metrics import _clean
from .discount_rates import (
    wacc as compute_wacc,
    cost_of_equity,
    detect_country,
    load_sector_multiples,
    risk_free_rate,
)
from . import dcf_engine


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _locked_model(name: str, reason: str, detail: dict | None = None) -> dict:
    return {
        "model": name,
        "value": None,
        "locked": True,
        "reason": reason,
        "detail": detail or {},
    }


def _ok_model(name: str, value: float | None, detail: dict | None = None) -> dict:
    return {
        "model": name,
        "value": _clean(value),
        "locked": value is None,
        "reason": None,
        "detail": detail or {},
    }


def _fetch_aaa_yield() -> float:
    """Fetch Moody's AAA corporate bond yield from FRED (percent). Fallback 5.0."""
    try:
        from ..config import FRED_API_KEY
        if FRED_API_KEY:
            from fredapi import Fred
            fred = Fred(api_key=FRED_API_KEY)
            s = fred.get_series("AAA").dropna()
            if len(s) > 0:
                val = _clean(float(s.iloc[-1]))
                if val is not None and 0 < val < 20:
                    return val
    except Exception:
        pass

    try:
        from datetime import datetime, timedelta
        import pandas_datareader.data as web
        end = datetime.today()
        start = end - timedelta(days=30)
        df = web.DataReader("AAA", "fred", start=start, end=end)
        s = df.iloc[:, 0].dropna()
        if len(s) > 0:
            val = _clean(float(s.iloc[-1]))
            if val is not None and 0 < val < 20:
                return val
    except Exception:
        pass

    return 5.0  # fallback: 5%


# Cache AAA yield in module-level variable per process (decorated via cached below)
from ..cache import cached as _cached

@_cached("aaa_yield")
def _get_aaa_yield() -> float:
    return _fetch_aaa_yield()


# ---------------------------------------------------------------------------
# Context object for shared inputs
# ---------------------------------------------------------------------------

class _Ctx:
    """Pre-computed context shared across all models for a single valuation call."""

    def __init__(self, bundle: dict, beta: float | None, growth: float | None):
        # Statement figures converted to the trading currency (ADRs; C-16).
        bundle = dcf_engine.to_price_currency(bundle)
        self.bundle = bundle
        self.info: dict = bundle.get("info") or {}
        self.fin: dict = bundle.get("financials") or {}
        self.bs: dict = bundle.get("balance_sheet") or {}
        self.cf: dict = bundle.get("cashflow") or {}

        # WACC dict
        self.wacc_dict: dict = compute_wacc(bundle, beta)
        self.wacc_val: float | None = self.wacc_dict.get("wacc")
        self.ke: float | None = self.wacc_dict.get("costOfEquity")
        self.kd: float | None = self.wacc_dict.get("costOfDebt")
        self.tax: float | None = self.wacc_dict.get("taxRate")
        self.country: str = self.wacc_dict.get("country") or "United States"
        self.rf: float | None = self.wacc_dict.get("riskFree")
        self.beta = beta

        # Per-share data
        self.eps: float | None = _clean(self.info.get("trailingEps"))
        self.forward_eps: float | None = _clean(self.info.get("forwardEps"))
        self.bvps: float | None = _clean(self.info.get("bookValue"))
        self.spot: float | None = (
            _clean(self.info.get("currentPrice"))
            or _clean(self.info.get("regularMarketPrice"))
        )
        self.shares: float | None = _clean(self.info.get("sharesOutstanding"))

        # Validate shares: cross-check with marketCap / currentPrice
        if self.shares is not None and self.spot is not None and self.spot > 0:
            market_cap = _clean(self.info.get("marketCap"))
            if market_cap is not None and market_cap > 0:
                implied = market_cap / self.spot
                ratio = implied / self.shares if self.shares > 0 else 0
                if ratio > 5 or ratio < 0.2:
                    import logging
                    _log = logging.getLogger(__name__)
                    _log.warning(
                        "valuation_engine: sharesOutstanding=%s, marketCap/price=%s "
                        "(ratio=%.2f) — using implied shares",
                        self.shares, implied, ratio,
                    )
                    self.shares = implied
        self.currency: str = self.info.get("currency") or "USD"
        self.ticker: str = bundle.get("ticker") or ""
        self.sector: str | None = self.info.get("sector")

        # Growth rate (annual, as decimal e.g. 0.10). Yahoo's earningsGrowth
        # and revenueGrowth are *single-quarter* YoY changes; compounding a
        # quarter's +77% for ten years (capped at 50%) inflated DCF, Graham,
        # Lynch and DDM values (audit C-15). Preferred: consensus next-year EPS
        # growth (forwardEps / trailingEps − 1, an annual rate by
        # construction); then revenue growth; then a neutral 5%. A derived
        # rate is capped at 15%/yr because it is applied for up to ten years;
        # an explicit caller-supplied rate keeps the wider bounds.
        lo, hi = -0.10, 0.15
        if growth is not None:
            self.growth: float | None = _clean(growth)
            self.growth_source = "user"
            lo, hi = -0.20, 0.50
        else:
            fwd, trl = self.forward_eps, self.eps
            rg = _clean(self.info.get("revenueGrowth"))
            if fwd and trl and fwd > 0 and trl > 0:
                self.growth, self.growth_source = fwd / trl - 1.0, "consensus forward EPS"
            elif rg is not None:
                self.growth, self.growth_source = rg, "revenue growth (latest quarter YoY)"
            else:
                self.growth, self.growth_source = 0.05, "default 5%"

        if self.growth is not None:
            self.growth = max(lo, min(self.growth, hi))


# ---------------------------------------------------------------------------
# Model 1: DCF (Two-Stage) — reuses dcf_engine
# ---------------------------------------------------------------------------

def _model_dcf(ctx: _Ctx) -> dict:
    NAME = "DCF (Two-Stage)"
    wacc_val = ctx.wacc_val
    if wacc_val is None:
        return _locked_model(NAME, "WACC unavailable")

    fcf_growth = ctx.growth or 0.08
    terminal_growth = 0.025

    result = dcf_engine.two_stage_dcf(
        ctx.bundle,
        fcf_growth=fcf_growth,
        terminal_growth=terminal_growth,
        wacc=wacc_val,
        stage1_years=10,
    )

    if result.get("locked"):
        return _locked_model(NAME, result.get("reason", "DCF locked"), {
            "dcfResult": result,
        })

    value = _clean(result.get("intrinsicValue"))
    return {
        "model": NAME,
        "value": value,
        "locked": value is None,
        "reason": None if value is not None else "DCF returned None",
        "detail": {
            "scenarios": result.get("scenarios"),
            "sensitivity": result.get("sensitivity"),
            "inputs": result.get("inputs"),
        },
    }


# ---------------------------------------------------------------------------
# Model 2: DDM (Gordon Growth)
# ---------------------------------------------------------------------------

def _model_ddm(ctx: _Ctx) -> dict:
    NAME = "DDM (Gordon Growth)"
    div_rate = _clean(ctx.info.get("dividendRate"))
    if div_rate is None or div_rate <= 0:
        return _locked_model(NAME, "No dividend — DDM not applicable")

    ke = ctx.ke
    if ke is None:
        return _locked_model(NAME, "Cost of equity unavailable")

    g = ctx.growth or 0.04
    # Cap g so it stays below ke
    g = min(g, ke - 0.005)
    if g <= 0 or ke <= g:
        return _locked_model(NAME, f"Growth ({g:.4f}) ≥ cost of equity ({ke:.4f}) — Gordon Growth undefined")

    d1 = div_rate * (1.0 + g)
    value = d1 / (ke - g)

    return _ok_model(NAME, value, {
        "dividendRate": div_rate,
        "D1": _clean(d1),
        "costOfEquity": _clean(ke),
        "growthRate": _clean(g),
    })


# ---------------------------------------------------------------------------
# Model 3: Graham Formula (1962 revised)
# ---------------------------------------------------------------------------

def _model_graham_formula(ctx: _Ctx) -> dict:
    NAME = "Graham Formula"
    eps = ctx.eps
    if eps is None or eps <= 0:
        return _locked_model(NAME, "EPS ≤ 0 — Graham Formula not applicable")

    # g as whole number, capped at 20
    growth_whole = min((ctx.growth or 0.08) * 100.0, 20.0)
    growth_whole = max(growth_whole, 0.0)

    # Moody's AAA yield in percent
    aaa_yield = _get_aaa_yield()

    # V = EPS × (8.5 + 2g) × 4.4 / Y
    value = eps * (8.5 + 2.0 * growth_whole) * 4.4 / aaa_yield

    return _ok_model(NAME, value, {
        "eps": eps,
        "growthPctUsed": growth_whole,
        "aaaYieldPct": aaa_yield,
        "formula": "EPS × (8.5 + 2g) × 4.4 / Y",
    })


# ---------------------------------------------------------------------------
# Model 4: Graham Number
# ---------------------------------------------------------------------------

def _model_graham_number(ctx: _Ctx) -> dict:
    NAME = "Graham Number"
    eps = ctx.eps
    bvps = ctx.bvps
    if eps is None or eps <= 0:
        return _locked_model(NAME, "EPS ≤ 0 — Graham Number not applicable")
    if bvps is None or bvps <= 0:
        return _locked_model(NAME, "Book value per share ≤ 0 — Graham Number not applicable")

    value = math.sqrt(22.5 * eps * bvps)
    return _ok_model(NAME, value, {
        "eps": eps,
        "bvps": bvps,
        "formula": "√(22.5 × EPS × BVPS)",
    })


# ---------------------------------------------------------------------------
# Model 5: Peter Lynch / PEG
# ---------------------------------------------------------------------------

def _model_peter_lynch(ctx: _Ctx) -> dict:
    NAME = "Peter Lynch / PEG"
    eps = ctx.eps
    if eps is None or eps <= 0:
        return _locked_model(NAME, "EPS ≤ 0 — Lynch PEG not applicable")

    # Growth as whole number (earningsGrowth * 100), capped at 20
    growth_whole = (ctx.growth or 0.0) * 100.0
    if growth_whole <= 0:
        return _locked_model(NAME, "Earnings growth ≤ 0 — Lynch PEG not applicable")
    growth_whole = min(growth_whole, 20.0)

    # Lynch: fair P/E = growth rate → fair value = EPS × growth_rate
    value = eps * growth_whole

    return _ok_model(NAME, value, {
        "eps": eps,
        "growthPctUsed": growth_whole,
        "formula": "EPS × growth_rate (whole number)",
    })


# ---------------------------------------------------------------------------
# Model 6: EV/EBITDA Comps
# ---------------------------------------------------------------------------

_FINANCIALS_SECTORS = {
    "Financial Services",
    "Financials",
    "Banks",
    "Insurance",
}


def _model_ev_ebitda(ctx: _Ctx) -> dict:
    NAME = "EV/EBITDA Comps"

    sector = ctx.sector
    if sector in _FINANCIALS_SECTORS:
        return _locked_model(NAME, "EV/EBITDA not meaningful for Financial Services sector")

    ebitda = _clean(ctx.info.get("ebitda"))
    if ebitda is None or ebitda <= 0:
        return _locked_model(NAME, "EBITDA unavailable or ≤ 0")

    # Look up sector multiple
    sm_data = load_sector_multiples()
    sectors: dict = sm_data.get("sectors", {})
    sector_entry = sectors.get(sector) if sector else None
    if sector_entry is None:
        return _locked_model(NAME, f"No sector multiple for '{sector}'")

    multiple = _clean(sector_entry.get("evEbitda"))
    if multiple is None:
        return _locked_model(NAME, f"EV/EBITDA multiple missing for '{sector}'")

    shares = ctx.shares
    if shares is None or shares <= 0:
        return _locked_model(NAME, "Shares outstanding unavailable")

    implied_ev = multiple * ebitda
    total_cash = _clean(ctx.info.get("totalCash")) or 0.0
    total_debt = (
        _clean(ctx.info.get("totalDebt"))
        or _clean(ctx.bs.get("Total Debt"))
        or 0.0
    )
    net_debt = total_debt - total_cash
    equity_val = implied_ev - net_debt

    value = equity_val / shares

    return _ok_model(NAME, value, {
        "sector": sector,
        "sectorMultiple": multiple,
        "ebitda": ebitda,
        "impliedEV": _clean(implied_ev),
        "netDebt": _clean(net_debt),
        "impliedEquity": _clean(equity_val),
        "shares": _clean(shares),
    })


# ---------------------------------------------------------------------------
# Model 7: Residual Income Model (RIM / Edwards-Bell-Ohlson)
# ---------------------------------------------------------------------------

def _model_rim(ctx: _Ctx) -> dict:
    NAME = "Residual Income (RIM)"
    bvps = ctx.bvps
    if bvps is None or bvps <= 0:
        return _locked_model(NAME, "Book value per share unavailable")

    roe = _clean(ctx.info.get("returnOnEquity"))
    if roe is None:
        return _locked_model(NAME, "ROE unavailable")

    ke = ctx.ke
    if ke is None:
        return _locked_model(NAME, "Cost of equity unavailable")

    # Dividend payout and retention
    payout = _clean(ctx.info.get("payoutRatio")) or 0.0
    payout = min(max(payout, 0.0), 1.0)
    retention = 1.0 - payout

    # Project 5 years of residual income
    YEARS = 5
    book = bvps
    pv_ri = 0.0
    for t in range(1, YEARS + 1):
        ri = (roe - ke) * book
        pv_ri += ri / ((1.0 + ke) ** t)
        book = book * (1.0 + retention * roe)

    # Terminal: assume RI fades to 0 after stage (conservative)
    value = bvps + pv_ri

    return _ok_model(NAME, value, {
        "bvps": bvps,
        "roe": roe,
        "costOfEquity": ke,
        "retentionRate": retention,
        "pvRI": _clean(pv_ri),
        "years": YEARS,
    })


# ---------------------------------------------------------------------------
# Model 8: Earnings Power Value (EPV)
# ---------------------------------------------------------------------------

def _model_epv(ctx: _Ctx) -> dict:
    NAME = "EPV (Earnings Power Value)"

    wacc_val = ctx.wacc_val
    if wacc_val is None:
        return _locked_model(NAME, "WACC unavailable")

    # EBIT: try info then financials
    ebit_raw = (
        ctx.info.get("ebit")
        or ctx.fin.get("EBIT")
        or ctx.fin.get("Operating Income")
    )
    ebit = _clean(ebit_raw)
    if ebit is None:
        # Try operating income from info
        ebit = _clean(ctx.info.get("operatingIncome"))
    if ebit is None:
        return _locked_model(NAME, "EBIT unavailable")

    shares = ctx.shares
    if shares is None or shares <= 0:
        return _locked_model(NAME, "Shares outstanding unavailable")

    tax = ctx.tax or 0.21
    nopat = ebit * (1.0 - tax)

    # EPV = NOPAT / WACC (no-growth assumption)
    epv_firm = nopat / wacc_val

    # Subtract net debt → equity value
    total_cash = _clean(ctx.info.get("totalCash")) or 0.0
    total_debt = (
        _clean(ctx.info.get("totalDebt"))
        or _clean(ctx.bs.get("Total Debt"))
        or 0.0
    )
    net_debt = total_debt - total_cash
    equity_val = epv_firm - net_debt

    value = equity_val / shares

    return _ok_model(NAME, value, {
        "ebit": ebit,
        "taxRate": tax,
        "nopat": _clean(nopat),
        "wacc": wacc_val,
        "epvFirm": _clean(epv_firm),
        "netDebt": _clean(net_debt),
        "impliedEquity": _clean(equity_val),
        "shares": _clean(shares),
    })


# ---------------------------------------------------------------------------
# CAPM Implied Fair Value
# ---------------------------------------------------------------------------

def _capm_implied(ctx: _Ctx) -> dict:
    """Earnings-capitalization: fairValue = forwardEPS / costOfEquity."""
    ke = ctx.ke
    feps = ctx.forward_eps or ctx.eps

    if ke is None or ke <= 0:
        return {
            "model": "CAPM Implied",
            "value": None,
            "locked": True,
            "reason": "Cost of equity unavailable",
            "detail": {},
        }

    if feps is None or feps <= 0:
        return {
            "model": "CAPM Implied",
            "value": None,
            "locked": True,
            "reason": "Forward EPS unavailable or ≤ 0",
            "detail": {},
        }

    value = _clean(feps / ke)
    return {
        "model": "CAPM Implied",
        "value": value,
        "locked": value is None,
        "reason": None,
        "detail": {
            "forwardEps": _clean(feps),
            "costOfEquity": _clean(ke),
            "formula": "forwardEPS / costOfEquity",
        },
    }


# ---------------------------------------------------------------------------
# EconoSift Fair Value composite
# ---------------------------------------------------------------------------

# Model name → base weight (will renormalize over unlocked models)
_WEIGHTS: dict[str, float] = {
    "DCF (Two-Stage)":           0.30,
    "EV/EBITDA Comps":           0.20,
    "Residual Income (RIM)":     0.15,
    "EPV (Earnings Power Value)":0.15,
    "Graham Formula":            0.10,
    "Peter Lynch / PEG":         0.05,
    "DDM (Gordon Growth)":       0.05,
}


def _composite_fair_value(models: list[dict], spot: float | None) -> dict:
    """Weighted composite of unlocked models, renormalised."""
    available: list[tuple[str, float, float]] = []  # (name, value, weight)
    for m in models:
        if not m.get("locked") and m.get("value") is not None:
            name = m["model"]
            w = _WEIGHTS.get(name)
            if w is not None:
                available.append((name, m["value"], w))

    if not available:
        return {
            "value": None,
            "upsidePct": None,
            "verdict": "Insufficient Data",
            "weightsUsed": {},
        }

    total_w = sum(w for _, _, w in available)
    composite = sum(v * w for _, v, w in available) / total_w
    composite = _clean(composite)

    upside: float | None = None
    if composite is not None and spot is not None and spot > 0:
        upside = _clean((composite - spot) / spot)

    # Verdict band
    verdict = "Insufficient Data"
    if upside is not None:
        if upside > 0.25:
            verdict = "Significantly Undervalued"
        elif upside > 0.10:
            verdict = "Undervalued"
        elif upside > -0.10:
            verdict = "Fairly Valued"
        elif upside > -0.25:
            verdict = "Overvalued"
        else:
            verdict = "Significantly Overvalued"

    weights_used = {
        name: round(w / total_w, 6)
        for name, _, w in available
    }

    return {
        "value": composite,
        "upsidePct": upside,
        "verdict": verdict,
        "weightsUsed": weights_used,
    }


# ---------------------------------------------------------------------------
# Top-level entry point
# ---------------------------------------------------------------------------

def valuation_models(
    bundle: dict,
    beta: float | None = None,
    growth: float | None = None,
) -> dict:
    """
    Compute all 8 valuation models + CAPM implied + the EconoSift composite fair value.

    Parameters
    ----------
    bundle : dict
        Output from yfinance_service.get_info(ticker).
    beta : float | None
        Market beta (from risk_metrics); uses 1.0 if absent.
    growth : float | None
        Override annual growth rate (decimal). If None, inferred from info.

    Returns
    -------
    dict with keys:
        ticker, currency, spotPrice,
        wacc (WACC dict),
        models (list of 8 model dicts),
        capmImplied (CAPM implied fair value dict),
        axiomFairValue (legacy composite dict key; retained for API compatibility),
        asOf (ISO date string)
    """
    ctx = _Ctx(bundle, beta, growth)

    models: list[dict] = [
        _model_dcf(ctx),
        _model_ddm(ctx),
        _model_graham_formula(ctx),
        _model_graham_number(ctx),
        _model_peter_lynch(ctx),
        _model_ev_ebitda(ctx),
        _model_rim(ctx),
        _model_epv(ctx),
    ]

    capm_implied = _capm_implied(ctx)
    composite = _composite_fair_value(models, ctx.spot)

    return {
        "ticker": ctx.ticker,
        "currency": ctx.currency,
        "spotPrice": ctx.spot,
        "wacc": ctx.wacc_dict,
        "models": models,
        "capmImplied": capm_implied,
        "axiomFairValue": composite,
        "growthInput": {"rate": ctx.growth, "source": ctx.growth_source},
        "statementFx": ctx.bundle.get("_fx"),
        "asOf": date.today().isoformat(),
    }

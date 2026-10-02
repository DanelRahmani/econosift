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

from .. import provenance as pv
from .metrics import _clean
from .discount_rates import (
    wacc as compute_wacc,
    cost_of_equity,
    detect_country,
    load_erp,
    load_sector_multiples,
    risk_free_rate,
)
from . import dcf_engine
from . import yfinance_service as yfs


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


# Long-run ROE ceiling. A TTM ROE far above this (AAPL 149 %, MSFT 33 %) mostly reflects a book
# value shrunk by buybacks, and competition erodes excess returns, so it is not compounded.
_ROE_CAP = 0.25
# Perpetual dividend growth cap when no risk-free rate is available (long-run nominal GDP).
_DEFAULT_GROWTH_CAP = 0.04


def _dividend_payout(info: dict) -> float | None:
    """Dividend payout ratio: Yahoo payoutRatio, else dividendRate / trailingEps."""
    payout = _clean(info.get("payoutRatio"))
    if payout is None:
        rate, eps = _clean(info.get("dividendRate")), _clean(info.get("trailingEps"))
        if rate is not None and eps is not None and eps > 0:
            payout = rate / eps
    return None if payout is None else min(max(payout, 0.0), 1.0)


def _buyback_ratio(info: dict, fin: dict, cf: dict) -> float:
    """Net share repurchases / net income from the latest annual statements (0 when unknown)."""
    ni = (_clean(fin.get("Net Income Common Stockholders")) or _clean(fin.get("Net Income"))
          or _clean(info.get("netIncomeToCommon")))
    if ni is None or ni <= 0:
        return 0.0
    flow = _clean(cf.get("Net Common Stock Issuance"))
    if flow is None:
        flow = _clean(cf.get("Repurchase Of Capital Stock"))
    if flow is None or flow >= 0:
        return 0.0
    return -flow / ni


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
        # Why there is no discount rate, e.g. no local 10-year yield for the listing (audit M-10).
        self.rate_reason: str | None = (self.wacc_dict.get("unavailable") or {}).get("riskFree")
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

def _no_rate(ctx: _Ctx, what: str) -> str:
    """Lock reason for a missing WACC / cost of equity, naming the cause when it is known."""
    return f"{what}: {ctx.rate_reason}" if ctx.rate_reason else what


def _lock_non_positive(models: list[dict]) -> list[dict]:
    """Generic guard: an unlocked model with a per-share value <= 0 becomes null + reason.

    A negative price per share (net debt above implied EV, etc.) is not a valuation.
    Models that already carry a more specific lock keep their reason; ``detail`` is kept.
    """
    for m in models:
        v = m.get("value")
        if v is not None and v <= 0:
            m["value"] = None
            m["locked"] = True
            m["reason"] = NON_POSITIVE_REASON
    return models


NON_POSITIVE_REASON = "not meaningful: value ≤ 0 after net debt"


def _model_dcf(ctx: _Ctx) -> dict:
    NAME = "DCF (Two-Stage)"
    wacc_val = ctx.wacc_val
    if wacc_val is None:
        return _locked_model(NAME, _no_rate(ctx, "WACC unavailable"))

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
        return _locked_model(NAME, _no_rate(ctx, "Cost of equity unavailable"))

    # Perpetual dividend growth is the *sustainable* rate, retention x ROE, with ROE normalised
    # (capped at _ROE_CAP) and g capped at the risk-free rate (long-run nominal growth) and below ke.
    # It is never the 10-year earnings-growth rate (audit M-03).
    roe_raw = _clean(ctx.info.get("returnOnEquity"))
    payout = _dividend_payout(ctx.info)
    if roe_raw is None or payout is None:
        return _locked_model(NAME, "Sustainable dividend growth unavailable (ROE or payout ratio missing)")
    roe = min(roe_raw, _ROE_CAP)
    g_sustainable = max((1.0 - payout) * roe, 0.0)
    cap = ctx.rf if ctx.rf is not None else _DEFAULT_GROWTH_CAP
    cap = min(cap, ke - 0.005)
    g = min(g_sustainable, cap)
    if g < 0 or ke <= g:
        return _locked_model(NAME, f"Growth ({g:.4f}) ≥ cost of equity ({ke:.4f}) — Gordon Growth undefined")

    d1 = div_rate * (1.0 + g)
    value = d1 / (ke - g)

    return _ok_model(NAME, value, {
        "dividendRate": div_rate,
        "D1": _clean(d1),
        "costOfEquity": _clean(ke),
        "growthRate": _clean(g),
        "sustainableGrowth": _clean(g_sustainable),
        "growthCap": _clean(cap),
        "roe": _clean(roe),
        "payoutRatio": _clean(payout),
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

def _rim_value(bvps: float, roe0: float, ke: float, retention: float, years: int = 5) -> tuple[float, float]:
    """Residual-income value per share and the PV of the residual income.

    ROE fades linearly from ``roe0`` to the cost of equity over ``years``
    (ROE_t = ke + (roe0 - ke) * (1 - t / years)), so excess returns are gone by
    the end of the horizon and no terminal value is added. Book value follows
    clean surplus: book_t = book_(t-1) * (1 + retention * ROE_t), and
    RI_t = (ROE_t - ke) * book_(t-1).
    """
    book = bvps
    pv_ri = 0.0
    for t in range(1, years + 1):
        roe_t = ke + (roe0 - ke) * (1.0 - t / years)
        pv_ri += (roe_t - ke) * book / ((1.0 + ke) ** t)
        book *= 1.0 + retention * roe_t
    return bvps + pv_ri, pv_ri


def _model_rim(ctx: _Ctx) -> dict:
    """Residual income (Edwards-Bell-Ohlson), audit M-05 formula.

    * ROE starts at Yahoo's TTM ROE capped at ``_ROE_CAP`` (a 149 % ROE on a
      buyback-shrunk book is not compounded) and fades to ke over 5 years
      (see :func:`_rim_value`).
    * Retention = 1 - dividend payout - net buybacks / net income, clamped to
      [0, 1]: buybacks leave the company just as dividends do, so ignoring
      them overstated book growth.
    """
    NAME = "Residual Income (RIM)"
    bvps = ctx.bvps
    if bvps is None or bvps <= 0:
        return _locked_model(NAME, "Book value per share unavailable")

    roe_raw = _clean(ctx.info.get("returnOnEquity"))
    if roe_raw is None:
        return _locked_model(NAME, "ROE unavailable")
    if roe_raw > 1.0:
        # Book value shrunk by buybacks: ROE x a tiny book is not an economic return.
        return _locked_model(NAME, "not meaningful: ROE above 100% on a buyback-shrunk book",
                             {"roeRaw": roe_raw, "bvps": bvps})

    ke = ctx.ke
    if ke is None:
        return _locked_model(NAME, _no_rate(ctx, "Cost of equity unavailable"))

    roe = min(roe_raw, _ROE_CAP)
    payout = _dividend_payout(ctx.info) or 0.0
    buyback = _buyback_ratio(ctx.info, ctx.fin, ctx.cf)
    retention = min(max(1.0 - payout - buyback, 0.0), 1.0)

    YEARS = 5
    value, pv_ri = _rim_value(bvps, roe, ke, retention, YEARS)

    return _ok_model(NAME, value, {
        "bvps": bvps,
        "roeRaw": roe_raw,
        "roe": roe,
        "costOfEquity": ke,
        "retentionRate": retention,
        "dividendPayoutRatio": payout,
        "buybackPayoutRatio": _clean(buyback),
        "pvRI": _clean(pv_ri),
        "years": YEARS,
    })


# ---------------------------------------------------------------------------
# Model 8: Earnings Power Value (EPV)
# ---------------------------------------------------------------------------

def _model_epv(ctx: _Ctx) -> dict:
    NAME = "EPV (Earnings Power Value)"

    # EPV subtracts net debt; a bank's debt and cash are operating balances (audit M-02).
    if dcf_engine.is_bank(ctx.info):
        return _locked_model(NAME, "not meaningful for banks")

    wacc_val = ctx.wacc_val
    if wacc_val is None:
        return _locked_model(NAME, _no_rate(ctx, "WACC unavailable"))

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
            "reason": _no_rate(ctx, "Cost of equity unavailable"),
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
    """Weighted composite of the models with a positive value, weights renormalised.

    A null or non-positive per-share value is "not meaningful" and is excluded,
    so the composite can never be negative (audit M-02). ``reason`` is set only
    when nothing remains.
    """
    available: list[tuple[str, float, float]] = []  # (name, value, weight)
    for m in models:
        if not m.get("locked") and m.get("value") is not None and m["value"] > 0:
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
            "reason": "no model produced a positive value",
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
        "reason": None,
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
    _lock_non_positive(models + [capm_implied])
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


# ---------------------------------------------------------------------------
# Provenance
# ---------------------------------------------------------------------------

def provenance(bundle: dict, result: dict, beta: float | None, root: str = "valuation") -> dict:
    """Provenance keys (under ``root``) for a :func:`valuation_models` result."""
    def k(*parts: str) -> str:
        return ".".join(p for p in (root, *parts) if p)

    sym = result.get("ticker") or bundle.get("ticker") or ""
    info: dict = bundle.get("info") or {}
    w: dict = result.get("wacc") or {}
    ccy = result.get("currency")

    def y(field: str, **kw) -> dict:
        return pv.yahoo(sym, f"info.{field}", **kw)

    fx = result.get("statementFx") or {}
    fx_note = (f"Statement-currency figures (debt, cash, EBITDA, cash flow) are converted from {fx['from']} to "
               f"{fx['to']} at the latest Yahoo FX rate ({fx['rate']})."
               if fx.get("rate") not in (None, 1.0) and fx.get("from") != fx.get("to") else None)
    prov: dict = {
        k(): pv.derived(
            "eight valuation models, a CAPM-implied value and a weighted composite, from Yahoo fundamentals "
            "and the discount-rate inputs below", [k("wacc"), k("growthInput")],
            title="Valuation engine", note=fx_note),
        k("spotPrice"): y("currentPrice (else regularMarketPrice)", units=ccy),
        k("currency"): y("currency"),
    }

    # -- discount rate ------------------------------------------------------
    country = w.get("country") or "United States"
    rf_source = w.get("riskFreeSource") or ""
    rf_missing = (w.get("unavailable") or {}).get("riskFree")
    if rf_source.startswith("FRED IRLTLT") or rf_source.startswith("FRED INDIRLTLT"):
        # Non-USD listing: the local 10-year yield in the price currency (audit M-10).
        prov[k("wacc", "riskFree")] = pv.fred(
            rf_source.split(" ", 1)[1], f"{country} 10-year government bond yield (OECD, monthly average)",
            units="decimal (FRED percent / 100)", frequency="monthly", observed=w.get("riskFreeAsOf"),
            flags=("stale",) if w.get("riskFreeStale") else (),
            note="Local-currency rate for a listing priced in that currency; OECD publishes it one to two "
                 "months late, so the latest month is used.")
    elif rf_missing:
        prov[k("wacc", "riskFree")] = pv.derived("not available", title="Risk-free rate", note=rf_missing)
    else:
        rf_fallback = rf_source == "fallback 4%"
        prov[k("wacc", "riskFree")] = pv.fred(
            "DGS10", "US 10-year Treasury constant-maturity yield", units="decimal (FRED percent / 100)",
            frequency="daily", flags=("fallback",) if rf_fallback else (),
            note="Used for USD-priced listings; other currencies use their own 10-year yield."
                 + (" FRED could not be read, so the hard-coded 4% stands in." if rf_fallback else ""))
    erp_data = load_erp()
    countries = erp_data.get("countries") or {}
    entry = countries.get(country)
    as_of = erp_data.get("asOf")
    observed = as_of if isinstance(as_of, str) and as_of[:2] == "20" else None
    if entry is not None and _clean(entry.get("erp")) is not None:
        erp_ref = pv.ref("damodaran", "ctryprem", f"Total equity risk premium, {country}", units="decimal",
                         frequency="annual", observed=observed, url=erp_data.get("sourceUrl"))
    elif _clean(erp_data.get("matureMarketERP")) is not None:
        erp_ref = pv.ref("damodaran", "ctryprem", f"Mature-market equity risk premium (no row for {country})",
                         units="decimal", frequency="annual", observed=observed, url=erp_data.get("sourceUrl"),
                         flags=("proxy",))
    else:
        erp_ref = pv.derived("hard-coded 5% equity risk premium", title="Equity risk premium", flags=("fallback",))
    prov[k("wacc", "erp")] = erp_ref
    prov[k("wacc", "country")] = pv.derived(
        "country of the listing: info.exchange code, else keywords in info.fullExchangeName, else info.country "
        "if it is in the ERP table, else United States", [y("exchange"), y("fullExchangeName"), y("country")],
        title="Country used for the equity risk premium")
    raw_formula = "cov(r, r_benchmark) / var(r_benchmark) of 2 years of daily log returns"
    beta_missing = (w.get("unavailable") or {}).get("beta")
    if w.get("betaAdjustment") == "Blume":
        prov[k("wacc", "beta")] = pv.derived(
            f"0.67 × raw beta + 0.33 (Blume), raw beta = {raw_formula}",
            [pv.yahoo(sym, "Daily adjusted close, 2y", frequency="daily"),
             pv.yahoo(yfs.benchmark_for(sym), "Local index daily adjusted close, 2y", frequency="daily")],
            title="Beta used in CAPM (Blume-adjusted, local index)",
            note="Raw beta in wacc.rawBeta. The Blume adjustment shrinks a local-index beta toward 1.")
    elif beta is not None and not beta_missing:
        prov[k("wacc", "beta")] = pv.derived(
            raw_formula, [pv.yahoo(sym, "Daily adjusted close, 2y", frequency="daily"),
                          pv.yahoo(yfs.benchmark_for(sym), "Benchmark daily adjusted close, 2y", frequency="daily")],
            title="Beta used in CAPM", note="Computed here, not Yahoo's info.beta.")
    else:
        prov[k("wacc", "beta")] = pv.derived("beta = 1.0", title="Beta used in CAPM", flags=("fallback",),
                                             note=beta_missing or "No beta could be computed.")
    prov[k("wacc", "costOfEquity")] = pv.derived("risk-free rate + beta × equity risk premium (CAPM)",
                                                 [k("wacc", "riskFree"), k("wacc", "beta"), k("wacc", "erp")],
                                                 title="Cost of equity")
    kd, rf = w.get("costOfDebt"), w.get("riskFree")
    if kd is not None and rf is not None and abs(kd - (rf + 0.02)) < 1e-12:
        prov[k("wacc", "costOfDebt")] = pv.derived(
            "risk-free rate + 2% credit spread", [k("wacc", "riskFree")], title="Cost of debt", flags=("fallback",),
            note="Used because interest expense / total debt was missing or outside 1%-15%.")
    else:
        prov[k("wacc", "costOfDebt")] = pv.derived(
            "|interest expense| / total debt (info, else statements), accepted between 1% and 15%",
            [y("interestExpense"), y("totalDebt")], title="Cost of debt")
    etr = _clean(info.get("effectiveTaxRate"))
    if etr is not None and 0.0 < etr < 0.6:
        prov[k("wacc", "taxRate")] = y("effectiveTaxRate", units="decimal")
    elif entry is not None and _clean(entry.get("taxRate")) is not None:
        prov[k("wacc", "taxRate")] = pv.ref(
            "damodaran", "ctryprem", f"Statutory corporate tax rate, {country}", units="decimal",
            frequency="annual", observed=observed, url=erp_data.get("sourceUrl"),
            note="Used because Yahoo's effectiveTaxRate was missing or outside 0-60%.")
    else:
        prov[k("wacc", "taxRate")] = pv.derived("hard-coded 21% US statutory rate", title="Tax rate",
                                                flags=("fallback",))
    debt = [y("marketCap"), y("totalDebt")]
    prov[k("wacc", "weightEquity")] = pv.derived("market cap / (market cap + total debt)", debt,
                                                 title="Equity weight")
    prov[k("wacc", "weightDebt")] = pv.derived("total debt / (market cap + total debt)", debt, title="Debt weight")
    prov[k("wacc", "wacc")] = pv.derived(
        "equity weight × cost of equity + debt weight × cost of debt × (1 − tax rate); equals the cost of equity "
        "when market cap is missing; floored at 5%",
        [k("wacc", n) for n in ("weightEquity", "costOfEquity", "weightDebt", "costOfDebt", "taxRate")],
        title="WACC")

    # -- growth ---------------------------------------------------------------
    src = (result.get("growthInput") or {}).get("source")
    cap = "capped to -10%...+15% a year"
    if src == "consensus forward EPS":
        prov[k("growthInput")] = pv.derived(f"forwardEps / trailingEps − 1, {cap}",
                                            [y("forwardEps"), y("trailingEps")], title="Growth rate used")
    elif src == "revenue growth (latest quarter YoY)":
        prov[k("growthInput")] = pv.derived(
            f"info.revenueGrowth (latest quarter versus the same quarter a year earlier), {cap}",
            [y("revenueGrowth")], title="Growth rate used")
    else:
        prov[k("growthInput")] = pv.derived(
            "5% a year: neither forward EPS growth nor revenue growth was available", title="Growth rate used",
            flags=("fallback",))

    # -- models ---------------------------------------------------------------
    net_debt = pv.derived("(info.totalDebt, else balance-sheet Total Debt) − info.totalCash; a missing one counts as 0",
                          [y("totalDebt"), y("totalCash")], title="Net debt")
    shares = y("sharesOutstanding", note="Replaced by marketCap / price when the two disagree by more than 5x.")
    eps, growth, ke = y("trailingEps"), k("growthInput"), k("wacc", "costOfEquity")
    m_aaa = k("models", "Graham Formula", "detail", "aaaYieldPct")
    prov[m_aaa] = pv.fred(
        "AAA", "Moody's seasoned Aaa corporate bond yield", units="%", frequency="monthly",
        note="The code substitutes 5.0 when FRED cannot be read; the response does not say whether that happened.")
    sm = load_sector_multiples()
    sector = info.get("sector")
    m_mult = k("models", "EV/EBITDA Comps", "detail", "sectorMultiple")
    prov[m_mult] = pv.ref("damodaran", "vebitda", f"Median EV/EBITDA, {sector} sector", units="x",
                          observed=sm.get("asOf"), url=sm.get("sourceUrl"),
                          note="Static snapshot bundled with the app: median of Damodaran's US industry multiples "
                               "mapped to sectors.")
    formulas = {
        "DDM (Gordon Growth)": ("D1 / (ke − g), D1 = dividendRate × (1 + g), g = (1 − payout ratio) × ROE (ROE capped at 25%), "
                                "capped at the risk-free rate and at ke − 0.5pp; earnings growth is not used",
                                [y("dividendRate"), ke, y("returnOnEquity"), y("payoutRatio"),
                                 k("wacc", "riskFree")]),
        "Graham Formula": ("EPS × (8.5 + 2g) × 4.4 / Y, g = growth in percent (0-20), Y = Aaa corporate yield in percent",
                           [eps, growth, m_aaa]),
        "Graham Number": ("√(22.5 × EPS × book value per share)", [eps, y("bookValue")]),
        "Peter Lynch / PEG": ("EPS × growth in percent (capped at 20): fair P/E equals the growth rate",
                              [eps, growth]),
        "EV/EBITDA Comps": ("(sector EV/EBITDA × EBITDA − net debt) / shares", [y("ebitda"), m_mult, net_debt, shares]),
        "Residual Income (RIM)": (
            "book value per share + Σ(t = 1…5) (ROE_t − ke) × book_(t−1) / (1 + ke)^t; ROE starts at Yahoo's "
            "TTM ROE capped at 25% and fades linearly to ke by year 5; book grows by ROE_t × retention, "
            "retention = 1 − dividend payout − net buybacks / net income (clamped to 0–1); no terminal value",
            [y("bookValue"), y("returnOnEquity"), ke, y("payoutRatio"),
             pv.yahoo(sym, "Annual cash-flow statement: net common stock issuance / repurchases, and net income")]),
        "EPV (Earnings Power Value)": (
            "(EBIT × (1 − tax rate) / WACC − net debt) / shares; tax rate 21% if unavailable",
            [y("ebit (else statement EBIT / Operating Income)"), k("wacc", "taxRate"), k("wacc", "wacc"), net_debt,
             shares]),
    }
    for m in result.get("models") or []:
        name = m.get("model")
        if name == "DCF (Two-Stage)":
            d = (m.get("detail") or {}).get("inputs")
            if d:
                sub = dcf_engine.provenance(sym, {"inputs": d, "currency": ccy}, k("models", name, "detail"),
                                            growth=growth, wacc=k("wacc", "wacc"))
                prov.update(sub)
                prov[k("models", name)] = sub[k("models", name, "detail")]
        elif name in formulas:
            formula, inputs = formulas[name]
            prov[k("models", name)] = pv.derived(formula, inputs, title=name)
    prov[k("capmImplied")] = pv.derived("forward EPS (trailing EPS if missing) / cost of equity",
                                        [y("forwardEps"), eps, ke], title="CAPM-implied value")
    prov[k("axiomFairValue")] = pv.derived(
        "weighted mean of the models that produced a positive value (null or non-positive values are excluded), weights renormalised: DCF 30%, EV/EBITDA 20%, RIM 15%, "
        "EPV 15%, Graham Formula 10%, Lynch 5%, DDM 5% (Graham Number and CAPM-implied carry no weight)",
        [k("models", mm["model"]) for mm in result.get("models") or []], title="Composite fair value")
    prov[k("axiomFairValue", "upsidePct")] = pv.derived("(composite value − spot price) / spot price",
                                                        [k("axiomFairValue"), k("spotPrice")], title="Upside")
    prov[k("axiomFairValue", "verdict")] = pv.derived(
        "upside > 25% Significantly Undervalued; > 10% Undervalued; > −10% Fairly Valued; > −25% Overvalued; "
        "otherwise Significantly Overvalued", [k("axiomFairValue", "upsidePct")], title="Verdict")
    return prov

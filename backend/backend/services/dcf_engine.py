"""Two-stage DCF valuation engine with scenario analysis and sensitivity heatmap."""
from __future__ import annotations

import logging
import math
from datetime import date

from .. import provenance as pv
from .metrics import _clean

log = logging.getLogger(__name__)

# yfinance ``info`` fields reported in the *statement* currency
# (``financialCurrency``) rather than the trading currency (``currency``).
_STATEMENT_INFO_FIELDS = (
    "freeCashflow", "operatingCashflow", "totalDebt", "totalCash", "ebitda",
    "totalRevenue", "grossProfits", "netIncomeToCommon", "totalStockholderEquity",
)


# Yahoo quote currencies in minor units -> (major currency, major units per minor unit).
_MINOR_UNITS = {"GBp": ("GBP", 0.01), "GBX": ("GBP", 0.01), "ZAc": ("ZAR", 0.01), "ILA": ("ILS", 0.01)}


def _fx_rate(from_ccy: str, to_ccy: str) -> float | None:
    """Latest price of 1 ``from_ccy`` in ``to_ccy`` (Yahoo ``XXXYYY=X``).

    Minor units (London pence "GBp", Johannesburg cents "ZAc", Tel Aviv agorot
    "ILA") are scaled from their major currency; GBP -> GBp is ×100 with no lookup.
    """
    (src, src_k), (dst, dst_k) = (_MINOR_UNITS.get(c, (c, 1.0)) for c in (from_ccy, to_ccy))
    if src_k != 1.0 or dst_k != 1.0:
        base = 1.0 if src == dst else _fx_rate(src, dst)
        return base * src_k / dst_k if base is not None else None
    from . import yfinance_service as yfs
    sym = f"{from_ccy}{to_ccy}=X"
    try:
        frame = yfs.get_close_frame((sym,), "5d")
        s = frame[sym].dropna() if sym in frame.columns else None
        return float(s.iloc[-1]) if s is not None and len(s) else None
    except Exception:
        log.debug("FX %s unavailable", sym, exc_info=True)
        return None


def to_price_currency(bundle: dict) -> dict:
    """Return a copy of ``bundle`` with statement figures in the price currency.

    ADRs and other cross-listings (TSM, NVO, BABA) quote in USD but report
    FCF, debt, cash and statements in TWD/DKK/CNY; valuing those as dollars
    produced intrinsic values tens of times off (audit C-16). Monetary
    ``info`` fields and every statement line except share counts and rates
    are converted at the latest FX rate; book value per share is the converted
    stockholders' equity / (market cap / price), because Yahoo's priceToBook
    mixes currencies for these tickers (None when equity is unavailable).

    Sets ``_fx = {"from", "to", "rate"}`` (rate None when unavailable, in
    which case the caller must not value the company).
    """
    if bundle.get("_fx") is not None:
        return bundle  # already normalised
    info = dict(bundle.get("info") or {})
    fin_ccy = info.get("financialCurrency")
    px_ccy = info.get("currency")
    out = dict(bundle)
    if not fin_ccy or not px_ccy or fin_ccy == px_ccy:
        out["_fx"] = {"from": fin_ccy or px_ccy, "to": px_ccy, "rate": 1.0}
        return out
    rate = _fx_rate(fin_ccy, px_ccy)
    out["_fx"] = {"from": fin_ccy, "to": px_ccy, "rate": rate}
    if rate is None:
        return out
    for k in _STATEMENT_INFO_FIELDS:
        v = _clean(info.get(k))
        if v is not None:
            info[k] = v * rate
    out["info"] = info

    def _scale(stmt: dict) -> dict:
        return {k: (v * rate if isinstance(v, (int, float)) and "Share" not in k and "Rate" not in k else v)
                for k, v in (stmt or {}).items()}

    for key in ("financials", "balance_sheet", "cashflow"):
        if isinstance(bundle.get(key), dict):
            out[key] = _scale(bundle[key])

    # Book value per ADR-equivalent share = converted equity / (marketCap / price). Yahoo's priceToBook
    # divides a trading-currency price by a statement-currency book, so price / priceToBook is wrong
    # for these tickers (TSM: 4.86 vs about 32.7; audit M-01).
    bs = out.get("balance_sheet") or {}
    equity = _clean(bs.get("Stockholders Equity")) or _clean(bs.get("Common Stock Equity"))
    price = _clean(info.get("currentPrice") or info.get("regularMarketPrice"))
    mcap = _clean(info.get("marketCap"))
    info["bookValue"] = equity * price / mcap if equity and price and mcap and mcap > 0 else None
    return out


def is_bank(info: dict) -> bool:
    """True for deposit-taking banks (Yahoo industry "Banks - ...", screener "... Banks").

    A bank's debt and cash are operating balances (deposits, reserves), so
    neither a free-cash-flow DCF nor an EV-based multiple is meaningful.
    Other financials (payment networks, asset managers) have real FCF and are
    not matched.
    """
    return "bank" in str((info or {}).get("industry") or "").lower()


def _single_dcf(
    fcf: float,
    fcf_growth: float,
    terminal_growth: float,
    wacc: float,
    stage1_years: int,
    net_debt: float,
    shares: float,
) -> float | None:
    """Compute per-share intrinsic value for one parameter set.

    Returns None if invalid, or if the equity value is not positive (net debt
    exceeds the enterprise value): a negative price per share is not a
    valuation (audit M-02).
    """
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
    intrinsic = _clean(equity / shares)
    if intrinsic is None or intrinsic <= 0:
        return None
    return intrinsic


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
    bundle = to_price_currency(bundle)
    info: dict = bundle.get("info") or {}
    ticker: str = bundle.get("ticker") or ""
    fx = bundle.get("_fx") or {}

    # --- Extract inputs ---
    # Yahoo's freeCashflow is *levered* FCF (after interest). Operating cash
    # flow is not FCF at all and is no longer substituted (audit C-27); the
    # levered-FCF-at-WACC approximation is disclosed in the inputs.
    fcf_raw = info.get("freeCashflow")
    # get_info marks an annual-statement fill (no trailing figure) with its fiscal year (P3-26).
    fcf_period = info.get("_fcfPeriod") or "TTM"
    fcf_basis = ("levered FCF (Yahoo freeCashflow), TTM" if fcf_period == "TTM"
                 else f"levered FCF (annual cash-flow statement, {fcf_period}; Yahoo has no trailing figure)")
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

    # --- Validate shares outstanding ---
    # yfinance sometimes returns sharesOutstanding in inconsistent units.
    # Cross-check: if marketCap and currentPrice are available, compute
    # implied shares = marketCap / price. Use this if the direct
    # sharesOutstanding looks wrong (e.g., off by >10x for mega-caps).
    if shares is not None and spot is not None and spot > 0:
        market_cap = _clean(info.get("marketCap"))
        if market_cap is not None and market_cap > 0:
            implied_shares = market_cap / spot
            ratio = implied_shares / shares if shares > 0 else 0
            if ratio > 5 or ratio < 0.2:
                # sharesOutstanding is likely in wrong units — use implied
                import logging
                _log = logging.getLogger(__name__)
                _log.warning(
                    "dcf_engine: sharesOutstanding=%s, marketCap/price implies %s "
                    "(ratio=%.2f) — using implied shares",
                    shares, implied_shares, ratio,
                )
                shares = implied_shares

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
                "fcfBasis": fcf_basis,
                "fcfPeriod": fcf_period,
                "statementCurrency": fx.get("from"),
                "fxRate": fx.get("rate"),
            },
            "scenarios": [],
            "sensitivity": {},
            "asOf": as_of,
        }

    if is_bank(info):
        return _locked("not meaningful for banks")
    if fx.get("rate") is None:
        return _locked(f"No FX rate to convert {fx.get('from')} statements to {fx.get('to')}")
    if fcf is None:
        return _locked("TTM free cash flow unavailable")
    if fcf <= 0:
        return _locked("not meaningful: free cash flow ≤ 0")
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
    if intrinsic is None:
        return _locked("not meaningful: equity value ≤ 0 after net debt")

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
            "fcfBasis": fcf_basis,
            "fcfPeriod": fcf_period,
            "statementCurrency": fx.get("from"),
            "fxRate": fx.get("rate"),
        },
        "scenarios": scenarios,
        "sensitivity": sensitivity,
        "asOf": as_of,
    }


def _assumption(text: str) -> dict:
    """A user-supplied or model-default assumption rather than observed data."""
    r = pv.ref("other", None, text)
    r["providerName"] = "Assumption (request parameter or model default)"
    return r


def provenance(sym: str, result: dict, root: str = "", *, growth=None, wacc=None) -> dict:
    """Provenance for a successful :func:`two_stage_dcf` result.

    Keys sit under ``root`` (``""`` = the response root). ``growth`` / ``wacc`` are
    provenance keys or refs for those inputs when they are not plain request parameters.
    """
    def k(*parts: str) -> str:
        return ".".join(p for p in (root, *parts) if p) or "*"

    inp = result.get("inputs") or {}
    from_ccy, rate = inp.get("statementCurrency"), inp.get("fxRate")
    to_ccy = result.get("currency")
    converted = bool(from_ccy and to_ccy and from_ccy != to_ccy and rate not in (None, 1.0))
    fx = [pv.yahoo(f"{from_ccy}{to_ccy}=X", f"Latest close, {from_ccy} to {to_ccy}", frequency="daily")] if converted else []
    conv = f" × FX rate ({from_ccy}→{to_ccy})" if converted else ""

    period = inp.get("fcfPeriod") or "TTM"
    fcf = pv.yahoo(sym, "info.freeCashflow: trailing-twelve-month levered free cash flow (Yahoo)" if period == "TTM"
                   else f"Free Cash Flow, annual cash-flow statement {period} (Yahoo has no trailing figure)")
    prov = {
        k("inputs", "ttmFcf"): pv.derived(f"Yahoo freeCashflow{conv}", [fcf, *fx], title="Free cash flow used")
        if converted else fcf,
        k("inputs", "shares"): pv.yahoo(
            sym, "info.sharesOutstanding",
            note="Replaced by marketCap / price when the two disagree by more than 5x."),
        k("inputs", "netDebt"): pv.derived(
            f"(info.totalDebt − info.totalCash, a missing one counted as 0){conv}",
            [pv.yahoo(sym, "info.totalDebt"), pv.yahoo(sym, "info.totalCash"), *fx], title="Net debt"),
        k("inputs", "fcfGrowth"): growth or _assumption("Stage-1 free-cash-flow growth (fcf_growth parameter)"),
        k("inputs", "terminalGrowth"): _assumption("Terminal growth rate (terminal_growth parameter)"),
        k("inputs", "wacc"): wacc or _assumption("Discount rate (wacc parameter)"),
        k("inputs", "stage1Years"): _assumption("Length of stage 1 in years (stage1_years parameter)"),
        k("spotPrice"): pv.yahoo(sym, "info.currentPrice (else regularMarketPrice)", units=to_ccy),
    }
    prov[k()] = pv.derived(
        "Σ FCF₀(1+g)ᵗ/(1+w)ᵗ for t = 1…N  +  FCF_N(1+gₜ)/(w−gₜ)/(1+w)ᴺ, minus net debt, divided by shares "
        "(g = stage-1 growth, w = discount rate, gₜ = terminal growth, N = stage-1 years)",
        [k("inputs", n) for n in ("ttmFcf", "netDebt", "shares", "fcfGrowth", "terminalGrowth", "wacc", "stage1Years")],
        title="Two-stage DCF intrinsic value per share",
        note="Levered FCF is discounted at the WACC (an approximation).")
    prov[k("upsidePct")] = pv.derived("(intrinsic value − spot price) / spot price", [k(), k("spotPrice")],
                                      title="Upside vs spot price")
    prov[k("scenarios")] = pv.derived(
        "Bear: growth −3pp, discount rate +1pp; Base: as given; Bull: growth +3pp, discount rate −1pp "
        "(never below terminal growth + 0.5pp); each re-runs the two-stage DCF",
        [k()], title="DCF scenarios")
    prov[k("sensitivity")] = pv.derived(
        "7×7 grid re-running the DCF: growth = base + (−3…+3) × 1pp down the rows, discount rate = "
        "base + (−3…+3) × 0.5pp across; blank where the discount rate ≤ terminal growth",
        [k()], title="DCF sensitivity grid")
    return prov

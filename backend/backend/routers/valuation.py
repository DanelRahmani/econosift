"""CAPM + DCF valuation."""
from __future__ import annotations

import asyncio
from fastapi import APIRouter, Query

from .. import provenance as pv
from ..services import yfinance_service as yfs
from ..services import metrics
from ..services import dcf_engine
from ..services import valuation_engine
from ..services import fundamentals as fundamentals_svc
from ..services import analyst_service
from ..services.dcf_engine import two_stage_dcf
from ..services.valuation_engine import valuation_models
from ..services.fundamentals import extended_fundamentals
from ..services.analyst_service import analyst_data
from ..services import fama_french

router = APIRouter(prefix="/api/valuation", tags=["valuation"])


def _kpis(info: dict, bundle: dict | None = None) -> dict:
    """Headline KPI + extended-fundamental fields straight from Ticker.info.

    Every access is guarded; short data is US-listed only and may be absent.
    ``evToFcf`` / ``fcfYield`` are built in the price currency (ADRs report in
    another one, audit M-01), and so is ``bookValue`` (``bundle`` supplies the
    balance sheet it needs); ``unavailable`` maps a field to the reason it is None.
    """
    g = info.get
    mm = metrics.market_multiples({**(bundle or {}), "info": info})
    return {
        "price": g("currentPrice") or g("regularMarketPrice"),
        "marketCap": g("marketCap"),
        "trailingPE": g("trailingPE"),
        "forwardPE": g("forwardPE"),
        "trailingEps": g("trailingEps"),
        "forwardEps": g("forwardEps"),
        "dividendYield": g("dividendYield"),
        "fiftyTwoWeekHigh": g("fiftyTwoWeekHigh"),
        "fiftyTwoWeekLow": g("fiftyTwoWeekLow"),
        "beta": g("beta"),
        "averageVolume": g("averageVolume") or g("averageDailyVolume10Day"),
        "bookValue": mm["values"]["bookValue"],
        "evToFcf": mm["values"]["evToFcf"],
        "fcfYield": mm["values"]["fcfYield"],
        "unavailable": {**{k: v for k, v in mm["unavailable"].items() if k in ("evToFcf", "fcfYield", "bookValue")},
                        **({} if g("currency") else {"currency": "Yahoo reported no quote currency"})},
        "shortPercentOfFloat": g("shortPercentOfFloat"),
        "shortRatio": g("shortRatio"),
        "sector": g("sector"),
        "industry": g("industry"),
        "currency": g("currency") or None,
    }


def _beta_for(sym: str) -> float | None:
    """Compute beta vs the symbol's benchmark over 2y of daily prices."""
    bench = yfs.benchmark_for(sym)
    frame = yfs.get_close_frame(tuple(dict.fromkeys([sym, bench])), "2y")
    if frame is None or frame.empty or sym not in frame.columns:
        return None
    bench_series = frame[bench] if bench in frame.columns else None
    m = metrics.risk_metrics(frame[sym], bench_series, 0.04)
    return m.get("beta")


def _signal(spot, target, expected_return) -> str:
    if spot is None or target is None:
        return "INCOMPLETE"
    upside = (target - spot) / spot
    if upside > 0.10:
        return "BUY"
    if upside < -0.10:
        return "OVERVALUED"
    return "FAIR VALUE"


@router.get("/capm-dcf")
async def capm_dcf(
    tickers: str = Query(...),
    period: str = "1y",
    risk_free: float = 0.04,
    market_premium: float = 0.055,
    fcf_growth: float = 0.08,
    terminal_growth: float = 0.025,
):
    syms = [t.strip().upper() for t in tickers.split(",") if t.strip()]
    benchmarks = sorted({yfs.benchmark_for(s) for s in syms})
    all_syms = tuple(dict.fromkeys(syms + benchmarks))

    frame = await asyncio.to_thread(yfs.get_close_frame, all_syms, period)

    valuations = []
    for sym in syms:
        bench = yfs.benchmark_for(sym)
        beta = None
        if frame is not None and not frame.empty and sym in frame.columns:
            bench_series = frame[bench] if bench in frame.columns else None
            m = metrics.risk_metrics(frame[sym], bench_series, risk_free)
            beta = m.get("beta")

        bundle = await asyncio.to_thread(yfs.get_info, sym)
        info = bundle.get("info", {}) or {}

        expected_return = metrics.capm_expected_return(beta, risk_free, market_premium)
        discount = expected_return if expected_return else risk_free + market_premium
        target = metrics.dcf_target(info, fcf_growth, terminal_growth, discount)

        spot = info.get("currentPrice") or info.get("regularMarketPrice")
        spot = float(spot) if spot else None

        valuations.append({
            "ticker": sym,
            "benchmark": bench,
            "beta": beta,
            "expectedReturn": expected_return,
            "trailingPE": info.get("trailingPE"),
            "spotPrice": spot,
            "dcfTarget": target,
            "currency": info.get("currency") or None,
            **({} if info.get("currency") else {"unavailable": {"currency": "Yahoo reported no quote currency"}}),
            "signal": _signal(spot, target, expected_return),
        })

    return pv.attach({"valuations": valuations},
                     _capm_dcf_provenance(valuations, frame, period, risk_free, market_premium,
                                          fcf_growth, terminal_growth))


def _capm_dcf_provenance(rows: list[dict], frame, period: str, rf: float, mp: float,
                         g: float, gt: float) -> dict:
    """``valuations.<ticker>.<field>`` for each row of /capm-dcf."""
    prov: dict = {"*": pv.derived(
        "CAPM expected return and a 5-year free-cash-flow DCF for each ticker, from Yahoo prices and fundamentals",
        title="CAPM and DCF valuation")}
    for v in rows:
        sym, bench = v["ticker"], v["benchmark"]
        base = f"valuations.{sym}"
        prices = [pv.yahoo(sym, f"Daily adjusted close, {period}", frequency="daily",
                           observed=pv.last_date(frame[sym]) if frame is not None and sym in frame.columns else None),
                  pv.yahoo(bench, f"Benchmark daily adjusted close, {period}", frequency="daily",
                           observed=pv.last_date(frame[bench]) if frame is not None and bench in frame.columns
                           else None)]
        info = {f: pv.yahoo(sym, f"info.{f}") for f in
                ("trailingPE", "freeCashflow", "operatingCashflow", "sharesOutstanding", "totalDebt", "totalCash")}
        prov[f"{base}.beta"] = pv.derived(
            f"cov(r, r_{bench}) / var(r_{bench}) of daily log returns over the common days", prices, title="Beta")
        prov[f"{base}.expectedReturn"] = pv.derived(
            f"risk-free rate + beta × market premium; risk-free rate {rf:g} and market premium {mp:g} are "
            "request parameters (server defaults 0.04 and 0.055), not observed data",
            [f"{base}.beta"], title="CAPM expected return")
        prov[f"{base}.trailingPE"] = info["trailingPE"]
        prov[f"{base}.spotPrice"] = pv.yahoo(sym, "info.currentPrice (else regularMarketPrice)",
                                             units=v.get("currency"))
        prov[f"{base}.currency"] = pv.yahoo(sym, "info.currency")
        prov[f"{base}.dcfTarget"] = pv.derived(
            "Σ FCF(1+g)^t/(1+r)^t for t = 1…5 + FCF₅(1+gₜ)/(r−gₜ)/(1+r)^5, plus cash minus debt, divided by shares; "
            f"FCF = info.freeCashflow (else operatingCashflow), r = the CAPM expected return (risk-free + market "
            f"premium if there is no beta), g = {g:g} and gₜ = {gt:g} are request parameters",
            [info["freeCashflow"], info["operatingCashflow"], info["sharesOutstanding"], info["totalDebt"],
             info["totalCash"], f"{base}.expectedReturn"], title="DCF target price",
            note="Statement figures are used in the reporting currency, without conversion to the trading currency.")
        prov[f"{base}.signal"] = pv.derived(
            "upside = (DCF target − spot price) / spot price: above +10% BUY, below −10% OVERVALUED, otherwise "
            "FAIR VALUE; INCOMPLETE if either price is missing", [f"{base}.dcfTarget", f"{base}.spotPrice"],
            title="Signal")
    return prov


@router.get("/risk-free-rates")
async def risk_free_rates():
    """Live country risk-free rates from FRED (cached nightly)."""
    from ..services.risk_free_service import get_risk_free_rates
    rates = await get_risk_free_rates()
    return pv.attach({"rates": rates}, _risk_free_provenance(rates))


def _risk_free_provenance(rates: list[dict]) -> dict:
    """``rates.<country>`` (FRED yield or hard-coded fallback) and ``rates.<country>.erp`` per row."""
    from ..services.discount_rates import bundled_as_of, load_erp
    erp_data = load_erp()
    table = erp_data.get("countries") or {}
    as_of = erp_data.get("asOf")
    erp_obs = as_of if isinstance(as_of, str) and as_of[:2] == "20" else None
    erp_stamp = bundled_as_of(erp_data)  # a bundled snapshot is dated by its own asOf
    prov: dict = {"*": pv.ref("fred", None, "Government bond and money-market rates by country")}
    for r in rates:
        name = r["name"]
        key = f"rates.{name}"
        if r.get("basis") == "observed":
            flags = tuple(f for f, on in (("stale", r.get("stale")), ("proxy", "proxy" in (r.get("tenor") or "")))
                          if on)
            prov[key] = pv.fred(
                r["series"], f"{name}: {r['tenor']}", units="decimal (FRED percent / 100)",
                frequency="daily" if r["series"] == "DGS10" else "monthly", observed=r.get("asOf"), flags=flags)
        else:
            prov[key] = pv.ref("econosift", None, f"{name}: hard-coded risk-free estimate (FRED had no observation)",
                               flags=("fallback",))
        entry = table.get(name)
        try:
            has_erp = bool(isinstance(entry, dict) and "erp" in entry and float(entry["erp"]))
        except (TypeError, ValueError):
            has_erp = False
        if has_erp:
            prov[f"{key}.erp"] = pv.ref("damodaran", "ctryprem", f"Total equity risk premium, {name}",
                                        units="decimal (source percent / 100)", frequency="annual",
                                        observed=erp_obs, url=erp_data.get("sourceUrl"))
            if erp_stamp:
                prov[f"{key}.erp"]["fetchedAt"] = erp_stamp
        else:
            prov[f"{key}.erp"] = pv.ref("econosift", None, f"{name}: hard-coded equity risk premium (no Damodaran row)",
                                        units="decimal", flags=("fallback",))
    return prov


@router.get("/dcf")
async def dcf(
    ticker: str,
    fcf_growth: float = 0.08,
    terminal_growth: float = 0.025,
    wacc: float = 0.09,
    stage1_years: int = 10,
):
    """Two-stage DCF valuation with scenario table and sensitivity heatmap."""
    sym = ticker.strip().upper()
    bundle = await asyncio.to_thread(yfs.get_info, sym)
    result = two_stage_dcf(
        bundle,
        fcf_growth=fcf_growth,
        terminal_growth=terminal_growth,
        wacc=wacc,
        stage1_years=stage1_years,
    )
    if result.get("locked"):
        return result
    return pv.attach(result, dcf_engine.provenance(sym, result))


@router.get("/full")
async def full(ticker: str):
    """Full valuation bundle (compute tier: runs on page load).

    Combines the 8-model valuation engine + EconoSift composite, extended
    fundamentals (Piotroski / Beneish / Ohlson / DuPont / ROIC / CCC), and
    analyst data (price targets, consensus, surprises, estimates).
    """
    sym = ticker.strip().upper()
    # The three upstream fetches are independent; run them together rather
    # than paying their cold latencies one after another.
    bundle, beta, analyst = await asyncio.gather(
        asyncio.to_thread(yfs.get_info, sym),
        asyncio.to_thread(_beta_for, sym),
        asyncio.to_thread(analyst_data, sym),
    )
    valuation, fundamentals = await asyncio.gather(
        asyncio.to_thread(valuation_models, bundle, beta),
        asyncio.to_thread(extended_fundamentals, bundle),
    )
    kpis = _kpis(bundle.get("info", {}) or {}, bundle)
    # Fix 7: Inject computed beta when yfinance info.beta is null
    beta_injected = kpis.get("beta") is None and beta is not None
    if beta_injected:
        kpis["beta"] = beta
    prov = {"*": pv.yahoo(sym, "Company fundamentals, valuation inputs and analyst data")}
    info = bundle.get("info", {}) or {}
    prov.update(_kpi_provenance(sym, kpis, beta_injected,
                                info.get("financialCurrency") not in (None, info.get("currency"))))
    prov.update(valuation_engine.provenance(bundle, valuation, beta, "valuation"))
    prov.update(fundamentals_svc.provenance(bundle, "fundamentals"))
    prov.update(analyst_service.provenance(analyst, "analyst"))
    # A bundle Yahoo answered only in part is never cached (get_info's skip_if), so asking again soon
    # gets the full one; the UI says so and re-requests (P2-39).
    degraded = yfs._info_failed(bundle)
    no_price = not (info.get("currentPrice") or info.get("regularMarketPrice"))
    return pv.attach({
        "ticker": sym,
        "kpis": kpis,
        "valuation": valuation,
        "fundamentals": fundamentals,
        "analyst": analyst,
        "degraded": degraded,
        "degradedReason": (None if not degraded else
                           "Yahoo returned no price for this ticker; the models cannot run." if no_price else
                           "Yahoo returned partial company data (no sector, industry or revenue); models that "
                           "need it may be off or locked."),
    }, prov)


def _kpi_provenance(sym: str, kpis: dict, beta_injected: bool, cross_currency: bool = False) -> dict:
    """``kpis.<field>`` refs for the headline block of /full."""
    def y(field: str, **kw) -> dict:
        return pv.yahoo(sym, f"info.{field}", **kw)

    eps_note = ("Yahoo's field; when Yahoo omits it, get_info derives it (price / P/E, or the current-year "
                "earnings estimate) and the response does not say which.")
    prov = {f"kpis.{f}": y(f) for f in (
        "marketCap", "trailingPE", "forwardPE", "fiftyTwoWeekHigh", "fiftyTwoWeekLow", "bookValue",
        "shortPercentOfFloat", "shortRatio", "sector", "industry")}
    prov["kpis.price"] = y("currentPrice (else regularMarketPrice)", units=kpis.get("currency"))
    prov["kpis.trailingEps"] = y("trailingEps", note=eps_note)
    prov["kpis.forwardEps"] = y("forwardEps", note=eps_note)
    prov["kpis.dividendYield"] = y("dividendYield", units="percent (0.98 = 0.98%)")
    prov["kpis.averageVolume"] = y("averageVolume (else averageDailyVolume10Day)", units="shares")
    prov["kpis.currency"] = y("currency")
    fx_note = ("Statements are reported in a different currency from the price, so free cash flow, debt and "
               "cash are converted to the price currency first and EV = market cap + debt − cash."
               if cross_currency else None)
    prov["kpis.evToFcf"] = pv.derived("info.enterpriseValue / info.freeCashflow",
                                      [y("enterpriseValue"), y("freeCashflow")], title="EV / free cash flow",
                                      note=fx_note)
    prov["kpis.fcfYield"] = pv.derived("info.freeCashflow / info.marketCap", [y("freeCashflow"), y("marketCap")],
                                       title="Free cash flow yield", note=fx_note)
    if cross_currency:
        prov["kpis.bookValue"] = pv.derived(
            "stockholders' equity × FX to the price currency × price / market cap",
            [pv.yahoo(sym, "Balance sheet, latest fiscal year", frequency="annual"), y("marketCap")],
            title="Book value per share", note="Yahoo's bookValue mixes currencies for ADRs, so it is rebuilt.")
    if beta_injected:
        prov["kpis.beta"] = pv.derived(
            "cov(r, r_benchmark) / var(r_benchmark) of 2 years of daily log returns",
            [pv.yahoo(sym, "Daily adjusted close, 2y", frequency="daily"),
             pv.yahoo(yfs.benchmark_for(sym), "Benchmark daily adjusted close, 2y", frequency="daily")],
            title="Beta", flags=("fallback",), note="Yahoo supplied no beta, so this computed beta stands in.")
    else:
        prov["kpis.beta"] = y("beta", note="Yahoo's beta; when Yahoo has none, get_info substitutes fast_info's beta "
                                          "or a 2-year beta against the benchmark, and the response does not say which.")
    return prov


@router.get("/factors")
async def factors(ticker: str, model: str = "3", period: str = "2y"):
    """Fama-French 3F/5F per-ticker attribution (compute tier: on-demand)."""
    sym = ticker.strip().upper()
    result = await asyncio.to_thread(
        fama_french.factor_regression, sym, model, period
    )
    if "error" in result:
        return result
    five = model == "5"
    factor_ref = pv.ref(
        "kenfrench", "F-F_Research_Data_5_Factors_2x3_daily" if five else "F-F_Research_Data_Factors_daily",
        "Fama-French " + ("5" if five else "3") + "-factor daily returns and risk-free rate",
        units="decimal (source percent / 100)", frequency="daily")
    price_ref = pv.yahoo(sym, f"Daily adjusted close, {period}", frequency="daily")
    names = "Mkt-RF, SMB, HML" + (", RMW, CMA" if five else "")
    return pv.attach(result, {
        "*": pv.derived(
            f"OLS of the daily excess return (simple return of the adjusted close − RF) on {names}, with an intercept, "
            "over the days both series cover", [price_ref, factor_ref], title="Fama-French factor regression"),
        "alpha": pv.derived("intercept of the regression × 252", ["*"], title="Annualised alpha"),
        "alphaDaily": pv.derived("intercept of the regression", ["*"], title="Daily alpha"),
        "betas": pv.derived("regression coefficient on each factor", ["*"], title="Factor loadings"),
        "tStats": pv.derived("OLS coefficient / standard error, intercept and each factor", ["*"],
                             title="t-statistics"),
        "rSquared": pv.derived("1 − residual sum of squares / total sum of squares of the excess return", ["*"],
                               title="R-squared"),
    })

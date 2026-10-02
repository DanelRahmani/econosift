"""App data for AI summaries (P1-19): compact blocks built from EconoSift's own payloads.

Each builder takes what the app already serves (the same cached endpoints the pages use)
and keeps only the headline figures, so the model writes its numbers from EconoSift data
instead of from memory. Builders are pure: the router fetches, these only select and round.
"""
from __future__ import annotations

import math
from typing import Any


def _r(v: Any, sig: int = 6) -> Any:
    """Round a float to ``sig`` significant digits; pass everything else through. NaN/inf -> None."""
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return v
    if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
        return None
    if v == 0 or isinstance(v, int):
        return v
    return float(f"{v:.{sig}g}")


def _pick(d: dict | None, *keys: str) -> dict:
    """Subset of ``d`` with rounded values, dropping missing/None entries."""
    d = d or {}
    return {k: _r(d[k]) for k in keys if d.get(k) is not None}


def company_block(quote: dict | None, full: dict | None) -> dict:
    """Headline figures for one ticker from ``/market/quote`` and ``/valuation/full``."""
    full = full or {}
    val = full.get("valuation") or {}
    fund = full.get("fundamentals") or {}
    analyst = full.get("analyst") or {}
    kpis = full.get("kpis") or {}

    models = []
    for m in val.get("models") or []:
        row = {"model": m.get("model")}
        if m.get("locked") or m.get("value") is None:
            row["value"] = None
            row["reason"] = m.get("reason")
        else:
            row["value"] = _r(m.get("value"))
        models.append(row)

    pio = fund.get("piotroski") or {}
    ben = fund.get("beneish") or {}
    ohl = fund.get("ohlson") or {}
    block = {
        "quote": _pick(quote, "price", "changePercent", "currency"),
        "kpis": {**_pick(kpis, "marketCap", "trailingPE", "forwardPE", "trailingEps", "forwardEps", "beta",
                         "fiftyTwoWeekHigh", "fiftyTwoWeekLow", "currency", "sector", "industry"),
                 # Yahoo's dividendYield is already a percent (0.49 = 0.49 %)
                 **({"dividendYieldPct": _r(kpis["dividendYield"])} if kpis.get("dividendYield") is not None else {})},
        "fairValue": _pick(val.get("axiomFairValue"), "value", "upsidePct", "verdict"),
        "valuationModels": models,
        "discountRate": _pick(val.get("wacc"), "wacc", "costOfEquity", "riskFree", "riskFreeSource", "beta", "country"),
        "healthScores": {
            **({"piotroski": f"{pio['score']}/{pio['maxScore']}"} if pio.get("maxScore") else {}),
            **({"beneishM": _r(ben["mScore"]), "beneishFlagged": ben.get("manipulationLikely")}
               if ben.get("mScore") is not None else {}),
            **({"ohlsonProbDefault": _r(ohl["probDefault"])} if ohl.get("probDefault") is not None else {}),
            **({"roic": _r((fund.get("roic") or {}).get("roic"))} if (fund.get("roic") or {}).get("roic") is not None else {}),
        },
        "analysts": {
            "priceTarget": _pick(analyst.get("priceTarget"), "meanPrice", "highPrice", "lowPrice",
                                 "numberOfAnalysts", "upsidePct"),
            "consensus": _pick(analyst.get("consensus"), "recommendationKey", "recommendationMean"),
            "recentEarningsSurprises": [_pick(s, "date", "epsEstimate", "epsActual", "surprisePct")
                                        for s in (analyst.get("earningsSurprises") or [])[:4]],
        },
    }
    return _drop_empty(block)


def macro_block(snapshot: dict | None) -> dict:
    """Latest World Bank headline indicators per country from ``/macro/snapshot``: {iso2: {id: {value, year, unit}}}."""
    out: dict[str, dict] = {}
    for ind in (snapshot or {}).get("indicators") or []:
        for iso, v in (ind.get("values") or {}).items():
            if v.get("value") is None:
                continue
            out.setdefault(iso, {})[ind["id"]] = {"value": _r(v["value"]), "year": v.get("year"), "unit": ind.get("unit")}
    return out


def dashboard_block(breadth: dict | None, indices: dict | None, fear_greed: dict | None,
                    movers: dict | None) -> dict:
    """Market snapshot from the Dashboard endpoints (breadth, global indices, Fear & Greed, movers)."""
    def mover_rows(key: str) -> list[dict]:
        return [_pick(m, "ticker", "name", "changePercent") for m in ((movers or {}).get(key) or [])[:5]]

    block = {
        "breadthSP500": _pick(breadth, "asOf", "session", "advancing", "declining", "unchanged", "newHighs",
                              "newLows", "pctAboveSma50", "pctAboveSma200", "mcclellanOscillator"),
        "indices": [_pick(i, "name", "region", "price", "change1d", "change1m", "changeYtd", "asOf")
                    for i in (indices or {}).get("indices") or []],
        "fearGreed": {**_pick(fear_greed, "index", "label", "asOf"),
                      "signals": [_pick(s, "label", "score", "label_text") for s in (fear_greed or {}).get("signals") or []]},
        "topGainers": mover_rows("gainers"),
        "topLosers": mover_rows("losers"),
    }
    return _drop_empty(block)


def _drop_empty(d: Any) -> Any:
    """Remove empty dicts/lists recursively so the prompt carries no blank sections."""
    if isinstance(d, dict):
        cleaned = {k: _drop_empty(v) for k, v in d.items()}
        return {k: v for k, v in cleaned.items() if v not in ({}, [], None)}
    if isinstance(d, list):
        return [x for x in (_drop_empty(v) for v in d) if x not in ({}, [], None)]
    return d

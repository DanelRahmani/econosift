"""Cross-Asset & Factor Analytics service — Phase 39.

Three capabilities built on existing data infrastructure:
- Cross-asset correlation matrix (stocks, bonds, FX, commodities)
- FX / commodity / macro-link analysis
- Multi-country portfolio with FX-adjusted returns
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from ..cache import cached
from ..services import yfinance_service as yfs
from ..services.fx_service import fx_rates


# ── Asset universe helpers ────────────────────────────────────────────

# yfinance tickers for proxy ETFs / FX pairs
_ASSET_UNIVERSE = {
    "equities": {
        "SPY": "S&P 500",
        "QQQ": "Nasdaq 100",
        "IWM": "Russell 2000",
        "EFA": "MSCI EAFE",
        "EEM": "MSCI EM",
        "VGK": "Europe",
        "EWJ": "Japan",
        "FXI": "China",
    },
    "bonds": {
        "TLT": "Long Treasury",
        "IEF": "Int. Treasury",
        "SHY": "Short Treasury",
        "LQD": "IG Corporates",
        "HYG": "HY Corporates",
        "TIP": "TIPS",
        "AGG": "Aggregate Bond",
    },
    "commodities": {
        "GLD": "Gold",
        "SLV": "Silver",
        "USO": "Oil (WTI)",
        "DBA": "Agriculture",
        "DBB": "Base Metals",
        "UNG": "Natural Gas",
    },
    "fx": {
        "EURUSD=X": "EUR/USD",
        "USDJPY=X": "USD/JPY",
        "GBPUSD=X": "GBP/USD",
        "AUDUSD=X": "AUD/USD",
        "USDCAD=X": "USD/CAD",
        "USDCHF=X": "USD/CHF",
    },
}


def _get_correlation_matrix(prices: pd.DataFrame) -> dict:
    """Compute Pearson correlation matrix from daily returns, return as JSON-serializable dict."""
    rets = prices.pct_change().dropna(how="all")
    if rets.empty or rets.shape[1] < 2:
        return {"assets": list(prices.columns), "matrix": [], "dates": []}

    corr = rets.corr()
    assets = list(corr.columns)
    matrix = []
    for i, a1 in enumerate(assets):
        row = []
        for j, a2 in enumerate(assets):
            val = corr.loc[a1, a2] if a1 in corr.index and a2 in corr.columns else None
            row.append(round(float(val), 4) if val is not None and not np.isnan(val) else None)
        matrix.append(row)

    # Rolling 60-day correlation for the first pair
    rolling_dates: list[str] = []
    rolling_vals: list[float] = []
    if len(assets) >= 2 and len(rets) >= 60:
        roll = rets[assets[0]].rolling(60).corr(rets[assets[1]])
        roll = roll.dropna()
        rolling_dates = [str(d.date()) for d in roll.index]
        rolling_vals = [round(float(v), 4) if not np.isnan(v) else 0.0 for v in roll.values]

    return {
        "assets": assets,
        "labels": [_ASSET_UNIVERSE.get("equities", {}).get(a, "")
                    or _ASSET_UNIVERSE.get("bonds", {}).get(a, "")
                    or _ASSET_UNIVERSE.get("commodities", {}).get(a, "")
                    or _ASSET_UNIVERSE.get("fx", {}).get(a, a)
                    for a in assets],
        "matrix": matrix,
        "rolling": {
            "dates": rolling_dates,
            "values": rolling_vals,
        },
    }


async def get_cross_asset_correlations(tickers: list[str], period: str = "3y") -> dict:
    """Compute correlation matrix for a mixed set of assets.

    Accepts tickers from any asset class — stocks, bond/commodity ETFs, FX pairs (CCY=X format).
    """
    # Normalize to tuple for hashable cache key
    tickers = list(dict.fromkeys(t.strip().upper() for t in tickers if t.strip()))
    if not tickers or len(tickers) < 2:
        return {"assets": [], "labels": [], "matrix": [], "rolling": {"dates": [], "values": []}}

    frame = yfs.get_close_frame(tuple(tickers), period)
    if frame is None or frame.empty:
        return {"assets": tickers, "labels": tickers, "matrix": [], "rolling": {"dates": [], "values": []}}

    # Drop columns that are all-NaN
    frame = frame.dropna(axis=1, how="all")
    present = [c for c in tickers if c in frame.columns]
    if len(present) < 2:
        return {"assets": present, "labels": present, "matrix": [], "rolling": {"dates": [], "values": []}}

    return _get_correlation_matrix(frame[present])


async def get_fx_macro_link() -> dict:
    """Build FX / commodity / macro linkage data.

    Uses existing BIS effective FX, commodity ETF prices, and macro indicators
    to show relationships like AUD/USD ↔ Copper, CAD/USD ↔ Oil.
    """
    # Known macro links
    links = [
        {"fxPair": "AUDUSD=X", "commodity": "DBA", "label": "AUD/USD vs Agriculture"},
        {"fxPair": "USDCAD=X", "commodity": "USO", "label": "USD/CAD vs Oil"},
        {"fxPair": "AUDUSD=X", "commodity": "GLD", "label": "AUD/USD vs Gold"},
        {"fxPair": "USDNOK=X", "commodity": "USO", "label": "USD/NOK vs Oil"},
        {"fxPair": "USDBRL=X", "commodity": "DBA", "label": "USD/BRL vs Agriculture"},
        {"fxPair": "NZDUSD=X", "commodity": "DBA", "label": "NZD/USD vs Agriculture"},
    ]

    # Fetch all unique tickers
    all_tickers = set()
    for link in links:
        all_tickers.add(link["fxPair"])
        all_tickers.add(link["commodity"])
    tickers = tuple(all_tickers)

    frame = yfs.get_close_frame(tickers, "5y")
    if frame is None or frame.empty:
        return {"links": [], "error": "No data available"}

    frame = frame.dropna(axis=1, how="all")
    results = []

    for link in links:
        fx = link["fxPair"]
        comm = link["commodity"]
        if fx not in frame.columns or comm not in frame.columns:
            continue

        pair_frame = frame[[fx, comm]].dropna()
        if len(pair_frame) < 60:
            continue

        rets = pair_frame.pct_change().dropna()
        if len(rets) < 30:
            continue

        # Rolling 60-day correlation
        roll_corr = rets[fx].rolling(60).corr(rets[comm]).dropna()
        current_corr = float(roll_corr.iloc[-1]) if len(roll_corr) > 0 else None

        # Cross-correlation: does comm lead FX?
        max_lag = 21
        cross_corrs = []
        for lag in range(-max_lag, max_lag + 1):
            if lag < 0:
                c = rets[fx].iloc[-lag:].corr(rets[comm].iloc[:lag]) if lag != 0 else None
            elif lag > 0:
                c = rets[fx].iloc[:-lag].corr(rets[comm].iloc[lag:]) if lag != 0 else None
            else:
                c = rets[fx].corr(rets[comm])
            if c is not None and not np.isnan(c):
                cross_corrs.append({"lag": lag, "correlation": round(float(c), 4)})

        # Find best lead/lag
        best = max(cross_corrs, key=lambda x: abs(x["correlation"])) if cross_corrs else {"lag": 0, "correlation": 0}

        # Price series for chart (last 2 years, normalized to 100)
        chart_data = pair_frame.tail(504)
        if not chart_data.empty:
            fx0 = chart_data[fx].iloc[0]
            comm0 = chart_data[comm].iloc[0]
            series = []
            for idx in chart_data.index:
                series.append({
                    "date": str(idx.date()),
                    "fx": round(float(chart_data[fx].loc[idx] / fx0 * 100), 2) if fx0 != 0 else None,
                    "commodity": round(float(chart_data[comm].loc[idx] / comm0 * 100), 2) if comm0 != 0 else None,
                })
        else:
            series = []

        results.append({
            **link,
            "currentCorrelation": current_corr,
            "bestLag": best["lag"],
            "bestLagCorrelation": best["correlation"],
            "rollingCorrelation": {
                "dates": [str(d.date()) for d in roll_corr.index],
                "values": [round(float(v), 4) if not np.isnan(v) else None for v in roll_corr.values],
            },
            "series": series,
        })

    return {"links": results}


async def get_multi_country_portfolio(holdings: list[dict], period: str = "3y") -> dict:
    """Compute FX-adjusted portfolio metrics for holdings denominated in different currencies.

    Each holding: {"ticker": str, "weight": float, "currency": str (e.g. "USD", "EUR", "JPY")}
    Returns USD-normalized portfolio metrics.
    """
    if not holdings:
        return {"error": "No holdings provided"}

    # Normalize
    cleaned = []
    for h in holdings:
        ticker = str(h.get("ticker", "")).strip().upper()
        weight = float(h.get("weight", 0))
        currency = str(h.get("currency", "USD")).strip().upper()
        if ticker and weight > 0:
            cleaned.append({"ticker": ticker, "weight": weight, "currency": currency})

    if not cleaned:
        return {"error": "No valid holdings"}

    # Get price data
    tickers = tuple(dict.fromkeys(h["ticker"] for h in cleaned))
    frame = yfs.get_close_frame(tickers, period)
    if frame is None or frame.empty:
        return {"error": "No price data available", "holdings": cleaned}

    frame = frame.dropna(axis=1, how="all")

    # Get FX rates for all non-USD currencies
    currencies = set(h["currency"] for h in cleaned if h["currency"] != "USD")
    fx_data: dict[str, pd.Series] = {}
    if currencies:
        fx_frame = yfs.get_close_frame(tuple(f"{c}USD=X" for c in currencies) + tuple(f"USD{c}=X" for c in currencies), period)
        if fx_frame is not None and not fx_frame.empty:
            for ccy in currencies:
                direct = f"{ccy}USD=X"
                inverse = f"USD{ccy}=X"
                if direct in fx_frame.columns:
                    fx_data[ccy] = fx_frame[direct]
                elif inverse in fx_frame.columns:
                    fx_data[ccy] = 1.0 / fx_frame[inverse]

    # Compute USD-normalized returns for each holding
    all_rets = pd.DataFrame(index=frame.index)
    for h in cleaned:
        tk = h["ticker"]
        ccy = h["currency"]
        if tk not in frame.columns:
            continue
        px = frame[tk].dropna()
        rets = px.pct_change().dropna()

        if ccy != "USD" and ccy in fx_data:
            fx = fx_data[ccy]
            fx = fx.reindex(rets.index, method="ffill")
            # Convert to USD: multiply local return by FX return
            fx_rets = fx.pct_change().reindex(rets.index).fillna(0)
            usd_rets = rets + fx_rets  # approximation: local_ret + fx_ret
            all_rets[tk] = usd_rets
        else:
            all_rets[tk] = rets

    all_rets = all_rets.dropna(how="all")
    if all_rets.empty:
        return {"error": "Insufficient data after FX conversion", "holdings": cleaned}

    # Portfolio weighted returns
    weights = {}
    for h in cleaned:
        if h["ticker"] in all_rets.columns:
            weights[h["ticker"]] = h["weight"]
    total_w = sum(weights.values()) or 1
    weights = {k: v / total_w for k, v in weights.items()}
    cols = list(weights.keys())

    if len(cols) < 1:
        return {"error": "No valid tickers after FX conversion", "holdings": cleaned}

    w_vec = np.array([weights[c] for c in cols])
    port_rets = pd.Series(all_rets[cols].fillna(0).to_numpy() @ w_vec, index=all_rets.index)

    # Metrics
    ann_factor = np.sqrt(252)
    ann_ret = float(port_rets.mean() * 252)
    ann_vol = float(port_rets.std() * ann_factor)
    sharpe = ann_ret / ann_vol if ann_vol > 0 else 0

    # Cumulative series
    cum_ret = (1 + port_rets).cumprod()
    series = [{"date": str(d.date()), "value": round(float(v), 4)}
              for d, v in cum_ret.items()]

    # Country allocation
    country_alloc: dict[str, float] = {}
    currency_exposure: dict[str, float] = {}
    for h in cleaned:
        ccy = h["currency"]
        w = h["weight"] / total_w
        country_alloc[ccy] = country_alloc.get(ccy, 0) + w
        currency_exposure[ccy] = currency_exposure.get(ccy, 0) + w

    # Per-holding return
    holding_returns = []
    for c in cols:
        hret = all_rets[c].dropna()
        if len(hret) > 0:
            ann_hret = float(hret.mean() * 252)
            ann_hvol = float(hret.std() * ann_factor)
        else:
            ann_hret = None
            ann_hvol = None
        holding_returns.append({
            "ticker": c,
            "weight": round(weights[c] * 100, 1),
            "annReturn": round(ann_hret * 100, 2) if ann_hret is not None else None,
            "annVolatility": round(ann_hvol * 100, 2) if ann_hvol is not None else None,
        })

    return {
        "holdings": holding_returns,
        "series": series,
        "metrics": {
            "annReturn": round(ann_ret * 100, 2),
            "annVolatility": round(ann_vol * 100, 2),
            "sharpe": round(sharpe, 2),
        },
        "countryAllocation": country_alloc,
        "currencyExposure": currency_exposure,
    }

"""Funding and Liquidity service using FRED data."""
from __future__ import annotations

import pandas as pd
from datetime import datetime, timedelta

from .yfinance_service import _FRED_API_KEY
from .macro_expansion_service import _fetch_fred_series
from ..cache import cached

@cached(ttl_seconds=3600)
def get_funding_liquidity() -> dict:
    """Fetch M2SL, SOFR, and CP spread composites from FRED."""
    if not _FRED_API_KEY:
        return {"error": "FRED API key required"}

    end = datetime.now()
    start = end - timedelta(days=365*2) # 2 years of data

    # M2SL = M2 Money Stock
    m2 = _fetch_fred_series("M2SL", start, end)
    
    # SOFR = Secured Overnight Financing Rate
    sofr = _fetch_fred_series("SOFR", start, end)
    
    # CP = 3-Month Commercial Paper Minus FEDFUNDS (CPF3M - FEDFUNDS)
    # Using CPF3M (3-Month Commercial Paper Rate) and FEDFUNDS
    cpf3m = _fetch_fred_series("CPF3M", start, end)
    fedfunds = _fetch_fred_series("FEDFUNDS", start, end)

    def _to_points(series: pd.Series) -> list[dict]:
        if series is None or series.empty:
            return []
        series = series.dropna()
        return [{"date": str(idx)[:10], "value": float(v)} for idx, v in series.items()]

    # Calculate CP spread composite
    cp_spread = pd.Series(dtype=float)
    if cpf3m is not None and fedfunds is not None:
        # Reindex to match and calculate spread
        common_idx = cpf3m.index.intersection(fedfunds.index)
        cp_spread = cpf3m.loc[common_idx] - fedfunds.loc[common_idx]

    return {
        "m2": _to_points(m2),
        "sofr": _to_points(sofr),
        "cp_spread": _to_points(cp_spread),
    }

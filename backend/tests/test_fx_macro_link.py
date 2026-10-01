"""FX-commodity lead/lag detection (cross_asset_service.get_fx_macro_link)."""
import asyncio

import numpy as np
import pandas as pd

from backend.services import cross_asset_service as cas


def test_best_lag_finds_a_commodity_that_leads_fx(monkeypatch):
    rng = np.random.default_rng(7)
    n, lead = 600, 3
    comm_ret = rng.normal(0, 0.01, n)
    fx_ret = np.r_[np.zeros(lead), comm_ret[:-lead]] * 0.8 + rng.normal(0, 0.002, n)
    idx = pd.bdate_range("2022-01-03", periods=n)
    prices = {}
    for sym in ("AUDUSD=X", "USDCAD=X", "USDNOK=X", "USDBRL=X", "NZDUSD=X"):
        prices[sym] = 100 * np.cumprod(1 + fx_ret)
    for sym in ("DBA", "USO", "GLD"):
        prices[sym] = 100 * np.cumprod(1 + comm_ret)
    frame = pd.DataFrame(prices, index=idx)
    monkeypatch.setattr(cas.yfs, "get_close_frame", lambda tickers, period: frame)

    fn = getattr(cas.get_fx_macro_link, "__wrapped__", cas.get_fx_macro_link)
    out = asyncio.run(fn())
    link = next(x for x in out["links"] if x["label"] == "USD/CAD vs Oil")
    assert link["bestLag"] == lead          # positive = the commodity moves first
    assert link["bestLagCorrelation"] > 0.9

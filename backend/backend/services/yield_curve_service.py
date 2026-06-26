"""Multi-country yield curve service — Phase 18A.

Fetches US spot curve (11 tenors), real yields (TIPS), breakevens,
ACM term premium, and 8 foreign 10Y yields via FRED.
"""
from __future__ import annotations

from ..cache import async_cached
from . import macro_expansion_service as mes

_US_TENORS = [
    ("1m",  "DGS1MO",  1 / 12),
    ("3m",  "DGS3MO",  0.25),
    ("6m",  "DGS6MO",  0.5),
    ("1y",  "DGS1",    1),
    ("2y",  "DGS2",    2),
    ("3y",  "DGS3",    3),
    ("5y",  "DGS5",    5),
    ("7y",  "DGS7",    7),
    ("10y", "DGS10",   10),
    ("20y", "DGS20",   20),
    ("30y", "DGS30",   30),
]
_REAL_TENORS = [
    ("5y",  "DFII5",  5),
    ("10y", "DFII10", 10),
    ("20y", "DFII20", 20),
    ("30y", "DFII30", 30),
]
_BREAKEVEN_SERIES = {"5y": "T5YIE", "10y": "T10YIE", "30y": "T30YIE"}
_FOREIGN = {
    "Germany":   "IRLTLT01DEM156N",
    "UK":        "IRLTLT01GBM156N",
    "Japan":     "IRLTLT01JPM156N",
    "France":    "IRLTLT01FRM156N",
    "Italy":     "IRLTLT01ITM156N",
    "Canada":    "IRLTLT01CAM156N",
    "Australia": "IRLTLT01AUM156N",
    "Spain":     "IRLTLT01ESM156N",
}
_ALL_SERIES = tuple(
    [sid for _, sid, _ in _US_TENORS]
    + [sid for _, sid, _ in _REAL_TENORS]
    + list(_BREAKEVEN_SERIES.values())
    + ["ACMTP10"]
    + list(_FOREIGN.values())
)
_START = "2000-01-01"


def _latest(pts: list[dict]) -> float | None:
    """Return the most recent non-None value from a FRED series list."""
    for pt in reversed(pts):
        v = pt.get("value")
        if v is not None:
            try:
                return float(v)
            except (TypeError, ValueError):
                continue
    return None


async def _fetch_series() -> dict:
    """Thin wrapper so tests can patch a single symbol."""
    return await mes.fetch_fred_series(_ALL_SERIES, start=_START)


@async_cached("yield_curves")
async def get_yield_curves() -> dict:
    """Return structured yield curve data for US + 8 foreign markets."""
    data = await _fetch_series()

    # US spot curve
    curve_points = [
        {"tenor": label, "years": years, "yield": _latest(data.get(sid, []))}
        for label, sid, years in _US_TENORS
    ]

    dgs2  = _latest(data.get("DGS2",   []))
    dgs10 = _latest(data.get("DGS10",  []))
    dgs3m = _latest(data.get("DGS3MO", []))

    spread_2y10y  = round(dgs10 - dgs2,  4) if dgs10 is not None and dgs2  is not None else None
    spread_3m10y  = round(dgs10 - dgs3m, 4) if dgs10 is not None and dgs3m is not None else None

    # Real yields (TIPS)
    real_points = [
        {"tenor": label, "years": years, "yield": _latest(data.get(sid, []))}
        for label, sid, years in _REAL_TENORS
    ]

    # Breakevens
    breakevens = {
        tenor: _latest(data.get(sid, []))
        for tenor, sid in _BREAKEVEN_SERIES.items()
    }

    # ACM term premium
    tp_hist = [p for p in data.get("ACMTP10", []) if p.get("value") is not None]
    term_premium = {
        "current": _latest(data.get("ACMTP10", [])),
        "history": tp_hist[-120:],
    }

    # Foreign 10Y yields + spread vs US
    foreign: dict = {}
    for name, sid in _FOREIGN.items():
        val = _latest(data.get(sid, []))
        foreign[name] = {
            "yield_10y": val,
            "spread_vs_us": (
                round(val - dgs10, 4)
                if val is not None and dgs10 is not None
                else None
            ),
        }

    return {
        "us_curve": {
            "points":       curve_points,
            "spread_2y10y": spread_2y10y,
            "spread_3m10y": spread_3m10y,
            "inverted":     bool(spread_2y10y is not None and spread_2y10y < 0),
        },
        "real_yields":  real_points,
        "breakevens":   breakevens,
        "term_premium": term_premium,
        "foreign_10y":  foreign,
    }

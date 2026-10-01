"""Multi-country yield curve service — Phase 18A.

Fetches US spot curve (11 tenors), real yields (TIPS), breakevens,
ACM term premium, and 20+ foreign 10Y yields via FRED.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime

from .. import provenance as pv
from ..cache import async_cached
from . import macro_expansion_service as mes
from . import atlas_service

log = logging.getLogger(__name__)

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
# 5y5y forward breakeven — the inflation compensation priced for the five years
# starting five years out. Strips near-term energy passthrough, which is why it
# is the anchor measure the FOMC cites. Note it still embeds an inflation risk
# premium, so it is not a pure expectation.
_FWD_BREAKEVEN_SERIES = "T5YIFR"
# ISO2-keyed dict with name + FRED series per country (23 countries)
_FOREIGN: dict[str, dict[str, str]] = {
    "DE": {"name": "Germany",      "fred": "IRLTLT01DEM156N"},
    "GB": {"name": "UK",           "fred": "IRLTLT01GBM156N"},
    "JP": {"name": "Japan",        "fred": "IRLTLT01JPM156N"},
    "FR": {"name": "France",       "fred": "IRLTLT01FRM156N"},
    "IT": {"name": "Italy",        "fred": "IRLTLT01ITM156N"},
    "CA": {"name": "Canada",       "fred": "IRLTLT01CAM156N"},
    "AU": {"name": "Australia",    "fred": "IRLTLT01AUM156N"},
    "ES": {"name": "Spain",        "fred": "IRLTLT01ESM156N"},
    "KR": {"name": "South Korea",  "fred": "IRLTLT01KRM156N"},
    "CH": {"name": "Switzerland",  "fred": "IRLTLT01CHM156N"},
    "SE": {"name": "Sweden",       "fred": "IRLTLT01SEM156N"},
    "NO": {"name": "Norway",       "fred": "IRLTLT01NOM156N"},
    "NL": {"name": "Netherlands",  "fred": "IRLTLT01NLM156N"},
    "NZ": {"name": "New Zealand",  "fred": "IRLTLT01NZM156N"},
    "BE": {"name": "Belgium",      "fred": "IRLTLT01BEM156N"},
    "AT": {"name": "Austria",      "fred": "IRLTLT01ATM156N"},
    "PT": {"name": "Portugal",     "fred": "IRLTLT01PTM156N"},
    "IE": {"name": "Ireland",      "fred": "IRLTLT01IEM156N"},
    "FI": {"name": "Finland",      "fred": "IRLTLT01FIM156N"},
    "DK": {"name": "Denmark",      "fred": "IRLTLT01DKM156N"},
    "PL": {"name": "Poland",       "fred": "IRLTLT01PLM156N"},
    "MX": {"name": "Mexico",       "fred": "IRLTLT01MXM156N"},
    "ZA": {"name": "South Africa", "fred": "IRLTLT01ZAM156N"},
}

_TERM_PREMIUM_SERIES = "THREEFYTP10"

_ALL_SERIES = tuple(
    [sid for _, sid, _ in _US_TENORS]
    + [sid for _, sid, _ in _REAL_TENORS]
    + list(_BREAKEVEN_SERIES.values())
    + [_FWD_BREAKEVEN_SERIES]
    # 10y term premium: Kim-Wright (Fed Board) on FRED. "ACMTP10" is not a
    # FRED series, so the ACM premium requested here was always empty (D-18).
    + [_TERM_PREMIUM_SERIES]
    + [info["fred"] for info in _FOREIGN.values()]
)
_START = "2000-01-01"

from ..config import iso2_to_iso3 as _iso2_to_iso3


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


def _last_obs(pts: list[dict]) -> str | None:
    """Date of the most recent non-null point of a FRED series list."""
    for pt in reversed(pts or []):
        if pt.get("value") is not None:
            return str(pt["date"])[:10]
    return None


def _provenance(data: dict, cpi_map: dict) -> dict:
    """Source map for the yield-curve payload (see provenance.py)."""
    prov: dict = {
        "*": pv.ref("fred", None, "US Treasury and OECD government-bond yields", units="percent"),
    }
    us10 = "us_curve.points.10y"

    # US spot curve: Treasury constant-maturity yields, daily.
    for label, sid, _ in _US_TENORS:
        prov[f"us_curve.points.{label}"] = pv.fred(
            sid, f"US Treasury {label} constant-maturity yield", units="percent",
            frequency="daily", observed=_last_obs(data.get(sid, [])))
    prov["us_curve.spread_2y10y"] = pv.derived(
        "DGS10 - DGS2 (latest available value of each series)",
        ["us_curve.points.10y", "us_curve.points.2y"], title="10y minus 2y Treasury spread")
    prov["us_curve.spread_3m10y"] = pv.derived(
        "DGS10 - DGS3MO (latest available value of each series)",
        ["us_curve.points.10y", "us_curve.points.3m"], title="10y minus 3m Treasury spread")
    prov["us_curve.inverted"] = pv.derived(
        "true when the 2y10y spread is negative", ["us_curve.spread_2y10y"], title="Curve inverted")

    # TIPS real yields.
    for label, sid, _ in _REAL_TENORS:
        prov[f"real_yields.{label}"] = pv.fred(
            sid, f"US Treasury {label} inflation-indexed (TIPS) real yield", units="percent",
            frequency="daily", observed=_last_obs(data.get(sid, [])))

    # Breakevens; the 30y falls back to nominal minus TIPS when T30YIE is empty.
    for tenor, sid in _BREAKEVEN_SERIES.items():
        if tenor == "30y" and _last_obs(data.get(sid, [])) is None:
            prov["breakevens.30y"] = pv.derived(
                "DGS30 - DFII30 (nominal 30y minus 30y TIPS yield); used because T30YIE returned no data",
                ["us_curve.points.30y", "real_yields.30y"], title="30y breakeven inflation",
                note="T30YIE was empty, so the breakeven was computed instead of read.")
            continue
        prov[f"breakevens.{tenor}"] = pv.fred(
            sid, f"{tenor} breakeven inflation rate", units="percent", frequency="daily",
            observed=_last_obs(data.get(sid, [])))
    prov["forward_breakeven_5y5y"] = pv.fred(
        _FWD_BREAKEVEN_SERIES, "5-year, 5-year forward inflation expectation rate",
        units="percent", frequency="daily", observed=_last_obs(data.get(_FWD_BREAKEVEN_SERIES, [])),
        note="Includes an inflation risk premium, so it is not a pure expectation.")
    prov["term_premium"] = pv.fred(
        _TERM_PREMIUM_SERIES, "10-year Treasury term premium (Kim-Wright)", units="percent",
        frequency="daily", observed=_last_obs(data.get(_TERM_PREMIUM_SERIES, [])),
        note="Kim-Wright model estimated by the Federal Reserve Board, distributed on FRED.")

    # Non-US 10y yields: OECD monthly series on FRED.
    today = datetime.now()
    for iso2, info in _FOREIGN.items():
        sid = info["fred"]
        obs = _last_obs(data.get(sid, []))
        flags = ()
        if obs and (today - datetime.strptime(obs, "%Y-%m-%d")).days > 120:
            flags = ("stale",)
        yld = pv.fred(sid, f"{info['name']} 10-year government bond yield (OECD)", units="percent",
                      frequency="monthly", observed=obs, flags=flags,
                      note="OECD monthly average, so it lags the daily US yield it is compared with.")
        row = f"global_yields.{iso2}"
        prov[f"foreign_10y.{info['name']}"] = yld
        prov[f"foreign_10y.{info['name']}.spread_vs_us"] = pv.derived(
            "foreign 10y yield - DGS10", [f"foreign_10y.{info['name']}", us10],
            title=f"{info['name']} 10y spread vs US")
        prov[row] = pv.fred(sid, f"{info['name']} 10-year government bond yield (OECD)", units="percent",
                            frequency="monthly", observed=obs, flags=flags,
                            note="OECD monthly average; history holds the last 60 monthly values.")
        prov[f"{row}.inflation"] = pv.ref(
            "worldbank", atlas_service._WB_CODES["inflation"], "Inflation, consumer prices (annual %)",
            units="% per year", frequency="annual",
            note="Latest annual value within the last three calendar years; the year is not returned per country.")
        prov[f"{row}.real_yield"] = pv.derived(
            "10y nominal yield - latest annual CPI inflation (ex-post, backward-looking; "
            "not a market TIPS real yield)", [row, f"{row}.inflation"],
            title=f"{info['name']} ex-post real 10y yield")
        for other, label in (("us", "DGS10"), ("de", "German 10y yield"), ("jp", "Japanese 10y yield")):
            ref_key = us10 if other == "us" else f"global_yields.{'DE' if other == 'de' else 'JP'}"
            prov[f"{row}.spread_vs_{other}"] = pv.derived(
                f"10y yield - {label}", [row, ref_key], title=f"{info['name']} 10y spread vs {other.upper()}")
    return prov


async def _fetch_series() -> dict:
    """Thin wrapper so tests can patch a single symbol."""
    return await mes.fetch_fred_series(_ALL_SERIES, start=_START)


async def _get_cpi_map() -> dict[str, float | None]:
    """Fetch latest annual CPI inflation for all yield countries via World Bank.
    Returns {iso2: latest_inflation_pct or None}."""
    try:
        cur_year = datetime.now().year
        wb_inf = await atlas_service._wb_timeline("inflation", cur_year - 3, cur_year - 1)
    except Exception:
        log.warning("Failed to fetch WB CPI for real yields", exc_info=True)
        return {}
    cpi_map: dict[str, float | None] = {}
    for iso2 in _FOREIGN:
        iso3 = _iso2_to_iso3(iso2)
        year_map = wb_inf.get(iso3, {})
        if year_map:
            latest_yr = max(year_map)
            cpi_map[iso2] = round(float(year_map[latest_yr]), 2)
        else:
            cpi_map[iso2] = None
    return cpi_map


@async_cached("yield_curves")
async def get_yield_curves() -> dict:
    """Return structured yield curve data for US + 20+ foreign markets
    with yield spread matrix and real yields."""
    data, cpi_map = await asyncio.gather(
        _fetch_series(),
        _get_cpi_map(),
    )

    # US spot curve
    curve_points = [
        {"tenor": label, "years": years, "yield": _latest(data.get(sid, []))}
        for label, sid, years in _US_TENORS
    ]

    dgs2  = _latest(data.get("DGS2",   []))
    dgs10 = _latest(data.get("DGS10",  []))
    dgs3m = _latest(data.get("DGS3MO", []))

    spread_2y10y = round(dgs10 - dgs2, 4) if dgs10 is not None and dgs2 is not None else None
    spread_3m10y = round(dgs10 - dgs3m, 4) if dgs10 is not None and dgs3m is not None else None

    # Real yields (TIPS)
    real_points = [
        {"tenor": label, "years": years, "yield": _latest(data.get(sid, []))}
        for label, sid, years in _REAL_TENORS
    ]

    # Breakevens — with 30Y fallback from (DGS30 - DFII30)
    breakevens = {
        tenor: _latest(data.get(sid, []))
        for tenor, sid in _BREAKEVEN_SERIES.items()
    }
    # T30YIE FRED series sometimes returns empty; compute from nominal - TIPS
    if breakevens.get("30y") is None:
        dgs30 = _latest(data.get("DGS30", []))
        dfii30 = _latest(data.get("DFII30", []))
        if dgs30 is not None and dfii30 is not None:
            breakevens["30y"] = round(dgs30 - dfii30, 4)

    # 5y5y forward breakeven — kept out of the `breakevens` dict because it is a
    # forward, not a spot tenor, and would corrupt a breakeven-vs-tenor curve.
    fwd_be_hist = [p for p in data.get(_FWD_BREAKEVEN_SERIES, []) if p.get("value") is not None]
    forward_breakeven_5y5y = {
        "current": _latest(data.get(_FWD_BREAKEVEN_SERIES, [])),
        "history": fwd_be_hist[-500:],
    }

    # 10y term premium (Kim-Wright, daily)
    tp_hist = [p for p in data.get(_TERM_PREMIUM_SERIES, []) if p.get("value") is not None]
    term_premium = {
        "current": _latest(data.get(_TERM_PREMIUM_SERIES, [])),
        "history": tp_hist[-120:],
        "model": "Kim-Wright (Federal Reserve Board), FRED THREEFYTP10",
        "asOf": tp_hist[-1]["date"][:10] if tp_hist else None,
    }

    # Legacy foreign_10y (backward compat)
    foreign: dict = {}
    for iso2, info in _FOREIGN.items():
        val = _latest(data.get(info["fred"], []))
        foreign[info["name"]] = {
            "yield_10y": val,
            "spread_vs_us": (
                round(val - dgs10, 4)
                if val is not None and dgs10 is not None
                else None
            ),
        }

    # Global yields with spread matrix and real yields
    de_yield = _latest(data.get(_FOREIGN["DE"]["fred"], []))
    jp_yield = _latest(data.get(_FOREIGN["JP"]["fred"], []))

    global_yields: list[dict] = []
    for iso2, info in _FOREIGN.items():
        fred_sid = info["fred"]
        series = data.get(fred_sid, [])
        nominal = _latest(series)
        cpi = cpi_map.get(iso2)
        real = round(nominal - cpi, 2) if nominal is not None and cpi is not None else None
        spread_us = round(nominal - dgs10, 2) if nominal is not None and dgs10 is not None else None
        spread_de = round(nominal - de_yield, 2) if nominal is not None and de_yield is not None else None
        spread_jp = round(nominal - jp_yield, 2) if nominal is not None and jp_yield is not None else None
        history_vals = [p for p in series if p.get("value") is not None]
        history = [{"date": p["date"][:10], "value": round(float(p["value"]), 4)} for p in history_vals[-60:]]
        global_yields.append({
            "iso2": iso2, "name": info["name"],
            # Monthly OECD average vs the daily US yield: dated so the lag is visible.
            "yieldAsOf": history_vals[-1]["date"][:10] if history_vals else None,
            # Ex-post: nominal minus the latest *annual* CPI (backward-looking),
            # not a market (TIPS-style) real yield.
            "yield_10y": nominal, "real_yield": real, "realYieldBasis": "ex-post (nominal − latest annual CPI)",
            "inflation": cpi,
            "spread_vs_us": spread_us, "spread_vs_de": spread_de, "spread_vs_jp": spread_jp,
            "history": history,
        })

    global_yields.sort(key=lambda c: c["yield_10y"] or float("-inf"), reverse=True)

    return pv.attach({
        "us_curve": {
            "points":       curve_points,
            "spread_2y10y": spread_2y10y,
            "spread_3m10y": spread_3m10y,
            "inverted":     bool(spread_2y10y is not None and spread_2y10y < 0),
        },
        "real_yields":  real_points,
        "breakevens":   breakevens,
        "forward_breakeven_5y5y": forward_breakeven_5y5y,
        "term_premium": term_premium,
        "foreign_10y":  foreign,
        "global_yields": global_yields,
    }, _provenance(data, cpi_map))

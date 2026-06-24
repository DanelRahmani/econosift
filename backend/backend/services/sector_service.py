"""Sector performance, fundamentals, rotation, and industry drill-down — Phase 10."""
from __future__ import annotations

import logging
import math
import sqlite3
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date

import numpy as np
import yfinance as yf

from ..cache import cached
from . import yfinance_service as yfs
from . import regime_service

logger = logging.getLogger(__name__)

SECTOR_ETFS: dict[str, str] = {
    "XLK": "Technology",
    "XLF": "Financials",
    "XLV": "Health Care",
    "XLE": "Energy",
    "XLI": "Industrials",
    "XLY": "Consumer Discretionary",
    "XLP": "Consumer Staples",
    "XLB": "Materials",
    "XLRE": "Real Estate",
    "XLC": "Communication Services",
    "XLU": "Utilities",
}

PHASE_LEADERS: dict[str, list[str]] = {
    "Early": ["Consumer Discretionary", "Financials", "Real Estate", "Industrials"],
    "Mid": ["Technology", "Communication Services", "Industrials", "Materials"],
    "Late": ["Energy", "Materials", "Consumer Staples", "Health Care"],
    "Recession": ["Consumer Staples", "Health Care", "Utilities", "Financials"],
}

_QUADRANT_TO_PHASE: dict[str, str] = {
    "Goldilocks": "Mid",
    "Overheating": "Late",
    "Slowdown": "Recession",
    "Stagflation": "Late",
}


def _safe_pct(cur: float | None, ref: float | None) -> float | None:
    if cur is None or ref is None or ref == 0:
        return None
    try:
        v = (cur / ref - 1.0) * 100.0
        return round(v, 2) if math.isfinite(v) else None
    except Exception:
        return None


def _clean(v) -> float | None:
    if v is None:
        return None
    try:
        f = float(v)
        return round(f, 4) if math.isfinite(f) else None
    except Exception:
        return None


@cached("sector_returns")
def get_sector_returns() -> dict:
    all_syms = tuple(list(SECTOR_ETFS.keys()) + ["SPY"])
    frame = yfs.get_close_frame(all_syms, "1y")

    if frame is None or frame.empty:
        return {"periods": {k: [] for k in ("1d", "1w", "1m", "3m", "ytd", "1y")}}

    frame = frame.sort_index()
    today_year = frame.index[-1].year
    ytd_start = frame[frame.index >= f"{today_year}-01-01"]

    def _spy_ret(n_days: int | None, ytd: bool = False) -> float | None:
        if "SPY" not in frame.columns:
            return None
        s = frame["SPY"].dropna()
        if ytd:
            ys = ytd_start["SPY"].dropna() if "SPY" in ytd_start.columns else s.iloc[:0]
            return _safe_pct(float(s.iloc[-1]) if len(s) else None,
                             float(ys.iloc[0]) if len(ys) else None)
        if n_days is None or len(s) < 2:
            return None
        idx = max(0, len(s) - 1 - n_days)
        return _safe_pct(float(s.iloc[-1]), float(s.iloc[idx]))

    period_defs: list[tuple[str, int | None, bool]] = [
        ("1d", 1, False),
        ("1w", 5, False),
        ("1m", 21, False),
        ("3m", 63, False),
        ("ytd", None, True),
        ("1y", 252, False),
    ]

    periods: dict[str, list[dict]] = {}
    for period_key, n_days, is_ytd in period_defs:
        spy_ret = _spy_ret(n_days, ytd=is_ytd)
        rows: list[dict] = []
        for etf, sector in SECTOR_ETFS.items():
            if etf not in frame.columns:
                rows.append({"ticker": etf, "sector": sector, "changePercent": None, "vsSpy": None})
                continue
            s = frame[etf].dropna()
            if len(s) < 2:
                rows.append({"ticker": etf, "sector": sector, "changePercent": None, "vsSpy": None})
                continue
            if is_ytd:
                ys = ytd_start[etf].dropna() if etf in ytd_start.columns else s.iloc[:0]
                ret = _safe_pct(float(s.iloc[-1]), float(ys.iloc[0]) if len(ys) else None)
            else:
                idx = max(0, len(s) - 1 - n_days)
                ret = _safe_pct(float(s.iloc[-1]), float(s.iloc[idx]))
            vs_spy = round(ret - spy_ret, 2) if ret is not None and spy_ret is not None else None
            rows.append({"ticker": etf, "sector": sector, "changePercent": ret, "vsSpy": vs_spy})
        periods[period_key] = rows

    return {"periods": periods}


@cached("sector_fundamentals")
def get_sector_fundamentals() -> list[dict]:
    # Fetch close frame for vol/drawdown/return calcs
    all_syms = tuple(SECTOR_ETFS.keys())
    frame = yfs.get_close_frame(all_syms, "1y")
    frame = frame.sort_index() if frame is not None and not frame.empty else None

    def _fetch_info(etf: str) -> dict:
        info: dict = {}
        try:
            info = yf.Ticker(etf).info or {}
        except Exception:
            logger.exception("yf.Ticker(%s).info failed", etf)

        price = _clean(info.get("regularMarketPrice") or info.get("currentPrice"))
        aum = _clean(info.get("totalAssets"))
        trailing_pe = _clean(info.get("trailingPE"))
        price_to_book = _clean(info.get("priceToBook"))
        div_yield = info.get("yield")
        div_yield_pct = round(float(div_yield) * 100, 4) if div_yield is not None and math.isfinite(float(div_yield or 0)) else None
        beta = _clean(info.get("beta"))

        vol30d = None
        max_dd = None
        ret1m = ret3m = ret6m = ret1y = None

        if frame is not None and etf in frame.columns:
            s = frame[etf].dropna()
            if len(s) >= 2:
                rets = s.pct_change().dropna()
                if len(rets) >= 30:
                    vol30d = round(float(rets.tail(30).std() * np.sqrt(252) * 100), 4)
                # Max drawdown over 1Y
                roll_max = s.cummax()
                dd = (s - roll_max) / roll_max * 100
                max_dd = round(float(dd.min()), 4) if not dd.empty else None
                cur = float(s.iloc[-1])
                ret1m = _safe_pct(cur, float(s.iloc[-22]) if len(s) > 21 else None)
                ret3m = _safe_pct(cur, float(s.iloc[-63]) if len(s) > 62 else None)
                ret6m = _safe_pct(cur, float(s.iloc[-126]) if len(s) > 125 else None)
                ret1y = _safe_pct(cur, float(s.iloc[0]))

        return {
            "ticker": etf,
            "sector": SECTOR_ETFS[etf],
            "price": price,
            "aum": aum,
            "trailingPE": trailing_pe,
            "priceToBook": price_to_book,
            "dividendYield": div_yield_pct,
            "beta": beta,
            "vol30d": vol30d,
            "maxDrawdown": max_dd,
            "return1m": ret1m,
            "return3m": ret3m,
            "return6m": ret6m,
            "return1y": ret1y,
        }

    results: list[dict] = [{}] * len(SECTOR_ETFS)
    etf_list = list(SECTOR_ETFS.keys())
    with ThreadPoolExecutor(max_workers=11) as ex:
        futures = {ex.submit(_fetch_info, etf): i for i, etf in enumerate(etf_list)}
        for fut in as_completed(futures):
            idx = futures[fut]
            try:
                results[idx] = fut.result()
            except Exception:
                logger.exception("sector_fundamentals fetch failed for index %d", idx)
                results[idx] = {"ticker": etf_list[idx], "sector": SECTOR_ETFS[etf_list[idx]]}

    return results


@cached("sector_rotation")
def get_sector_rotation() -> dict:
    returns_data = get_sector_returns()
    rows_3m = returns_data["periods"].get("3m", [])

    # Sort sectors by 3M vsSpy descending for phase scoring
    ranked = sorted(
        [r for r in rows_3m if r.get("vsSpy") is not None],
        key=lambda r: r["vsSpy"],
        reverse=True,
    )
    rank_map: dict[str, int] = {r["sector"]: i + 1 for i, r in enumerate(ranked)}

    # Score each phase: lower rank = better = higher score
    n = len(SECTOR_ETFS)
    phase_scores: dict[str, float] = {}
    for phase, leaders in PHASE_LEADERS.items():
        score = 0.0
        for i, sector in enumerate(leaders):
            rank = rank_map.get(sector)
            if rank is not None:
                # Weight by expected position importance (first leader matters most)
                positional_weight = len(leaders) - i
                score += positional_weight * (n - rank + 1)
        phase_scores[phase] = score

    max_score = max(phase_scores.values()) if phase_scores else 1.0
    implied_phase = max(phase_scores, key=lambda p: phase_scores[p]) if phase_scores else "Mid"
    confidence = round((phase_scores[implied_phase] / max_score) * 100) if max_score > 0 else 0

    # Cross-validate with macro regime
    regime_quadrant: str | None = None
    regime_phase: str | None = None
    try:
        regime_data = regime_service.regime_series("US")
        current = regime_data.get("current") or {}
        regime_quadrant = current.get("quadrant")
        if regime_quadrant:
            regime_phase = _QUADRANT_TO_PHASE.get(regime_quadrant)
    except Exception:
        logger.exception("regime_service.regime_series failed in sector_rotation")

    # Fetch AUM for bubble sizing
    fund_data = get_sector_fundamentals()
    aum_map: dict[str, float | None] = {r["ticker"]: r.get("aum") for r in fund_data}

    sectors_out: list[dict] = []
    for r in rows_3m:
        sectors_out.append({
            "ticker": r["ticker"],
            "sector": r["sector"],
            "return3m": r.get("changePercent"),
            "vsSpy": r.get("vsSpy"),
            "aum": aum_map.get(r["ticker"]),
            "phaseRank": rank_map.get(r["sector"]),
        })

    return {
        "phase": implied_phase,
        "confidence": confidence,
        "regimePhase": regime_phase,
        "regimeQuadrant": regime_quadrant,
        "sectors": sectors_out,
    }


def get_sector_industry_drill(sector: str) -> list[dict]:
    from . import screener_cache as sc

    conn = sc._get_conn()
    try:
        cur = conn.execute(
            "SELECT symbol, name, industry, market_cap, change_percent "
            "FROM fundamentals "
            "WHERE sector = ? AND industry IS NOT NULL "
            "ORDER BY market_cap DESC",
            (sector,),
        )
        rows = cur.fetchall()
    except Exception:
        logger.exception("sector_industry_drill SQL failed for sector=%s", sector)
        return []

    # Group by industry, top-3 per industry by market cap
    industry_map: dict[str, list[dict]] = {}
    for symbol, name, industry, market_cap, change_percent in rows:
        group = industry_map.setdefault(industry, [])
        if len(group) < 3:
            group.append({
                "symbol": symbol,
                "name": name,
                "change1d": _clean(change_percent),
            })

    return [{"industry": ind, "stocks": stocks} for ind, stocks in industry_map.items()]

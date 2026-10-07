"""Advanced technical indicators service — Phase 12.

Computes the full technical indicator suite for a given ticker using pandas_ta.
All indicators are derived from OHLCV data fetched via yfinance.
"""
from __future__ import annotations

import logging
import math
from datetime import datetime, timedelta, timezone
from typing import Any

import numpy as np
import pandas as pd
import yfinance as yf

from .. import provenance as pv
from ..cache import cached

try:
    import pandas_ta as ta  # type: ignore
    _HAS_TA = True
except ImportError:
    _HAS_TA = False

logger = logging.getLogger(__name__)

# Period → extra lookback days to ensure accurate indicator seeding
_LOOKBACK_EXTRA = {
    "1mo": 120, "3mo": 180, "6mo": 270, "1y": 365, "2y": 365, "5y": 365,
}


# Period -> calendar window shown to the user (months, years)
_DISPLAY_OFFSET = {
    "1mo": pd.DateOffset(months=1), "3mo": pd.DateOffset(months=3), "6mo": pd.DateOffset(months=6),
    "1y": pd.DateOffset(years=1), "2y": pd.DateOffset(years=2), "5y": pd.DateOffset(years=5),
}


def _display_window(df: pd.DataFrame, period: str) -> pd.DataFrame:
    """Rows of a tz-naive, date-indexed frame inside the calendar window ending on its last bar."""
    cutoff = df.index[-1] - _DISPLAY_OFFSET.get(period, _DISPLAY_OFFSET["1y"])
    return df[df.index >= cutoff]


def _clean(v: Any) -> float | None:
    if v is None:
        return None
    try:
        f = float(v)
        return None if (math.isnan(f) or math.isinf(f)) else f
    except (TypeError, ValueError):
        return None


def _series_to_list(s: pd.Series, key: str) -> list[dict]:
    """Convert a named series with DatetimeIndex to [{date, key: value}]."""
    out = []
    for idx, val in s.items():
        v = _clean(val)
        if v is not None:
            out.append({"date": str(idx.date()), key: v})
    return out


def _pivot_classic(high: float, low: float, close: float) -> dict:
    p = (high + low + close) / 3.0
    r1 = 2 * p - low
    r2 = p + (high - low)
    s1 = 2 * p - high
    s2 = p - (high - low)
    return {
        "p": round(p, 4), "r1": round(r1, 4), "r2": round(r2, 4),
        "s1": round(s1, 4), "s2": round(s2, 4),
    }


def _displace_senkou(df: pd.DataFrame) -> None:
    """pandas-ta displaces Senkou A/B by kijun - 1 = 25 bars; the standard Ichimoku displacement is 26."""
    for name in ("ISA_9", "ISB_26"):
        col = _find_col(df, [name])
        if col:
            df[col] = df[col].shift(1)


def _forward_senkou(last_vals: dict, span: pd.DataFrame | None) -> pd.DataFrame:
    """The 26 projected Senkou A/B bars after the last bar (26-bar displacement).

    ``last_vals`` are the last bar's pandas-ta values (25-bar displacement, taken before
    ``_displace_senkou``); ``span`` is the frame pandas-ta's ``ichimoku`` returns for the future bars
    (index = the 26 business days after the last bar, row j = 25-bar displacement of source bar n-25+j,
    last row NaN). With the extra 1-bar shift: future bar 0 = ``last_vals``, future bar k = span row k-1,
    so the historical cloud (shifted in place) and this one join with no gap or overlap.
    """
    cols = ["ISA_9", "ISB_26"]
    if span is None or len(span) < 2:
        return pd.DataFrame(columns=cols)
    body = span[[c for c in cols if c in span.columns]].iloc[:-1]
    first = pd.DataFrame([{c: last_vals.get(c) for c in body.columns}], dtype=float)
    out = pd.concat([first, body.reset_index(drop=True)], ignore_index=True)
    out.index = span.index[: len(out)]
    return out


def _today() -> pd.Timestamp:
    """Reference date for deciding whether a week/month is over (patched in tests)."""
    return pd.Timestamp.now().normalize()


def _last_completed(df: pd.DataFrame, rule: str, today: pd.Timestamp) -> pd.Series | None:
    """H/L/C of the most recent finished period (``rule`` = "W-FRI" or "ME"), or None.

    The latest bucket is finished when the last bar is on or after the period's final weekday, or when
    the reference date is already past the period's end (holiday-shortened week/month). Otherwise it is
    still forming and the previous bucket is the one the pivots must use.
    """
    agg = df.resample(rule).agg({"High": "max", "Low": "min", "Close": "last"}).dropna()
    if agg.empty:
        return None
    period_end = agg.index[-1]
    last_weekday = pd.offsets.BDay().rollback(period_end)
    if df.index[-1].normalize() >= last_weekday or today.normalize() > period_end:
        return agg.iloc[-1]
    return agg.iloc[-2] if len(agg) >= 2 else None


def _now_ny() -> pd.Timestamp:
    """Current time in New York (patched in tests)."""
    return pd.Timestamp.now(tz="America/New_York")


def _last_session_complete(last_bar: pd.Timestamp, now: pd.Timestamp) -> bool:
    """True when the last bar's US session is over: bar date before today in New York, or today after 16:00.

    Limit: no trading calendar is available, so a holiday is treated like any other weekday, and a
    holiday-shortened (e.g. 13:00 close) session counts as complete only from 16:00.
    """
    if now.tzinfo is None:
        now = now.tz_localize("America/New_York")
    else:
        now = now.tz_convert("America/New_York")
    d = last_bar.normalize().tz_localize(None) if last_bar.tzinfo else last_bar.normalize()
    today = now.tz_localize(None).normalize()
    if d < today:
        return True
    return d == today and now.hour >= 16


def _pivot_points(df: pd.DataFrame, today: pd.Timestamp, now: pd.Timestamp | None = None) -> dict[str, dict]:
    """Classic pivots for the next daily / weekly / monthly period from the last completed one.

    Weekly / monthly limit: with no trading calendar, a week whose Friday is a holiday is only recognised
    as complete via ``today`` (the reference date passing the period end), so it can read one period stale
    until the following Saturday / month rollover.
    """
    pivots: dict[str, dict] = {}
    if len(df) < 1:
        return pivots

    # Daily: the last COMPLETED session (the last bar may still be forming during US market hours)
    if now is None:
        now = _now_ny()
    complete = _last_session_complete(df.index[-1], now)
    prev = df.iloc[-1] if (complete or len(df) < 2) else df.iloc[-2]
    h_d = _clean(prev.get("High"))
    l_d = _clean(prev.get("Low"))
    c_d = _clean(prev.get("Close"))
    if h_d and l_d and c_d:
        pivots["daily"] = _pivot_classic(h_d, l_d, c_d)

    for key, rule in (("weekly", "W-FRI"), ("monthly", "ME")):
        try:
            row = _last_completed(df, rule, today)
        except Exception:
            continue
        if row is None:
            continue
        h = _clean(row["High"]); l = _clean(row["Low"]); c = _clean(row["Close"])
        if h and l and c:
            pivots[key] = _pivot_classic(h, l, c)
    return pivots


def _fib_swing(df: pd.DataFrame, window: int = 126) -> dict | None:
    """Swing high / low from intraday High / Low over the last ``window`` bars, with the swing direction.

    "downswing" = the low came after the high (levels retrace up from the low); "upswing" = the high
    came after the low (levels retrace down from the high).
    """
    w = df.tail(window)
    if w.empty:
        return None
    high = _clean(w["High"].max())
    low = _clean(w["Low"].min())
    if not high or not low or high <= low:
        return None
    direction = "downswing" if w["Low"].values.argmin() > w["High"].values.argmax() else "upswing"
    return {"high": high, "low": low, "direction": direction,
            "highDate": str(w["High"].idxmax().date()), "lowDate": str(w["Low"].idxmin().date())}


def _fib_levels(swing_high: float, swing_low: float, direction: str = "upswing") -> list[dict]:
    diff = swing_high - swing_low
    ratios = [
        (0.0, "0%"), (0.236, "23.6%"), (0.382, "38.2%"),
        (0.500, "50%"), (0.618, "61.8%"), (0.786, "78.6%"), (1.0, "100%"),
    ]
    levels = []
    for ratio, label in ratios:
        price = swing_low + diff * ratio if direction == "downswing" else swing_high - diff * ratio
        levels.append({"level": ratio, "label": label, "price": round(price, 4)})
    return levels


def _quote_currency(ticker: str) -> str | None:
    """Yahoo quote currency from the cached quote helper; None when unknown (never assumed USD)."""
    from . import yfinance_service as yfs
    try:
        return (yfs.get_quote(ticker) or {}).get("currency") or None
    except Exception:
        return None


@cached("technicals")
def get_technicals(ticker: str, period: str = "1y") -> dict:
    """Fetch OHLCV and compute full technical indicator suite.

    Returns a structured dict with summary KPIs, time-series for sub-charts,
    overlay data for the price chart (Bollinger, Ichimoku, Fibonacci, Pivots).
    """
    ticker = ticker.upper().strip()

    # Fetch with extra lookback so early indicator values are accurate
    extra_days = _LOOKBACK_EXTRA.get(period, 365)
    # Map period to yfinance period string; always fetch more via start date trick
    period_map = {"1mo": 90, "3mo": 180, "6mo": 270, "1y": 500, "2y": 900, "5y": 2000}
    fetch_days = period_map.get(period, 500)
    start = (datetime.now(timezone.utc) - timedelta(days=fetch_days)).strftime("%Y-%m-%d")

    df = yf.download(ticker, start=start, progress=False, auto_adjust=True)
    if df is None or df.empty:
        return _empty_response(ticker, period)

    # Flatten MultiIndex columns if present
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    df = df[["Open", "High", "Low", "Close", "Volume"]].copy()
    df.index = pd.to_datetime(df.index)
    if df.index.tz is not None:
        # yfinance may return a tz-aware index; keep the exchange-local calendar dates, tz-naive
        df.index = df.index.tz_localize(None)
    df = df.dropna(subset=["Close"])

    if len(df) < 30:
        return _empty_response(ticker, period)

    # Trim to requested period for output (but compute on full fetch for accuracy)
    display_df = _display_window(df, period)

    close = df["Close"]
    high = df["High"]
    low = df["Low"]
    volume = df["Volume"]

    # -----------------------------------------------------------------------
    # Compute indicators via pandas_ta (or fallback manual)
    # -----------------------------------------------------------------------
    span_frame = None
    last_senkou: dict = {}
    if _HAS_TA:
        df.ta.macd(append=True)
        df.ta.bbands(length=20, std=2, ddof=0, append=True)  # population std, as TA-Lib / most charting packages
        df.ta.atr(length=14, append=True)
        df.ta.obv(append=True)
        df.ta.cmf(length=20, append=True)
        df.ta.stochrsi(length=14, rsi_length=14, k=3, d=3, append=True)
        df.ta.willr(length=14, append=True)
        # RSI
        df.ta.rsi(length=14, append=True)
        # SMA
        df.ta.sma(length=50, append=True)
        df.ta.sma(length=200, append=True)
        # Ichimoku — append=True puts ITS_9, IKS_26, ICS_26, ISA_9, ISB_26 into df
        try:
            res = df.ta.ichimoku(tenkan=9, kijun=26, senkou=52, append=True)
            if isinstance(res, tuple) and len(res) == 2:
                span_frame = res[1]  # the 26 projected Senkou bars after the last bar
            for name in ("ISA_9", "ISB_26"):
                col = _find_col(df, [name])
                if col:
                    last_senkou[name] = _clean(df[col].iloc[-1])
            _displace_senkou(df)
            # pandas-ta's Chikou is close.shift(-25); the standard displacement is 26 (close of t + 26)
            ics = _find_col(df, ["ICS_26"])
            if ics:
                df[ics] = df[ics].shift(-1)
        except Exception:
            pass
    else:
        # Minimal manual fallback (RSI only)
        _append_rsi_manual(df)

    # -----------------------------------------------------------------------
    # Summary KPIs
    # -----------------------------------------------------------------------
    sma50_col = _find_col(df, ["SMA_50"])
    sma200_col = _find_col(df, ["SMA_200"])
    rsi_col = _find_col(df, ["RSI_14"])
    macd_col = _find_col(df, ["MACD_12_26_9"])
    macds_col = _find_col(df, ["MACDs_12_26_9"])  # signal line

    last_close = _clean(close.iloc[-1]) or 0.0
    sma50_val = _clean(df[sma50_col].iloc[-1]) if sma50_col else None
    sma200_val = _clean(df[sma200_col].iloc[-1]) if sma200_col else None

    trend = "Neutral"
    if sma50_val and sma200_val:
        trend = "Bullish" if sma50_val > sma200_val else "Bearish"
    elif sma200_val:
        trend = "Bullish" if last_close > sma200_val else "Bearish"

    rsi_val = _clean(df[rsi_col].iloc[-1]) if rsi_col else None
    macd_val = _clean(df[macd_col].iloc[-1]) if macd_col else None
    macds_val = _clean(df[macds_col].iloc[-1]) if macds_col else None
    macd_signal_str = "Neutral"
    if macd_val is not None and macds_val is not None:
        macd_signal_str = "Bullish" if macd_val > macds_val else "Bearish"

    avg_vol_20 = _clean(volume.tail(20).mean())
    last_vol = _clean(volume.iloc[-1])
    vol_ratio = (last_vol / avg_vol_20) if (last_vol and avg_vol_20 and avg_vol_20 > 0) else None

    # Intraday highs/lows, the same definition as Yahoo's fiftyTwoWeekHigh/Low
    # on the Overview tab (P3-19).
    high52 = _clean(df["High"].tail(252).max())
    low52 = _clean(df["Low"].tail(252).min())
    week52pos = None
    if high52 and low52 and high52 > low52:
        week52pos = _clean((last_close - low52) / (high52 - low52) * 100.0)

    # -----------------------------------------------------------------------
    # Price series (display range only)
    # -----------------------------------------------------------------------
    prices = []
    for idx, row in display_df.iterrows():
        o = _clean(row.get("Open"))
        h = _clean(row.get("High"))
        l = _clean(row.get("Low"))
        c = _clean(row.get("Close"))
        v = _clean(row.get("Volume"))
        if c is not None:
            prices.append({"date": str(idx.date()), "open": o, "high": h, "low": l, "close": c, "volume": v})

    # -----------------------------------------------------------------------
    # Bollinger Bands
    # -----------------------------------------------------------------------
    bbu_col = _find_col(df, ["BBU_20_2.0"])
    bbm_col = _find_col(df, ["BBM_20_2.0"])
    bbl_col = _find_col(df, ["BBL_20_2.0"])
    bbb_col = _find_col(df, ["BBB_20_2.0"])  # bandwidth
    bbp_col = _find_col(df, ["BBP_20_2.0"])  # %B

    bollinger = []
    if bbu_col and bbm_col and bbl_col:
        for idx in display_df.index:
            if idx not in df.index:
                continue
            upper = _clean(df.at[idx, bbu_col])
            mid = _clean(df.at[idx, bbm_col])
            lower = _clean(df.at[idx, bbl_col])
            pctb = _clean(df.at[idx, bbp_col]) if bbp_col else None
            bw = _clean(df.at[idx, bbb_col]) if bbb_col else None
            if upper and mid and lower:
                bollinger.append({
                    "date": str(idx.date()),
                    "upper": upper, "mid": mid, "lower": lower,
                    "pctB": pctb, "bandwidth": bw,
                })

    # Bollinger squeeze: last value bandwidth < 5%
    bb_squeeze = False
    if bbb_col and not df[bbb_col].dropna().empty:
        last_bw = _clean(df[bbb_col].dropna().iloc[-1])
        bb_squeeze = bool(last_bw is not None and last_bw < 5.0)

    # -----------------------------------------------------------------------
    # Ichimoku
    # -----------------------------------------------------------------------
    # Column names depend on pandas_ta version — try common names
    tenkan_col = _find_col(df, ["ITS_9", "ISA_9"])
    kijun_col = _find_col(df, ["IKS_26", "ISB_26"])
    # Senkou spans are in the span df appended:
    senkou_a_col = _find_col(df, ["ISA_9"])
    senkou_b_col = _find_col(df, ["ISB_26"])
    chikou_col = _find_col(df, ["ICS_26"])

    # Re-check with correct pandas_ta naming:
    # ITS_9 = Tenkan-sen, IKS_26 = Kijun-sen
    # ISA_9 = Senkou Span A, ISB_26 = Senkou Span B
    # ICS_26 = Chikou Span
    tenkan_col = _find_col(df, ["ITS_9"])
    kijun_col = _find_col(df, ["IKS_26"])
    senkou_a_col = _find_col(df, ["ISA_9"])
    senkou_b_col = _find_col(df, ["ISB_26"])
    chikou_col = _find_col(df, ["ICS_26"])

    ichimoku = []
    if tenkan_col or kijun_col:
        # Include the 26 projected Senkou bars (future business days) for the forward cloud
        fwd = _forward_senkou(last_senkou, span_frame)
        ichi_idx = display_df.index.union(fwd.index)
        for idx in ichi_idx:
            entry: dict = {"date": str(idx.date())}
            for key, col in [
                ("tenkan", tenkan_col), ("kijun", kijun_col),
                ("senkouA", senkou_a_col), ("senkouB", senkou_b_col),
                ("chikou", chikou_col),
            ]:
                if col and idx in df.index:
                    entry[key] = _clean(df.at[idx, col])
                elif idx in fwd.index and key in ("senkouA", "senkouB"):
                    entry[key] = _clean(fwd.at[idx, "ISA_9" if key == "senkouA" else "ISB_26"])
                else:
                    entry[key] = None
            # Only emit rows that have at least one non-None value
            if any(v is not None for k, v in entry.items() if k != "date"):
                ichimoku.append(entry)

    # -----------------------------------------------------------------------
    # MACD
    # -----------------------------------------------------------------------
    macdh_col = _find_col(df, ["MACDh_12_26_9"])

    macd_series = []
    if macd_col and macds_col and macdh_col:
        for idx in display_df.index:
            if idx not in df.index:
                continue
            m = _clean(df.at[idx, macd_col])
            s = _clean(df.at[idx, macds_col])
            h = _clean(df.at[idx, macdh_col])
            if m is not None or s is not None:
                macd_series.append({"date": str(idx.date()), "macd": m, "signal": s, "hist": h})

    # -----------------------------------------------------------------------
    # RSI
    # -----------------------------------------------------------------------
    rsi_series = []
    if rsi_col:
        for idx in display_df.index:
            if idx not in df.index:
                continue
            v = _clean(df.at[idx, rsi_col])
            if v is not None:
                rsi_series.append({"date": str(idx.date()), "value": v})

    # -----------------------------------------------------------------------
    # Stochastic RSI
    # -----------------------------------------------------------------------
    stochrsi_k_col = _find_col(df, ["STOCHRSIk_14_14_3_3"])
    stochrsi_d_col = _find_col(df, ["STOCHRSId_14_14_3_3"])

    stoch_rsi_series = []
    if stochrsi_k_col and stochrsi_d_col:
        for idx in display_df.index:
            if idx not in df.index:
                continue
            k = _clean(df.at[idx, stochrsi_k_col])
            d = _clean(df.at[idx, stochrsi_d_col])
            if k is not None or d is not None:
                stoch_rsi_series.append({"date": str(idx.date()), "k": k, "d": d})

    # -----------------------------------------------------------------------
    # Williams %R
    # -----------------------------------------------------------------------
    willr_col = _find_col(df, ["WILLR_14"])

    willr_series = []
    if willr_col:
        for idx in display_df.index:
            if idx not in df.index:
                continue
            v = _clean(df.at[idx, willr_col])
            if v is not None:
                willr_series.append({"date": str(idx.date()), "value": v})

    # -----------------------------------------------------------------------
    # OBV
    # -----------------------------------------------------------------------
    obv_col = _find_col(df, ["OBV"])

    obv_series = []
    if obv_col:
        for idx in display_df.index:
            if idx not in df.index:
                continue
            v = _clean(df.at[idx, obv_col])
            if v is not None:
                obv_series.append({"date": str(idx.date()), "value": v})

    # -----------------------------------------------------------------------
    # CMF
    # -----------------------------------------------------------------------
    cmf_col = _find_col(df, ["CMF_20"])

    cmf_series = []
    if cmf_col:
        for idx in display_df.index:
            if idx not in df.index:
                continue
            v = _clean(df.at[idx, cmf_col])
            if v is not None:
                cmf_series.append({"date": str(idx.date()), "value": v})

    # -----------------------------------------------------------------------
    # ATR
    # -----------------------------------------------------------------------
    atr_col = _find_col(df, ["ATRr_14"])

    atr_series = []
    if atr_col:
        for idx in display_df.index:
            if idx not in df.index:
                continue
            v = _clean(df.at[idx, atr_col])
            if v is not None:
                atr_series.append({"date": str(idx.date()), "value": v})

    # -----------------------------------------------------------------------
    # Fibonacci Retracement (auto-detect swing high/low from last 6 months)
    # -----------------------------------------------------------------------
    fib_swing = _fib_swing(df)
    fib_levels = _fib_levels(fib_swing["high"], fib_swing["low"], fib_swing["direction"]) if fib_swing else []

    # -----------------------------------------------------------------------
    # Pivot Points (daily / weekly / monthly classic)
    # -----------------------------------------------------------------------
    pivot_points = _pivot_points(df, _today(), _now_ny())

    return pv.attach({
        "ticker": ticker,
        "currency": _quote_currency(ticker),
        "period": period,
        "asOf": str(df.index[-1].date()),
        "summary": {
            "trend": trend,
            "rsi": rsi_val,
            "macdSignal": macd_signal_str,
            "volumeVs20d": _clean(vol_ratio),
            "week52Position": week52pos,
            "week52High": high52,
            "week52Low": low52,
            "bbSqueeze": bb_squeeze,
        },
        "prices": prices,
        "bollinger": bollinger,
        "ichimoku": ichimoku,
        "macd": macd_series,
        "rsi": rsi_series,
        "stochRsi": stoch_rsi_series,
        "williamsR": willr_series,
        "obv": obv_series,
        "cmf": cmf_series,
        "atr": atr_series,
        "fibLevels": fib_levels,
        "fibDirection": fib_swing["direction"] if fib_swing else None,
        "fibSwing": fib_swing,
        "pivotPoints": pivot_points,
    }, _provenance(ticker, str(df.index[-1].date())))


def _provenance(ticker: str, as_of: str) -> dict:
    """One key per indicator block; every indicator is computed from the same adjusted daily bars."""
    bars = pv.yahoo(ticker, "Daily OHLCV, split- and dividend-adjusted", frequency="daily", observed=as_of,
                    note="Fetched from a start date covering the period plus warm-up history; indicators are "
                         "computed on the full fetch and displayed for the requested period.")

    def d(formula: str, title: str) -> dict:
        return pv.derived(formula, [bars], title=title, observed=as_of)

    pivot = "P = (H + L + C) / 3; R1 = 2P − L; R2 = P + (H − L); S1 = 2P − H; S2 = P − (H − L)"
    return {
        "*": bars,
        "prices": bars,
        "summary.trend": d("Bullish if the 50-day SMA is above the 200-day SMA, else Bearish; if there is no "
                           "50-day SMA, close vs the 200-day SMA; Neutral if neither", "Trend"),
        "summary.rsi": d("RSI(14) of the close, pandas_ta (Wilder smoothing)", "RSI (14)"),
        "summary.macdSignal": d("Bullish if the MACD line (EMA12 − EMA26 of the close) is above its 9-day EMA "
                                "signal line, else Bearish", "MACD signal"),
        "summary.volumeVs20d": d("last session's volume / mean volume of the last 20 sessions", "Volume vs 20-day"),
        "summary.week52Position": d("(close − 52-week low) / (52-week high − 52-week low) × 100, high and low "
                                    "taken from the intraday highs and lows of the last 252 sessions", "52-week position"),
        "summary.week52High": d("highest intraday high of the last 252 sessions", "52-week high"),
        "summary.week52Low": d("lowest intraday low of the last 252 sessions", "52-week low"),
        "summary.bbSqueeze": d("true when the latest Bollinger bandwidth (20-day, 2σ) is below 5%", "Bollinger squeeze"),
        "bollinger": d("Bollinger Bands (20, 2σ): mid = 20-day SMA of the close, upper / lower = mid ± 2 × standard "
                       "deviation; %B = (close − lower) / (upper − lower); bandwidth = (upper − lower) / mid × 100",
                       "Bollinger Bands"),
        "ichimoku": d("Ichimoku (9, 26, 52), pandas_ta: Tenkan = mid of 9-day high/low, Kijun = mid of 26-day "
                      "high/low, Senkou A = (Tenkan + Kijun)/2 and Senkou B = mid of 52-day high/low both shifted "
                      "26 days ahead, Chikou = close shifted 26 days back, "
                      "plus the 26 projected future Senkou bars", "Ichimoku Cloud"),
        "macd": d("MACD (12, 26, 9): line = EMA12 − EMA26 of the close, signal = 9-day EMA of the line, "
                  "histogram = line − signal", "MACD"),
        "rsi": d("RSI(14) of the close, pandas_ta (Wilder smoothing)", "RSI (14)"),
        "stochRsi": d("Stochastic RSI (RSI length 14, stochastic length 14, %K smoothing 3, %D smoothing 3), "
                      "pandas_ta", "Stochastic RSI"),
        "williamsR": d("Williams %R (14) = (highest high − close) / (highest high − lowest low) × −100", "Williams %R"),
        "obv": d("On-balance volume: running sum of volume, added on up-closes and subtracted on down-closes", "OBV"),
        "cmf": d("Chaikin Money Flow (20) = Σ money-flow volume / Σ volume over 20 sessions", "CMF (20)"),
        "atr": d("Average True Range (14), pandas_ta: Wilder-smoothed mean of the true range", "ATR (14)"),
        "fibLevels": d("swing high / low = highest intraday high / lowest intraday low of the last 126 sessions; "
                       "upswing (high after low): level = swing high − range × ratio; downswing (low after high): "
                       "level = swing low + range × ratio, for 0, 23.6, 38.2, 50, 61.8, 78.6 and 100%",
                       "Fibonacci retracement"),
        "pivotPoints": d(pivot, "Classic pivot points"),
        "pivotPoints.daily": d(pivot + ", from the last completed session's high / low / close", "Daily pivot points"),
        "pivotPoints.weekly": d(pivot + ", from the previous complete week (Friday close)", "Weekly pivot points"),
        "pivotPoints.monthly": d(pivot + ", from the previous complete month", "Monthly pivot points"),
    }


def _find_col(df: pd.DataFrame, candidates: list[str]) -> str | None:
    """Return the first candidate column name that exists in df, else None.

    Tries exact match first, then case-insensitive, then prefix (startswith)
    so that e.g. 'BBU_20_2.0' matches 'BBU_20_2.0_2.0'.
    """
    col_set = set(df.columns)
    for c in candidates:
        if c in col_set:
            return c
    df_cols_lower = {col.lower(): col for col in df.columns}
    for c in candidates:
        if c.lower() in df_cols_lower:
            return df_cols_lower[c.lower()]
    # prefix match — handles version-dependent suffix differences (e.g. BB bands)
    for c in candidates:
        for col in df.columns:
            if col.startswith(c):
                return col
    return None


def _append_rsi_manual(df: pd.DataFrame) -> None:
    """Minimal RSI-14 fallback when pandas_ta is unavailable."""
    close = df["Close"]
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)
    avg_gain = gain.ewm(com=13, min_periods=14).mean()
    avg_loss = loss.ewm(com=13, min_periods=14).mean()
    # Dividing by a zero average loss is intentional: pandas yields +inf, so
    # RSI resolves to its correct limit of 100 for an unbroken advance.
    # Replacing the zero with NaN instead (as this used to) blanked RSI exactly
    # when it should read most overbought. A genuinely flat series gives 0/0 ->
    # NaN, which is right, since RSI is undefined without any movement.
    rs = avg_gain / avg_loss
    df["RSI_14"] = 100.0 - (100.0 / (1.0 + rs))


def _empty_response(ticker: str, period: str) -> dict:
    return {
        "ticker": ticker, "currency": None, "period": period, "asOf": None,
        "summary": {"trend": "N/A", "rsi": None, "macdSignal": "N/A",
                    "volumeVs20d": None, "week52Position": None,
                    "week52High": None, "week52Low": None, "bbSqueeze": False},
        "prices": [], "bollinger": [], "ichimoku": [], "macd": [], "rsi": [],
        "stochRsi": [], "williamsR": [], "obv": [], "cmf": [], "atr": [],
        "fibLevels": [], "fibDirection": None, "fibSwing": None, "pivotPoints": {},
    }

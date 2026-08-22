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


def _fib_levels(swing_high: float, swing_low: float) -> list[dict]:
    diff = swing_high - swing_low
    ratios = [
        (0.0, "0%"), (0.236, "23.6%"), (0.382, "38.2%"),
        (0.500, "50%"), (0.618, "61.8%"), (0.786, "78.6%"), (1.0, "100%"),
    ]
    levels = []
    for ratio, label in ratios:
        price = swing_high - diff * ratio
        levels.append({"level": ratio, "label": label, "price": round(price, 4)})
    return levels


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
    df = df.dropna(subset=["Close"])

    if len(df) < 30:
        return _empty_response(ticker, period)

    # Trim to requested period for output (but compute on full fetch for accuracy)
    period_days = {"1mo": 30, "3mo": 90, "6mo": 180, "1y": 365, "2y": 730, "5y": 1825}
    cutoff = pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=period_days.get(period, 365))
    display_df = df[df.index >= cutoff] if len(df) > period_days.get(period, 365) else df

    close = df["Close"]
    high = df["High"]
    low = df["Low"]
    volume = df["Volume"]

    # -----------------------------------------------------------------------
    # Compute indicators via pandas_ta (or fallback manual)
    # -----------------------------------------------------------------------
    if _HAS_TA:
        df.ta.macd(append=True)
        df.ta.bbands(length=20, std=2, append=True)
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
            df.ta.ichimoku(tenkan=9, kijun=26, senkou=52, append=True)
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

    high52 = _clean(close.tail(252).max())
    low52 = _clean(close.tail(252).min())
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
        # Include 26 extra future rows for cloud projection
        ichi_idx = display_df.index.union(
            pd.date_range(display_df.index[-1] + pd.Timedelta(days=1), periods=26, freq="B")
        )
        for idx in ichi_idx:
            entry: dict = {"date": str(idx.date())}
            for key, col in [
                ("tenkan", tenkan_col), ("kijun", kijun_col),
                ("senkouA", senkou_a_col), ("senkouB", senkou_b_col),
                ("chikou", chikou_col),
            ]:
                if col and idx in df.index:
                    entry[key] = _clean(df.at[idx, col])
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
    swing_window = close.tail(126)
    swing_high = _clean(swing_window.max())
    swing_low = _clean(swing_window.min())
    fib_levels = _fib_levels(swing_high, swing_low) if (swing_high and swing_low and swing_high > swing_low) else []

    # -----------------------------------------------------------------------
    # Pivot Points (daily / weekly / monthly classic)
    # -----------------------------------------------------------------------
    pivot_points: dict[str, dict] = {}
    if len(df) >= 1:
        # Daily: use previous session
        prev = df.iloc[-2] if len(df) >= 2 else df.iloc[-1]
        h_d = _clean(prev.get("High"))
        l_d = _clean(prev.get("Low"))
        c_d = _clean(prev.get("Close"))
        if h_d and l_d and c_d:
            pivot_points["daily"] = _pivot_classic(h_d, l_d, c_d)

        # Weekly: use previous complete week
        try:
            weekly = df.resample("W-FRI").agg({"High": "max", "Low": "min", "Close": "last"})
            weekly = weekly.dropna()
            if len(weekly) >= 2:
                prev_w = weekly.iloc[-2]
                hw = _clean(prev_w["High"]); lw = _clean(prev_w["Low"]); cw = _clean(prev_w["Close"])
                if hw and lw and cw:
                    pivot_points["weekly"] = _pivot_classic(hw, lw, cw)
        except Exception:
            pass

        # Monthly: use previous complete month
        try:
            monthly = df.resample("ME").agg({"High": "max", "Low": "min", "Close": "last"})
            monthly = monthly.dropna()
            if len(monthly) >= 2:
                prev_m = monthly.iloc[-2]
                hm = _clean(prev_m["High"]); lm = _clean(prev_m["Low"]); cm = _clean(prev_m["Close"])
                if hm and lm and cm:
                    pivot_points["monthly"] = _pivot_classic(hm, lm, cm)
        except Exception:
            pass

    return {
        "ticker": ticker,
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
        "pivotPoints": pivot_points,
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
        "ticker": ticker, "period": period, "asOf": None,
        "summary": {"trend": "N/A", "rsi": None, "macdSignal": "N/A",
                    "volumeVs20d": None, "week52Position": None,
                    "week52High": None, "week52Low": None, "bbSqueeze": False},
        "prices": [], "bollinger": [], "ichimoku": [], "macd": [], "rsi": [],
        "stochRsi": [], "williamsR": [], "obv": [], "cmf": [], "atr": [],
        "fibLevels": [], "pivotPoints": {},
    }

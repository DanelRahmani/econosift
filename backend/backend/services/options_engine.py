"""Options & IV analytics engine — Phase 7.

Provides Black-Scholes pricing/Greeks, IV backsolve, CRR binomial tree,
options chain hydration, IV metrics (IV30/Rank/Percentile/PCR/MaxPain),
term structure, IV smile, OI profile, and Monte Carlo options pricing.
"""
from __future__ import annotations

import math
import sys
from datetime import date, datetime
from typing import Any

import numpy as np
import yfinance as yf
from scipy.optimize import brentq
from scipy.stats import norm


# ──────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ──────────────────────────────────────────────────────────────────────────────

def _clean(x: Any) -> Any:
    """Return None for NaN / Inf / None; otherwise return x unchanged."""
    if x is None:
        return None
    try:
        if math.isnan(x) or math.isinf(x):
            return None
    except (TypeError, ValueError):
        return None
    return x


def _risk_free_rate() -> float:
    """Annualised 3-month T-bill rate from ^IRX; fallback 0.05."""
    try:
        t = yf.Ticker("^IRX")
        rate = t.fast_info.get("lastPrice") or t.fast_info.get("last_price")
        if rate and rate > 0:
            return float(rate) / 100.0
    except Exception:
        pass
    return 0.05


def _dte(expiry_str: str) -> int:
    """Calendar days to expiry from today. Returns 0 if already expired."""
    try:
        exp = datetime.strptime(expiry_str, "%Y-%m-%d").date()
        return max((exp - date.today()).days, 0)
    except ValueError:
        return 0


def _spot(ticker: str) -> float | None:
    """Return current spot price or None."""
    try:
        fi = yf.Ticker(ticker).fast_info
        price = fi.get("lastPrice") or fi.get("last_price")
        if price and price > 0:
            return float(price)
    except Exception:
        pass
    return None


# ──────────────────────────────────────────────────────────────────────────────
# Black-Scholes pricing & Greeks
# ──────────────────────────────────────────────────────────────────────────────

def bs_price(
    S: float,
    K: float,
    T: float,
    r: float,
    sigma: float,
    opt_type: str,
) -> float | None:
    """Black-Scholes theoretical price.

    Parameters
    ----------
    S       : spot price
    K       : strike price
    T       : time to expiry in years
    r       : risk-free rate (annualised)
    sigma   : implied volatility (annualised, e.g. 0.25 for 25 %)
    opt_type: 'call' or 'put'

    Returns None on any domain error.
    """
    if T <= 0 or sigma <= 0 or S <= 0 or K <= 0:
        return None
    try:
        sqrt_T = math.sqrt(T)
        d1 = (math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * sqrt_T)
        d2 = d1 - sigma * sqrt_T
        if opt_type.lower() == "call":
            price = S * norm.cdf(d1) - K * math.exp(-r * T) * norm.cdf(d2)
        else:
            price = K * math.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)
        return _clean(price)
    except Exception:
        return None


def bs_greeks(
    S: float,
    K: float,
    T: float,
    r: float,
    sigma: float,
    opt_type: str,
) -> dict:
    """Standard Black-Scholes Greeks.

    Returns
    -------
    dict with keys: delta, gamma, theta (per calendar day), vega (per 1 % IV),
    rho. All values are float or None on domain error.
    """
    null = {"delta": None, "gamma": None, "theta": None, "vega": None, "rho": None}
    if T <= 0 or sigma <= 0 or S <= 0 or K <= 0:
        return null
    try:
        sqrt_T = math.sqrt(T)
        d1 = (math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * sqrt_T)
        d2 = d1 - sigma * sqrt_T
        pdf_d1 = norm.pdf(d1)
        disc = math.exp(-r * T)
        is_call = opt_type.lower() == "call"

        # Delta
        delta = norm.cdf(d1) if is_call else norm.cdf(d1) - 1

        # Gamma (same for call and put)
        gamma = pdf_d1 / (S * sigma * sqrt_T)

        # Theta (per calendar day; divide by 365)
        if is_call:
            theta = (
                -(S * pdf_d1 * sigma) / (2 * sqrt_T)
                - r * K * disc * norm.cdf(d2)
            ) / 365.0
        else:
            theta = (
                -(S * pdf_d1 * sigma) / (2 * sqrt_T)
                + r * K * disc * norm.cdf(-d2)
            ) / 365.0

        # Vega per 1 % change in vol (raw vega * 0.01)
        vega = S * pdf_d1 * sqrt_T * 0.01

        # Rho per 1 % change in rates
        if is_call:
            rho = K * T * disc * norm.cdf(d2) * 0.01
        else:
            rho = -K * T * disc * norm.cdf(-d2) * 0.01

        return {
            "delta": _clean(delta),
            "gamma": _clean(gamma),
            "theta": _clean(theta),
            "vega": _clean(vega),
            "rho": _clean(rho),
        }
    except Exception:
        return null


def iv_backsolve(
    market_price: float,
    S: float,
    K: float,
    T: float,
    r: float,
    opt_type: str,
) -> float | None:
    """Back-solve implied volatility via Brent's method.

    Returns annualised IV (e.g. 0.30 for 30 %) or None on failure.
    Bounds: [0.001, 20.0].
    """
    if T <= 0 or S <= 0 or K <= 0 or market_price <= 0:
        return None
    try:
        def objective(sigma: float) -> float:
            p = bs_price(S, K, T, r, sigma, opt_type)
            if p is None:
                return float("nan")
            return p - market_price

        # Ensure sign change
        lo_val = objective(0.001)
        hi_val = objective(20.0)
        if lo_val is None or hi_val is None or math.isnan(lo_val) or math.isnan(hi_val):
            return None
        if lo_val * hi_val > 0:
            return None

        iv = brentq(objective, 0.001, 20.0, xtol=1e-6, maxiter=200)
        return _clean(iv)
    except Exception:
        return None


# ──────────────────────────────────────────────────────────────────────────────
# CRR Binomial Tree (American-style)
# ──────────────────────────────────────────────────────────────────────────────

def crr_price(
    S: float,
    K: float,
    T: float,
    r: float,
    sigma: float,
    opt_type: str,
    steps: int = 100,
) -> float | None:
    """Cox-Ross-Rubinstein binomial tree for American-style options.

    Early exercise is checked at every node (intrinsic vs. continuation).
    Returns theoretical price or None on domain error.
    """
    if T <= 0 or sigma <= 0 or S <= 0 or K <= 0 or steps < 1:
        return None
    try:
        dt = T / steps
        u = math.exp(sigma * math.sqrt(dt))
        d = 1.0 / u
        disc = math.exp(-r * dt)
        p = (math.exp(r * dt) - d) / (u - d)

        if not (0 < p < 1):
            return None

        is_call = opt_type.lower() == "call"

        # Terminal stock prices and payoffs as numpy array
        j = np.arange(steps + 1, dtype=np.float64)
        ST = S * (u ** (steps - j)) * (d ** j)
        if is_call:
            values = np.maximum(ST - K, 0.0)
        else:
            values = np.maximum(K - ST, 0.0)

        # Backward induction with early exercise
        for i in range(steps - 1, -1, -1):
            values = disc * (p * values[:-1] + (1 - p) * values[1:])
            ST = S * (u ** (i - np.arange(i + 1))) * (d ** np.arange(i + 1))
            intrinsic = np.maximum(ST - K, 0.0) if is_call else np.maximum(K - ST, 0.0)
            values = np.maximum(values, intrinsic)

        return _clean(float(values[0]))
    except Exception:
        return None


# ──────────────────────────────────────────────────────────────────────────────
# Options chain
# ──────────────────────────────────────────────────────────────────────────────

def _hydrate_chain_rows(
    df,
    S: float,
    T: float,
    r: float,
    opt_type: str,
) -> list[dict]:
    """Convert a yfinance calls/puts DataFrame to a list of OptionRow dicts."""
    rows = []
    for _, row in df.iterrows():
        strike = _clean(row.get("strike"))
        if strike is None:
            continue

        bid = _clean(row.get("bid")) or 0.0
        ask = _clean(row.get("ask")) or 0.0
        last = _clean(row.get("lastPrice"))
        volume = _clean(row.get("volume"))
        oi = _clean(row.get("openInterest"))
        iv_raw = _clean(row.get("impliedVolatility"))  # decimal, e.g. 0.25
        itm = bool(row.get("inTheMoney", False))

        iv_pct = (iv_raw * 100.0) if iv_raw and iv_raw > 0 else None
        mid = (bid + ask) / 2.0 if (bid or ask) else (last or 0.0)

        # Black-Scholes delta and theoretical price using IV from chain
        delta = None
        bs_p = None
        if iv_pct and iv_pct > 0 and T > 0:
            greeks = bs_greeks(S, float(strike), T, r, iv_raw, opt_type)
            delta = greeks.get("delta")
            bs_p = bs_price(S, float(strike), T, r, iv_raw, opt_type)

        rows.append({
            "strike": float(strike),
            "bid": _clean(bid),
            "ask": _clean(ask),
            "mid": _clean(mid),
            "last": last,
            "volume": int(volume) if volume is not None else None,
            "openInterest": int(oi) if oi is not None else None,
            "iv": _clean(iv_pct),
            "delta": _clean(delta),
            "bsPrice": _clean(bs_p),
            "itm": itm,
        })

    rows.sort(key=lambda x: x["strike"])
    return rows


def get_chain(ticker: str, expiry: str) -> dict:
    """Fetch and hydrate the full options chain for a ticker / expiry.

    Returns
    -------
    {ticker, expiry, spot, calls: [OptionRow], puts: [OptionRow]}
    or {"error": "..."} on failure.
    """
    ticker = ticker.upper()
    try:
        t = yf.Ticker(ticker)
        spot = _spot(ticker)
        if spot is None:
            return {"error": f"Cannot retrieve spot price for {ticker}"}

        dte_days = _dte(expiry)
        T = max(dte_days, 1) / 365.0

        r = _risk_free_rate()
        chain = t.option_chain(expiry)
        calls_df = chain.calls
        puts_df = chain.puts

        if calls_df is None or calls_df.empty:
            return {"error": f"No chain data for {ticker} expiry {expiry}"}

        calls = _hydrate_chain_rows(calls_df, spot, T, r, "call")
        puts = _hydrate_chain_rows(puts_df, spot, T, r, "put") if puts_df is not None else []

        return {
            "ticker": ticker,
            "expiry": expiry,
            "spot": spot,
            "dte": dte_days,
            "calls": calls,
            "puts": puts,
        }
    except Exception as exc:
        print(f"[options_engine] get_chain({ticker}, {expiry}): {exc}", file=sys.stderr)
        return {"error": str(exc)}


# ──────────────────────────────────────────────────────────────────────────────
# IV Metrics (top KPIs)
# ──────────────────────────────────────────────────────────────────────────────

def _atm_iv_for_expiry(t: yf.Ticker, spot: float, expiry: str) -> float | None:
    """Return ATM implied volatility (as %, e.g. 30.0) for a given expiry."""
    try:
        chain = t.option_chain(expiry)
        calls_df = chain.calls
        if calls_df is None or calls_df.empty:
            return None
        # Find closest strike to spot
        idx = (calls_df["strike"] - spot).abs().idxmin()
        iv_raw = calls_df.loc[idx, "impliedVolatility"]
        iv_clean = _clean(iv_raw)
        if iv_clean and iv_clean > 0:
            return iv_clean * 100.0
    except Exception:
        pass
    return None


def get_iv_metrics(ticker: str) -> dict:
    """Compute top-level IV KPIs for a ticker.

    Returns
    -------
    {iv30, iv30Approximate, ivRank, ivRankApproximate, ivPercentile,
     pcOIRatio, maxPain, impliedMove, spot, expiries}
    or adds 'error' key on failure.
    """
    ticker = ticker.upper()
    result: dict = {
        "ticker": ticker,
        "iv30": None,
        "iv30Approximate": False,
        "ivRank": None,
        "ivRankApproximate": False,
        "ivPercentile": None,
        "pcOIRatio": None,
        "maxPain": None,
        "impliedMove": None,
        "spot": None,
    }

    try:
        t = yf.Ticker(ticker)
        spot = _spot(ticker)
        if spot is None:
            result["error"] = f"Cannot retrieve spot price for {ticker}"
            return result
        result["spot"] = spot

        expiries = list(t.options or [])
        if not expiries:
            result["error"] = "No options data available"
            return result

        result["expiries"] = expiries

        # Compute DTE for each expiry and ATM IV
        dte_list: list[int] = [_dte(e) for e in expiries]
        atm_ivs: list[float | None] = []
        for exp in expiries:
            iv = _atm_iv_for_expiry(t, spot, exp)
            atm_ivs.append(iv)

        # ── IV30: linear interpolation between expiries bracketing 30 DTE ──
        target_dte = 30
        below_idx = None  # largest DTE < 30
        above_idx = None  # smallest DTE > 30
        exact_idx = None

        for i, dte in enumerate(dte_list):
            if dte == target_dte:
                exact_idx = i
                break
            if dte < target_dte:
                if below_idx is None or dte > dte_list[below_idx]:
                    below_idx = i
            else:
                if above_idx is None or dte < dte_list[above_idx]:
                    above_idx = i

        iv30: float | None = None
        iv30_approx = False

        if exact_idx is not None:
            iv30 = atm_ivs[exact_idx]
        elif below_idx is not None and above_idx is not None:
            iv_a = atm_ivs[above_idx]
            iv_b = atm_ivs[below_idx]
            dte_a = dte_list[above_idx]
            dte_b = dte_list[below_idx]
            if iv_a is not None and iv_b is not None and dte_a != dte_b:
                # Linear interpolation
                weight = (target_dte - dte_b) / (dte_a - dte_b)
                iv30 = iv_b + weight * (iv_a - iv_b)
            elif iv_a is not None:
                iv30 = iv_a
                iv30_approx = True
            elif iv_b is not None:
                iv30 = iv_b
                iv30_approx = True
            else:
                iv30_approx = True
        elif above_idx is not None:
            iv30 = atm_ivs[above_idx]
            iv30_approx = True
        elif below_idx is not None:
            iv30 = atm_ivs[below_idx]
            iv30_approx = True

        result["iv30"] = _clean(iv30)
        result["iv30Approximate"] = iv30_approx

        # ── IV Rank and IV Percentile ──
        valid_ivs = [iv for iv in atm_ivs if iv is not None]
        if valid_ivs and iv30 is not None:
            iv_min = min(valid_ivs)
            iv_max = max(valid_ivs)
            if iv_max > iv_min:
                iv_rank = (iv30 - iv_min) / (iv_max - iv_min) * 100.0
                result["ivRank"] = _clean(iv_rank)
            else:
                result["ivRank"] = 50.0  # all equal

            below_count = sum(1 for iv in valid_ivs if iv < iv30)
            result["ivPercentile"] = _clean(below_count / len(valid_ivs) * 100.0)

            if len(expiries) < 4:
                result["ivRankApproximate"] = True

        # ── Put/Call OI Ratio — nearest 4 expiries ──
        total_call_oi = 0
        total_put_oi = 0
        for exp in expiries[:4]:
            try:
                ch = t.option_chain(exp)
                if ch.calls is not None and not ch.calls.empty:
                    total_call_oi += int(ch.calls["openInterest"].fillna(0).sum())
                if ch.puts is not None and not ch.puts.empty:
                    total_put_oi += int(ch.puts["openInterest"].fillna(0).sum())
            except Exception:
                continue

        if total_call_oi > 0:
            result["pcOIRatio"] = _clean(total_put_oi / total_call_oi)

        # ── Max Pain — representative expiry (nearest with DTE >= 7) ──
        rep_expiry = None
        for i, dte in enumerate(dte_list):
            if dte >= 7:
                rep_expiry = expiries[i]
                break

        if rep_expiry is not None:
            try:
                ch = t.option_chain(rep_expiry)
                calls_df = ch.calls
                puts_df = ch.puts
                if calls_df is not None and puts_df is not None and not calls_df.empty:
                    all_strikes = sorted(
                        set(calls_df["strike"].tolist()) | set(puts_df["strike"].tolist())
                    )
                    min_loss = float("inf")
                    max_pain_strike = None
                    for test_k in all_strikes:
                        # Loss to call holders: sum over call strikes < test_k
                        c_loss = 0.0
                        for _, crow in calls_df.iterrows():
                            s_i = crow.get("strike", 0) or 0
                            oi_i = crow.get("openInterest", 0) or 0
                            if test_k > s_i:
                                c_loss += (test_k - s_i) * oi_i
                        # Loss to put holders: sum over put strikes > test_k
                        p_loss = 0.0
                        for _, prow in puts_df.iterrows():
                            s_i = prow.get("strike", 0) or 0
                            oi_i = prow.get("openInterest", 0) or 0
                            if test_k < s_i:
                                p_loss += (s_i - test_k) * oi_i
                        total_loss = c_loss + p_loss
                        if total_loss < min_loss:
                            min_loss = total_loss
                            max_pain_strike = test_k
                    result["maxPain"] = _clean(max_pain_strike)
            except Exception as exc:
                print(f"[options_engine] maxPain({ticker}): {exc}", file=sys.stderr)

        # ── Implied Earnings Move — nearest expiry with DTE >= 7 ──
        if rep_expiry is not None:
            try:
                ch = t.option_chain(rep_expiry)
                calls_df = ch.calls
                puts_df = ch.puts
                if calls_df is not None and not calls_df.empty:
                    # ATM strike for straddle
                    atm_idx = (calls_df["strike"] - spot).abs().idxmin()
                    atm_strike = calls_df.loc[atm_idx, "strike"]
                    call_bid = calls_df.loc[atm_idx, "bid"] or 0.0
                    call_ask = calls_df.loc[atm_idx, "ask"] or 0.0
                    call_mid = (call_bid + call_ask) / 2.0

                    put_mid = 0.0
                    if puts_df is not None and not puts_df.empty:
                        put_matches = puts_df[puts_df["strike"] == atm_strike]
                        if not put_matches.empty:
                            pb = put_matches.iloc[0].get("bid") or 0.0
                            pa = put_matches.iloc[0].get("ask") or 0.0
                            put_mid = (pb + pa) / 2.0

                    straddle = call_mid + put_mid
                    if straddle > 0 and spot > 0:
                        result["impliedMove"] = _clean(straddle / spot * 100.0)
            except Exception as exc:
                print(f"[options_engine] impliedMove({ticker}): {exc}", file=sys.stderr)

    except Exception as exc:
        print(f"[options_engine] get_iv_metrics({ticker}): {exc}", file=sys.stderr)
        result["error"] = str(exc)

    return result


# ──────────────────────────────────────────────────────────────────────────────
# IV Term Structure
# ──────────────────────────────────────────────────────────────────────────────

def get_term_structure(ticker: str) -> list[dict]:
    """IV term structure: ATM IV and straddle cost per expiry.

    Returns
    -------
    [{expiry, dte, atmIV, straddle}] sorted by DTE ascending.
    """
    ticker = ticker.upper()
    spot = _spot(ticker)
    if spot is None:
        return []

    try:
        t = yf.Ticker(ticker)
        expiries = list(t.options or [])
    except Exception:
        return []

    results = []
    for exp in expiries:
        try:
            dte = _dte(exp)
            ch = t.option_chain(exp)
            calls_df = ch.calls
            puts_df = ch.puts

            if calls_df is None or calls_df.empty:
                continue

            atm_idx = (calls_df["strike"] - spot).abs().idxmin()
            atm_strike = calls_df.loc[atm_idx, "strike"]
            iv_raw = _clean(calls_df.loc[atm_idx, "impliedVolatility"])
            atm_iv = iv_raw * 100.0 if iv_raw and iv_raw > 0 else None

            call_bid = calls_df.loc[atm_idx, "bid"] or 0.0
            call_ask = calls_df.loc[atm_idx, "ask"] or 0.0
            call_mid = (call_bid + call_ask) / 2.0

            put_mid = 0.0
            if puts_df is not None and not puts_df.empty:
                put_matches = puts_df[puts_df["strike"] == atm_strike]
                if not put_matches.empty:
                    pb = put_matches.iloc[0].get("bid") or 0.0
                    pa = put_matches.iloc[0].get("ask") or 0.0
                    put_mid = (pb + pa) / 2.0

            straddle = call_mid + put_mid

            results.append({
                "expiry": exp,
                "dte": dte,
                "atmIV": _clean(atm_iv),
                "straddle": _clean(straddle) if straddle > 0 else None,
            })
        except Exception as exc:
            print(f"[options_engine] term_structure expiry {exp}: {exc}", file=sys.stderr)
            continue

    results.sort(key=lambda x: x["dte"])
    return results


# ──────────────────────────────────────────────────────────────────────────────
# IV Smile
# ──────────────────────────────────────────────────────────────────────────────

def get_iv_smile(ticker: str, expiry: str) -> list[dict]:
    """IV smile: call and put IV by moneyness for a given expiry.

    Returns
    -------
    [{strike, moneyness, callIV, putIV}] filtered to moneyness ∈ [0.70, 1.30],
    sorted by moneyness ascending. Rows where both IVs are zero/None are dropped.
    """
    ticker = ticker.upper()
    spot = _spot(ticker)
    if spot is None:
        return []

    try:
        t = yf.Ticker(ticker)
        ch = t.option_chain(expiry)
        calls_df = ch.calls
        puts_df = ch.puts

        if calls_df is None or calls_df.empty:
            return []

        # Build puts lookup keyed by strike
        puts_iv: dict[float, float | None] = {}
        if puts_df is not None and not puts_df.empty:
            for _, row in puts_df.iterrows():
                strike = _clean(row.get("strike"))
                iv_raw = _clean(row.get("impliedVolatility"))
                if strike is not None:
                    puts_iv[float(strike)] = iv_raw * 100.0 if iv_raw and iv_raw > 0 else None

        results = []
        for _, row in calls_df.iterrows():
            strike = _clean(row.get("strike"))
            if strike is None:
                continue
            strike = float(strike)
            moneyness = strike / spot
            if not (0.70 <= moneyness <= 1.30):
                continue

            iv_raw = _clean(row.get("impliedVolatility"))
            call_iv = iv_raw * 100.0 if iv_raw and iv_raw > 0 else None
            put_iv = puts_iv.get(strike)

            if call_iv is None and put_iv is None:
                continue

            results.append({
                "strike": strike,
                "moneyness": round(moneyness, 4),
                "callIV": _clean(call_iv),
                "putIV": _clean(put_iv),
            })

        results.sort(key=lambda x: x["moneyness"])
        return results
    except Exception as exc:
        print(f"[options_engine] get_iv_smile({ticker}, {expiry}): {exc}", file=sys.stderr)
        return []


# ──────────────────────────────────────────────────────────────────────────────
# OI Profile
# ──────────────────────────────────────────────────────────────────────────────

def get_oi_profile(ticker: str, expiry: str) -> dict:
    """Open-interest profile and max pain for a specific expiry.

    Returns
    -------
    {strikes, callOI, putOI, maxPain, spot}
    or {"error": "..."} on failure.
    """
    ticker = ticker.upper()
    spot = _spot(ticker)
    if spot is None:
        return {"error": f"Cannot retrieve spot price for {ticker}"}

    try:
        t = yf.Ticker(ticker)
        ch = t.option_chain(expiry)
        calls_df = ch.calls
        puts_df = ch.puts

        if calls_df is None or calls_df.empty:
            return {"error": f"No chain data for {ticker} expiry {expiry}"}

        all_strikes = sorted(
            set(calls_df["strike"].tolist())
            | (set(puts_df["strike"].tolist()) if puts_df is not None else set())
        )

        # Build OI maps
        call_oi_map: dict[float, int] = {}
        for _, row in calls_df.iterrows():
            s = _clean(row.get("strike"))
            oi = _clean(row.get("openInterest"))
            if s is not None:
                call_oi_map[float(s)] = int(oi) if oi is not None else 0

        put_oi_map: dict[float, int] = {}
        if puts_df is not None and not puts_df.empty:
            for _, row in puts_df.iterrows():
                s = _clean(row.get("strike"))
                oi = _clean(row.get("openInterest"))
                if s is not None:
                    put_oi_map[float(s)] = int(oi) if oi is not None else 0

        call_oi = [call_oi_map.get(s, 0) for s in all_strikes]
        put_oi = [put_oi_map.get(s, 0) for s in all_strikes]

        # Max pain
        min_loss = float("inf")
        max_pain_strike = None
        for test_k in all_strikes:
            c_loss = sum(
                max(0, test_k - s_i) * call_oi_map.get(s_i, 0)
                for s_i in all_strikes
            )
            p_loss = sum(
                max(0, s_i - test_k) * put_oi_map.get(s_i, 0)
                for s_i in all_strikes
            )
            total_loss = c_loss + p_loss
            if total_loss < min_loss:
                min_loss = total_loss
                max_pain_strike = test_k

        return {
            "ticker": ticker,
            "expiry": expiry,
            "spot": spot,
            "strikes": [float(s) for s in all_strikes],
            "callOI": call_oi,
            "putOI": put_oi,
            "maxPain": _clean(max_pain_strike),
        }
    except Exception as exc:
        print(f"[options_engine] get_oi_profile({ticker}, {expiry}): {exc}", file=sys.stderr)
        return {"error": str(exc)}


# ──────────────────────────────────────────────────────────────────────────────
# Monte Carlo Options Pricing
# ──────────────────────────────────────────────────────────────────────────────

def mc_option_price(
    S: float,
    K: float,
    T: float,
    r: float,
    sigma: float,
    opt_type: str,
    sims: int = 10_000,
) -> dict:
    """GBM Monte Carlo option pricing.

    Simulates ``sims`` paths of S_T under risk-neutral GBM, discounts payoffs,
    and returns price statistics plus a 50-bin histogram of payoff distribution.

    Returns
    -------
    {price, std, var95, var99, distribution: [{bin, count}], bsPrice}
    """
    try:
        rng = np.random.default_rng()
        Z = rng.standard_normal(sims)
        S_T = S * np.exp((r - 0.5 * sigma ** 2) * T + sigma * math.sqrt(T) * Z)

        if opt_type.lower() == "call":
            payoffs = np.maximum(S_T - K, 0.0)
        else:
            payoffs = np.maximum(K - S_T, 0.0)

        disc_payoffs = np.exp(-r * T) * payoffs

        price = float(np.mean(disc_payoffs))
        std = float(np.std(disc_payoffs))
        sorted_payoffs = np.sort(disc_payoffs)
        var95 = float(np.percentile(sorted_payoffs, 5))  # loss at 95% conf
        var99 = float(np.percentile(sorted_payoffs, 1))

        # 50-bin histogram of discounted payoffs (excluding zero payoffs for clarity)
        nonzero = disc_payoffs[disc_payoffs > 0]
        if len(nonzero) > 0:
            counts, bin_edges = np.histogram(nonzero, bins=50)
            distribution = [
                {"bin": round(float(bin_edges[i]), 4), "count": int(counts[i])}
                for i in range(len(counts))
            ]
        else:
            distribution = []

        bs_p = bs_price(S, K, T, r, sigma, opt_type)

        return {
            "price": _clean(price),
            "std": _clean(std),
            "var95": _clean(var95),
            "var99": _clean(var99),
            "distribution": distribution,
            "bsPrice": _clean(bs_p),
            "sims": sims,
        }
    except Exception as exc:
        print(f"[options_engine] mc_option_price: {exc}", file=sys.stderr)
        return {"error": str(exc)}

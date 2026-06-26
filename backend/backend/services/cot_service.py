"""CFTC Commitments of Traders (COT) data service."""
from __future__ import annotations

import asyncio
import io
import logging
import zipfile
from datetime import date
from io import StringIO

import pandas as pd
import requests

from ..cache import async_cached

log = logging.getLogger(__name__)

COT_URLS = [
    "https://www.cftc.gov/dea/newcot/deafut.txt",  # live weekly futures-only
    "https://www.cftc.gov/files/dea/history/fut_fin_xls_2026.zip",
    "https://www.cftc.gov/dcom/files/dcotnoc.zip",  # legacy format
]

COT_CONTRACTS = [
    {"name": "S&P 500 E-mini", "code": "13874+"},
    {"name": "Nasdaq-100 E-mini", "code": "209742"},
    {"name": "EUR/USD", "code": "099741"},
    {"name": "Gold", "code": "088691"},
    {"name": "Crude Oil (WTI)", "code": "067651"},
    {"name": "10Y T-Note", "code": "043602"},
]

# Column name candidates (CFTC changes names across file versions)
DATE_COLS = ["Report_Date_as_YYYY_MM_DD", "As_of_Date_In_Form_YYMMDD",
             "As_of_Date_In_Form_YYYY-MM-DD", "Date", "Report Date",
             "Report_Date", "As_of_Date"]
CODE_COLS = ["CFTC_Contract_Market_Code", "Contract_Market_Code",
             "CFTC Market Code in Initials", "Market_and_Exchange_Names",
             "Market and Exchange Name", "Market_And_Exchange_Name"]
LONG_COLS = ["NonComm_Positions_Long_All", "Noncommercial Long", "Non-Commercial Long",
             "NonComm_Long", "Noncommercial_Positions_Long", "NonComm_Pos_Long"]
SHORT_COLS = ["NonComm_Positions_Short_All", "Noncommercial Short", "Non-Commercial Short",
              "NonComm_Short", "Noncommercial_Positions_Short", "NonComm_Pos_Short"]
OI_COLS = ["Open_Interest_All", "Open Interest", "Open_Interest", "Tot_Open_Interest"]


def _pick_col(df: pd.DataFrame, candidates: list[str]) -> str | None:
    for c in candidates:
        if c in df.columns:
            return c
    # Fuzzy match: check lowercase stripped
    lower_map = {col.lower().replace(" ", "_"): col for col in df.columns}
    for c in candidates:
        key = c.lower().replace(" ", "_")
        if key in lower_map:
            return lower_map[key]
    return None


def _download_cot_sync() -> pd.DataFrame:
    """Try multiple URLs for COT data, returning the first successful parse."""
    last_err = None
    for url in COT_URLS:
        try:
            resp = requests.get(url, timeout=60)
            resp.raise_for_status()
            if url.endswith(".zip"):
                zf = zipfile.ZipFile(io.BytesIO(resp.content))
                csv_name = next(
                    (n for n in zf.namelist() if n.lower().endswith((".txt", ".csv"))),
                    None,
                )
                if csv_name is None:
                    raise ValueError(f"No CSV/TXT in ZIP: {zf.namelist()}")
                df = pd.read_csv(zf.open(csv_name), skipinitialspace=True, low_memory=False)
            else:
                # Plain text file
                df = pd.read_csv(io.StringIO(resp.text), skipinitialspace=True, low_memory=False)
            # Strip string columns
            for col in df.select_dtypes(include="object").columns:
                try:
                    df[col] = df[col].str.strip()
                except Exception:
                    pass
            if not df.empty:
                return df
        except Exception as exc:
            last_err = exc
            log.debug("COT URL %s failed: %s", url, exc)
            continue
    raise ValueError(f"All COT URLs failed. Last error: {last_err}")


def _parse_cot(df: pd.DataFrame) -> list[dict]:
    date_col = _pick_col(df, DATE_COLS)
    code_col = _pick_col(df, CODE_COLS)
    long_col = _pick_col(df, LONG_COLS)
    short_col = _pick_col(df, SHORT_COLS)
    oi_col = _pick_col(df, OI_COLS)

    if not all([date_col, code_col, long_col, short_col]):
        log.warning("COT: could not identify required columns. Columns: %s", df.columns.tolist())
        return []

    # Normalize date column
    df = df.copy()
    df["_date"] = pd.to_datetime(df[date_col], errors="coerce")
    df = df.dropna(subset=["_date"]).sort_values("_date")

    contracts_out = []
    for contract in COT_CONTRACTS:
        code = contract["code"]
        # Match: strip "+" and use contains
        code_clean = code.replace("+", "").strip()
        mask = df[code_col].astype(str).str.contains(code_clean, na=False, regex=False)
        sub = df[mask].copy()
        if sub.empty:
            contracts_out.append({
                "name": contract["name"],
                "code": code,
                "net_speculator": 0,
                "net_commercial": 0,
                "cot_index": None,
                "open_interest": 0,
                "history": [],
            })
            continue

        sub = sub.sort_values("_date")
        sub["_long"] = pd.to_numeric(sub[long_col], errors="coerce").fillna(0)
        sub["_short"] = pd.to_numeric(sub[short_col], errors="coerce").fillna(0)
        sub["_net"] = sub["_long"] - sub["_short"]

        if oi_col:
            sub["_oi"] = pd.to_numeric(sub[oi_col], errors="coerce").fillna(0)
        else:
            sub["_oi"] = 0

        # 2-year weekly history (last 104 rows)
        hist_sub = sub.tail(104)
        history = [
            {"date": str(r._date.date()), "net_spec": int(r._net)}
            for r in hist_sub.itertuples()
        ]

        # Latest values
        latest = sub.iloc[-1]
        net_spec = int(latest["_net"])
        oi = int(latest["_oi"])

        # COT Index: (current - min_52w) / (max_52w - min_52w) * 100
        last_52 = sub.tail(52)["_net"]
        mn, mx = last_52.min(), last_52.max()
        cot_index: float | None = None
        if mx != mn:
            cot_index = round(float((net_spec - mn) / (mx - mn) * 100), 2)

        contracts_out.append({
            "name": contract["name"],
            "code": code,
            "net_speculator": net_spec,
            "net_commercial": 0,  # not always split in legacy COT
            "cot_index": cot_index,
            "open_interest": oi,
            "history": history,
        })

    return contracts_out


@async_cached("cot_data")
async def get_cot_data() -> dict:
    """Download and parse CFTC COT data for 6 key futures contracts."""
    try:
        df = await asyncio.to_thread(_download_cot_sync)
        contracts = await asyncio.to_thread(_parse_cot, df)
        # Determine asOf from last date in data
        as_of = str(date.today())
        if contracts:
            latest_dates = [
                c["history"][-1]["date"]
                for c in contracts
                if c.get("history")
            ]
            if latest_dates:
                as_of = max(latest_dates)
        return {
            "asOf": as_of,
            "contracts": contracts,
            "source": "CFTC",
            "error": None,
        }
    except Exception as exc:
        log.warning("get_cot_data failed: %s", exc)
        return {
            "asOf": str(date.today()),
            "contracts": [],
            "source": "CFTC",
            "error": str(exc),
        }

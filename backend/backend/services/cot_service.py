"""CFTC Commitments of Traders (COT) data service."""
from __future__ import annotations

import asyncio
import io
import logging
import zipfile
from datetime import date

import pandas as pd
import requests

from .. import provenance as pv
from ..cache import async_cached

log = logging.getLogger(__name__)

# Primary source: CFTC's Socrata open-data API (stable JSON schema).
# Legacy futures-only report, one row per contract per week.
SOCRATA_URL = "https://publicreporting.cftc.gov/resource/6dca-aqww.json"


def _legacy_urls() -> list[str]:
    """Fallback: legacy annual futures-only archives (current + prior year,
    so early-January requests still work before the new file exists)."""
    year = date.today().year
    return [
        f"https://www.cftc.gov/files/dea/history/deacot{year}.zip",
        f"https://www.cftc.gov/files/dea/history/deacot{year - 1}.zip",
    ]


COT_CONTRACTS = [
    {"name": "S&P 500 E-mini", "code": "13874A"},
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
COMM_LONG_COLS = ["Comm_Positions_Long_All", "Commercial Long", "Comm_Long"]
COMM_SHORT_COLS = ["Comm_Positions_Short_All", "Commercial Short", "Comm_Short"]
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


def _fetch_socrata_sync() -> pd.DataFrame:
    """Fetch ~2y of weekly rows per contract from the Socrata API."""
    frames = []
    for contract in COT_CONTRACTS:
        code = contract["code"].replace("+", "").strip()
        params = {
            "$where": f"cftc_contract_market_code='{code}'",
            "$order": "report_date_as_yyyy_mm_dd DESC",
            "$limit": "300",
        }
        resp = requests.get(SOCRATA_URL, params=params, timeout=60)
        resp.raise_for_status()
        records = resp.json()
        if records:
            frames.append(pd.DataFrame.from_records(records))
    if not frames:
        raise ValueError("Socrata returned no rows for any contract")
    return pd.concat(frames, ignore_index=True)


def _fetch_zip_sync(url: str) -> pd.DataFrame:
    """Fetch and read a legacy annual archive (zip containing one txt/csv)."""
    resp = requests.get(url, timeout=60)
    resp.raise_for_status()
    zf = zipfile.ZipFile(io.BytesIO(resp.content))
    csv_name = next(
        (n for n in zf.namelist() if n.lower().endswith((".txt", ".csv"))),
        None,
    )
    if csv_name is None:
        raise ValueError(f"No CSV/TXT in ZIP: {zf.namelist()}")
    df = pd.read_csv(zf.open(csv_name), skipinitialspace=True, low_memory=False)
    for col in df.columns:
        # is_string_dtype covers object (pandas 2.x) and str (pandas 3+) dtypes
        if not pd.api.types.is_string_dtype(df[col]):
            continue
        try:
            df[col] = df[col].str.strip()
        except Exception:
            pass
    return df


def _download_and_parse_sync() -> list[dict]:
    """Source waterfall. A source only counts as successful if it parses into
    at least one contract with history — an HTTP 200 with unusable columns
    (e.g. a headerless file) must fall through to the next source."""
    errors: list[str] = []
    sources = [("Socrata API", _fetch_socrata_sync)]
    for url in _legacy_urls():
        sources.append((url, lambda u=url: _fetch_zip_sync(u)))

    for label, fetch in sources:
        try:
            contracts = _parse_cot(fetch())
            if any(c["history"] for c in contracts):
                return contracts
            errors.append(f"{label}: parsed no contracts")
        except Exception as exc:
            errors.append(f"{label}: {exc}")
            log.debug("COT source %s failed: %s", label, exc)
    raise ValueError("All COT sources failed: " + " | ".join(errors))


def _parse_cot(df: pd.DataFrame) -> list[dict]:
    date_col = _pick_col(df, DATE_COLS)
    code_col = _pick_col(df, CODE_COLS)
    long_col = _pick_col(df, LONG_COLS)
    short_col = _pick_col(df, SHORT_COLS)
    oi_col = _pick_col(df, OI_COLS)
    comm_long_col = _pick_col(df, COMM_LONG_COLS)
    comm_short_col = _pick_col(df, COMM_SHORT_COLS)

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
            # Not in the report: unknown, not zero.
            contracts_out.append({
                "name": contract["name"],
                "code": code,
                "net_speculator": None,
                "net_commercial": None,
                "cot_index": None,
                "open_interest": None,
                "history": [],
            })
            continue

        # A prefix can match several sub-codes (e.g. 13874A / 13874+); keep
        # the variant with the most rows so the series isn't interleaved.
        if sub[code_col].nunique() > 1:
            top_code = sub[code_col].astype(str).value_counts().idxmax()
            sub = sub[sub[code_col].astype(str) == top_code]

        sub = sub.sort_values("_date")
        # A report with a missing leg is dropped rather than read as 0 contracts.
        sub["_long"] = pd.to_numeric(sub[long_col], errors="coerce")
        sub["_short"] = pd.to_numeric(sub[short_col], errors="coerce")
        sub = sub.dropna(subset=["_long", "_short"])
        if sub.empty:
            contracts_out.append({"name": contract["name"], "code": code, "net_speculator": None,
                                  "net_commercial": None, "cot_index": None, "open_interest": None,
                                  "history": []})
            continue
        sub["_net"] = sub["_long"] - sub["_short"]
        sub["_oi"] = pd.to_numeric(sub[oi_col], errors="coerce") if oi_col else float("nan")
        if comm_long_col and comm_short_col:
            sub["_comm"] = (pd.to_numeric(sub[comm_long_col], errors="coerce")
                            - pd.to_numeric(sub[comm_short_col], errors="coerce"))
        else:
            sub["_comm"] = float("nan")

        # 2-year weekly history (last 104 rows). NB: itertuples() renames
        # underscore-prefixed columns, so iterate the Series directly.
        hist_sub = sub.tail(104)
        history = [
            {"date": str(d.date()), "net_spec": int(n)}
            for d, n in zip(hist_sub["_date"], hist_sub["_net"])
        ]

        # Latest values
        latest = sub.iloc[-1]
        net_spec = int(latest["_net"])
        oi = int(latest["_oi"]) if pd.notna(latest["_oi"]) else None
        net_comm = int(latest["_comm"]) if pd.notna(latest["_comm"]) else None

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
            "net_commercial": net_comm,
            "cot_index": cot_index,
            "open_interest": oi,
            "history": history,
        })

    return contracts_out


def _cot_failed(result) -> bool:
    """skip_if predicate: never cache a failure envelope — it is a non-empty
    dict, so the default empty-container check would let it poison the cache."""
    return (not isinstance(result, dict)
            or bool(result.get("error"))
            or not result.get("contracts"))


def _provenance(as_of: str) -> dict:
    """Row fields are keyed ``contracts.<field>`` (one source for every contract)."""
    src = pv.ref("cftc", None, "Commitments of Traders, legacy report, futures only", frequency="weekly",
                 observed=as_of, note="Socrata open-data API (publicreporting.cftc.gov, dataset 6dca-aqww), "
                                      "falling back to the annual deacotYYYY.zip archives; as_of is the newest "
                                      "report date across contracts.")
    net = pv.derived("non-commercial long - non-commercial short futures contracts, at the latest report date",
                     [src], title="Net speculator position (contracts)", observed=as_of)
    return {
        "*": src,
        "contracts.net_speculator": net,
        "contracts.history": net,
        "contracts.cot_index": pv.derived(
            "(latest net position - lowest of the last 52 weekly reports) / (highest - lowest) x 100; empty "
            "when the 52-week range is flat", ["contracts.net_speculator"], title="COT index (52-week)",
            observed=as_of),
        "contracts.open_interest": pv.derived("total open interest (all), latest report date", [src],
                                              title="Open interest (contracts)", observed=as_of),
        "contracts.net_commercial": pv.derived(
            "commercial long - commercial short futures contracts, at the latest report date; empty when "
            "the report carries no commercial columns", [src], title="Net commercial position (contracts)",
            observed=as_of),
    }


@async_cached("cot_data", skip_if=_cot_failed)
async def get_cot_data() -> dict:
    """Download and parse CFTC COT data for 6 key futures contracts."""
    try:
        contracts = await asyncio.to_thread(_download_and_parse_sync)
        # Determine asOf from last date in data
        as_of = str(date.today())
        latest_dates = [
            c["history"][-1]["date"]
            for c in contracts
            if c.get("history")
        ]
        if latest_dates:
            as_of = max(latest_dates)
        return pv.attach({
            "asOf": as_of,
            "contracts": contracts,
            "source": "CFTC",
            "error": None,
        }, _provenance(as_of))
    except Exception as exc:
        log.warning("get_cot_data failed: %s", exc)
        return {
            "asOf": str(date.today()),
            "contracts": [],
            "source": "CFTC",
            "error": str(exc),
        }

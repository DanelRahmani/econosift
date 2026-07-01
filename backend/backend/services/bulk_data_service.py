"""Bulk data downloader: World Bank, Fama-French, IMF WEO.

Downloads large historical datasets in bulk instead of making hundreds of
individual API calls.  Data is stored as Parquet files under data/bulk/
for fast local reads.  Falls back to existing per-request API calls on failure.

Run weekly or manually from the admin panel.
"""
from __future__ import annotations

import io
import json
import logging
import pathlib
import threading
import zipfile
from datetime import datetime, timezone

import httpx
import pandas as pd

from ..config import DATA_DIR as _APP_DATA_DIR

logger = logging.getLogger(__name__)

# Docker mounts persistent data at /app/data (docker-compose.yml); use it when
# present. Otherwise (local dev, desktop app) fall back to the app's own data
# dir instead of a path relative to this file — under the frozen desktop exe
# that would resolve inside the read-only bundled resources, not a writable
# location, which is why bulk downloads silently failed there.
DATA_DIR = pathlib.Path("/app/data/bulk") if pathlib.Path("/app/data").exists() else (_APP_DATA_DIR / "bulk")
DATA_DIR.mkdir(parents=True, exist_ok=True)

_STATUS_PATH = DATA_DIR / "_status.json"

# ---------------------------------------------------------------------------
# Status tracking
# ---------------------------------------------------------------------------

def _load_status() -> dict:
    if _STATUS_PATH.exists():
        try:
            return json.loads(_STATUS_PATH.read_text())
        except Exception:
            pass
    return {}


def _save_status(status: dict) -> None:
    _STATUS_PATH.write_text(json.dumps(status, default=str, indent=2))


# Guards refresh_all_bulk_data() against concurrent runs (e.g. a second click
# before the first finishes), which previously caused interleaved writes to
# _status.json with the second run's last-write silently clobbering progress
# from the first.
_run_lock = threading.Lock()
_running = False


def is_bulk_running() -> bool:
    return _running


def get_bulk_status() -> dict:
    s = _load_status()
    result = {}
    for key in ("worldbank", "famafrench", "imf_weo", "bis", "factbook", "reinhart_rogoff", "factbook_profiles"):
        entry = s.get(key, {})
        result[key] = {
            "last_ok": entry.get("last_ok"),
            "last_attempt": entry.get("last_attempt"),
            "error": entry.get("error"),
            "rows": entry.get("rows"),
            "size_kb": entry.get("size_kb"),
        }
    return result


# ---------------------------------------------------------------------------
# World Bank - wbgapi bulk fetch per indicator
# ---------------------------------------------------------------------------

WB_INDICATORS = {
    "NY.GDP.MKTP.KD.ZG": "gdp_growth",
    "FP.CPI.TOTL.ZG":    "inflation",
    "SL.UEM.TOTL.ZS":    "unemployment",
    "GC.DOD.TOTL.GD.ZS": "debt_gdp",
    "BN.CAB.XOKA.GD.ZS": "current_account",
    "NY.GDP.PCAP.KD":    "gdp_per_capita",
}


def _download_worldbank() -> dict:
    total_rows = 0
    errors = []
    import wbgapi as wb

    for series_id, label in WB_INDICATORS.items():
        try:
            df = wb.data.DataFrame(
                series_id, economy="all", time=range(1960, 2030),
                labels=False, skipBlanks=True,
            )
            if df is None or df.empty:
                errors.append(f"{label}: no data from wbgapi")
                continue

            rows = []
            for economy, row_data in df.iterrows():
                for col, val in row_data.items():
                    year_str = str(col).replace("YR", "")
                    try:
                        year = int(year_str)
                        v = float(val)
                        if pd.notna(v):
                            rows.append({"iso3": str(economy), "year": year, "value": v})
                    except (ValueError, TypeError):
                        continue

            if not rows:
                errors.append(f"{label}: no parseable rows")
                continue

            result = pd.DataFrame(rows)
            path = DATA_DIR / f"wb_{label}.parquet"
            result.to_parquet(path, index=False)
            total_rows += len(result)
            logger.info("World Bank %s: %d rows -> %s", label, len(result), path)
        except Exception as exc:
            errors.append(f"{label}: {exc}")
            logger.warning("World Bank %s download failed: %s", label, exc)

    return {"rows": total_rows, "error": "; ".join(errors) if errors else None}


def load_worldbank(indicator_key: str, iso3_list: list[str],
                   start: int, end: int) -> pd.DataFrame | None:
    from ..sources.source_worldbank import INDICATOR_MAP as WB_MAP
    wb_code = WB_MAP.get(indicator_key)
    if not wb_code:
        return None
    label = WB_INDICATORS.get(wb_code)
    if not label:
        return None
    path = DATA_DIR / f"wb_{label}.parquet"
    if not path.exists():
        return None
    try:
        df = pd.read_parquet(path)
        mask = df["iso3"].isin(iso3_list) & (df["year"] >= start) & (df["year"] <= end)
        return df[mask]
    except Exception as exc:
        logger.warning("load_worldbank failed for %s: %s", indicator_key, exc)
        return None


# ---------------------------------------------------------------------------
# Fama-French - ZIP from Ken French's website
# ---------------------------------------------------------------------------

FF_URL = ("https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/"
          "ftp/F-F_Research_Data_Factors_CSV.zip")
FF_PATH = DATA_DIR / "ff_factors.parquet"


def _download_famafrench(client: httpx.Client | None = None) -> dict:
    try:
        cl = client or httpx.Client(timeout=60)
        resp = cl.get(FF_URL)
        resp.raise_for_status()

        with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
            csv_name = next(
                (n for n in zf.namelist() if "CSV" in n.upper() and "Factor" in n),
                zf.namelist()[0],
            )
            raw = zf.read(csv_name).decode("utf-8", errors="replace")

        lines = raw.splitlines()
        data_start = 0
        for i, line in enumerate(lines):
            if line.strip() == "" and i > 3:
                data_start = i + 1
                break

        rows = []
        for line in lines[data_start:]:
            parts = line.split(",")
            if len(parts) < 5:
                continue
            try:
                year_mon = int(parts[0].strip())
                year = year_mon // 100
                month = year_mon % 100
                if not (1 <= month <= 12):
                    continue
                rows.append({
                    "date": f"{year:04d}-{month:02d}-01",
                    "year": year, "month": month,
                    "mkt_rf": float(parts[1]) / 100 if parts[1].strip() else None,
                    "smb": float(parts[2]) / 100 if parts[2].strip() else None,
                    "hml": float(parts[3]) / 100 if parts[3].strip() else None,
                    "rf": float(parts[4]) / 100 if parts[4].strip() else None,
                })
            except (ValueError, IndexError):
                continue

        if not rows:
            raise Exception("no data rows parsed from FF CSV")

        df = pd.DataFrame(rows)
        df.to_parquet(FF_PATH, index=False)
        return {"rows": len(df), "error": None}
    except Exception as exc:
        logger.warning("Fama-French download failed: %s", exc)
        return {"rows": 0, "error": str(exc)}


def load_famafrench(start_year: int = 2000) -> pd.DataFrame | None:
    if not FF_PATH.exists():
        return None
    try:
        df = pd.read_parquet(FF_PATH)
        return df[df["year"] >= start_year]
    except Exception as exc:
        logger.warning("load_famafrench failed: %s", exc)
        return None


# ---------------------------------------------------------------------------
# IMF WEO - bulk via DataMapper API
# ---------------------------------------------------------------------------

IMF_URL = "https://www.imf.org/external/datamapper/api/v1"
IMF_PATH = DATA_DIR / "imf_weo.parquet"

IMF_INDICATORS = {
    "NGDP_RPCH":   "gdp_growth",
    "PCPIPCH":     "inflation",
    "LUR":         "unemployment",
    "GGXWDG_NGDP": "debt_gdp",
    "BCA_NGDPD":   "current_account",
    "NGDPDPC":     "gdp_per_capita",
}


def _download_imf() -> dict:
    """Download IMF WEO indicators one at a time (multi-indicator API returns empty)."""
    total_rows = 0
    errors = []

    for imf_code, label in IMF_INDICATORS.items():
        try:
            data_resp = httpx.get(
                f"{IMF_URL}/indicators/{imf_code}", timeout=60,
            )
            data_resp.raise_for_status()
            raw = data_resp.json()
            values = raw.get("values", {})
            indicator_data = values.get(imf_code, {})
            if not indicator_data:
                errors.append(f"{label}: no data")
                continue

            rows = []
            for iso3, years in indicator_data.items():
                if not iso3 or not isinstance(years, dict):
                    continue
                for year_str, val in years.items():
                    try:
                        year = int(year_str)
                        if year < 1980 or year > 2030:
                            continue
                        rows.append({
                            "iso3": iso3,
                            "indicator": label,
                            "year": year,
                            "value": float(val) if val is not None else None,
                        })
                    except (ValueError, TypeError):
                        continue

            if not rows:
                errors.append(f"{label}: no parseable rows")
                continue

            df = pd.DataFrame(rows)
            df = df.dropna(subset=["value"])
            # Store per-indicator for faster loading
            path = DATA_DIR / f"imf_{label}.parquet"
            df.to_parquet(path, index=False)
            total_rows += len(df)
            logger.info("IMF %s: %d rows -> %s", label, len(df), path)
        except Exception as exc:
            errors.append(f"{label}: {exc}")
            logger.warning("IMF %s download failed: %s", label, exc)

    return {"rows": total_rows, "error": "; ".join(errors) if errors else None}


def load_imf(indicator_key: str, iso2_list: list[str],
             start: int, end: int) -> pd.DataFrame | None:
    from ..sources.source_imf import INDICATOR_MAP as IMAP
    from ..config import iso2_to_iso3

    imf_code = IMAP.get(indicator_key)
    if not imf_code:
        return None
    label = IMF_INDICATORS.get(imf_code)
    if not label:
        return None

    path = DATA_DIR / f"imf_{label}.parquet"
    if not path.exists():
        return None

    iso3_set = {iso2_to_iso3(c) for c in iso2_list}
    try:
        df = pd.read_parquet(path)
        mask = df["iso3"].isin(iso3_set) & (df["year"] >= start) & (df["year"] <= end)
        return df[mask]
    except Exception as exc:
        logger.warning("load_imf failed for %s: %s", indicator_key, exc)
        return None


# ---------------------------------------------------------------------------
# BIS — Bulk CSV ZIP downloads (CPI, policy rates, exchange rates)
# ---------------------------------------------------------------------------

# Currencies where standard quote is USD per unit → BIS value must be inverted
# BIS uses ISO 3166-1 alpha-2 country codes: XM = Euro area, GB = UK, AU = Australia, NZ = New Zealand
BIS_INVERT_CURRENCIES = {"XM", "GB", "AU", "NZ"}

BIS_DATASETS = {
    "bis_cpi": {
        "zip_key": "cpi",
        "measure_filter": ("MEASURE", "771:"),   # YoY % change
        "freq": "A",
        "iso2_filter": None,  # all countries
        "label": "BIS CPI (YoY %)",
    },
    "bis_policy": {
        "zip_key": "policy",
        "measure_filter": None,
        "freq": "M",
        "iso2_filter": None,
        "label": "BIS Policy Rates",
    },
    "bis_fx": {
        "zip_key": "fx",
        "measure_filter": ("COLLECTION", "E:"),  # End of period
        "freq": "A",
        "iso2_filter": None,
        "label": "BIS Exchange Rates",
    },
    "bis_crossborder": {
        "zip_key": "crossborder",
        "measure_filter": None,
        "freq": "Q",
        "iso2_filter": None,
        "label": "BIS Cross-Border Claims (LBS)",
    },
    "bis_credit_gap": {
        "zip_key": "credit_gap",
        "measure_filter": ("CG_DTYPE", "C:"),  # C = credit-to-GDP gap (actual minus trend)
        "freq": "Q",
        "iso2_filter": None,
        "label": "BIS Credit-to-GDP Gaps",
    },
}


def _download_bis_dataset(ds: dict) -> dict:
    """Download and parse a single BIS dataset, store as parquet."""
    import io as _io, zipfile as _zipfile

    url_map = {
        "cpi":          "https://data.bis.org/static/bulk/WS_LONG_CPI_csv_flat.zip",
        "policy":       "https://data.bis.org/static/bulk/WS_CBPOL_csv_flat.zip",
        "fx":           "https://data.bis.org/static/bulk/WS_XRU_csv_flat.zip",
        "crossborder":  "https://data.bis.org/static/bulk/WS_LBS_csv_flat.zip",
        "credit_gap":   "https://data.bis.org/static/bulk/WS_CREDIT_GAP_csv_flat.zip",
    }
    url = url_map.get(ds["zip_key"])
    if not url:
        return {"rows": 0, "error": "unknown dataset"}

    try:
        resp = httpx.get(url, timeout=90)
        resp.raise_for_status()
        with _zipfile.ZipFile(_io.BytesIO(resp.content)) as zf:
            csv_name = [n for n in zf.namelist() if n.endswith(".csv")][0]
            df = pd.read_csv(zf.open(csv_name), low_memory=False)

        # Filter by measure if specified
        if ds["measure_filter"]:
            col_name, prefix = ds["measure_filter"]
            col = next(c for c in df.columns if col_name in c)
            df = df[df[col].str.startswith(prefix, na=False)]

        # Parse columns
        col_area = next(c for c in df.columns if "REF_AREA" in c)
        col_time = next(c for c in df.columns if "TIME_PERIOD" in c)
        col_val  = next(c for c in df.columns if "OBS_VALUE" in c)
        col_freq = next((c for c in df.columns if "FREQ" in c), None)

        # Extract ISO2
        df = df.copy()
        df["iso2"] = df[col_area].str.extract(r"^([A-Z]{2}):")

        # Frequency filter
        freq = ds["freq"]
        if col_freq and freq:
            freq_map = {"A": "A:", "Q": "Q:", "M": "M:"}
            df = df[df[col_freq].str.startswith(freq_map[freq], na=False)]

        # Parse value
        df["value"] = pd.to_numeric(df[col_val], errors="coerce")
        df = df[df["value"].notna()]

        # Parse time
        time_val = df[col_time]
        if freq == "A":
            df["year"] = pd.to_numeric(time_val, errors="coerce")
            df = df[df["year"].notna()]
            df["year"] = df["year"].astype(int)
        elif freq == "M":
            df["date"] = time_val  # Keep as YYYY-MM
        elif freq == "Q":
            df["date"] = time_val  # Keep as YYYY-QQ

        # Exchange rate conversion: BIS reports ALL as "foreign per USD"
        if ds["zip_key"] == "fx":
            for ccy in BIS_INVERT_CURRENCIES:
                mask = (df["iso2"] == ccy) & (df["value"] > 0)
                df.loc[mask, "value"] = 1.0 / df.loc[mask, "value"]

        # Select output columns
        out_cols = ["iso2", "year" if freq == "A" else "date", "value"]
        result = df[[c for c in out_cols if c in df.columns]].dropna()

        path = DATA_DIR / f"{ds['zip_key']}.parquet"
        result.to_parquet(path, index=False)
        return {"rows": len(result), "error": None}
    except Exception as exc:
        logger.warning("BIS %s download failed: %s", ds["zip_key"], exc)
        return {"rows": 0, "error": str(exc)}


# ---------------------------------------------------------------------------
# OpenFactbook — CIA World Factbook country profiles
# ---------------------------------------------------------------------------

FACTBOOK_URL = "https://raw.githubusercontent.com/mledoze/countries/master/dist/countries.json"
FACTBOOK_PATH = DATA_DIR / "factbook.json"


def _download_factbook() -> dict:
    """Download countries JSON (REST Countries format), validate, and store locally."""
    try:
        resp = httpx.get(FACTBOOK_URL, timeout=120)
        resp.raise_for_status()
        data = resp.json()
        count = len(data) if isinstance(data, list) else 0
        if count == 0:
            return {"rows": 0, "error": "empty or invalid JSON structure"}
        FACTBOOK_PATH.write_text(resp.text, encoding="utf-8")
        return {"rows": count, "error": None}
    except Exception as exc:
        logger.warning("Factbook download failed: %s", exc)
        return {"rows": 0, "error": str(exc)}


# ---------------------------------------------------------------------------
# Reinhart & Rogoff — Historical Sovereign Default Dataset
# ---------------------------------------------------------------------------

RR_URL = "https://raw.githubusercontent.com/danielmarcelin/reinhart-rogoff-data/main/RR_Defaults.csv"
RR_PATH = DATA_DIR / "rr_defaults.parquet"


def _download_reinhart_rogoff() -> dict:
    """Download Reinhart & Rogoff sovereign default CSV and store as parquet."""
    try:
        resp = httpx.get(RR_URL, timeout=60)
        resp.raise_for_status()
        df = pd.read_csv(io.StringIO(resp.text))
        if df.empty:
            return {"rows": 0, "error": "empty CSV"}
        df.to_parquet(RR_PATH, index=False)
        return {"rows": len(df), "error": None}
    except Exception as exc:
        logger.warning("Reinhart-Rogoff download failed: %s", exc)
        return {"rows": 0, "error": str(exc)}


# ---------------------------------------------------------------------------
# CIA World Factbook country profiles (factbook/factbook.json)
# ---------------------------------------------------------------------------

FACTBOOK_ZIP_URL = "https://github.com/factbook/factbook.json/archive/refs/heads/master.zip"
FACTBOOK_DIR = DATA_DIR / "factbook"


def _download_factbook_profiles() -> dict:
    """Download and extract CIA World Factbook country profiles from GitHub ZIP.

    Extracts ~260 country JSON files from regional folders into data/bulk/factbook/.
    """
    try:
        resp = httpx.get(FACTBOOK_ZIP_URL, timeout=180, follow_redirects=True)
        resp.raise_for_status()

        import zipfile as _zf, tempfile as _tf, shutil as _sh

        FACTBOOK_DIR.mkdir(parents=True, exist_ok=True)

        with _tf.TemporaryDirectory() as tmp:
            zip_path = pathlib.Path(tmp) / "factbook.zip"
            zip_path.write_bytes(resp.content)
            with _zf.ZipFile(zip_path) as zf:
                # Files are at factbook.json-master/{region}/{code}.json
                # Extract all .json files, flatten into factbook/ directory
                json_count = 0
                for name in zf.namelist():
                    if not name.endswith(".json"):
                        continue
                    # name format: factbook.json-master/europe/gm.json
                    parts = name.split("/")
                    if len(parts) >= 3:
                        region = parts[1]  # e.g., "europe"
                        filename = parts[-1]  # e.g., "gm.json"
                        # Also keep regional subfolders for easier lookup
                        region_dir = FACTBOOK_DIR / region
                        region_dir.mkdir(parents=True, exist_ok=True)
                        with zf.open(name) as src:
                            (region_dir / filename).write_bytes(src.read())
                        json_count += 1

            if json_count == 0:
                return {"rows": 0, "error": "no JSON files found in ZIP"}

        return {"rows": json_count, "error": None}
    except Exception as exc:
        logger.warning("Factbook profiles download failed: %s", exc)
        return {"rows": 0, "error": str(exc)}


# ---------------------------------------------------------------------------
# Master refresh
# ---------------------------------------------------------------------------

def refresh_all_bulk_data() -> dict:
    """Download all bulk datasets sequentially.

    Guarded by a lock so a duplicate trigger (e.g. clicking Refresh again
    before the first run finishes) is a no-op instead of starting a second,
    concurrent run whose interleaved writes to _status.json could clobber
    the first run's progress. Status is always saved in `finally` so a run
    that fails outside the per-dataset try/excepts below never leaves the
    frontend polling a stale "running" state forever.
    """
    global _running
    if not _run_lock.acquire(blocking=False):
        logger.info("Bulk data refresh already running; ignoring duplicate trigger.")
        return _load_status()

    _running = True
    status = _load_status()
    try:
        _download_all_bulk_datasets(status)
    finally:
        _save_status(status)
        logger.info("Bulk data refresh: %s", {k: f"{v.get('rows',0)} rows" for k, v in status.items()})
        _running = False
        _run_lock.release()
    return status


def _download_all_bulk_datasets(status: dict) -> None:
    now = datetime.now(timezone.utc).isoformat()

    with httpx.Client(timeout=120) as client:
        try:
            wb = _download_worldbank()
            status["worldbank"] = {
                "last_attempt": now,
                "last_ok": now if not wb["error"] else status.get("worldbank", {}).get("last_ok"),
                "error": wb["error"], "rows": wb["rows"],
                "size_kb": _dir_size(DATA_DIR, "wb_"),
            }
        except Exception as exc:
            status["worldbank"] = {**status.get("worldbank", {}), "last_attempt": now, "error": str(exc)}

        try:
            ff = _download_famafrench(client)
            status["famafrench"] = {
                "last_attempt": now,
                "last_ok": now if not ff["error"] else status.get("famafrench", {}).get("last_ok"),
                "error": ff["error"], "rows": ff["rows"],
                "size_kb": _file_size(FF_PATH),
            }
        except Exception as exc:
            status["famafrench"] = {**status.get("famafrench", {}), "last_attempt": now, "error": str(exc)}

        try:
            imf = _download_imf()
            status["imf_weo"] = {
                "last_attempt": now,
                "last_ok": now if not imf["error"] else status.get("imf_weo", {}).get("last_ok"),
                "error": imf["error"], "rows": imf["rows"],
                "size_kb": _file_size(IMF_PATH),
            }
        except Exception as exc:
            status["imf_weo"] = {**status.get("imf_weo", {}), "last_attempt": now, "error": str(exc)}

        # BIS datasets (includes crossborder)
        total_bis_rows = 0
        for ds_key, ds_config in BIS_DATASETS.items():
            try:
                bis_result = _download_bis_dataset(ds_config)
                total_bis_rows += bis_result["rows"]
                if bis_result["error"]:
                    status["bis"] = {
                        **status.get("bis", {}),
                        "last_attempt": now,
                        "error": (status.get("bis", {}).get("error", "") + "; " + bis_result["error"]).strip("; "),
                        "rows": total_bis_rows,
                        "size_kb": _dir_size(DATA_DIR, "cpi") or _dir_size(DATA_DIR, "policy") or _dir_size(DATA_DIR, "fx") or _dir_size(DATA_DIR, "crossborder"),
                    }
                else:
                    status["bis"] = {
                        "last_attempt": now,
                        "last_ok": now,
                        "error": None,
                        "rows": total_bis_rows,
                        "size_kb": _dir_size(DATA_DIR, "cpi") or _dir_size(DATA_DIR, "policy") or _dir_size(DATA_DIR, "fx") or _dir_size(DATA_DIR, "crossborder"),
                    }
            except Exception as exc:
                status["bis"] = {**status.get("bis", {}), "last_attempt": now, "error": str(exc)}

        # Factbook
        try:
            fb = _download_factbook()
            status["factbook"] = {
                "last_attempt": now,
                "last_ok": now if not fb["error"] else status.get("factbook", {}).get("last_ok"),
                "error": fb["error"], "rows": fb["rows"],
                "size_kb": _file_size(FACTBOOK_PATH),
            }
        except Exception as exc:
            status["factbook"] = {**status.get("factbook", {}), "last_attempt": now, "error": str(exc)}

        # Reinhart & Rogoff
        try:
            rr = _download_reinhart_rogoff()
            status["reinhart_rogoff"] = {
                "last_attempt": now,
                "last_ok": now if not rr["error"] else status.get("reinhart_rogoff", {}).get("last_ok"),
                "error": rr["error"], "rows": rr["rows"],
                "size_kb": _file_size(RR_PATH),
            }
        except Exception as exc:
            status["reinhart_rogoff"] = {**status.get("reinhart_rogoff", {}), "last_attempt": now, "error": str(exc)}

        # Factbook Profiles (CIA World Factbook)
        try:
            fbp = _download_factbook_profiles()
            status["factbook_profiles"] = {
                "last_attempt": now,
                "last_ok": now if not fbp["error"] else status.get("factbook_profiles", {}).get("last_ok"),
                "error": fbp["error"], "rows": fbp["rows"],
                "size_kb": _dir_size(FACTBOOK_DIR, ""),
            }
        except Exception as exc:
            status["factbook_profiles"] = {**status.get("factbook_profiles", {}), "last_attempt": now, "error": str(exc)}


def _dir_size(directory: pathlib.Path, prefix: str) -> int | None:
    try:
        total = sum(f.stat().st_size for f in directory.iterdir()
                    if f.is_file() and f.name.startswith(prefix))
        return round(total / 1024, 1)
    except Exception:
        return None


def _file_size(path: pathlib.Path) -> int | None:
    try:
        return round(path.stat().st_size / 1024, 1) if path.exists() else None
    except Exception:
        return None

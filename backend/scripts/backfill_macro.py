#!/usr/bin/env python3
"""
Backfill macro indicators from FRED into daily_macro table.
Requires FRED_API_KEY environment variable.
Run once after deployment: python backend/scripts/backfill_macro.py
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from backend.backend.database import SessionLocal, init_db
from backend.backend.db_models import DailyMacro
from datetime import datetime
import pandas as pd

# Key FRED series used in the macro tab (from existing services)
FRED_SERIES = [
    # Rates
    ("FEDFUNDS", "US", "Federal Funds Rate"),
    ("DGS10", "US", "10Y Treasury"),
    ("DGS2", "US", "2Y Treasury"),
    ("T10Y2Y", "US", "10Y-2Y Spread"),
    # Inflation
    ("CPIAUCSL", "US", "CPI"),
    ("PCEPI", "US", "PCE"),
    # Growth
    ("GDP", "US", "GDP"),
    ("UNRATE", "US", "Unemployment"),
    # Housing
    ("HOUST", "US", "Housing Starts"),
    ("CSUSHPISA", "US", "Case-Shiller HPI"),
    # Money supply
    ("M2SL", "US", "M2"),
    ("WALCL", "US", "Fed Balance Sheet"),
]


def main():
    fred_key = os.getenv("FRED_API_KEY")
    if not fred_key:
        print("WARNING: FRED_API_KEY not set. Skipping FRED backfill.")
        print("Set FRED_API_KEY environment variable and re-run.")
        sys.exit(0)

    print("Initializing database...")
    init_db()

    try:
        from fredapi import Fred
        fred = Fred(api_key=fred_key)
    except ImportError:
        print("ERROR: fredapi not installed. Run: pip install fredapi")
        sys.exit(1)

    total_rows = 0
    with SessionLocal() as session:
        for series_id, country, name in FRED_SERIES:
            try:
                print(f"Fetching {series_id} ({name})...")
                data = fred.get_series(series_id, observation_start="2000-01-01")
                rows = 0
                for date_idx, value in data.items():
                    if pd.isna(value):
                        continue
                    # Convert timestamp to date
                    if hasattr(date_idx, 'date'):
                        date_val = date_idx.date()
                    else:
                        date_val = date_idx
                    session.merge(DailyMacro(
                        indicator_id=series_id,
                        country=country,
                        date=date_val,
                        value=float(value),
                    ))
                    rows += 1
                session.commit()
                total_rows += rows
                print(f"  -> {rows} rows for {series_id}")
            except Exception as e:
                print(f"  ERROR fetching {series_id}: {e}")
                continue

    print(f"\nMacro backfill complete: {total_rows} total rows in daily_macro")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Backfill 5Y OHLCV data for all tracked tickers into daily_prices table.
Run once after deployment: python backend/scripts/backfill_ohlcv.py
"""
import sys
import os

# Add parent directories to path so imports work
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from backend.backend.database import SessionLocal, init_db
from backend.backend.db_models import DailyPrice
from backend.backend.services import constituents as cs
import yfinance as yf
import pandas as pd
from datetime import datetime, timezone


def get_all_tickers():
    """Get deduplicated list of S&P 500 + NDX 100 + Dow 30 tickers."""
    tickers = set()

    # S&P 500
    sp500_symbols = cs.constituent_symbols("sp500")
    tickers.update(sp500_symbols)
    print(f"S&P 500: {len(sp500_symbols)} tickers")

    # Nasdaq-100
    ndx_symbols = cs.constituent_symbols("ndx")
    tickers.update(ndx_symbols)
    print(f"Nasdaq-100: {len(ndx_symbols)} tickers")

    # Dow 30
    dow_symbols = cs.constituent_symbols("dow")
    tickers.update(dow_symbols)
    print(f"Dow 30: {len(dow_symbols)} tickers")

    return sorted(list(tickers))


def safe_float(v):
    """Safely convert to float, returning None for NaN/invalid values."""
    try:
        if pd.isna(v):
            return None
        f = float(v)
        return None if pd.isna(f) else f
    except (TypeError, ValueError):
        return None


def safe_int(v):
    """Safely convert to int, returning None for invalid values."""
    try:
        if pd.isna(v):
            return None
        return int(v)
    except (TypeError, ValueError):
        return None


def backfill_batch(tickers_batch: list[str], session) -> int:
    """Download and upsert OHLCV for a batch of tickers. Returns rows inserted."""
    if not tickers_batch:
        return 0

    try:
        # Use yfinance download for batch efficiency
        data = yf.download(
            tickers_batch,
            period="5y",
            auto_adjust=True,
            progress=False,
            threads=True,
        )

        if data is None or data.empty:
            return 0

        rows = 0

        # Handle single vs multi-ticker response
        if len(tickers_batch) == 1:
            sym = tickers_batch[0]
            for date_idx, row in data.iterrows():
                close_val = safe_float(row.get('Close'))
                if close_val is None:
                    continue
                session.merge(DailyPrice(
                    symbol=sym,
                    date=date_idx.date(),
                    open=safe_float(row.get('Open')),
                    high=safe_float(row.get('High')),
                    low=safe_float(row.get('Low')),
                    close=close_val,
                    adj_close=close_val,  # auto_adjust=True so Close IS adj
                    volume=safe_int(row.get('Volume')),
                ))
                rows += 1
        else:
            # Multi-ticker: data has MultiIndex columns (field, ticker)
            for sym in tickers_batch:
                try:
                    if isinstance(data.columns, pd.MultiIndex):
                        sym_data = data.xs(sym, axis=1, level=1)
                    else:
                        # Single ticker fallback
                        sym_data = data

                    if sym_data.empty:
                        continue

                    for date_idx, row in sym_data.iterrows():
                        close_val = safe_float(row.get('Close'))
                        if close_val is None:
                            continue
                        session.merge(DailyPrice(
                            symbol=sym,
                            date=date_idx.date(),
                            open=safe_float(row.get('Open')),
                            high=safe_float(row.get('High')),
                            low=safe_float(row.get('Low')),
                            close=close_val,
                            adj_close=close_val,
                            volume=safe_int(row.get('Volume')),
                        ))
                        rows += 1
                except (KeyError, Exception) as e:
                    print(f"  Skipping {sym}: {e}")
                    continue

        return rows
    except Exception as e:
        print(f"  Batch error: {e}")
        return 0


def main():
    print("Initializing database...")
    init_db()

    print("Getting ticker list...")
    tickers = get_all_tickers()
    if not tickers:
        print("ERROR: No tickers found. Check constituents.py integration.")
        sys.exit(1)

    print(f"Found {len(tickers)} unique tickers to backfill")

    BATCH_SIZE = 50
    total_rows = 0
    batches = [tickers[i:i+BATCH_SIZE] for i in range(0, len(tickers), BATCH_SIZE)]

    with SessionLocal() as session:
        for i, batch in enumerate(batches):
            print(f"\nBatch {i+1}/{len(batches)}: {batch[:3]}...{batch[-1]} ({len(batch)} tickers)")
            rows = backfill_batch(batch, session)
            session.commit()
            total_rows += rows
            print(f"  -> {rows} rows inserted (total: {total_rows})")

    print(f"\nBackfill complete: {total_rows} total rows in daily_prices")


if __name__ == "__main__":
    main()

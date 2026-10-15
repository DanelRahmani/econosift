"""Phase 66: econosift.db market-data tables and the store.prices() helper."""
import pandas as pd
import pytest

from backend import store

SYMS = ("ZZSTA", "ZZSTB")


@pytest.fixture(autouse=True)
def _clean():
    store.init_schema()
    yield
    with store.connect() as conn:
        conn.execute(f"DELETE FROM price_daily WHERE symbol IN ({','.join('?' * len(SYMS))})", SYMS)


def _bar(sym, day, close):
    return dict(symbol=sym, date=day, open=close, high=close, low=close,
                close=close, adj_close=close, volume=100.0)


def test_schema_has_the_plan_tables_and_price_daily_is_without_rowid():
    with store.connect() as conn:
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        sql = conn.execute("SELECT sql FROM sqlite_master WHERE name='price_daily'").fetchone()[0]
    assert {"security", "index_membership", "price_daily", "corporate_action", "quote_latest",
            "quote_intraday", "fundamental", "macro_series", "fx_daily", "source_health",
            "fetch_queue"} <= tables
    assert "WITHOUT ROWID" in sql


def test_upsert_inserts_then_updates_in_place():
    store.upsert("price_daily", [_bar("ZZSTA", "2026-01-02", 10.0)], ("symbol", "date"))
    store.upsert("price_daily", [_bar("ZZSTA", "2026-01-02", 11.0)], ("symbol", "date"))
    df = store.prices(["ZZSTA"])
    assert df["ZZSTA"].tolist() == [11.0]


def test_prices_is_a_wide_frame_filtered_by_date_and_ordered_as_asked():
    store.upsert("price_daily", [
        _bar("ZZSTA", "2026-01-02", 10.0), _bar("ZZSTA", "2026-01-05", 12.0),
        _bar("ZZSTB", "2026-01-02", 20.0), _bar("ZZSTB", "2026-01-05", 21.0),
    ], ("symbol", "date"))
    df = store.prices(["ZZSTB", "ZZSTA", "ZZNONE"], start="2026-01-03")
    assert list(df.columns) == ["ZZSTB", "ZZSTA"]  # no column for a symbol with no rows
    assert isinstance(df.index, pd.DatetimeIndex)
    assert df.index.tolist() == [pd.Timestamp("2026-01-05")]
    assert df.loc["2026-01-05", "ZZSTA"] == 12.0


def test_prices_with_nothing_stored_is_empty():
    assert store.prices(["ZZNONE"]).empty
    assert store.prices([]).empty


def test_prices_rejects_unknown_fields():
    with pytest.raises(ValueError):
        store.prices(["ZZSTA"], field="close; DROP TABLE price_daily")

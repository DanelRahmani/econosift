"""Sub-annual -> annual conversion keeps only complete years (audit D-03)."""
import pandas as pd

from backend.sources._annual import complete_years, to_annual


def _monthly(start: str, end: str, value=None) -> pd.Series:
    idx = pd.date_range(start, end, freq="MS")
    return pd.Series(range(1, len(idx) + 1) if value is None else [value] * len(idx), index=idx, dtype=float)


def test_running_year_is_dropped_not_averaged():
    # Jan 2023 - Aug 2025: 2025 is incomplete.
    s = _monthly("2023-01-01", "2025-08-01")
    assert complete_years(s) == {2023, 2024}
    out = to_annual(s, "mean", 2023, 2025)
    assert out == [(2023, 6.5), (2024, 18.5)]


def test_sum_and_yoy_need_complete_adjacent_years():
    s = pd.concat([_monthly("2022-01-01", "2022-12-01", 10.0), _monthly("2023-01-01", "2023-12-01", 11.0),
                   _monthly("2024-01-01", "2024-06-01", 12.0)])
    assert to_annual(s, "sum", 2022, 2024) == [(2022, 120.0), (2023, 132.0)]
    yoy = to_annual(s, "yoy", 2022, 2024)
    assert len(yoy) == 1 and yoy[0][0] == 2023 and abs(yoy[0][1] - 10.0) < 1e-9


def test_daily_series_with_string_dates_and_weekend_year_end():
    days = pd.bdate_range("2022-01-03", "2023-12-29")  # 2023 ends on a Friday
    s = pd.Series(1.0, index=[d.strftime("%Y-%m-%d") for d in days])
    assert [y for y, _ in to_annual(s, "mean", 2022, 2023)] == [2022, 2023]


def test_yoy_matches_by_date_when_a_month_is_missing():
    from backend.sources._annual import yoy_pct

    # Monthly index, +1 per month; October 2025 never published.
    idx = pd.date_range("2024-08-01", "2026-08-01", freq="MS").drop(pd.Timestamp("2025-10-01"))
    s = pd.Series([100.0 + i for i in range(len(idx))], index=idx)
    out = yoy_pct(s)
    aug26, aug25 = s[pd.Timestamp("2026-08-01")], s[pd.Timestamp("2025-08-01")]
    assert abs(out[pd.Timestamp("2026-08-01")] - (aug26 / aug25 - 1) * 100) < 1e-9
    # The month whose year-earlier value is missing gets no YoY at all.
    assert pd.Timestamp("2026-10-01") not in out.index


def test_yoy_quarterly_and_weekly_frequencies():
    from backend.sources._annual import yoy_pct

    q = pd.Series([100.0, 101, 102, 103, 110], index=pd.date_range("2024-01-01", periods=5, freq="QS"))
    assert abs(yoy_pct(q).iloc[-1] - 10.0) < 1e-9
    w = pd.Series(range(1, 60), index=pd.date_range("2024-01-05", periods=59, freq="W-FRI"), dtype=float)
    yw = yoy_pct(w)
    assert len(yw) > 0 and yw.index.min() >= pd.Timestamp("2025-01-01")

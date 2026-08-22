"""Tests for credit_conditions_service (SOFR-IORB, SLOOS, EBP, NFCI/ANFCI) — Phase 39."""
import pytest

from backend.services import credit_conditions_service as ccs


def _pts(pairs):
    return [{"date": d, "value": v} for d, v in pairs]


def test_spliced_floor_prefers_iorb_and_backfills_with_ioer():
    ioer = _pts([("2021-07-26", 0.15), ("2021-07-27", 0.15), ("2021-07-28", 0.15)])
    iorb = _pts([("2021-07-29", 0.15), ("2021-07-30", 0.15)])

    out = ccs._spliced_floor(iorb, ioer)

    dates = [p["date"] for p in out]
    assert dates == sorted(dates)
    assert dates[0] == "2021-07-26" and dates[-1] == "2021-07-30"
    assert len(out) == 5


def test_spliced_floor_drops_overlapping_ioer_observations():
    # IOER lingering past the IORB start must not duplicate those dates.
    ioer = _pts([("2021-07-28", 0.15), ("2021-07-29", 0.15), ("2021-07-30", 0.15)])
    iorb = _pts([("2021-07-29", 0.20), ("2021-07-30", 0.20)])

    out = ccs._spliced_floor(iorb, ioer)

    assert [p["date"] for p in out] == ["2021-07-28", "2021-07-29", "2021-07-30"]
    # IORB wins on the overlapping dates.
    assert [p["value"] for p in out] == [0.15, 0.20, 0.20]


def test_spliced_floor_falls_back_to_ioer_when_iorb_missing():
    ioer = _pts([("2015-01-01", 0.25)])
    assert ccs._spliced_floor([], ioer) == ioer


def test_spread_aligns_on_dates_and_skips_unmatched():
    sofr = _pts([("2024-01-02", 5.31), ("2024-01-03", 5.32), ("2024-01-04", 5.33)])
    floor = _pts([("2024-01-02", 5.40), ("2024-01-04", 5.40)])

    out = ccs._spread(sofr, floor)

    assert [p["date"] for p in out] == ["2024-01-02", "2024-01-04"]
    assert out[0]["value"] == pytest.approx(-0.09)
    assert out[1]["value"] == pytest.approx(-0.07)


def test_spread_ignores_none_values():
    a = _pts([("2024-01-02", None), ("2024-01-03", 5.0)])
    b = _pts([("2024-01-02", 4.0), ("2024-01-03", 4.0)])
    assert ccs._spread(a, b) == [{"date": "2024-01-03", "value": 1.0}]


def test_latest_skips_trailing_nulls():
    assert ccs._latest(_pts([("2024-01-01", 1.0), ("2024-01-02", None)])) == 1.0
    assert ccs._latest([]) is None


def test_signal_thresholds():
    assert ccs._signal(0.25, ccs._SOFR_IORB_STRESS) == "stress"
    assert ccs._signal(-0.02, ccs._SOFR_IORB_STRESS) == "normal"
    assert ccs._signal(None, ccs._SOFR_IORB_STRESS) == "unknown"


def test_is_empty_guard_blocks_caching_of_useless_payloads():
    """The skip_if guard must refuse payloads with no usable indicator."""
    assert ccs._is_empty({})
    assert ccs._is_empty({"error": "FRED API key required"})
    assert ccs._is_empty({"kpis": {"sofr_iorb": None, "sloos_ci": None, "ebp": None, "anfci": None}})
    # A single live indicator is enough to be worth caching.
    assert not ccs._is_empty({"kpis": {"sofr_iorb": None, "sloos_ci": None, "ebp": -0.3, "anfci": None}})


def test_fetch_ebp_returns_empty_on_source_failure(monkeypatch):
    """A transient download failure must degrade to [] and never raise."""
    def _boom(*args, **kwargs):
        raise RuntimeError("connection reset")

    monkeypatch.setattr(ccs.httpx, "get", _boom)
    assert ccs._fetch_ebp_sync() == []


def test_fetch_ebp_returns_empty_on_unexpected_schema(monkeypatch):
    """If the Fed changes the CSV layout we must not emit garbage rows."""
    class _Resp:
        text = "date,something_else\n1/1/2020,1.0\n"

        def raise_for_status(self):
            return None

    monkeypatch.setattr(ccs.httpx, "get", lambda *a, **k: _Resp())
    assert ccs._fetch_ebp_sync() == []


def test_fetch_ebp_parses_expected_schema(monkeypatch):
    class _Resp:
        text = (
            "date,gz_spread,ebp,est_prob\n"
            "1/1/2020,1.5,0.25,0.10\n"
            "2/1/2020,1.6,,0.12\n"
        )

        def raise_for_status(self):
            return None

    monkeypatch.setattr(ccs.httpx, "get", lambda *a, **k: _Resp())
    rows = ccs._fetch_ebp_sync()

    assert [r["date"] for r in rows] == ["2020-01-01", "2020-02-01"]
    assert rows[0]["ebp"] == 0.25
    assert rows[1]["ebp"] is None  # blank cell stays None, never coerced to 0
    assert rows[1]["gz_spread"] == 1.6

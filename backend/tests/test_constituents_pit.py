"""Tests for point-in-time index membership — Phase 42 (task C1).

`get_constituents` returns today's roster, so every historical study built on it
silently excluded companies that were delisted, acquired or went bankrupt.
`members_as_of` walks the Wikipedia change log backwards to reconstruct the
roster on a past date.

These run offline: the change log and current roster are injected rather than
fetched, so the reconstruction logic is tested rather than Wikipedia's uptime.
"""
from __future__ import annotations

import datetime as dt

import pytest

from backend.services import constituents as c


# ── Change-log parsing ───────────────────────────────────────────────────────

_CHANGE_TABLE = """
{| class="wikitable sortable"
|-
! Effective Date !! colspan="2" | Added !! colspan="2" | Removed !! Reason
|-
! Date !! Ticker !! Security !! Ticker !! Security !! Reason
|-
| August 18, 2026 || RDDT || [[Reddit]] || AVB || [[AvalonBay]] || Acquisition
|-
| March 4, 2024 || SMCI || [[Supermicro]] || WHR || [[Whirlpool]] || Market cap
|-
| December 21, 2020 || TSLA || [[Tesla]] || AIV || [[Aimco]] || Market cap
|}
"""


def test_parse_changes_reads_dates_and_both_ticker_columns():
    changes = c._parse_changes(_CHANGE_TABLE)

    assert len(changes) == 3
    assert changes[0]["date"] == dt.date(2026, 8, 18)
    assert changes[0]["added"] == "RDDT"
    assert changes[0]["removed"] == "AVB"


def test_parse_changes_returns_newest_first():
    dates = [ch["date"] for ch in c._parse_changes(_CHANGE_TABLE)]
    assert dates == sorted(dates, reverse=True)


def test_parse_changes_ignores_a_table_without_a_date_header():
    assert c._parse_changes("{| class='wikitable'\n|-\n! A !! B\n|-\n| 1 || 2\n|}") == []


def test_parse_changes_handles_empty_input():
    assert c._parse_changes("") == []


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("August 18, 2026", dt.date(2026, 8, 18)),
        ("Aug 5, 2020", dt.date(2020, 8, 5)),
        ("2019-03-04", dt.date(2019, 3, 4)),
        ("[[June 1, 2015]]", dt.date(2015, 6, 1)),
        ("not a date", None),
        ("", None),
    ],
)
def test_change_date_parsing(raw, expected):
    assert c._parse_change_date(raw) == expected


# ── Reconstruction ───────────────────────────────────────────────────────────

@pytest.fixture
def fake_index(monkeypatch):
    """Today's roster plus a change log, both injected — no network."""
    current = ["AAPL", "MSFT", "RDDT", "SMCI", "TSLA"]
    changes = [
        {"date": dt.date(2026, 8, 18), "added": "RDDT", "removed": "AVB"},
        {"date": dt.date(2024, 3, 4), "added": "SMCI", "removed": "WHR"},
        {"date": dt.date(2020, 12, 21), "added": "TSLA", "removed": "AIV"},
    ]
    monkeypatch.setattr(c, "constituent_symbols", lambda index: list(current))
    monkeypatch.setattr(c, "get_membership_changes", lambda index: list(changes))
    return current, changes


def test_as_of_today_returns_the_current_roster(fake_index):
    current, _ = fake_index
    out = c.members_as_of("sp500", dt.date.today())

    assert out["symbols"] == sorted(current)
    assert out["changesApplied"] == 0
    assert out["complete"] is True


def test_a_future_date_is_treated_as_today(fake_index):
    current, _ = fake_index
    out = c.members_as_of("sp500", dt.date.today() + dt.timedelta(days=30))
    assert out["symbols"] == sorted(current)


def test_a_recent_addition_is_absent_before_it_joined(fake_index):
    out = c.members_as_of("sp500", dt.date(2026, 8, 1))

    assert "RDDT" not in out["symbols"]      # joined 2026-08-18
    assert "AVB" in out["symbols"]           # had not yet been removed
    assert out["changesApplied"] == 1


def test_tesla_is_absent_before_december_2020_and_present_after(fake_index):
    """The canonical index-change check."""
    before = c.members_as_of("sp500", dt.date(2020, 6, 1))["symbols"]
    after = c.members_as_of("sp500", dt.date(2021, 6, 1))["symbols"]

    assert "TSLA" not in before
    assert "AIV" in before                   # Tesla replaced Aimco
    assert "TSLA" in after
    assert "AIV" not in after


def test_removed_companies_are_restored(fake_index):
    """This is the survivorship fix: names gone today were members then."""
    out = c.members_as_of("sp500", dt.date(2019, 1, 1))

    for gone_today in ("AVB", "WHR", "AIV"):
        assert gone_today in out["symbols"]
    for not_yet_added in ("RDDT", "SMCI", "TSLA"):
        assert not_yet_added not in out["symbols"]


def test_roster_size_stays_stable_across_time(fake_index):
    """Each change swaps one name for another, so the count should not drift."""
    sizes = {
        len(c.members_as_of("sp500", dt.date(y, 6, 1))["symbols"])
        for y in (2019, 2021, 2025)
    }
    assert sizes == {5}


def test_dates_before_coverage_are_flagged_incomplete(fake_index):
    out = c.members_as_of("sp500", dt.date(2005, 1, 1))

    assert out["complete"] is False
    assert "survivorship" in out["note"]
    assert out["coverageFrom"] == c._COVERAGE_FROM.isoformat()


def test_dates_after_coverage_are_flagged_complete(fake_index):
    assert c.members_as_of("sp500", dt.date(2015, 1, 1))["complete"] is True


def test_missing_change_log_degrades_honestly(monkeypatch):
    """Without the log we must not present today's roster as point-in-time."""
    monkeypatch.setattr(c, "constituent_symbols", lambda index: ["AAPL", "MSFT"])
    monkeypatch.setattr(c, "get_membership_changes", lambda index: [])

    out = c.members_as_of("sp500", dt.date(2015, 1, 1))

    assert out["complete"] is False
    assert "not a point-in-time" in out["note"]


def test_unavailable_current_roster_returns_empty_not_wrong(monkeypatch):
    monkeypatch.setattr(c, "constituent_symbols", lambda index: [])
    out = c.members_as_of("sp500", dt.date(2015, 1, 1))

    assert out["symbols"] == []
    assert out["complete"] is False


def test_changes_are_unsupported_for_indices_without_a_log():
    assert c.get_membership_changes("ndx") == []
    assert c.get_membership_changes("not-an-index") == []

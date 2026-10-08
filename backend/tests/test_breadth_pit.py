"""P2-35: breadth counts point-in-time index members, not today's roster.

Offline: the roster, the membership change log and the price download are
monkeypatched. Five sessions d1..d5, three symbols:

  A  member throughout, up every day
  B  added on d3 (member d3..d5), down every day
  C  removed on d4 (member d1..d3), up every day, still trades after removal
"""
from __future__ import annotations

import datetime as dt

import pandas as pd
import pytest

from backend.services import breadth_service as bs

SESSIONS = pd.bdate_range(end="2026-06-23", periods=5)
D1, D2, D3, D4, D5 = SESSIONS
CLOSES = {
    "A": [10.0, 11.0, 12.0, 13.0, 14.0],
    "B": [20.0, 19.0, 18.0, 17.0, 16.0],
    "C": [30.0, 31.0, 32.0, 33.0, 34.0],
}
CHANGES = [
    {"date": D4.date(), "added": None, "removed": "C"},
    {"date": D3.date(), "added": "B", "removed": None},
]


@pytest.fixture(autouse=True)
def _clear_caches():
    from backend import cache
    cache._caches.clear()
    cache._stats.clear()
    yield
    cache._caches.clear()
    cache._stats.clear()


def _ohlc(closes: dict[str, list[float]]) -> dict[str, pd.DataFrame]:
    out = {}
    for sym, vals in closes.items():
        s = pd.Series(vals, index=SESSIONS)
        out[sym] = pd.DataFrame({"Open": s, "High": s, "Low": s, "Close": s})
    return out


def _patch(monkeypatch, roster=("A", "B"), changes=CHANGES, closes=CLOSES):
    monkeypatch.setattr(bs.constituents, "constituent_symbols", lambda index="sp500": list(roster))
    monkeypatch.setattr(bs.constituents, "get_membership_changes", lambda index="sp500": list(changes))
    seen: dict = {}

    def fake_download(syms, period, **kw):
        seen["syms"] = tuple(syms)
        return _ohlc({s: v for s, v in closes.items() if s in syms})

    monkeypatch.setattr(bs.yfs, "get_ohlc_frame", fake_download)
    last = SESSIONS[-1]
    monkeypatch.setattr(bs, "_now_ny", lambda: dt.datetime(last.year, last.month, last.day, 17, 0,
                                                           tzinfo=bs._NY))
    return seen


def test_member_mask_follows_the_change_log(monkeypatch):
    _patch(monkeypatch)
    frames = bs._ohlc_frames("sp500")
    member = frames["member"]
    assert list(member.index) == list(frames["close"].index)
    assert list(member.columns) == list(frames["close"].columns)
    assert member["A"].tolist() == [True] * 5
    assert member["B"].tolist() == [False, False, True, True, True]
    assert member["C"].tolist() == [True, True, True, False, False]


def test_download_universe_is_roster_plus_changed_symbols(monkeypatch):
    seen = _patch(monkeypatch)
    bs._ohlc_frames("sp500")
    assert set(seen["syms"]) == {"A", "B", "C"}


def test_prices_stay_unmasked(monkeypatch):
    _patch(monkeypatch)
    frames = bs._ohlc_frames("sp500")
    assert frames["close"]["B"].tolist() == CLOSES["B"]  # pre-join prices kept
    assert frames["close"]["C"].tolist() == CLOSES["C"]  # post-removal prices kept


def test_advancers_decliners_are_point_in_time(monkeypatch):
    _patch(monkeypatch)
    frames = bs._ohlc_frames("sp500")
    ad = bs._adv_decl_series(frames["close"], frames["member"])
    got = {d: (int(r.adv), int(r.dec)) for d, r in ad.iterrows()}
    assert got == {D2: (2, 0), D3: (2, 1), D4: (1, 1), D5: (1, 1)}


def test_breadth_headline_counts_use_members_on_the_as_of_session(monkeypatch):
    _patch(monkeypatch)
    b = bs.breadth("sp500")
    assert b["asOf"] == D5.strftime("%Y-%m-%d")
    # Members on d5 are A and B; C (removed d4) is not counted.
    assert (b["advancing"], b["declining"], b["total"]) == (1, 1, 2)
    hist = {h["date"]: (h["adv"], h["dec"]) for h in b["advDeclHistory"]}
    assert hist[D2.strftime("%Y-%m-%d")] == (2, 0)
    assert hist[D3.strftime("%Y-%m-%d")] == (2, 1)
    # cumulative A-D from the masked net series: +2, +3, +3 (=+0 on d4), +3 (+0 on d5)
    cum = [p["value"] for p in b["cumulativeAdLine"]]
    assert cum == [2.0, 3.0, 3.0, 3.0]


def test_membership_block_point_in_time(monkeypatch):
    _patch(monkeypatch)
    m = bs.breadth("sp500")["membership"]
    assert m["pointInTime"] is True
    assert m["missingSymbols"] == 0
    assert "point-in-time" in m["note"]


def test_member_without_yahoo_data_is_counted_as_missing(monkeypatch):
    _patch(monkeypatch, roster=("A", "B", "D"))
    b = bs.breadth("sp500")
    assert b["membership"]["missingSymbols"] == 1
    assert "1 former member" in b["membership"]["note"] or "no Yahoo data" in b["membership"]["note"]
    # D has no bars, so it adds nothing to the counts.
    assert b["total"] == 2


def test_changed_symbol_without_data_is_missing_only_if_it_was_a_member(monkeypatch):
    # C is dropped from the download (no data) but was a member on d1..d3.
    _patch(monkeypatch, closes={"A": CLOSES["A"], "B": CLOSES["B"]})
    assert bs.breadth("sp500")["membership"]["missingSymbols"] == 1


def test_no_change_log_falls_back_to_todays_roster(monkeypatch):
    _patch(monkeypatch, changes=[])
    frames = bs._ohlc_frames("sp500")
    assert set(frames["close"].columns) == {"A", "B"}
    assert frames["member"].all().all()
    b = bs.breadth("sp500")
    assert b["membership"]["pointInTime"] is False
    assert "survivorship" in b["membership"]["note"]
    ad = bs._adv_decl_series(frames["close"], frames["member"])
    # Today's roster {A, B}: d2 has A up, B down.
    assert (int(ad.loc[D2, "adv"]), int(ad.loc[D2, "dec"])) == (1, 1)


def test_internals_use_the_masked_series(monkeypatch):
    _patch(monkeypatch)
    internals = bs.breadth_internals("sp500")
    assert internals["asOf"] == D5
    assert "membership" in internals


def test_highs_lows_series_counts_members_only():
    """Fear & Greed reads this series: a non-member at a 52-week high is not counted (P2-35 review)."""
    import pandas as pd
    from backend.services.breadth_service import _highs_lows_series

    idx = pd.bdate_range("2026-01-01", periods=40)
    # A and B both rise every day, so each sets a new 52-week high on every session from day 30 on.
    high = pd.DataFrame({"A": range(1, 41), "B": range(101, 141)}, index=idx, dtype=float)
    low = high - 0.5
    close = high - 0.25
    member = pd.DataFrame(True, index=idx, columns=["A", "B"])
    member.loc[idx[-1], "B"] = False          # B left the index on the last session

    unmasked = _highs_lows_series(high, low, close)
    masked = _highs_lows_series(high, low, close, member)
    assert unmasked["highs"].iloc[-1] == 2    # both at a new high
    assert masked["highs"].iloc[-1] == 1      # only A, a member that session
    assert masked["highs"].iloc[-2] == 2      # B still counted while a member


def test_fear_greed_breadth_signals_carry_the_membership_note():
    """P3-39: the point-in-time residual reaches the Fear & Greed breadth signals' sources."""
    from backend.services.feargreed_service import _provenance

    note = "point-in-time S&P 500 members; 16 members have no Yahoo data (delisted or acquired) and left out"
    prov = _provenance([{"key": "highLow", "asOf": "2026-10-06"}, {"key": "mcclellan", "asOf": "2026-10-06"}],
                       {"pointInTime": True, "missingSymbols": 16, "note": note})
    assert prov["signals.highLow"]["note"] == note
    assert prov["signals.mcclellan"]["note"] == note

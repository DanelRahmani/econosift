"""Phase 67: pages read index rosters and membership history from the store."""
import datetime as dt
from unittest.mock import patch

import pytest

from backend import fetcher, store
from backend.services import constituents as c

TABLES = ("security", "index_membership")


@pytest.fixture(autouse=True)
def _clean():
    def wipe():
        with store.connect() as conn:
            for t in TABLES:
                conn.execute(f"DELETE FROM {t}")
    store.init_schema()
    wipe()
    yield
    wipe()


def _store_universe(current, changes):
    store.upsert("security", [dict(symbol=s, name=f"{s} Inc", sector="Tech", industry=None)
                              for s in {*current, *(x for ch in changes for x in (ch["added"], ch["removed"]) if x)}],
                 ("symbol",))
    store.upsert("index_membership", [dict(index_name="sp500", symbol=s, start=a, end=e)
                                      for s, a, e in fetcher.membership_intervals(current, changes)],
                 ("index_name", "symbol", "start"))


CHANGES = [  # newest first
    {"date": dt.date(2025, 6, 1), "added": "NEW", "removed": "OLD"},
    {"date": dt.date(2020, 1, 1), "added": "OLD", "removed": "GONE"},
]


def test_stored_roster_is_read_without_wikipedia():
    _store_universe(["NEW", "KEEP"], CHANGES)
    with patch.object(c, "_fetch_wikitext", side_effect=AssertionError("pages must not call Wikipedia")):
        members = c.get_constituents("sp500")
        assert [m["symbol"] for m in members] == ["KEEP", "NEW"]
        assert members[0] == {"symbol": "KEEP", "name": "KEEP Inc", "sector": "Tech", "industry": None}
        assert c.constituent_symbols("spx") == ["KEEP", "NEW"]


@pytest.mark.parametrize("as_of, members", [
    (dt.date(2026, 1, 1), ["KEEP", "NEW"]),
    (dt.date(2023, 1, 1), ["KEEP", "OLD"]),
    (dt.date(2019, 1, 1), ["GONE", "KEEP"]),
])
def test_point_in_time_rosters_from_stored_intervals_match_the_change_log(as_of, members):
    _store_universe(["NEW", "KEEP"], CHANGES)
    with patch.object(c, "_fetch_wikitext", side_effect=AssertionError("pages must not call Wikipedia")):
        assert c.members_as_of("sp500", as_of)["symbols"] == members


def test_nothing_stored_falls_back_to_wikipedia():
    with patch.object(c, "_fetch_wikitext", side_effect=RuntimeError("offline")):
        assert c.get_constituents("dow") == []  # tried the live source, never fabricates

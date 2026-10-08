"""P2-26: the Wiki (served from wiki_service.TERMS) states how the app counts new 52-week highs/lows."""
from backend.services.wiki_service import TERMS


def test_new_highs_lows_entry_states_the_app_definition():
    term = next(t for t in TERMS if t["slug"] == "new-highs-new-lows")
    d = term["definition"]
    for phrase in ("point-in-time", "intraday", "252 sessions", "as traded", "can differ"):
        assert phrase in d, phrase

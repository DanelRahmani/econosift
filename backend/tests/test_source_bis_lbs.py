"""BIS Locational Banking Statistics parsing (audit D-26)."""
from backend.sources.source_bis import _parse_lbs

_HEADER = "DATAFLOW,FREQ,L_REP_CTY,L_CP_COUNTRY,TIME_PERIOD,OBS_VALUE,UNIT_MULT\n"
_ROWS = [
    "BIS:WS_LBS_D_PUB(1.0),Q,GB,US,2026-Q1,2440737.0,6",
    "BIS:WS_LBS_D_PUB(1.0),Q,JP,US,2026-Q1,2379304.3,6",
    "BIS:WS_LBS_D_PUB(1.0),Q,DE,GB,2026-Q1,1606574.0,6",
    # aggregates: all reporters (5A) / all counterparties (5J)
    "BIS:WS_LBS_D_PUB(1.0),Q,5A,5J,2026-Q1,47621926.0,6",
    "BIS:WS_LBS_D_PUB(1.0),Q,GB,5J,2026-Q1,9000000.0,6",
    "BIS:WS_LBS_D_PUB(1.0),Q,5A,US,2026-Q1,8000000.0,6",
    # a discontinued pair whose last observation is years old
    "BIS:WS_LBS_D_PUB(1.0),Q,TW,KI,2014-Q2,99999999.0,6",
]


def test_pairs_are_latest_quarter_countries_only_in_usd():
    out = _parse_lbs(_HEADER + "\n".join(_ROWS) + "\n")
    assert out["period"] == "2026-Q1"
    assert [(c["creditor"], c["debtor"]) for c in out["claims"]] == [("GB", "US"), ("JP", "US"), ("DE", "GB")]
    # BIS reports USD millions
    assert out["claims"][0]["value_usd"] == 2_440_737_000_000
    assert out["pairCount"] == 3


def test_total_is_the_published_aggregate_not_a_sum_of_pairs():
    out = _parse_lbs(_HEADER + "\n".join(_ROWS) + "\n")
    assert out["totalUsd"] == 47_621_926_000_000


def test_empty_response_is_empty():
    assert _parse_lbs(_HEADER) == {}

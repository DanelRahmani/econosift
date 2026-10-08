"""Tests for sovereign default risk score module."""
import pytest
from backend.services.sovereign_default_service import _score_rows, _provenance


def test_score_rows_basic():
    """Test _score_rows with example data."""
    raw = [
        ("AAA", "A", 0.02),
        ("BBB", "B", 0.30),
        ("CCC", "C", 0.10),
        ("DDD", "D", 0.10),
        ("EEE", "E", 0.05),
    ]
    result = _score_rows(raw)

    # Expected scores: BBB 30.0, CCC 10.0, DDD 10.0, EEE 5.0, AAA 2.0
    # Expected ranks: BBB 1, CCC 2, DDD 2, EEE 4, AAA 5 (competition ranking)
    # Expected signal: BBB red (>=20), CCC/DDD yellow, EEE yellow (5 inclusive), AAA green (<5)
    # Expected order: BBB, CCC, DDD, EEE, AAA (score desc, iso3 asc on tie)

    assert len(result) == 5

    # Check order
    assert result[0]["iso3"] == "BBB"
    assert result[1]["iso3"] == "CCC"
    assert result[2]["iso3"] == "DDD"
    assert result[3]["iso3"] == "EEE"
    assert result[4]["iso3"] == "AAA"

    # Check scores
    assert result[0]["score"] == 30.0
    assert result[1]["score"] == 10.0
    assert result[2]["score"] == 10.0
    assert result[3]["score"] == 5.0
    assert result[4]["score"] == 2.0

    # Check ranks (competition ranking)
    assert result[0]["rank"] == 1
    assert result[1]["rank"] == 2
    assert result[2]["rank"] == 2
    assert result[3]["rank"] == 4
    assert result[4]["rank"] == 5

    # Check signals
    assert result[0]["signal"] == "red"
    assert result[1]["signal"] == "yellow"
    assert result[2]["signal"] == "yellow"
    assert result[3]["signal"] == "yellow"
    assert result[4]["signal"] == "green"

    # Check that each dict has exactly the expected keys
    for row in result:
        assert set(row.keys()) == {"iso3", "name", "score", "rank", "signal"}


def test_score_rows_names():
    """Test that names are preserved."""
    raw = [("USA", "United States", 0.01)]
    result = _score_rows(raw)
    assert result[0]["name"] == "United States"


def test_score_rows_rounding():
    """Test score rounding to 1 decimal place."""
    raw = [
        ("TST", "Test", 0.1234),
        ("TST2", "Test2", 0.1268),
    ]
    result = _score_rows(raw)
    # 0.1234 * 100 = 12.34 -> 12.3
    # 0.1268 * 100 = 12.68 -> 12.7
    assert [r["score"] for r in result] == [12.7, 12.3]  # sorted desc: 12.68 -> 12.7, 12.34 -> 12.3


def test_signal_uses_the_unrounded_score():
    """4.96 rounds to a displayed 5.0 but is below the 5 band, so it stays green."""
    result = _score_rows([("AAA", "A", 0.0496), ("BBB", "B", 0.05)])
    by = {r["iso3"]: r for r in result}
    assert by["AAA"]["score"] == 5.0 and by["AAA"]["signal"] == "green"
    assert by["BBB"]["signal"] == "yellow"


def test_score_rows_signal_thresholds():
    """Test signal thresholds."""
    raw = [
        ("G", "Green", 0.04),    # score 4.0 < 5 -> green
        ("Y1", "Yellow1", 0.05),  # score 5.0 >= 5 and < 20 -> yellow
        ("Y2", "Yellow2", 0.15),  # score 15.0 -> yellow
        ("R", "Red", 0.20),       # score 20.0 >= 20 -> red
        ("R2", "Red2", 0.25),     # score 25.0 >= 20 -> red
    ]
    result = _score_rows(raw)
    # Extract by iso3
    signals = {r["iso3"]: r["signal"] for r in result}
    assert signals["G"] == "green"
    assert signals["Y1"] == "yellow"
    assert signals["Y2"] == "yellow"
    assert signals["R"] == "red"
    assert signals["R2"] == "red"


def test_score_rows_ranking_with_ties():
    """Test competition ranking with ties."""
    raw = [
        ("A", "A", 0.1),
        ("B", "B", 0.1),
        ("C", "C", 0.1),
        ("D", "D", 0.05),
        ("E", "E", 0.05),
    ]
    result = _score_rows(raw)
    # First 3 tied at score 10.0: ranks 1, 1, 1
    # Next 2 tied at score 5.0: ranks 4, 4
    # (Note: competition ranking means rank skips; after 3 items tied at 1, next is 4)
    ranks = [r["rank"] for r in result]
    assert ranks == [1, 1, 1, 4, 4]


def test_score_rows_tie_breaking_by_iso3():
    """Test that ties are broken by iso3 ascending."""
    raw = [
        ("ZZZ", "Z", 0.10),
        ("AAA", "A", 0.10),
        ("MMM", "M", 0.10),
    ]
    result = _score_rows(raw)
    # All have same score, so sorted by iso3
    assert result[0]["iso3"] == "AAA"
    assert result[1]["iso3"] == "MMM"
    assert result[2]["iso3"] == "ZZZ"


def test_provenance_wording():
    """Test that provenance text uses rank/score wording, not probability."""
    raw = [("USA", "United States", 0.05)]
    rows = _score_rows(raw)
    # Call _provenance with minimal fakes
    pred_data = {
        "debt_gdp": {"USA": {2023: 120.0}},
        "fiscal_balance": {"USA": {2023: -5.0}},
        "current_account": {"USA": {2023: -3.0}},
        "inflation": {"USA": {2023: 3.0}},
        "gdp_growth": {"USA": {2023: 2.5}},
    }
    prov = _provenance(pred_data, rows, 47)

    # Check that "countries" title does not contain "probabilities"
    assert "probabilities" not in prov["countries"]["title"].lower()
    # Check that it does say something about ranking (in the formula field)
    assert "ranking, not a default probability" in prov["countries"]["formula"]

    # Check that "*" (the model) title is about "risk score" not "probability"
    assert "risk score" in prov["*"]["title"].lower()

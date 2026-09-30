"""Snowflake dividend-coverage units (audit C-03)."""
from backend.services.snowflake_service import _fcf_coverage_score


def test_coverage_mixes_percent_yield_with_fraction_fcf_yield():
    # KO-like: dividend yield 2.43 % (percent units), FCF yield 0.014 (fraction)
    # → coverage 0.014 / 0.0243 ≈ 0.58 → band (≥0.7 → 2.0, else 0.5).
    assert _fcf_coverage_score(2.43, 0.014) == 0.5
    # Covered 2.5x: FCF yield 6 % vs dividend 2.4 % → coverage 2.5 → 8.0.
    assert _fcf_coverage_score(2.4, 0.06) == 8.0
    # Covered 3x+ → top score.
    assert _fcf_coverage_score(1.0, 0.035) == 10.0

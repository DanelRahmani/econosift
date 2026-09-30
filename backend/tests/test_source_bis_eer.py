"""BIS effective exchange rate parsing (audit D-27)."""
import pandas as pd

from backend.sources.source_bis import _parse_eer


def _frame():
    rows = []
    for typ, basket, freq, period, val in [
        ("R: Real", "B: Broad (64 economies)", "M: Monthly", "2026-07", 101.5),
        ("R: Real", "B: Broad (64 economies)", "M: Monthly", "2026-08", 102.25),
        ("N: Nominal", "B: Broad (64 economies)", "M: Monthly", "2026-08", 140.0),
        ("R: Real", "N: Narrow (27 economies)", "M: Monthly", "2026-08", 99.0),
        ("R: Real", "B: Broad (64 economies)", "D: Daily", "2026-08-31", 103.0),
    ]:
        rows.append({"FREQ:Frequency": freq, "EER_TYPE:Type": typ, "EER_BASKET:Basket": basket,
                     "REF_AREA:Reference area": "BR: Brazil", "TIME_PERIOD:Time period or range": period,
                     "OBS_VALUE:Observation Value": val})
    return pd.DataFrame(rows)


def test_only_monthly_real_broad_series_are_returned():
    out = _parse_eer(_frame(), ["BR", "MX"])
    assert out == {"BR": [{"date": "2026-07", "value": 101.5}, {"date": "2026-08", "value": 102.25}]}

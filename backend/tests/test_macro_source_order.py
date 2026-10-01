"""Macro waterfall source priority."""
from backend.services import macro_service
from backend.sources import source_imf, source_worldbank


def test_debt_uses_one_definition_imf_general_government_first():
    for countries in (("KR",), ("US", "DE")):
        order = macro_service._source_order("debt_gdp", countries)
        assert order[0] is source_imf
        assert order.index(source_imf) < order.index(source_worldbank)

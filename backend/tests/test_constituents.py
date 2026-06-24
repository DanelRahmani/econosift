"""Offline unit tests for the Wikipedia constituent parser.

No network: we feed hand-crafted wikitext (including the symbol-template and
external-link shapes Wikipedia actually uses) straight to the parser.
"""
from __future__ import annotations

from backend.services import constituents as C


_SP_WIKITEXT = """
{| class="wikitable sortable"
|-
! Symbol !! Security !! GICS Sector !! GICS Sub-Industry
|-
| {{NyseSymbol|MMM}} || 3M || Industrials || Industrial Conglomerates
|-
| {{NasdaqSymbol|AAPL}} || Apple Inc. || Information Technology || Technology Hardware
|-
| BRK.B || Berkshire Hathaway || Financials || Multi-Sector Holdings
|}
"""

_DOW_WIKITEXT = """
{| class="wikitable"
|-
! Company !! Exchange !! Symbol !! Sector
|-
| 3M || NYSE || {{NYSE link|MMM}} || Industrials
|-
| Amgen || Nasdaq || {{NASDAQ link|AMGN}} || Health care
|}
"""


class TestCleanSymbol:
    def test_plain_symbol(self):
        assert C._clean_symbol("AAPL") == "AAPL"

    def test_template_wrapped_symbol(self):
        assert C._clean_symbol("{{NyseSymbol|MMM}}") == "MMM"

    def test_nasdaq_link_template(self):
        assert C._clean_symbol("{{NASDAQ link|AMGN}}") == "AMGN"

    def test_class_share_dot_to_dash(self):
        assert C._clean_symbol("BRK.B") == "BRK-B"

    def test_exchange_prefix_stripped(self):
        assert C._clean_symbol("NYSE: ABC") == "ABC"


class TestParseConstituents:
    def test_sp500_table_parsed(self):
        rows = C._parse_constituents(_SP_WIKITEXT, "sp500")
        syms = [r["symbol"] for r in rows]
        assert syms == ["MMM", "AAPL", "BRK-B"]

    def test_sp500_names_and_sectors(self):
        rows = C._parse_constituents(_SP_WIKITEXT, "sp500")
        by = {r["symbol"]: r for r in rows}
        assert by["AAPL"]["name"] == "Apple Inc."
        assert by["MMM"]["sector"] == "Industrials"

    def test_dow_symbol_column_not_first(self):
        # Symbol is the 3rd column here — header detection must find it.
        rows = C._parse_constituents(_DOW_WIKITEXT, "dow")
        assert [r["symbol"] for r in rows] == ["MMM", "AMGN"]

    def test_no_duplicate_symbols(self):
        rows = C._parse_constituents(_SP_WIKITEXT + _SP_WIKITEXT, "sp500")
        syms = [r["symbol"] for r in rows]
        assert len(syms) == len(set(syms))


class TestAliases:
    def test_spx_alias(self):
        assert C.ALIASES["spx"] == "sp500"

    def test_djia_alias(self):
        assert C.ALIASES["djia"] == "dow"

    def test_unknown_index_returns_empty(self):
        assert C.get_constituents("not-an-index") == []

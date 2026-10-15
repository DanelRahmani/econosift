"""SEC companyfacts -> `fundamental` rows (Phase 68, plan §3 / §8.3).

Concepts are stored under the statement labels the app's fundamentals code
already reads (Yahoo's row names, e.g. "Total Revenue"), so the read side
builds the same statement frames from SEC as it did from Yahoo. Each label
has a fallback chain of XBRL tags (§8.3); the first tag with a value for a
period wins, and ``source`` names the tag that supplied it.

Periods:
- duration facts are annual (bare label) or one fiscal quarter (label + "|Q");
  year-to-date facts are only used to compute Q4.
- an off-calendar or 10-K-only fiscal Q4 is FY - (Q1+Q2+Q3), or FY - 9-month
  YTD, from filed numbers. Never estimated; only for additive flows.
- instants (balance sheet) are stored once per date under the bare label.

Point-in-time: ``filed`` is the filing date. A period re-reported unchanged in
later filings keeps only its first filing; a restated value adds a row.
Outflows use Yahoo's sign (capex, dividends and buybacks are negative).
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date

QUARTER = "|Q"
MIN_PERIOD_END = "2008-01-01"   # XBRL filings start in 2009; earlier facts are a few comparatives
# Periodic reports only: proxies (pay-versus-performance tables), prospectuses and
# 8-Ks repeat figures, sometimes rounded differently, and would add false versions.
FORMS = {"10-K", "10-K/A", "10-Q", "10-Q/A", "10-KT", "10-KT/A", "10-QT", "10-QT/A",
         "20-F", "20-F/A", "40-F", "40-F/A"}

# label -> (unit, kind, chain, sign); kind: "flow" (additive duration), "ratio"
# (duration, not additive: EPS, average shares) or "instant".
CONCEPTS: dict[str, tuple[str, str, tuple[str, ...], int]] = {
    "Total Revenue": ("USD", "flow", (
        "us-gaap:Revenues", "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax",
        "us-gaap:RevenuesNetOfInterestExpense", "us-gaap:InterestAndDividendIncomeOperating",
        "us-gaap:RevenueFromContractWithCustomerIncludingAssessedTax", "us-gaap:InterestIncomeExpenseNet",
        "us-gaap:RegulatedAndUnregulatedOperatingRevenue", "us-gaap:SalesRevenueNet"), 1),
    "Cost Of Revenue": ("USD", "flow", (
        "us-gaap:CostOfRevenue", "us-gaap:CostOfGoodsAndServicesSold", "us-gaap:CostOfGoodsSold"), 1),
    "Gross Profit": ("USD", "flow", ("us-gaap:GrossProfit",), 1),
    "Operating Income": ("USD", "flow", ("us-gaap:OperatingIncomeLoss",), 1),
    "Pretax Income": ("USD", "flow", (
        "us-gaap:IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest",
        "us-gaap:IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments",
    ), 1),
    "Tax Provision": ("USD", "flow", ("us-gaap:IncomeTaxExpenseBenefit",), 1),
    "Net Income": ("USD", "flow", ("us-gaap:NetIncomeLoss",), 1),
    "Net Income Common Stockholders": ("USD", "flow", (
        "us-gaap:NetIncomeLossAvailableToCommonStockholdersBasic", "us-gaap:NetIncomeLoss"), 1),
    "Interest Expense": ("USD", "flow", (
        "us-gaap:InterestExpense", "us-gaap:InterestExpenseNonoperating", "us-gaap:InterestExpenseDebt"), 1),
    "Selling General And Administration": ("USD", "flow", ("us-gaap:SellingGeneralAndAdministrativeExpense",), 1),
    "Research And Development": ("USD", "flow", ("us-gaap:ResearchAndDevelopmentExpense",), 1),
    "Depreciation And Amortization": ("USD", "flow", (
        "us-gaap:DepreciationDepletionAndAmortization", "us-gaap:DepreciationAndAmortization",
        "us-gaap:DepreciationAmortizationAndAccretionNet", "us-gaap:Depreciation"), 1),
    "Operating Cash Flow": ("USD", "flow", (
        "us-gaap:NetCashProvidedByUsedInOperatingActivities",
        "us-gaap:NetCashProvidedByUsedInOperatingActivitiesContinuingOperations"), 1),
    "Capital Expenditure": ("USD", "flow", (
        "us-gaap:PaymentsToAcquirePropertyPlantAndEquipment", "us-gaap:PaymentsToAcquireProductiveAssets"), -1),
    "Cash Dividends Paid": ("USD", "flow", (
        "us-gaap:PaymentsOfDividendsCommonStock", "us-gaap:PaymentsOfDividends"), -1),
    "Repurchase Of Capital Stock": ("USD", "flow", ("us-gaap:PaymentsForRepurchaseOfCommonStock",), -1),
    "Diluted EPS": ("USD/shares", "ratio", ("us-gaap:EarningsPerShareDiluted",), 1),
    "Basic EPS": ("USD/shares", "ratio", ("us-gaap:EarningsPerShareBasic",), 1),
    "Diluted Average Shares": ("shares", "ratio", ("us-gaap:WeightedAverageNumberOfDilutedSharesOutstanding",), 1),
    "Total Assets": ("USD", "instant", ("us-gaap:Assets",), 1),
    "Current Assets": ("USD", "instant", ("us-gaap:AssetsCurrent",), 1),
    "Total Liabilities Net Minority Interest": ("USD", "instant", ("us-gaap:Liabilities",), 1),
    "Current Liabilities": ("USD", "instant", ("us-gaap:LiabilitiesCurrent",), 1),
    "Stockholders Equity": ("USD", "instant", (
        "us-gaap:StockholdersEquity",
        "us-gaap:StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"), 1),
    "Total Equity Gross Minority Interest": ("USD", "instant", (
        "us-gaap:StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
        "us-gaap:StockholdersEquity"), 1),
    "Cash And Cash Equivalents": ("USD", "instant", (
        "us-gaap:CashAndCashEquivalentsAtCarryingValue",
        "us-gaap:CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents"), 1),
    "Other Short Term Investments": ("USD", "instant", (
        "us-gaap:ShortTermInvestments", "us-gaap:MarketableSecuritiesCurrent",
        "us-gaap:AvailableForSaleSecuritiesDebtSecuritiesCurrent"), 1),
    "Cash Cash Equivalents And Short Term Investments": ("USD", "instant", (
        "us-gaap:CashCashEquivalentsAndShortTermInvestments",), 1),
    "Long Term Debt": ("USD", "instant", (
        "us-gaap:LongTermDebtNoncurrent", "us-gaap:LongTermDebtAndCapitalLeaseObligations"), 1),
    "Current Debt": ("USD", "instant", ("us-gaap:DebtCurrent", "us-gaap:LongTermDebtCurrent"), 1),
    "Retained Earnings": ("USD", "instant", ("us-gaap:RetainedEarningsAccumulatedDeficit",), 1),
    "Accounts Receivable": ("USD", "instant", (
        "us-gaap:AccountsReceivableNetCurrent", "us-gaap:ReceivablesNetCurrent"), 1),
    "Inventory": ("USD", "instant", ("us-gaap:InventoryNet",), 1),
    "Accounts Payable": ("USD", "instant", (
        "us-gaap:AccountsPayableCurrent", "us-gaap:AccountsPayableAndAccruedLiabilitiesCurrent"), 1),
    "Net PPE": ("USD", "instant", ("us-gaap:PropertyPlantAndEquipmentNet",), 1),
    "Gross PPE": ("USD", "instant", ("us-gaap:PropertyPlantAndEquipmentGross",), 1),
    "Ordinary Shares Number": ("shares", "instant", ("us-gaap:CommonStockSharesOutstanding",), 1),
    "Share Issued": ("shares", "instant", ("us-gaap:CommonStockSharesIssued",), 1),
    # Shares as of the cover page (the latest count); the read side falls back to the snapshot's.
    "Shares Outstanding": ("shares", "instant", (
        "dei:EntityCommonStockSharesOutstanding", "us-gaap:CommonStockSharesOutstanding"), 1),
}

# Liabilities fallback (§8.3): total liabilities-and-equity minus total equity, labelled derived.
LIABILITIES = "Total Liabilities Net Minority Interest"
DERIVED_LIABILITIES = ("us-gaap:LiabilitiesAndStockholdersEquity", (
    "us-gaap:StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
    "us-gaap:StockholdersEquity"))


def _days(start: str, end: str) -> int:
    return (date.fromisoformat(end) - date.fromisoformat(start)).days


def _period(fact: dict) -> str | None:
    """'FY', 'Q' or 'YTD9' for a duration fact; None for any other span."""
    days = _days(fact["start"], fact["end"])
    if 350 <= days <= 380:
        return "FY"
    if 80 <= days <= 100:
        return "Q"
    if 260 <= days <= 285:
        return "YTD9"
    return None


def _facts(doc: dict, tag: str, unit: str) -> list[dict]:
    taxonomy, name = tag.split(":")
    units = (((doc.get("facts") or {}).get(taxonomy) or {}).get(name) or {}).get("units") or {}
    out = []
    for f in units.get(unit) or []:
        if (f.get("val") is None or not f.get("end") or not f.get("filed") or f["end"] < MIN_PERIOD_END
                or f.get("form") not in FORMS):
            continue
        out.append(f)
    return out


def _versions(facts: list[dict]) -> list[dict]:
    """One fact per distinct value of a period, oldest filing first.

    The same period appears in every later filing that compares against it;
    only a changed (restated) value is a new version. Two different values in
    one filing (a multi-class cover page) are ambiguous: the period is dropped.
    """
    by_filing: dict[str, set] = defaultdict(set)
    for f in facts:
        by_filing[f["filed"]].add(float(f["val"]))
    if any(len(v) > 1 for v in by_filing.values()):
        return []
    out, last = [], None
    for f in sorted(facts, key=lambda f: (f["filed"], f.get("accn") or "")):
        if last is None or float(f["val"]) != last:
            out.append(f)
            last = float(f["val"])
    return out


def _as_of(versions: list[dict], filed: str) -> dict | None:
    """The version that was current on ``filed``."""
    known = [v for v in versions if v["filed"] <= filed]
    return known[-1] if known else None


def _tag_periods(doc: dict, tag: str, unit: str, kind: str) -> dict[tuple[str, str], list[dict]]:
    """(period, end) -> versions for one tag; period is 'FY', 'Q' or 'I'.

    Each version is {val, filed, form, derived}. Q4 is derived here, per tag,
    so the FY figure and its quarters always come from the same tag.
    """
    raw: dict[tuple[str, str, str | None], list[dict]] = defaultdict(list)
    for f in _facts(doc, tag, unit):
        if kind == "instant":
            raw[("I", f["end"], None)].append(f)
        elif f.get("start"):
            p = _period(f)
            if p:
                raw[(p, f["end"], f["start"])].append(f)
    groups = {k: v for k, v in ((k, _versions(fs)) for k, fs in raw.items()) if v}

    out: dict[tuple[str, str], list[dict]] = {}
    for (p, end, _start), vs in groups.items():
        if p == "YTD9":
            continue
        key = (p, end)
        if key in out:  # two spans of the same length ending the same day (a 52/53-week year): keep the first
            continue
        out[key] = [dict(val=float(v["val"]), filed=v["filed"], form=v.get("form"), derived=False) for v in vs]

    if kind != "flow":
        return out
    quarters = [(start, end, vs) for (p, end, start), vs in groups.items() if p == "Q"]
    ytd9 = {start: (end, vs) for (p, end, start), vs in groups.items() if p == "YTD9"}
    for (p, fy_end, fy_start), fy_versions in groups.items():
        if p != "FY" or ("Q", fy_end) in out:
            continue  # the filing reports Q4 itself
        q4 = []
        for fy in fy_versions:
            parts = None
            # Q1-Q3 of this year: inside it (52/53-week years shift starts a few days) and not its Q4.
            inside = [(e, _as_of(vs, fy["filed"])) for s, e, vs in quarters
                      if _days(fy_start, s) >= -7 and e <= fy_end and _days(e, fy_end) >= 60]
            inside = [(e, v) for e, v in inside if v is not None]
            ends = {e for e, _ in inside}
            if len(inside) == 3 and len(ends) == 3:
                parts = sum(float(v["val"]) for _, v in inside)
            elif fy_start in ytd9 and _days(ytd9[fy_start][0], fy_end) >= 60:
                v = _as_of(ytd9[fy_start][1], fy["filed"])
                parts = float(v["val"]) if v else None
            if parts is None:
                continue
            val = float(fy["val"]) - parts
            if not q4 or q4[-1]["val"] != val:
                q4.append(dict(val=val, filed=fy["filed"], form=fy.get("form"), derived=True))
        if q4:
            out[("Q", fy_end)] = q4
    return out


def _derived_liabilities(doc: dict) -> dict[tuple[str, str], list[dict]]:
    total_tag, equity_tags = DERIVED_LIABILITIES
    totals = _tag_periods(doc, total_tag, "USD", "instant")
    equity: dict[tuple[str, str], tuple[str, list[dict]]] = {}
    for tag in equity_tags:
        for key, vs in _tag_periods(doc, tag, "USD", "instant").items():
            equity.setdefault(key, (tag, vs))
    out = {}
    for key, tvs in totals.items():
        if key not in equity:
            continue
        t, e = tvs[-1], equity[key][1][-1]  # the latest values of both
        out[key] = [dict(val=t["val"] - e["val"], filed=max(t["filed"], e["filed"]), form=t["form"],
                         derived=True, equity_tag=equity[key][0])]
    return out


def rows(doc: dict, symbol: str) -> list[dict]:
    """`fundamental` rows for one symbol from a companyfacts document."""
    out: list[dict] = []
    for label, (unit, kind, chain, sign) in CONCEPTS.items():
        chosen: dict[tuple[str, str], tuple[str, list[dict]]] = {}
        for tag in chain:  # per period, the first tag in the chain that has it
            for key, vs in _tag_periods(doc, tag, unit, kind).items():
                chosen.setdefault(key, (tag, vs))
        if label == LIABILITIES:
            for key, vs in _derived_liabilities(doc).items():
                if key not in chosen:
                    chosen[key] = (f"derived:{DERIVED_LIABILITIES[0]} - {vs[0]['equity_tag']}", vs)
        for (period, end), (tag, vs) in chosen.items():
            concept = label + QUARTER if period == "Q" else label
            for v in vs:
                src = tag if tag.startswith("derived:") else (f"derived:Q4 {tag}" if v["derived"] else tag)
                out.append(dict(symbol=symbol, concept=concept, period_end=end, filed=v["filed"],
                                value=sign * v["val"], unit=unit, form=v["form"], source=f"sec:{src}"))
    return out


def filings(doc: dict) -> dict[str, tuple[str, str | None]]:
    """accn -> (filed, form) for every filing the document's facts come from.

    All forms, not only the periodic ones the facts are read from: the nightly
    frames check compares against this list, and an accn missing from it
    would re-fetch the company every night."""
    out: dict[str, tuple[str, str | None]] = {}
    for taxonomy in (doc.get("facts") or {}).values():
        for concept in taxonomy.values():
            for facts in (concept.get("units") or {}).values():
                for f in facts:
                    if f.get("accn") and f.get("filed"):
                        out.setdefault(f["accn"], (f["filed"], f.get("form")))
    return out


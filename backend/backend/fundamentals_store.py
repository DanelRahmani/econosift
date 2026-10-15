"""Company fundamentals from the store, in the shape `yfinance_service.get_info` returned (Phase 68).

The bundle the valuation, ratios, screener, corporate-health, dividend, DuPont
and Snowflake code consumes is built here from three stored sources, so none
of it calls Yahoo on a page open:

- ``fundamental``: statements from SEC companyfacts (or Yahoo's, stored by the
  fetcher for a company SEC has none for), point-in-time by filing date;
- ``quote_latest``: the 15-minute snapshot (price, market cap, P/E, yield);
- ``yahoo_doc`` kind ``info``: Yahoo-only fields (forward EPS, analyst targets,
  beta, sector names, short interest), refreshed weekly by the fetcher.

``info`` keeps Yahoo's key names and units (``debtToEquity`` in percent,
``dividendYield`` in percent, margins as fractions). Where SEC has the inputs,
the statement-based keys are computed from SEC facts (trailing twelve months =
the last four filed quarters) and override Yahoo's copy. ``bundle["_sources"]``
records where each overridden key came from, for provenance.
"""
from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from . import provenance as pv
from . import store, yahoo_info

ANNUAL_COLUMNS = 4      # Yahoo's annual statements show four years
QUARTER_COLUMNS = 5
Q = "|Q"

INCOME = ("Total Revenue", "Cost Of Revenue", "Gross Profit", "Operating Income", "Pretax Income",
          "Tax Provision", "Net Income", "Net Income Common Stockholders", "Interest Expense",
          "Selling General And Administration", "Research And Development", "Depreciation And Amortization",
          "Diluted EPS", "Basic EPS", "Diluted Average Shares")
BALANCE = ("Total Assets", "Current Assets", "Total Liabilities Net Minority Interest", "Current Liabilities",
           "Stockholders Equity", "Total Equity Gross Minority Interest", "Cash And Cash Equivalents",
           "Other Short Term Investments", "Cash Cash Equivalents And Short Term Investments", "Long Term Debt",
           "Current Debt", "Retained Earnings", "Accounts Receivable", "Inventory", "Accounts Payable",
           "Net PPE", "Gross PPE", "Ordinary Shares Number", "Share Issued")
CASHFLOW = ("Operating Cash Flow", "Capital Expenditure", "Cash Dividends Paid", "Repurchase Of Capital Stock",
            "Depreciation And Amortization")
SEC_STATEMENTS = {"financials": INCOME, "balance_sheet": BALANCE, "cashflow": CASHFLOW}

# GICS sector names (index rosters) -> Yahoo's, which the valuation code compares against.
GICS_TO_YAHOO = {"Information Technology": "Technology", "Health Care": "Healthcare",
                 "Financials": "Financial Services", "Consumer Discretionary": "Consumer Cyclical",
                 "Consumer Staples": "Consumer Defensive", "Materials": "Basic Materials"}

# quote_latest column -> Yahoo info key (same units: the snapshot is Yahoo's screen).
QUOTE_KEYS = {"price": ("currentPrice", "regularMarketPrice"), "market_cap": ("marketCap",),
              "pe": ("trailingPE",), "forward_pe": ("forwardPE",), "eps_ttm": ("trailingEps",),
              "pb": ("priceToBook",), "div_yield": ("dividendYield",), "high52": ("fiftyTwoWeekHigh",),
              "low52": ("fiftyTwoWeekLow",), "avg_vol_3m": ("averageVolume",),
              "avg_vol_10d": ("averageVolume10days",), "prev_close": ("regularMarketPreviousClose",),
              "volume": ("regularMarketVolume",), "open": ("regularMarketOpen",),
              "high": ("dayHigh",), "low": ("dayLow",)}


def _f(v) -> float | None:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if np.isfinite(f) else None


# ---------------------------------------------------------------------------
# Facts
# ---------------------------------------------------------------------------

def facts(symbol: str, as_of: str | None = None) -> tuple[dict[str, dict[str, dict]], str | None]:
    """concept -> period_end -> {value, filed, source, form}: the version current
    on ``as_of`` (default: the latest). SEC rows win over Yahoo's when a symbol
    has both. Returns (facts, "sec" | "yahoo" | None)."""
    sql = "SELECT concept, period_end, filed, value, source, form FROM fundamental WHERE symbol = ?"
    params: list = [symbol]
    if as_of:
        sql += " AND filed <= ?"
        params.append(as_of)
    with store.connect() as conn:
        rows = conn.execute(sql + " ORDER BY concept, period_end, filed", params).fetchall()
    if not rows:
        return {}, None
    origin = "sec" if any(r[4].startswith("sec:") for r in rows) else "yahoo"
    out: dict[str, dict[str, dict]] = {}
    for concept, end, filed, value, source, form in rows:
        if origin == "sec" and not source.startswith("sec:"):
            continue
        out.setdefault(concept, {})[end] = dict(value=value, filed=filed, source=source, form=form)
    return out, origin


def _statement_labels(fx: dict, origin: str, name: str) -> list[str]:
    if origin == "sec":
        return list(SEC_STATEMENTS[name])
    labels = []
    for concept, periods in fx.items():
        if any(p["form"] == f"yahoo:{name}" for p in periods.values()):
            labels.append(concept[:-len(Q)] if concept.endswith(Q) else concept)
    return list(dict.fromkeys(labels))


def _ends(fx: dict, labels, quarterly: bool, n: int) -> list[str]:
    ends: set[str] = set()
    for label in labels:
        ends.update(fx.get(label + Q if quarterly else label, {}))
    return sorted(ends, reverse=True)[:n]


def _frame(fx: dict, labels, ends: list[str], quarterly: bool, flows: bool) -> pd.DataFrame | None:
    if not ends:
        return None
    data = {}
    for label in labels:
        series = fx.get(label + Q if quarterly and flows else label, {})
        vals = [series[e]["value"] if e in series else np.nan for e in ends]
        if not all(np.isnan(v) for v in vals):
            data[label] = vals
    if not data:
        return None
    df = pd.DataFrame(data, index=pd.DatetimeIndex(pd.to_datetime(ends))).T
    return df


def _add_derived(df: pd.DataFrame | None, name: str) -> pd.DataFrame | None:
    """Yahoo's convenience rows, computed per column from the filed lines."""
    if df is None:
        return None
    rows = {}

    def g(label):
        return df.loc[label] if label in df.index else pd.Series(np.nan, index=df.columns)

    if name == "financials":
        if "Gross Profit" not in df.index or g("Gross Profit").isna().all():
            rows["Gross Profit"] = g("Total Revenue") - g("Cost Of Revenue")
        ebit = (g("Pretax Income") + g("Interest Expense")).fillna(g("Operating Income"))
        rows["EBIT"] = ebit
        rows["EBITDA"] = ebit + g("Depreciation And Amortization")
    elif name == "balance_sheet":
        ltd, cur = g("Long Term Debt"), g("Current Debt")
        total_debt = ltd.add(cur, fill_value=0).where(ltd.notna() | cur.notna())
        rows["Total Debt"] = total_debt
        rows["Common Stock Equity"] = g("Stockholders Equity")
        rows["Working Capital"] = g("Current Assets") - g("Current Liabilities")
        rows["Invested Capital"] = g("Stockholders Equity") + total_debt
        rows["Receivables"] = g("Accounts Receivable")
        if "Cash Cash Equivalents And Short Term Investments" not in df.index:
            cash, sti = g("Cash And Cash Equivalents"), g("Other Short Term Investments")
            rows["Cash Cash Equivalents And Short Term Investments"] = cash.add(sti, fill_value=0).where(cash.notna())
    elif name == "cashflow":
        rows["Free Cash Flow"] = g("Operating Cash Flow") + g("Capital Expenditure")
        rows["Total Cash From Operating Activities"] = g("Operating Cash Flow")
    extra = pd.DataFrame({k: v for k, v in rows.items() if k not in df.index and not v.isna().all()}).T
    return pd.concat([df, extra]) if not extra.empty else df


def statements(symbol: str, as_of: str | None = None) -> dict:
    """Annual and quarterly statement frames (Yahoo layout: labels x period ends, newest first)."""
    fx, origin = facts(symbol, as_of)
    out: dict = {"origin": origin, "facts": fx}
    if origin is None:
        return out
    flows_by_name = {"financials": True, "balance_sheet": False, "cashflow": True}
    labels = {n: _statement_labels(fx, origin, n) for n in flows_by_name}
    flow_labels = labels["financials"] + labels["cashflow"]
    annual_ends = _ends(fx, flow_labels, False, ANNUAL_COLUMNS)
    q_ends = _ends(fx, flow_labels, True, QUARTER_COLUMNS)
    if origin == "yahoo":
        q_balance = _ends(fx, labels["balance_sheet"], False, QUARTER_COLUMNS + ANNUAL_COLUMNS)
        q_ends = sorted(set(q_ends) | set(q_balance), reverse=True)[:QUARTER_COLUMNS]
    for name, flows in flows_by_name.items():
        out[f"{name}_df"] = _add_derived(_frame(fx, labels[name], annual_ends, False, flows), name)
        out[f"{name}_q_df"] = _add_derived(_frame(fx, labels[name], q_ends, True, flows), name)
    return out


def _latest_col(df: pd.DataFrame | None) -> dict:
    if df is None or df.empty:
        return {}
    col = df.columns[0]
    return {str(k): (None if pd.isna(v) else float(v)) for k, v in df[col].items()}


# ---------------------------------------------------------------------------
# Trailing figures
# ---------------------------------------------------------------------------

def ttm(fx: dict, label: str) -> tuple[float | None, str | None]:
    """Sum of the last four filed quarters; (value, last quarter end). None when the
    four aren't consecutive (a quarter is missing)."""
    q = fx.get(label + Q) or {}
    ends = sorted(q, reverse=True)[:4]
    if len(ends) < 4:
        return None, None
    span = (date.fromisoformat(ends[0]) - date.fromisoformat(ends[3])).days
    if not 250 <= span <= 300:
        return None, None
    return sum(q[e]["value"] for e in ends), ends[0]


def latest(fx: dict, label: str) -> tuple[float | None, str | None]:
    series = fx.get(label) or {}
    if not series:
        return None, None
    end = max(series)
    return series[end]["value"], end


def _yoy_quarter(fx: dict, label: str) -> float | None:
    """Latest quarter vs the same quarter a year earlier (Yahoo's revenueGrowth/earningsGrowth)."""
    q = fx.get(label + Q) or {}
    if not q:
        return None
    end = max(q)
    d = date.fromisoformat(end)
    prior = [e for e in q if 350 <= (d - date.fromisoformat(e)).days <= 380]
    if not prior:
        return None
    base = q[max(prior)]["value"]
    if not base or base <= 0:
        return None
    return q[end]["value"] / base - 1


def _sec_info(fx: dict) -> tuple[dict, dict]:
    """Statement-based info keys from SEC facts, and each key's (period, kind) for provenance."""
    out: dict = {}
    src: dict = {}

    def put(key, val, period, how):
        val = _f(val)
        if val is not None:
            out[key] = val
            src[key] = (period, how)

    def flow(label):
        v, end = ttm(fx, label)
        if v is not None:
            return v, end, "ttm"
        v, end = latest(fx, label)
        return v, end, "annual"

    rev, rev_end, rev_how = flow("Total Revenue")
    ni, ni_end, ni_how = flow("Net Income")
    nic, _, _ = flow("Net Income Common Stockholders")
    op, op_end, op_how = flow("Operating Income")
    cost, _, _ = flow("Cost Of Revenue")
    gp, gp_end, gp_how = flow("Gross Profit")
    if gp is None and rev is not None and cost is not None:
        gp, gp_end, gp_how = rev - cost, rev_end, rev_how
    da, _, _ = flow("Depreciation And Amortization")
    pretax, _, _ = flow("Pretax Income")
    interest, _, _ = flow("Interest Expense")
    ocf, ocf_end, ocf_how = flow("Operating Cash Flow")
    capex, _, _ = flow("Capital Expenditure")
    divs, _, _ = flow("Cash Dividends Paid")
    tax, _, _ = flow("Tax Provision")

    put("totalRevenue", rev, rev_end, rev_how)
    put("netIncomeToCommon", nic if nic is not None else ni, ni_end, ni_how)
    put("grossProfits", gp, gp_end, gp_how)
    put("operatingCashflow", ocf, ocf_end, ocf_how)
    if ocf is not None and capex is not None:
        put("freeCashflow", ocf + capex, ocf_end, ocf_how)
    ebit = (pretax + interest) if pretax is not None and interest is not None else op
    if ebit is not None and da is not None:
        put("ebitda", ebit + da, op_end or rev_end, op_how or rev_how)
    if rev:
        if ni is not None:
            put("profitMargins", ni / rev, ni_end, ni_how)
        if op is not None:
            put("operatingMargins", op / rev, op_end, op_how)
        if gp is not None:
            put("grossMargins", gp / rev, gp_end, gp_how)
        if "ebitda" in out:
            put("ebitdaMargins", out["ebitda"] / rev, rev_end, rev_how)
    if pretax and tax is not None and pretax > 0:
        put("effectiveTaxRate", tax / pretax, ni_end, ni_how)
    if ni and divs is not None and ni > 0:
        put("payoutRatio", -divs / ni, ni_end, ni_how)

    equity, eq_end = latest(fx, "Stockholders Equity")
    assets, as_end = latest(fx, "Total Assets")
    ltd, ltd_end = latest(fx, "Long Term Debt")
    cur_debt, cd_end = latest(fx, "Current Debt")
    cash, cash_end = latest(fx, "Cash And Cash Equivalents")
    sti, sti_end = latest(fx, "Other Short Term Investments")
    combined, comb_end = latest(fx, "Cash Cash Equivalents And Short Term Investments")
    ca, ca_end = latest(fx, "Current Assets")
    cl, cl_end = latest(fx, "Current Liabilities")
    inv, inv_end = latest(fx, "Inventory")
    liab, liab_end = latest(fx, "Total Liabilities Net Minority Interest")

    put("totalAssets", assets, as_end, "latest")
    put("totalStockholderEquity", equity, eq_end, "latest")
    put("totalLiabilities", liab, liab_end, "latest")
    debt = None
    if ltd is not None or cur_debt is not None:  # parts filed at the latest balance-sheet date only
        end = max(e for e in (ltd_end, cd_end) if e)
        debt = sum(v for v, e in ((ltd, ltd_end), (cur_debt, cd_end)) if v is not None and e == end)
        put("totalDebt", debt, end, "latest")
    if combined is not None and (cash_end is None or comb_end >= cash_end):
        put("totalCash", combined, comb_end, "latest")
    elif cash is not None:
        put("totalCash", cash + (sti if sti is not None and sti_end == cash_end else 0.0), cash_end, "latest")
    if ca is not None and cl:
        put("currentRatio", ca / cl, ca_end, "latest")
        if inv is not None and inv_end == ca_end:
            put("quickRatio", (ca - inv) / cl, ca_end, "latest")
    if equity:
        if ni is not None:
            put("returnOnEquity", ni / equity, ni_end, ni_how)
        if debt is not None:
            put("debtToEquity", debt / equity * 100, eq_end, "latest")
    if assets and ni is not None:
        put("returnOnAssets", ni / assets, ni_end, ni_how)
    rg = _yoy_quarter(fx, "Total Revenue")
    put("revenueGrowth", rg, max(fx.get("Total Revenue" + Q) or {"": None}) or None, "yoy")
    eg = _yoy_quarter(fx, "Net Income")
    put("earningsGrowth", eg, max(fx.get("Net Income" + Q) or {"": None}) or None, "yoy")

    shares, sh_end = latest(fx, "Shares Outstanding")
    put("sharesOutstanding", shares, sh_end, "latest")
    if shares and equity is not None:
        put("bookValue", equity / shares, eq_end, "latest")
    return out, src


# ---------------------------------------------------------------------------
# The bundle
# ---------------------------------------------------------------------------

def _security(symbol: str) -> dict:
    with store.connect() as conn:
        row = conn.execute("SELECT name, cik, sector, industry, facts_at FROM security WHERE symbol = ?",
                           (symbol,)).fetchone()
    return dict(zip(("name", "cik", "sector", "industry", "facts_at"), row)) if row else {}


def _beta_from_store(symbol: str) -> float | None:
    from .services.yfinance_service import benchmark_for, get_close_frame
    bench = benchmark_for(symbol)
    close = get_close_frame((symbol, bench), "2y")
    if close.empty or symbol not in close.columns or bench not in close.columns:
        return None
    r = np.log(close[symbol] / close[symbol].shift(1))
    br = np.log(close[bench] / close[bench].shift(1))
    joined = pd.concat([r, br], axis=1, join="inner").dropna()
    if len(joined) <= 2:
        return None
    var_b = joined.iloc[:, 1].var(ddof=1)
    return _f(joined.iloc[:, 0].cov(joined.iloc[:, 1]) / var_b) if var_b and var_b > 0 else None


def bundle(symbol: str, as_of: str | None = None) -> dict:
    """The `get_info` bundle for ``symbol`` from stored data only.

    ``status: "pending"`` when nothing about the symbol is stored yet (the
    caller queues the fetch). Keys: ticker, info, financials, balance_sheet,
    cashflow (latest-column dicts), *_df and *_q_df frames, _sources.
    """
    st = statements(symbol, as_of)
    fx, origin = st["facts"], st["origin"]
    yahoo = yahoo_info.stored([symbol]).get(symbol)
    quote = store.quotes([symbol]).get(symbol) or {}
    sec = _security(symbol)

    info: dict = dict(yahoo[0]) if yahoo else {}
    sources: dict = {"origin": origin, "cik": sec.get("cik"), "yahooFetchedAt": yahoo[1] if yahoo else None,
                     "quoteTs": quote.get("ts"), "fields": {},
                     "latestFiled": max((v["filed"] for per in fx.values() for v in per.values()), default=None)}
    if origin == "sec":
        sec_info, sec_src = _sec_info(fx)
        info.update(sec_info)
        sources["fields"].update({k: ("sec",) + v for k, v in sec_src.items()})
    for col, keys in QUOTE_KEYS.items():
        v = _f(quote.get(col))
        if v is not None:
            for k in keys:
                info[k] = v
                sources["fields"][k] = ("snapshot",)
    if not quote.get("price"):
        # Outside the snapshot universe (a foreign listing): the last stored daily close.
        with store.connect() as conn:
            row = conn.execute("SELECT date, close FROM price_daily WHERE symbol = ? AND close IS NOT NULL "
                               "ORDER BY date DESC LIMIT 1", (symbol,)).fetchone()
        if row:
            info["currentPrice"] = info["regularMarketPrice"] = float(row[1])
            sources["fields"]["currentPrice"] = sources["fields"]["regularMarketPrice"] = ("close", row[0])
    if info.get("sharesOutstanding") is None and _f(quote.get("shares")) is not None:
        info["sharesOutstanding"] = _f(quote["shares"])  # the §8.3 chain's last step
        sources["fields"]["sharesOutstanding"] = ("snapshot",)
    if not quote.get("market_cap") and _f(info.get("currentPrice")) and _f(info.get("sharesOutstanding")):
        info["marketCap"] = info["currentPrice"] * info["sharesOutstanding"]  # not a week-old stored cap
        sources["fields"]["marketCap"] = ("derived",)
    if quote.get("currency") and not info.get("currency"):
        info["currency"] = quote["currency"]
    if origin == "sec":
        info.setdefault("financialCurrency", "USD")
        info.setdefault("quoteType", "EQUITY")
    name = quote.get("name") or sec.get("name")
    if name:
        info.setdefault("shortName", name)
        info.setdefault("longName", name)
    if not info.get("sector") and sec.get("sector"):
        info["sector"] = GICS_TO_YAHOO.get(sec["sector"], sec["sector"])
    if not info.get("industry") and sec.get("industry"):
        info["industry"] = sec["industry"]
    info.setdefault("symbol", symbol)

    price = _f(info.get("currentPrice") or info.get("regularMarketPrice"))
    mcap = _f(info.get("marketCap"))
    if origin == "sec" and mcap:
        debt, cash = _f(info.get("totalDebt")), _f(info.get("totalCash"))
        if debt is not None and cash is not None:
            ev = mcap + debt - cash
            info["enterpriseValue"] = ev
            sources["fields"]["enterpriseValue"] = ("derived",)
            if _f(info.get("ebitda")):
                info["enterpriseToEbitda"] = ev / info["ebitda"]
                sources["fields"]["enterpriseToEbitda"] = ("derived",)
            if _f(info.get("totalRevenue")):
                info["enterpriseToRevenue"] = ev / info["totalRevenue"]
                sources["fields"]["enterpriseToRevenue"] = ("derived",)
        if _f(info.get("totalRevenue")):
            info["priceToSalesTrailing12Months"] = mcap / info["totalRevenue"]
            sources["fields"]["priceToSalesTrailing12Months"] = ("derived",)
    if info.get("priceToBook") is None and price and _f(info.get("bookValue")):
        info["priceToBook"] = price / info["bookValue"]
    if info.get("trailingEps") is None and price and _f(info.get("trailingPE")):
        info["trailingEps"] = price / info["trailingPE"]
    if info.get("forwardEps") is None and price and _f(info.get("forwardPE")):
        info["forwardEps"] = price / info["forwardPE"]
    if info.get("beta") is None:
        beta = _beta_from_store(symbol)
        if beta is not None:
            info["beta"] = beta
            sources["fields"]["beta"] = ("derived",)

    out: dict = {"ticker": symbol, "info": info, "_sources": sources}
    for name in ("financials", "balance_sheet", "cashflow"):
        out[name] = _latest_col(st.get(f"{name}_df"))
        out[f"{name}_df"] = st.get(f"{name}_df")
        # Quarterly frames only where the annual one has a single column (Beneish/health date-match).
        annual = st.get(f"{name}_df")
        out[f"{name}_q_df"] = st.get(f"{name}_q_df") if annual is not None and annual.shape[1] < 2 else None
    if info.get("freeCashflow") is None and out["cashflow"].get("Free Cash Flow") is not None:
        info["freeCashflow"] = out["cashflow"]["Free Cash Flow"]
        info["_fcfPeriod"] = f"FY{out['cashflow_df'].columns[0].year}"
    if info.get("operatingCashflow") is None and out["cashflow"].get("Operating Cash Flow") is not None:
        info["operatingCashflow"] = out["cashflow"]["Operating Cash Flow"]
    if not (origin or yahoo or quote):
        out["status"] = "pending"
    return out


# ---------------------------------------------------------------------------
# Provenance
# ---------------------------------------------------------------------------

def statement_ref(b: dict, title: str, observed: str | None = None) -> dict:
    """Ref for statement data in bundle ``b``: SEC (with the filing date) or Yahoo."""
    src = b.get("_sources") or {}
    sym = b.get("ticker")
    if src.get("origin") == "sec":
        filed = src.get("latestFiled")
        return pv.ref("sec_edgar", src.get("cik"), title, observed=observed,
                      note="XBRL company facts (10-K/10-Q)" + (f"; latest filing stored {filed}" if filed else ""))
    note = (f"Yahoo's statements as stored by the fetcher on {src['latestFiled']}"
            if src.get("origin") == "yahoo" and src.get("latestFiled") else None)
    return pv.yahoo(sym, title, observed=observed, note=note)


def field_ref(b: dict, field: str, *, note: str | None = None, flags: tuple = (), **kw) -> dict:
    """Ref for ``info.<field>`` of bundle ``b``: SEC fact, snapshot, Yahoo info or computed.
    ``note``/``flags`` are added to the source's own; other keywords (units...) go to the ref."""
    src = b.get("_sources") or {}
    sym = b.get("ticker")
    how = (src.get("fields") or {}).get(field) or ("yahoo",)

    def notes(*parts):
        return "; ".join(p for p in parts if p) or None

    if how[0] == "sec":
        desc = {"ttm": "sum of the last four filed quarters", "annual": "latest annual filing",
                "latest": "latest balance sheet", "yoy": "latest quarter vs the same quarter a year earlier"}
        return pv.ref("sec_edgar", src.get("cik"), f"{field} from XBRL company facts ({desc.get(how[2], how[2])})",
                      observed=how[1], note=note, flags=flags, **kw)
    if how[0] == "snapshot":
        return pv.yahoo(sym, f"{field} (15-minute quote snapshot)", note=note,
                        flags=tuple(dict.fromkeys(("delayed", *flags))), **kw)
    if how[0] == "close":
        return pv.yahoo(sym, "last stored daily close", observed=how[1], note=note, flags=flags, **kw)
    if how[0] == "derived":
        return pv.derived(f"{field} computed from the stored quote and statements", title=field,
                          note=note, flags=flags)
    fetched = f"stored Ticker.info copy fetched {src['yahooFetchedAt'][:10]}" if src.get("yahooFetchedAt") else None
    return pv.yahoo(sym, f"info.{field}", note=notes(note, fetched), flags=flags, **kw)

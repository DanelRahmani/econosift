"""Data provenance: where each number in a response came from.

Endpoints attach a top-level ``"provenance"`` map to their response::

    "provenance": {
        "*":       <ref or [refs]>,   # default for the whole payload
        "cpiYoY":  <ref>,             # a specific field
        "series.US": [<ref>, <ref>],  # dotted keys for nested data
    }

The frontend's right-click → Source panel looks a datapoint's key up in this
map (exact key, then each parent key, then ``"*"``). The map is additive —
existing ``source`` / ``asOf`` fields are unchanged.

A *ref* names the provider and, where it applies, the exact series, its
units/frequency, the observation it describes, and any caveat flags. Computed
metrics use :func:`derived`, which records the formula and the inputs it was
computed from. :func:`attach` adds the map to a response and stamps each ref
with when its data was fetched. Nothing here fetches data; these are
descriptions built by the code that did.

Key conventions (the frontend looks a key up, then each parent, then ``"*"``,
so add a key only where its source differs from its parent's):

* ``"*"`` — default for the whole payload; every response has one.
* ``fieldName`` — a top-level response field; ``parent.child`` for nested objects.
* ``listField.<id>`` — one row of a list, keyed by the row's natural id
  (``symbol``, ``ticker``, ``iso2``, ``key`` ...), never by array index;
  ``listField.<id>.<field>`` when fields of a row differ in source.
* A value may be another key's name (a string) instead of a ref: "same
  source as that key". It avoids repeating a ref for fields that share it.

Rules for writing refs:

* Describe only what the code does. Take provider, series id and transform
  from the code that fetched and computed the value; never guess a source.
* ``observed`` is the date/period of the observation (the last bar, the
  statement date, the data year), never today's date.
* Flag caveats: ``fallback`` for a hard-coded default, ``estimate`` for a
  projection, ``stale``, ``partial``, ``delayed``, ``proxy``.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from . import cache

log = logging.getLogger(__name__)

# provider id -> (display name, homepage, series URL template or None).
# ``{id}`` in a template is replaced by the series id.
PROVIDERS: dict[str, tuple[str, str, str | None]] = {
    "yahoo": ("Yahoo Finance", "https://finance.yahoo.com", "https://finance.yahoo.com/quote/{id}"),
    "fred": ("FRED (Federal Reserve Bank of St. Louis)", "https://fred.stlouisfed.org",
             "https://fred.stlouisfed.org/series/{id}"),
    "alfred": ("ALFRED (FRED vintage data)", "https://alfred.stlouisfed.org",
               "https://alfred.stlouisfed.org/series?seid={id}"),
    "worldbank": ("World Bank (World Development Indicators)", "https://data.worldbank.org",
                  "https://data.worldbank.org/indicator/{id}"),
    "imf": ("IMF (World Economic Outlook)", "https://www.imf.org/en/Publications/WEO",
            "https://www.imf.org/external/datamapper/{id}@WEO"),
    "dbnomics": ("DB.nomics (OECD / BIS / IMF mirror)", "https://db.nomics.world",
                 "https://db.nomics.world/{id}"),
    "ecb": ("ECB Data Portal", "https://data.ecb.europa.eu", "https://data.ecb.europa.eu/data/datasets/{id}"),
    "bis": ("BIS (Bank for International Settlements)", "https://data.bis.org", None),
    "frankfurter": ("Frankfurter (ECB reference rates)", "https://frankfurter.dev", None),
    "finnhub": ("Finnhub", "https://finnhub.io", None),
    "sec_edgar": ("SEC EDGAR", "https://www.sec.gov/edgar",
                  "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={id}"),
    "cftc": ("CFTC (Commitments of Traders)", "https://www.cftc.gov/MarketReports/CommitmentsofTraders", None),
    "kenfrench": ("Ken French Data Library",
                  "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html", None),
    "damodaran": ("Aswath Damodaran (NYU Stern)", "https://pages.stern.nyu.edu/~adamodar/", None),
    "nyfed": ("Federal Reserve Bank of New York", "https://www.newyorkfed.org", None),
    "fedboard": ("Federal Reserve Board", "https://www.federalreserve.gov", None),
    "eurostat": ("Eurostat", "https://ec.europa.eu/eurostat",
                 "https://ec.europa.eu/eurostat/databrowser/view/{id}"),
    "wikipedia": ("Wikipedia (index constituents)", "https://en.wikipedia.org", None),
    "factbook": ("CIA World Factbook", "https://www.cia.gov/the-world-factbook/", None),
    "gemini": ("Google Gemini (AI-generated text)", "https://ai.google.dev", None),
    "econosift": ("EconoSift (recorded by this app)", "", None),
    "other": ("Other source", "", None),
    "derived": ("Computed by EconoSift", "", None),
}

# Caveats the UI renders as chips.
FLAGS = frozenset({
    "fallback",   # a hard-coded/default value stood in for missing data
    "estimate",   # a projection, not an observation (e.g. IMF WEO future years)
    "stale",      # the latest observation is older than expected
    "partial",    # covers an incomplete period
    "delayed",    # quotes delayed by the provider (e.g. ~15 min)
    "proxy",      # a stand-in series for the thing named (e.g. Germany for EUR)
})


def _fetched_at() -> str:
    """UTC time the data read in this request was fetched: the oldest cache
    entry used, or now if everything was fetched live."""
    ts = cache.oldest_fetch()
    when = datetime.fromtimestamp(ts, timezone.utc) if ts else datetime.now(timezone.utc)
    return when.strftime("%Y-%m-%dT%H:%M:%SZ")


def attach(result, prov: dict):
    """Return ``result`` with a ``"provenance"`` map added.

    ``prov`` maps response keys (``"*"`` for the whole payload, dotted keys
    for nested data) to a ref or a list of refs. Keys already present in
    ``result["provenance"]`` win, so a service can set specifics and a router
    add the default. Non-dict results are returned unchanged. Each ref gets
    ``fetchedAt`` unless it already carries one.
    """
    if not isinstance(result, dict):
        return result
    merged = {**prov, **(result.get("provenance") or {})}
    stamp = _fetched_at()
    for key, value in list(merged.items()):
        if isinstance(value, str):
            continue  # alias of another key
        refs = value if isinstance(value, list) else [value]
        if not refs or not all(isinstance(r, dict) for r in refs):
            # A malformed entry must not break the response it describes.
            log.warning("provenance: dropping malformed entry %r", key)
            del merged[key]
            continue
        for r in refs:
            r.setdefault("fetchedAt", stamp)
    return {**result, "provenance": merged}


def ref(provider: str, series: str | None = None, title: str | None = None, *,
        units: str | None = None, frequency: str | None = None,
        observed: str | None = None, transform: str | None = None,
        flags: tuple[str, ...] | list[str] = (), note: str | None = None,
        url: str | None = None) -> dict:
    """A source reference for data taken (possibly transformed) from a provider."""
    if provider not in PROVIDERS:
        raise ValueError(f"unknown provider '{provider}'")
    bad = set(flags) - FLAGS
    if bad:
        raise ValueError(f"unknown provenance flag(s): {sorted(bad)}")
    name, home, template = PROVIDERS[provider]
    out: dict = {"provider": provider, "providerName": name}
    link = url or (template.format(id=series) if template and series else home)
    for key, val in (("series", series), ("title", title), ("units", units),
                     ("frequency", frequency), ("observed", observed),
                     ("transform", transform), ("note", note), ("url", link or None)):
        if val:
            out[key] = val
    if flags:
        out["flags"] = list(flags)
    return out


def derived(formula: str, inputs: list | tuple = (), *, title: str | None = None,
            observed: str | None = None, flags: tuple[str, ...] | list[str] = (),
            note: str | None = None) -> dict:
    """A reference for a value EconoSift computed.

    ``inputs`` are provenance keys in the same map (strings) and/or inline
    refs; the UI resolves the keys so the user can follow a computed metric
    back to the raw series it was built from.
    """
    bad = set(flags) - FLAGS
    if bad:
        raise ValueError(f"unknown provenance flag(s): {sorted(bad)}")
    out: dict = {"provider": "derived", "providerName": PROVIDERS["derived"][0], "formula": formula}
    if inputs:
        out["inputs"] = list(inputs)
    for key, val in (("title", title), ("observed", observed), ("note", note)):
        if val:
            out[key] = val
    if flags:
        out["flags"] = list(flags)
    return out


def last_date(obj) -> str | None:
    """ISO date of the last row of a pandas Series/DataFrame index, for ``observed``."""
    try:
        idx = obj.dropna(how="all").index if hasattr(obj, "dropna") else obj.index
        return str(idx[-1])[:10] if len(idx) else None
    except Exception:
        return None


def yahoo(ticker: str, field: str | None = None, **kw) -> dict:
    """Shorthand for a Yahoo Finance quote/fundamental field."""
    return ref("yahoo", ticker, field, **kw)


def fred(series_id: str, title: str | None = None, **kw) -> dict:
    """Shorthand for a FRED series."""
    return ref("fred", series_id, title, **kw)


def label_to_ref(source_label: str, *, series: str | None = None, **kw) -> dict:
    """Map a macro-waterfall ``source_label`` string to a ref.

    The waterfall adapters identify themselves by label; this keeps the
    mapping in one place instead of scattering provider ids through them.
    """
    low = source_label.lower()
    # Most specific first: "Frankfurter (ECB FX data)" is Frankfurter, not the ECB.
    for needle, provider in (("frankfurter", "frankfurter"), ("db.nomics", "dbnomics"),
                             ("fred", "fred"), ("world bank", "worldbank"), ("imf", "imf"),
                             ("ecb", "ecb"), ("bis", "bis")):
        if needle in low:
            return ref(provider, series, source_label, **kw)
    # Unrecognised label: keep the adapter's own wording rather than guess.
    out = ref("other", series, **kw)
    out["providerName"] = source_label
    return out

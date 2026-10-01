# EconoSift Calculation and Data Audit Plan

> **Purpose:** Establish an evidence-based review of every calculation-bearing app module and verify the correctness, timing, units, and provenance of macroeconomic and market data. This is a plan for the next work session; no calculations or data sources have been audited by this document.

## Audit standard

- Do not label a module or dataset correct until its implementation, inputs, and expected outputs have been checked and the evidence recorded.
- Keep mathematical correctness, source-data correctness, and presentation/label correctness as separate verdicts.
- Record source, endpoint/series, units, frequency, date/as-of convention, transformations, cache/fallback behavior, and known limitations for each data flow.
- Report coverage explicitly as **verified**, **issue found**, **not applicable with reason**, or **not yet audited**. No implicit pass from shared code or a passing build.
- Preserve API contracts while correcting implementation defects. Treat changes to API routes or payload shapes as a separate compatibility decision.

## Coverage inventory

During the audit, derive the definitive inventory from routes, services, source adapters, frontend API clients, and calculation call sites. README labels are not sufficient evidence. Check each listed page/module individually, even when several share a service or formula engine.

| Area | App modules/pages to cover | Audit emphasis |
|---|---|---|
| Market analysis | Markets, valuation, ratios, technicals, sector, treemap, screener | Price/fundamental inputs, corporate actions, ratios, indicators, ranking and filtering semantics |
| Instruments and events | Options, dividends, insider, mergers, calendar | Contract/event dates, units, yields, event classification, aggregation and stale-data handling |
| User analysis | Portfolio, scenario, risk, research, corporate health | Return and risk math, weighting, scenario assumptions, benchmark alignment and derived metrics |
| Macro and policy | Macro, yield, policy, sovereign, stability, cross-border, trade | Frequency conversions, release/vintage dates, real/nominal values, rates, country mappings and comparability |
| Reference and country views | Atlas, country profiles, wiki | Source attribution, transformations, units, country/entity matching, and any derived indicators |
| Shared surfaces | Dashboard, search, admin, screener, and shared charts/widgets | Aggregations, duplicated formulas, date synchronization, sorting/ranking, displayed precision and status labels |

Also inspect backend-only calculation and data modules that have no direct page, and frontend-only calculations that do not call a dedicated endpoint. Mark purely descriptive modules not applicable only after checking their code paths.

## Work sequence

### 1. Establish a baseline and map the system

- [ ] Confirm branch, worktree status, current documentation, and existing tests before changing files.
- [ ] Inventory every backend router, service, source adapter, scheduled/background job, formula helper, frontend page, and client-side calculation.
- [ ] Trace each displayed metric from UI label to API field, implementation, input series/instrument, and upstream provider.
- [ ] Identify shared calculations, duplicated calculations, and metrics with implicit assumptions (annualization, currency, timezone, benchmark, trading calendar, or lookback window).
- [ ] Create a coverage ledger with one row per module and one row per material metric/data flow. Record owner path(s) and audit status.

### 2. Audit formulas and calculations

- [ ] For every material formula, write down its intended definition, units, frequency, sign convention, denominator, date window, and assumptions before judging code.
- [ ] Independently derive expected results with hand calculations, authoritative formula references, or a small independent reference implementation that does not reuse the production function.
- [ ] Compare production outputs against known-value examples and synthetic fixtures, including normal and edge cases.
- [ ] Check missing/NaN/infinite values, zero or near-zero denominators, negative values, short histories, gaps, duplicate dates, leap years, timezone boundaries, market holidays, and window endpoints.
- [ ] Check annualization and compounding conventions, percent-vs-decimal scaling, currency conversion, split/dividend adjustments, weighted versus unweighted aggregation, and rounding only at display boundaries.
- [ ] For portfolio and backtest calculations, check look-ahead bias, survivorship/universe selection, rebalancing timing, transaction-cost assumptions, and alignment of prices with signals.
- [ ] Reconcile each material displayed output to its underlying inputs and expected result. Save reproducible fixtures or a concise calculation trace for each check.

### 3. Verify macroeconomic data

- [ ] Enumerate every macro provider and series used in code (including, where present, FRED, World Bank, IMF, BIS, ECB, OECD, Eurostat, and DB.nomics); capture exact series/table identifiers and transformations.
- [ ] Compare representative values with provider documentation or downloadable primary-source observations, and independently cross-check important headline series where a suitable second source exists.
- [ ] Verify units, seasonal adjustment, frequency, nominal/real basis, annual/quarterly/monthly interpretation, geographic coverage, and observation/release dates.
- [ ] Distinguish observation period, publication/release date, retrieval time, and revision/vintage. Check whether historical analysis uses only information available at the simulated decision date.
- [ ] Review conversions such as quarterly SAAR to growth, monthly index to year-over-year inflation, calendar-year aggregation, annualization, and country-code mapping.
- [ ] Inspect partial current-year values and forecasts: never present partial observations or forecasts as completed-year actuals without clear labeling and a period/as-of date.
- [ ] Exercise stale, missing, delayed, revised, malformed, and rate-limited responses; verify cache TTLs, cache keys, retries, fallback providers, and visible provenance/status.

### 4. Verify market and instrument data

- [ ] Enumerate every market data provider and endpoint used (including, where present, yfinance, Finnhub, EDGAR, Ken French, CFTC, and exchange/regulator sources); capture symbol, field, interval, currency, and adjustment settings.
- [ ] Verify representative quotes, OHLCV bars, fundamentals, options chains, dividends, splits, insider transactions, and corporate events against provider responses and authoritative issuer/exchange/regulator sources when available.
- [ ] Check timestamp meaning (exchange-local session, UTC, intraday/delayed/close), trading calendar, quote staleness, missing bars, symbol changes, delistings, and provider-specific adjusted/unadjusted fields.
- [ ] Verify units, currency, share counts, per-share versus total amounts, fiscal-period labels, TTM versus point-in-time values, and restatement behavior.
- [ ] Test symbol normalization and cross-provider mapping, including ambiguous tickers and non-US listings.
- [ ] Review cache freshness and error/fallback behavior. Empty/error results must not be cached or shown as valid zero values; stale values must be identifiable.

### 5. Reconcile findings and close coverage

- [ ] Log each defect with affected module/metric, severity, reproducible inputs, observed versus expected output, evidence/source links, likely cause, and compatibility implications.
- [ ] Revalidate current candidate issues recorded in `ACTIVE_ISSUES.md` (including the Fear & Greed date-alignment and current-year macro labeling entries) against live code and primary-source data; treat them as leads, not confirmed audit conclusions.
- [ ] Fix findings in small, module-scoped changes with focused regression coverage. Keep unrelated refactors out of audit fixes.
- [ ] Run the relevant backend unit/integration checks and frontend type/build checks after fixes; run data-specific checks separately and record their commands/results.
- [ ] Re-run each affected audit case after the fix, then review the complete coverage ledger for gaps.
- [ ] Produce an audit report with methodology, audited commit, coverage counts, evidence, findings, fixes, remaining uncertainties, and explicit modules/data flows not completed.

## Evidence and reporting template

For each formula or data flow, capture:

```text
Module / UI label:
Implementation path and function:
API field / response contract:
Source, endpoint or series:
Definition / units / frequency / as-of rule:
Input fixture or observation and retrieval date:
Independent expected result / primary-source evidence:
Observed result:
Verdict: verified | issue found | not applicable (reason) | not yet audited
Finding or limitations:
Regression case / validation command:
```

## Initial leads to recheck

The working tree currently contains candidate entries in `ACTIVE_ISSUES.md` concerning date alignment among Fear & Greed inputs and current-year GDP/CPI labeling. They should be independently reproduced and checked against source observations before being treated as established findings. The audit should also search for similar synchronization, stale-data, partial-period, and unit-labeling issues elsewhere.

## Definition of done

The audit is complete only when every discovered module and material formula/data flow has a recorded verdict, high-impact calculations and macro/market inputs have reproducible evidence, findings have disposition (fixed, accepted with rationale, or open), relevant regression checks pass, and the final report clearly states remaining scope and uncertainty. A successful build alone does not satisfy this definition.

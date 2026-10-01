# EconoSift Data & Calculation Audit

> **Audited commit:** `74aade5` (DEV) · **Started:** 2026-09-30 · **Standard:** [`docs/superpowers/plans/2026-09-30-econosift-calculation-and-data-audit.md`](../superpowers/plans/2026-09-30-econosift-calculation-and-data-audit.md)
>
> Verdicts: **verified** · **issue found** · **fixed** · **accepted (reason)** · **not applicable (reason)** · **not yet audited**.
> Severity: **H** = wrong number shown to the user · **M** = wrong in edge cases or mislabelled · **L** = cosmetic / minor.
> Finding IDs: **L-** live symptom seen in the running app · **D-** data sourcing / pipeline · **C-** calculation.

## Status summary

| Bucket | Found | Fixed | Accepted / n.a. | Open or partly open |
|---|---|---|---|---|
| Live symptoms (L) | 24 | 22 | 1 | 1 |
| Data (D) | 56 | 51 | 2 | 3 |
| Calculation (C) | 46 | 41 | 1 | 4 |

Phases: 45 live baseline + missing≠0 foundation · 46 Fear & Greed / breadth · 47 macro & data pipeline · 48 calculations · 49 provenance backend · 50 provenance frontend ("right-click → Source") + fixes it exposed. Every open item is tracked in `ACTIVE_ISSUES.md`.

---

## Cross-cutting root causes

1. **Missing data surfaces as 0, and the 0 is cached.** `cache._is_empty_result` only skips `None`/empty containers, so a failure placeholder such as the breadth `empty` dict (`advancing: 0, newHighs: 0, …`) is cached for 60 min and persisted to SQLite. Same class: `x or 0` / `fillna(0)` on inputs that feed displayed values, and non-empty failure envelopes (`{"error": …}`, `{"rates": {}}`) that get cached.
2. **Partial periods aggregated as complete.** `resample("YE")` includes the in-progress calendar year in every annual macro adapter; dividends sum the partial calendar year as an annual dividend.
3. **Unit / definition / frequency mix-ups** inside the macro waterfall (levels shown as growth rates, $mn next to % of GDP, `pct_change(12)` on quarterly data, FX quotes inverted twice).
4. **No provenance.** ~14% of endpoints return any source; the waterfall labels a whole series with the first provider that touched it; `asOf` is frequently `date.today()` rather than the observation date; the cache keeps no fetch time.

---

## Live findings (L-xx)

*Populated by the Phase 45 browser walk of the running Docker app. Each row links to the D-/C- finding that explains it.*

Baseline: fresh Docker install (factory-reset volumes), cold scan of 105 endpoints on 2026-09-30, then a warm re-scan. Scanner and raw JSON kept outside the repo; findings reproduced below.

| ID | Sev | Page / tab | Symptom | Endpoint · field | Explained by | Verdict |
|---|---|---|---|---|---|---|
| L-01 | H | Dashboard · Fear & Greed | Put/Call signal pinned at **0.0 ("Extreme Fear")**, dragging the index ~7 pts lower. Live SPY OI put/call = 2.29–2.42; the fixed 0.7–1.7 mapping clips everything above 1.7. | `/dashboard/fear-greed` · `signals.putCall` | Miscalibrated fixed band; SPY is a structural hedging vehicle | fixed — ranked vs own recorded history (`MetricSnapshot`), "building history" until 60 sessions |
| L-02 | H | Macro · Inequality | Tab always fails (HTTP 500). | `/macro/inequality` | `NameError: INEQUALITY_COUNTRIES` (list is `INEQ_COUNTRIES`) | fixed |
| L-03 | H | Insider; Markets · Form 4, 13F | Always empty / HTTP 500 "No Form 4 data retrieved". | `/insider/aggregate`, `/market/form4`, `/market/13f` | edgartools: "User-Agent identity is not set" — SEC requires a declared identity | fixed in code (`EDGAR_IDENTITY` setting, explicit 503 reason); **needs an identity configured** |
| L-04 | H | Macro · FX | FX table empty for an hour after a transient failure. | `/macro/fx` · `rates` | D-34: failure envelope `{"rates": {}}` cached 60 min + persisted | fixed (D-01/D-34) |
| L-05 | H | Macro · Commodities | 1W and YTD change **always null**; "Copper ($/lb)" showed 13,542 and "Wheat ($/bu)" 228 (both World Bank **$/mt**); gold row priced from futures under a dead FRED ID; gold/oil ratio empty; 1D change from futures next to a lagging FRED spot price. | `/macro/commodities` | D-15 + mixed-source rows + wrong unit labels | fixed — one source per row (front-month futures), units stated, all windows computed |
| L-06 | H | Cold start | ~25 macro endpoints exceed nginx's 180 s proxy timeout (HTTP 504) on an empty cache; pages show empty panels on first load after install/restart. | many `/macro/*` | Cold fan-out to FRED/WB/IMF under 6-way concurrency | open — ACTIVE_ISSUES P1-14 |
| L-07 | H | Macro · FX heatmap | USD/JPY ≈ 0.0064 with sign-flipped change; "USD/CHF" was CNY, "USD/SEK" was CHF. | `/macro/fx/heatmap` | D-07 | fixed |
| L-08 | M | Macro · FX PPP | Japan's PPP used CPI frozen in 2021; UK/Australia CPI series no longer exist; relative-PPP base assumed Jan-2005 rates were fair. | `/macro/fx/ppp` | D-14, D-17 | fixed — World Bank ICP `PA.NUS.PPP` absolute PPP (2025) vs FRED spot |
| L-09 | M | Macro · Leading | "CB LEI" showed Feb-2020 value of the *Philadelphia Fed* leading index (USSLIND); ISM PMI series does not exist on FRED. | `/macro/leading` | D-16 | fixed — reported unavailable with reason (licensed sources) |
| L-10 | M | Macro · Regime | Growth input OECD CLI (USALOLITONOSTSAM) frozen at Jan-2024; missing momentum defaulted to "falling". | `/macro/regime` | D-17, D-29 | fixed — CFNAI-MA3, staleness guard |
| L-11 | M | Yield | ACM decomposition chart always empty ("unavailable"): the configured URL was the Staff Report 340 **PDF**; `ACMTP10` is not a FRED series, so the term-premium KPI was null. | `/macro/rates` · `acm`, `/yield/curves` · `term_premium` | D-18 | fixed — NY Fed `ACMTermPremium.xls` (+`xlrd`), Kim-Wright `THREEFYTP10` |
| L-12 | M | Macro · Country Risk | ~30% of indicator cells null (debt/GDP, fiscal balance). | `/macro/country-risk` | WDI coverage gaps (`GC.DOD.TOTL.GD.ZS`) | fixed — IMF WEO gap-fill (actual years only), per-cell source |
| L-13 | M | Dashboard · Fear & Greed | Headline 38.9 while the history's same-day point read 49.2. | `/dashboard/fear-greed` | C-21 | fixed |
| L-14 | M | Dashboard · Breadth | 2026-09-29: app 8 highs / 21 lows (close-based, stale bars) vs published 4 / 29. | `/dashboard/breadth` | C-22 | fixed in method (46); after deploy the app reads 9 / 34 vs the cited 4 / 29 — external definition unknown, ACTIVE_ISSUES P2-26 |
| L-15 | L | Credit Conditions | `sofr_iorb = 0.0`, `sloos_ci = 0.0` looked like placeholders. | `/macro/credit-conditions` | — | verified genuine (history varies around 0; July SLOOS print is 0.0) |
| L-16 | H | Dashboard · Macro regime | US "current" regime blank (latest row was the unfinished quarter with no GDP); Japan empty (CPI series ended 2021 and an empty input wiped the frame); euro area timed out (~108 s full-table Eurostat downloads; HICP dataset discontinued 2025-12). | `/macro/regime-series` | D-43 | fixed (47) |
| L-17 | H | Cross-Border | Showed World Bank trade-openness % labelled as USD bank claims; BIS bulk file was 404. | `/crossborder/claims` | D-26, D-28 | fixed (47) — $47.6tn total, GB→US $2.44tn (2026-Q1) |
| L-18 | M | Stability · Currency crisis | Real-FX overvaluation signal never fired (filter matched no rows); legend thresholds (≥4/2–3/0–1) differed from the backend (≥5/3–4/0–2). | `/stability/currency-crisis` | D-27, D-41 | fixed (47) |
| L-19 | M | Stability · Banking; Macro · Energy | Bank Z-score and CO₂ per capita null for every country. | `/stability/banking`, `/macro/energy` | D-20 | fixed (45) |
| L-20 | H | Macro · data (FX) | Exchange-rate indicator empty after Phase 47; monthly FRED/ECB series silently replaced by annual fallbacks. | `/macro/data` | D-49 | fixed (`28d63bb`) |
| L-21 | H | Markets · Analyst | Upside +12% shown as "+0.12%". | `/valuation/full` · `analyst.priceTarget.upsidePct` | C-42 | fixed (50b) |
| L-22 | M | Research · FX-Macro link | "Best lag" was noise: every lag compared the same days. | `/research/fx-macro-link` | C-41 | fixed (50b) |
| L-23 | M | Macro · Inflation, Growth, Financial; Yield | Multi-series charts paired series by array position (wrong dates); quantity-theory chart never drew. | frontend | D-53, C-44 | fixed (50b) |
| L-24 | M | Macro · Positioning | Net commercial "+0" for every contract. | `/macro/positioning` | D-51 | fixed (50b) |

---

## Data findings (D-xx)

| ID | Sev | Location | Finding | Fix | Verdict |
|---|---|---|---|---|---|
| D-01 | H | `cache.py:62-73` | Non-empty failure placeholders/envelopes are cached for 60 min and persisted. | Skip dicts with truthy `error` / `status=="unavailable"`; services return `None`, not 0. | fixed (45) |
| D-02 | H | `breadth_service.py:69-78` | Failed download returns `advancing/declining/newHighs/newLows = 0` → displayed as real zeros and cached. | Return `None` fields + `status: "unavailable"`. | fixed (45/46) |
| D-03 | H | `sources/source_fred.py:36-42`, `source_datareader.py`, `source_ecb.py`, `source_dbnomics.py`, `source_frankfurter.py:96-97`, `routers/macro.py:491-495` | Current partial year averaged/summed and presented as a full-year value (P2-25). First requested year dropped by `pct_change`. | Exclude incomplete year; fetch `start-1`; separate labelled "latest reading". | fixed (47; helper bug fixed in `28d63bb`) |
| D-04 | H | `source_fred.py:21`, `source_datareader.py:22` | US `current_account` = BOPGSTB (goods & services *trade balance*, $mn, summed) shown as "Current Account % GDP" and outranks World Bank. | Remove mapping; WB/IMF supply % GDP. | fixed (47) |
| D-05 | H | `source_dbnomics.py:19,21` | "inflation" = CPI index level; "gdp_growth" = real GDP volume level. | Convert to YoY % or drop. | fixed (47) |
| D-06 | H | `source_imf.py:42,72` | ISO3 truncated to 2 chars → CHN→CH (Switzerland), AUT→AU, KOR→KO. | Proper ISO3→ISO2 map, drop unknowns. | fixed (47) |
| D-07 | H | `routers/macro.py:712-719,737-743,769-772,809` | FX heatmap: DEX*US series already foreign-per-USD but inverted again (USD/JPY ≈ 0.0067, sign-flipped change); DEXCHUS labelled USD/CHF (is CNY), DEXSZUS labelled USD/SEK (is CHF). | Correct labels, no inversion for DEX*US, add DEXSDUS. | fixed (47) |
| D-08 | H | `atlas_service.py:277,405-423` | Cached `dict[int→float]` comes back from SQLite with **string** year keys → all-null timelines after restart. Also `fiscal_service`, `country_risk_service`. | Normalise keys to int on read. | fixed (45) |
| D-09 | M | `routers/macro.py:299`, `macro_expansion_service.py:114` | `pct_change(12)` applied to quarterly GDP → 3-year change labelled YoY. | Frequency-aware `yoy()` helper. | fixed (47) |
| D-10 | M | `source_fred.py:15`, `routers/macro.py:360,391` | `A191RL1Q225SBEA` (q/q SAAR) labelled "Real GDP YoY". | Relabel; use `A191RL1A225NBEA` for completed years. | fixed (47) |
| D-11 | M | `routers/macro.py:600-603` | `change1m = series[-22]` on monthly series → 22 months back / always None. | Frequency-aware lookback. | fixed (47 — commodities rewrite computes each window from dates) |
| D-12 | M | `source_frankfurter.py:72` | `ccy_to_country` overwritten → only last euro country gets EUR series. | Map currency → list of countries. | fixed (47) |
| D-13 | M | `source_ecb.py:65-70` | Euro-area MRR presented as each member's own policy rate. | Label as euro-area rate. | fixed (47) |
| D-14 | M | `routers/macro.py:835` | PPP base spot ~60 days ago vs CPI base 2005. | Common base date. | fixed (47 — World Bank ICP PPP vs FRED spot) |
| D-15 | M | `routers/macro.py:568,582,627` | `GOLDAMGBD228NLBR` discontinued (2022); silently falls back to `GC=F` while row still shows FRED ID. | Verify, replace, attribute honestly. | fixed (47 — Yahoo front-month futures, one source per row) |
| D-16 | M | `routers/macro.py:897,899`; `credit_market.py:11` | `USSLIND`, `NAPM`, `TEDRATE` discontinued. | Verify `observation_end`; replace/remove. | fixed (47 — USSLIND/NAPM reported unavailable; TEDRATE fallback removed) |
| D-17 | M | `macro_regime_service.py:8`, `centralbanks_service.py:20-25`, `policy_service.py:14-19`, `risk_free_service.py:17-28`, `routers/macro.py:767-773`, `regime_service.py:290` | OECD MEI series on FRED (`USALOLITONOSTSAM`, `IRSTCI01*`, `IR3TIB01*`, `*CPIALLMINMEI`) may have stopped updating; no staleness guard. | Shared staleness helper (pattern: `carry_service.py:88-101`) → `stale` flag; replace where possible. | fixed (47 — CLI→CFNAI-MA3, Japan CPI→BIS, risk-free→IRLTLT01; remaining OECD proxies carry `stale`/`proxy` flags; see ACTIVE_ISSUES P2-29) |
| D-18 | M | `yield_curve_service.py:75,170-174`; `rates_service.py:104-117` | `ACMTP10` likely not a FRED series (null term premium); ACM CSV column match looks for "exp". | Verify; use NY Fed CSV or THREEFYTP10 with correct label. | fixed (47 — NY Fed ACM xls + Kim-Wright THREEFYTP10) |
| D-19 | M | `routers/macro.py:569` | `DSLVUSDM` existence unconfirmed. | Verify. | not applicable (series no longer used after D-15) |
| D-20 | M | `source_worldbank.py:39,50` | `EN.ATM.CO2E.PC` replaced in WDI 2024; `GFDD.SI.01` is GFDD not WDI. | Verify; switch source DB/code. | fixed (45 — EN.GHG.CO2.PC.CE.AR5; GFDD via database 32; IC.REG.DURS archived → reported unavailable) |
| D-21 | M | `source_worldbank.py:55`, `atlas_service.py:79` | `income_bottom40` maps to `SI.DST.FRST.20` (bottom 20%). | Sum FRST.20 + 02ND.20. | fixed (47 — relabelled income_bottom20) |
| D-22 | M | `atlas_service.py:42` vs `:101` | `gdp_per_capita` mixes WB constant US$ with IMF current US$ in one series. | One basis, labelled. | fixed (47 — World Bank constant US$ only) |
| D-23 | M | `bulk_data_service.py:266` | IMF WEO projections fill the current year without an estimate flag. | `estimate` flag in provenance/UI. | fixed (47/49 — `estimate` flag on points and in provenance) |
| D-24 | M | `source_bis.py:176` | `get_policy_rate(freq="M")` unsupported by parser → always `[]`. | Parse monthly periods. | fixed (47) |
| D-25 | M | `source_bis.py:230,264,300,332` | Quarterly obs labelled with year only (4 points share a date). | Emit `YYYY-Qn`. | fixed (47) |
| D-26 | M | `source_bis.py:402` | Cross-border claims summed across every dimension → double counting. | Filter to totals. | fixed (47 — BIS SDMX API, totals only; bulk file no longer existed) |
| D-27 | M | `currency_crisis_service.py:97-106`, `source_bis.py:443-451` | EER filter uses non-existent `MEASURE`/annual freq; nominal not real EER; fixed thresholds labelled "KLR (1998)". | Correct filter, REER, honest label. | fixed (47 — real broad EER, monthly; relabelled as a threshold checklist) |
| D-28 | M | `routers/crossborder.py:45` | Fallback puts WB merchandise trade % GDP (ISO3) into `value_usd` (ISO2 elsewhere). | Separate field/label or drop fallback. | fixed (47 — fallback removed; reports unavailable) |
| D-29 | M | `macro_regime_service.py:87,103,130-138` | Growth z-score on LEI *level*; missing LEI defaults to "falling". | Use changes; missing → `None`. | fixed (47) |
| D-30 | M | `yield_curve_service.py:199-201,183` | "Real yield" = nominal − last year's WB CPI; foreign spreads mix monthly OECD with daily DGS10. | US: TIPS (DFII*); foreign: label ex-post + as-of. | fixed for the US (TIPS); foreign real yields labelled ex-post — residual in ACTIVE_ISSUES P2-34 |
| D-31 | M | `routers/macro.py` (`/fama-french`), `source_datareader.py:79,107`, `bulk_data_service.py:201` | Shape and units differ by path (monthly decimals vs annual percent). | One shape/unit. | fixed (47) |
| D-32 | M | `risk_free_service.py:16-28` | US uses 10y; other countries 3m/policy → maturity mismatch feeding valuations. | Explicit short vs long rf per use. | fixed (47 — 10Y yields; proxies and fallbacks flagged) |
| D-33 | M | `discount_rates.py:225,244,283`, `options_engine.py:45`, `risk_free_service.py:33-47,104` | Hard-coded fallbacks (rf 4%/5%, ERP 5%, tax 21%) served and cached as real data. | Keep fallback, flag it, don't cache as real. | fixed (47/49 — fallbacks flagged in responses and provenance) |
| D-34 | M | `source_frankfurter.py:34,57`, `carry_service.py:185,239`, `rates_service.py:271-280`, `macro_expansion_service.py:84` | Failure envelopes cached (e.g. `inverted: False` on failure). | Covered by D-01 fix + explicit error keys. | fixed (45) |
| D-35 | M | `routers/macro.py:389,436,937,986`, `short_interest_service.py:44`, `rates_service.py:245-250` | `asOf = date.today()` instead of observation date. | Real observation date or omit. | fixed (45/47) |
| D-36 | M | `frontend/components/DataFreshnessBadge.tsx:6` | Parses `YYYY-MM-DD` as UTC midnight. | Parse as local date. | fixed (45) |
| D-37 | M | `metrics.py:109-110`, `corporate_health_service.py:582-585`, `cross_asset_service.py:83,209` | Missing debt/cash → 0; NaN correlation → 0.0. | Propagate `None`. | fixed (45) |
| D-38 | M | `yfinance_service.py:298-317` | Beta fallback (2y daily) not comparable to Yahoo 5y monthly and not flagged. | Flag computed beta in provenance. | accepted — computed beta flagged in provenance (`beta` fallback note) |
| D-39 | L | `source_datareader.py:12` | FRED data labelled "pandas-datareader". | Label as FRED (via pandas-datareader). | fixed (47) |
| D-40 | L | `yfinance_service.py:190` | Unknown currency defaults to "USD". | `None` when unknown. | open (Low) — ACTIVE_ISSUES P2-34 |
| D-41 | M | `frontend/components/stability/CurrencyCrisisPanel.tsx` | Legend thresholds disagreed with the backend's red/yellow cut-offs. | Match backend (≥5 / 3–4 / 0–2). | fixed (47) |
| D-42 | M | `regime_service._fetch_eurozone` | Unfiltered Eurostat tables (~2 min); `prc_hicp_midx` ended 2025-12. | Filtered API queries; `prc_hicp_minr` RCH_A. | fixed (47) |
| D-43 | H | `regime_service.regime_series` | "Current" = unfinished quarter; Japan CPI dead; one empty input wiped all rows; uncached. | Latest classified period; BIS CPI; robust join; cached. | fixed (47) |
| D-44 | M | business/energy/fiscal/inequality/labor/trade/supply-chain services | `asOf` = today and `latestYear` = end of request for 2021–2024 data. | Per-KPI `periods`, payload dated by its newest data year. | fixed (45) |
| D-45 | M | `supply_chain_service.py` | Composite of one indicator presented as the mean of two. | Require both. | fixed (45) |
| D-46 | M | `cache.clear_all` | A failed SQLite flush reported success; stale rows kept being served. | Report the error. | fixed (49) |
| D-47 | M | `ma_service.py` | "Deals" are headlines; acquirer/target are the first upper-case words. | Disclosed in provenance; relabel/real source pending. | open — ACTIVE_ISSUES P2-27 |
| D-48 | M | `ai_service.py`, `routers/ai.py` | Summaries ungrounded (no app data sent); cached rows showed a fresh time; daily briefing served forever. | UI disclosure; real timestamps; per-day key. | partly fixed (50b) — grounding open, P2-28 |
| D-49 | H | `sources/_annual.py` | Grouping by the unfiltered index raised whenever a running year existed; adapters returned nothing. | Group the filtered series; tests with a running year. | fixed (`28d63bb`) |
| D-50 | M | `atlas_service.get_timeline` | Supply-chain layer matched no country (ISO2 vs numeric id); timeline capped at 2024. | ISO3 join, value on its data year; end = last complete year. | fixed (50b) |
| D-51 | H | `cot_service._parse_cot` | Net commercial hard-coded 0; absent contracts reported 0 positions. | Read commercial columns; missing → null. | fixed (50b) |
| D-52 | M | `frontend/components/markets/DcfPanel.tsx` | Hard-coded country rates shown until/unless the API answered. | Removed. | fixed (47) |
| D-53 | M | Inflation/Growth/Financial tabs, Yield page | Series paired by array index. | Date join (`lib/series.ts`). | fixed (50b) |
| D-54 | L | `components/macro/CountrySelector.tsx` | Bare `/api` fetch broke country names in the desktop build. | Use the configured API base. | fixed (50b) |
| D-55 | H | `routers/macro._yoy`, `macro_expansion_service`, `regime_service._cpi_yoy_quarterly` | Row-count YoY lag (`pct_change(12)`) spans 13 months across a missing observation; US CPI read 3.71% vs 3.35% (Oct-2025 print missing). | Date-matched lag (`_annual.yoy_pct`). | fixed (`96aa195`) |
| D-56 | M | `macro_service._source_order` | Debt series switched from World Bank central-government to IMF general-government mid-line. | IMF general government first. | fixed (`96aa195`) |

---

## Calculation findings (C-xx)

| ID | Sev | Location | Finding | Fix | Verdict |
|---|---|---|---|---|---|
| C-01 | H | `dividend_service.py:103-107` | DPS = per-share dividend ÷ shares (≈1e-10) → payout "safe" for every stock; FCF payout uses OCF and mixes per-share with total. | DPS = TTM dividends; payout = DPS/EPS; FCF payout = DPS·shares/FCF. | fixed (48) |
| C-02 | H | `dividend_service.py:56-65` | Partial current calendar year used as annual dividend → CAGR, streak (breaks to 0), DDM wrong. | Drop incomplete year; TTM for current. | fixed (48) |
| C-03 | H | `snowflake_service.py:130-134` | Coverage = fcfYield (decimal) / divYield (percent) → ~100× too small, min score for all. | Common units. | fixed (48) |
| C-04 | H | `risk_parity_service.py:138-140` | "CAGR" = total return / years (arithmetic). | `(1+R)^(1/y) − 1`. | fixed (48) |
| C-05 | H | `risk_parity_service.py:302-305` | Month-boundary returns dropped for strategy but kept for 60/40 benchmark. | Compute returns before segmenting. | fixed (48) |
| C-06 | H | `carry_service.py:269-302` | Carry backtest: today's ranking applied to history (look-ahead); no carry accrued. | Monthly rebalance on then-available carry; accrue differential. | fixed (48) |
| C-07 | H | `options_engine.py:497-508` | IV Rank/Percentile computed across expiries on one day, not over 252-day IV history. | Persist daily IV30; `null` until enough history. | fixed (48 — recorded IV30 history, null until 60 sessions) |
| C-08 | H | `portfolio.py:663,712,720` | Black-Litterman mixes excess and total returns; rf subtracted twice; prior uses user weights. | Consistent excess returns; market-cap prior. | fixed (48) |
| C-09 | H | `portfolio.py:366-369` | Kelly uses log-mean (0.5 too low) and ignores rf; test pins bug. | `(μ_arith − rf)/σ²`; fix test. | fixed (48) |
| C-10 | H | `fundamentals.py:232,317-321` | Piotroski F7 compares shares with itself → always passes. | Real prior-year shares. | fixed (48) |
| C-11 | H | `fundamentals.py:435` | Ohlson SIZE uses log(TA $) not log(TA $mn / GNP deflator) → P(default) ≈ 0 everywhere. | Correct scaling; fix test. | fixed (48) |
| C-12 | H | `corporate_health_service.py:395-405` | Beneish missing index adds 0 instead of neutral 1.0 → biased to "not flagged". | Neutral values; require coverage. | fixed (48) |
| C-13 | H | `corporate_health_service.py:148-158,291-301` | Quarterly fallback: `iloc[3]` = 3 quarters back; single quarter vs annual → SGI≈4, false manipulator flag. | 4 quarters, TTM vs TTM. | fixed (48) |
| C-14 | H | `corporate_health_service.py:181-242` | Piotroski: missing prior counts as pass (up to +6). | Missing → not scored. | fixed (48) |
| C-15 | H | `valuation_engine.py:149-155` | Quarterly YoY `earningsGrowth` used as 10-year growth, 50% cap. | Annual/long-run growth with sane cap. | fixed (48) |
| C-16 | H | `dcf_engine.py:70-75`, `valuation_engine.py:116-124` | ADRs: statement currency vs price currency not converted. | FX-convert `financialCurrency` → `currency`. | fixed (48) |
| C-17 | M | `metrics.py:49-50`, `advanced_risk.py:52-58`, `portfolio.py:76-77` | Sortino downside deviation = std of negatives around own mean. | `sqrt(mean(min(r−MAR,0)²))` over all obs. | fixed (48) |
| C-18 | M | `portfolio.py:113` | Drawdown compounds log returns as simple. | Use simple returns. | fixed (48) |
| C-19 | M | `portfolio.py:263,330,400,791` | Portfolio return = weighted sum of log returns; NaN handling inconsistent. | Simple returns; consistent alignment. | fixed (48) |
| C-20 | M | `portfolio.py:57` | `fillna(0)` gives pre-IPO holdings 0% return with full weight. | Re-normalise weights over available assets. | fixed (48 — per-day reweighting over available assets) |
| C-21 | M | `feargreed_service.py:77,108,176-185` | Headline (full-sample percentile, 7 signals) ≠ history (rolling, 5 signals). | Same definitions. | fixed (46) |
| C-22 | M | `breadth_service.py:89-100` | Highs/lows on closes, stale last bar per symbol (dropna), trailing partial session. | Session-aligned, intraday H/L. | fixed (46) — residual count gap in ACTIVE_ISSUES P2-26 |
| C-23 | M | `breadth_service.py:22-25,59-62` | Survivorship; Summation level depends on window start. | PIT constituents; warm-up. | accepted — warm-up fixed (46); survivorship documented, ACTIVE_ISSUES P2-35 |
| C-24 | M | `fundamentals.py:267-270` | F2 duplicates F1; ΔROA missing. | Implement ΔROA. | fixed (48) |
| C-25 | M | `corporate_health_service.py:277` | Typo "Total Liabilities Net Minority Investment" (should be Interest). | Fix key. | fixed (48) |
| C-26 | M | `corporate_health_service.py:286,313` | DEPI uses accumulated depreciation, not expense. | Use D&A expense. | fixed (48) |
| C-27 | M | `dcf_engine.py:70` | Levered FCF (or OCF) discounted at WACC then net debt subtracted. | Unlevered FCF proxy or label; no OCF substitution. | fixed (48 — no OCF substitution; basis disclosed) |
| C-28 | M | `metrics.py:175-210` | Inventory turnover uses revenue; FCF margin mixes TTM and annual. | COGS; matched periods. | fixed (48) |
| C-29 | M | `metrics.py:131-137` | Altman Z: missing inputs → 0; manufacturing coefficients for all. | `None` if incomplete; Z''/label for non-manufacturers. | fixed (48 — null when incomplete; financial-firm note kept; no Z'' variant) |
| C-30 | M | `options_engine.py:73-160,294-298` | Black-Scholes without dividend yield `q`. | Add `q`. | fixed (48) |
| C-31 | M | `edgar_service.py:96,165`, `insider_aggregator.py:65-72` | 50-transaction cap per ticker biases buy/sell ratio. | Paginate / window-based cap. | fixed (48) |
| C-32 | M | `backtest_signals.py:136-138` | Universe = first 120 alphabetical current constituents. | PIT universe, no alphabetical cut. | fixed (48) |
| C-33 | M | `frontend/components/risk/RiskKPIRow.tsx:51,55,67` | "30-day window" (actually selected period), hard-coded "(3Y)", "Parametric" VaR (actually historical). | Correct labels. | fixed (48) |
| C-34 | L | `options_engine.py:476` | IV30 interpolated in vol, not total variance. | → ACTIVE_ISSUES. | open (Low) — ACTIVE_ISSUES P2-34 |
| C-35 | L | `options_engine.py:891` | MC "VaR95" is a payoff percentile; RNG unseeded. | → ACTIVE_ISSUES. | fixed label (50b); RNG still unseeded — P2-34 |
| C-36 | L | `advanced_risk.py:160-163,191` | Calmar uses log-mean×252; R² mixes samples. | → ACTIVE_ISSUES. | open (Low) — P2-34 |
| C-37 | L | `dividend_service.py:149`, `valuation_engine.py:218` | DDM hard-coded rf 4.5%; forward dividend grown twice. | → ACTIVE_ISSUES. | DDM rate exposed (50b); double growth open — P2-34 |
| C-38 | L | `realized_moments_service.py:57-59` | Garman-Klass ignores overnight gaps. | → ACTIVE_ISSUES. | open (Low) — P2-34 |
| C-39 | L | `discount_rates.py:287` | Sharpe/frontier use 10y as rf. | Covered by D-32. | fixed with D-32 |
| C-40 | L | frontend (20 files) | Undefined CSS vars `--color-*`, class `text-muted`. | → ACTIVE_ISSUES. | open (Low) — P2-34 |
| C-41 | M | `cross_asset_service.get_fx_macro_link` | `.corr()` of two `.iloc` slices realigns by date, undoing the lag. | `shift(lag)`; test with a known 3-day lead. | fixed (50b) |
| C-42 | H | `frontend/components/markets/AnalystPanel.tsx` | Fraction printed as percent. | ×100. | fixed (50b) |
| C-43 | M | `frontend/components/portfolio/FFAttribution.tsx` | Read `factor`; API sends `name` (blank column). | Use `name`. | fixed (50b) |
| C-44 | M | `frontend/components/macro/InflationTab.tsx` | Quantity-theory chart read non-existent fields. | Use `nominalGdpYoY` / `m2YoY`. | fixed (50b) |
| C-45 | M | `movers_service.top_movers` | Adjusted closes from a separate download: 1-day change dividend-adjusted, high/low lists disagreed with breadth counts. | Reuse breadth's session-aligned prices. | fixed (49) |
| C-46 | M | Options/risk Monte Carlo, GARCH, carry, DDM labels | Payoff percentiles labelled VaR; annualised vol labelled 1D; full-period vol labelled 30d; DDM rate stated as 9.5%. | Correct labels; expose DDM rate. | fixed (50b) |

**Checked and correct (no change):** FRED percent→decimal risk-free handling; Black-Scholes price & Greeks (θ/365, vega/ρ per 1%); CRR tree; max pain; Nelson-Siegel λ; 5y5y via T5YIFR; McClellan RANA×1000 EMA19−EMA39; Fama-French ÷100; backtest t→t+1 alignment; 12-1 momentum offsets; risk-parity weights use prior data only; Hurst, OU, Engle-Granger; `regime_service` GDP/CPI YoY.

---

## Coverage ledger

*Grouped by router with the services and adapters behind it. "Verified · provenance" means each value's inputs and formula were read from the code to write its provenance ref, findings were fixed or logged, and the endpoint was called live. List-returning endpoints cannot carry a map (ACTIVE_ISSUES P2-32).*

| Module | Providers | Verdict | Findings | Evidence |
|---|---|---|---|---|
| dashboard (breadth, indices, fear-greed, movers, constituents) | Yahoo, FRED, Wikipedia | verified · provenance | L-01, L-13, L-14, C-21–C-23, C-45 | backend tests + live endpoint scan 2026-10-01 (provenance present on 126 endpoints) |
| market (prices, quote, events, news, sectors, relative-strength, fx-rates, risk) | Yahoo | verified · provenance | D-40 | backend tests + live endpoint scan 2026-10-01 (provenance present on 126 endpoints) |
| market_data (13F, Form 4, composite, short interest) | SEC EDGAR, Yahoo | verified · provenance (SEC needs identity) | L-03, C-31 | backend tests + live endpoint scan 2026-10-01 (provenance present on 126 endpoints) |
| ratios, valuation (capm-dcf, dcf, full, factors, risk-free-rates) | Yahoo, FRED, Damodaran, Ken French | verified · provenance | C-15, C-16, C-27, C-28, D-32, D-38, L-21 | backend tests + live endpoint scan 2026-10-01 (provenance present on 126 endpoints) |
| snowflake, technicals, treemap, sector, screener | Yahoo, Wikipedia | verified · provenance (batch/list endpoints excepted) | C-03, P2-31, P2-32 | backend tests + live endpoint scan 2026-10-01 (provenance present on 126 endpoints) |
| dividend, corporate, insider, mergers | Yahoo, SEC EDGAR, Finnhub | verified · provenance | C-01, C-02, C-10–C-14, D-47 | backend tests + live endpoint scan 2026-10-01 (provenance present on 126 endpoints) |
| options | Yahoo option chains, EconoSift IV30 record | verified · provenance (list endpoints excepted) | C-07, C-30, C-34, C-35 | backend tests + live endpoint scan 2026-10-01 (provenance present on 126 endpoints) |
| portfolio, risk, scenario | Yahoo, FRED, Ken French | verified · provenance (three list endpoints excepted) | C-08, C-09, C-17–C-20, C-36 | backend tests + live endpoint scan 2026-10-01 (provenance present on 126 endpoints) |
| research (risk parity, carry, momentum, moments, DuPont, event study, factor regime, cross-asset, FX-macro, multi-country, backtest) | Yahoo, FRED, Ken French, Wikipedia, Fed Board | verified · provenance | C-04–C-06, C-32, C-38, C-41 | backend tests + live endpoint scan 2026-10-01 (provenance present on 126 endpoints) |
| macro (43 endpoints) + macro services | FRED, World Bank, IMF, ECB, DB.nomics, Frankfurter, BIS, Eurostat, NY Fed, CFTC, Yahoo | verified · provenance | D-03–D-17, D-21–D-25, D-29, D-31, D-42–D-45, D-49, D-51, D-53 | backend tests + live endpoint scan 2026-10-01 (provenance present on 126 endpoints) |
| yield_curve, policy, sovereign, credit | FRED, Fed Board (Kim-Wright), World Bank, IMF | verified · provenance | D-18, D-30, P2-29, P2-30 | backend tests + live endpoint scan 2026-10-01 (provenance present on 126 endpoints) |
| stability, crossborder | World Bank (WDI, GFDD), BIS (EER, LBS, credit gaps) | verified · provenance | D-20, D-26–D-28, D-41, L-17–L-19 | backend tests + live endpoint scan 2026-10-01 (provenance present on 126 endpoints) |
| atlas, factbook, calendar | World Bank, IMF, CIA Factbook, REST Countries, FRED, Finnhub, Yahoo | verified · provenance | D-08, D-50, P1-15 | backend tests + live endpoint scan 2026-10-01 (provenance present on 126 endpoints) |
| ai | Google Gemini (no app data sent) | issue disclosed | D-48 | backend tests + live endpoint scan 2026-10-01 (provenance present on 126 endpoints) |
| admin, wiki, search | n/a (configuration, reference text) | not applicable — no market data | — | backend tests + live endpoint scan 2026-10-01 (provenance present on 126 endpoints) |
| sources/* adapters (FRED, datareader, ECB, World Bank, IMF, DB.nomics, Frankfurter, BIS) | as named | verified | D-03–D-06, D-12, D-13, D-24–D-27, D-49 | backend tests + live endpoint scan 2026-10-01 (provenance present on 126 endpoints) |
| cache.py, provenance.py | — | verified (tests: test_cache, test_provenance) | D-01, D-46 | backend tests + live endpoint scan 2026-10-01 (provenance present on 126 endpoints) |

---

## Primary-source spot checks

| Metric | App value | Primary source value | Source & retrieval date | Match |
|---|---|---|---|---|
| US CPI inflation, Aug 2026 YoY | 3.71% | 3.35% | FRED API `CPIAUCSL`, 2026-10-01 | ✗ → fixed in `96aa195` (row-count lag spanned 13 months across the missing Oct-2025 print; lag now matched by date); re-checked after rebuild: app 3.353% ✓ |
| US real GDP, 2026-Q2 YoY | 2.19% | 2.19% | FRED API `GDPC1`, 2026-10-01 | ✓ |
| US real GDP growth 2023 / 2024 / 2025 | 2.9 / 3.0 / 2.3 | 2.9 / 3.0 / 2.3 | FRED `A191RL1A225NBEA`, 2026-10-01 | ✓ (no partial 2026 value) |
| US current account, % GDP 2023 / 2024 / 2025 | −3.34 / −4.05 / −3.63 | −3.34 / −4.05 / −3.63 | World Bank API `BN.CAB.XOKA.GD.ZS`, 2026-10-01 | ✓ (was the $mn trade balance before Phase 47) |
| USD/JPY, USD/CNY, USD/CHF on 2026-09-25 | 157.18 / 6.711 / 0.8282 | 157.18 / 6.711 / 0.8282 | FRED API `DEXJPUS` / `DEXCHUS` / `DEXSZUS`, 2026-10-01 | ✓ (was ≈0.0064 for USD/JPY, CNY/CHF mislabelled) |
| GDP growth 2023: Germany / Brazil / India (Atlas) | −0.87 / 3.24 / 7.21 | −0.87 / 3.24 / 7.21 | World Bank API `NY.GDP.MKTP.KD.ZG`, 2026-10-01 | ✓ |
| Gov. debt % GDP 2023 / 2024: China, Austria | 84.1 / 90.4; 77.8 / 79.2 | 84.1 / 90.4; 77.8 / 79.2 | IMF DataMapper `GGXWDG_NGDP`, 2026-10-01 | ✓ (China read Switzerland's 37.3 / 40.5 before the ISO3 fix) |
| Gov. debt % GDP 2023 / 2024: Korea | 48.6 / 47.8 (World Bank, central gov.) then IMF from 2025 | 50.5 / 49.7 (IMF, general gov.) | IMF DataMapper, 2026-10-01 | ✗ → fixed in `96aa195`: IMF general-government first for every country |
| Cross-border claims 2026-Q1: total; GB→US | $47.6tn; $2.44tn | $47.6tn; $2.44tn | BIS SDMX API `WS_LBS_D_PUB`, 2026-10-01 | ✓ (page showed World Bank trade % as USD before) |
| S&P 500 new 52-week highs / lows, 2026-09-29 | 9 / 34 | 4 / 29 (cited report) | user-supplied report, definition unknown | ✗ unexplained — ACTIVE_ISSUES P2-26 |
| KO, JNJ dividend per share / payout | — | — | issuer investor-relations pages | not checked: issuer pages were not retrieved in this pass; payout maths covered by known-value tests (C-01, C-02) |

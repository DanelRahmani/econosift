# Markets page calculation audit — 2026-10-01

Read-only audit of every computed number on `/markets` (Overview, Technicals, Valuation,
Ratios, Sectors, Treemap). Run by a Sonnet sub-agent against the live Docker stack, with
figures recomputed independently from raw yfinance / FRED / Ken French data. Tickers:
AAPL, MSFT, JPM (bank), 005930.KS, ASML.AS, plus TSM and NVO as ADR probes.

**Status: findings, not yet independently re-verified.** Each item is confirmed (or
rejected) with a known-value test when it is fixed. Items already tracked in
`ACTIVE_ISSUES.md` / `2026-10-econosift-data-audit.md` are not repeated.

## High — wrong numbers a user would act on

| ID | Finding | Where | Example |
|---|---|---|---|
| M-01 | ADRs/cross-listings: statement-currency figures (FCF, revenue, EBITDA, liabilities) divided by USD market cap / price; Yahoo's own ADR multiples passed through. `to_price_currency` only protects the DCF and 8 models. | `metrics.py:118-144, 224-233`; `routers/valuation.py:45-46` (`_kpis`) | TSM FCF yield 30.9 % (≈0.97 %), Altman Z 3.06 (≈20.4), P/S 0.53 (≈19.9); NVO EV/EBITDA 1.5 (≈6.9). TSM RIM $12.8 / Graham $38 vs price $456 |
| M-02 | DCF not locked when FCF ≤ 0 or for banks; composite goes negative; negative EV/FCF ranks as best value in Snowflake | `dcf_engine.py:205-215`; `valuation_engine.py:181-214, 544-594`; `snowflake_service.py:219-222` | JPM DCF −$1,966.74, Bear/Base/Bull inverted, composite −$721.87 (−318 %), Snowflake value 9.2/10 from EV/FCF −4.85 |
| M-03 | DDM: earnings growth (≤15 %) used as perpetual dividend growth, clipped to ke − 0.5 pp | `valuation_engine.py:231-238` | MSFT DDM $854.86 vs price $512.90; JPM $769 vs $331 |
| M-04 | Technicals: 1mo/3mo/6mo return HTTP 500 (tz-naive vs tz-aware compare); 1y/2y windows count rows vs calendar days and show far more history | `technicals_service.py:111-113` | AAPL 1y = 344 bars from 2025-05-19 |
| M-05 | Residual-income model explodes for high-ROE buyback companies (TTM ROE compounding, retention ignores buybacks) | `valuation_engine.py:388-426` | AAPL RIM $340.98 (ROE 148.8 %) |

### Status of the High findings (Phase 53, 2026-10-01)

All five reproduced against the live stack or by direct computation. Live values after the fix are from the rebuilt stack.

| ID | Status | Before → after (live) | Tests |
|---|---|---|---|
| M-01 | ✅ fixed | TSM FCF yield 30.9 % → 0.97 %, Altman Z 3.06 → 20.3, P/S 0.53 → 17.0 (TTM revenue; the audit's 19.9 used annual revenue), P/B 93.8 → 14.1, book value 4.86 → 32.4, Graham Number $38 → $99, RIM $12.8 → $39.6; NVO EV/EBITDA 1.5 → 6.93 | `test_metrics_currency.py`, `test_screener_currency.py`, `test_fx_minor_units.py`, `TestAdrBookValue`, `test_fallback_value_inputs_*` |
| M-02 | ✅ fixed | JPM DCF −$1,966.74 → null "not meaningful for banks"; composite −$721.87 → +$229; EPV locked for banks; Snowflake EV/FCF 9.2/10 → n/a "not meaningful: negative multiple"; KPI EV/FCF −4.85 → n/a | `TestDcfLockAndComposite`, `TestNonPositiveGuard`, `test_negative_*`, `TestNegativeFcfEvMultiple` |
| M-03 | ✅ fixed | MSFT DDM $854.86 → ≈$96; JPM $769 → $162 | `TestDdmSustainableGrowth` |
| M-04 | ✅ fixed | AAPL 1mo/3mo/6mo HTTP 500 → 200; 1y 344 bars from 2025-05-19 → 252 bars from 2025-10-01 | `test_technicals_display_window_is_a_calendar_window` |
| M-05 | ✅ fixed | AAPL RIM $340.98 → n/a "not meaningful: ROE above 100% on a buyback-shrunk book" (ROE now capped at 25 % and faded to ke for other firms) | `TestRimNormalised` |

None rejected. Found while fixing: a half-failed Yahoo `info` call was cached for up to a day (fixed, `test_yf_info_partial.py`); `/api/valuation/capm-dcf` keeps an unlocked DCF but no page calls it (P3-28); Altman Z on `/corporate` and dividend FCF coverage still mix currencies (P2-38).

## Medium — misleading values, labels or edge cases

| ID | Finding | Where |
|---|---|---|
| M-06 | Quote-card change % uses `fast_info.previous_close` (unreliable): AAPL +0.85 % vs +1.10 % (Treemap on the same page shows +1.10 %) | `yfinance_service.py:188-189, 205-208` |
| M-07 | YTD base = first January close instead of prior year-end close (XLE 37.39 % vs 40.28 %) | `sector_service.py:79, 115-117`; `treemap_service.py:55-61` |
| M-08 | Sector table 3M/6M off by one session vs the chart (XLK 8.52 % vs 5.58 %) | `sector_service.py:179-180` vs `:119` |
| M-09 | South Korea maps to "South Korea" but the Damodaran key is "Korea" → US ERP and tax used for Samsung | `discount_rates.py:43` |
| M-10 | Non-US valuations use US 10Y rf and local-index betas (ASML β 2.23 vs ^AEX; unmapped suffixes fall back to ^GSPC). *Needs owner confirmation of intent.* | `discount_rates.py`; `yfinance_service.py:12-17` |
| M-11 | Live Damodaran ERP download reads the wrong sheet (always falls back to the static file) and has an undefined `log` → NameError → 500 if the download raises | `discount_rates.py:99-108, 148, 157` |
| M-12 | Forward-EPS fallback uses the current-year (`0y`) estimate instead of `+1y` (Samsung Fwd EPS ₩47,965 beside Fwd P/E 3.89x — inconsistent) | `yfinance_service.py:252-262` |
| M-13 | Snowflake health uses a crippled 4-point Piotroski; non-index tickers get the whole universe as "sector peers" (Yahoo vs GICS names); FCF-coverage display unit mix | `snowflake_service.py:347-367, 464-466` |
| M-14 | Beneish M-Score always "not available" on Markets although `/corporate/health` computes it (AAPL −2.29); note rendered as a green badge | `fundamentals.py:378-397`; `ValuationKpiPanel.tsx:85-97` |
| M-15 | Ohlson O-Score: SIZE uses statement-currency assets (KRW/JPY not converted); "P(default) 9.8 %" shown green for AAPL | `fundamentals.py:468-475`; `ValuationKpiPanel.tsx:105` |
| M-16 | Two different DCFs on one tab (panel defaults WACC 9 % / g 8 % for every ticker); region selector labelled "WACC" is rf + ERP (β = 1) | `DcfPanel.tsx:65-70`; `ValuationTab.tsx:48-53, 112` |
| M-17 | Three different betas per ticker (1y local index / Yahoo 5y monthly / 2y daily) with wrong labels | `ratios.py:15`; `lib/ratioGuide.ts:242` |
| M-18 | Sharpe/Sortino use mean log returns and a hard-coded 4 % rf (MSFT −0.14 vs +0.02 with simple returns) | `metrics.py:41-43, 53-55`; `markets/page.tsx:157` |
| M-19 | Pivot points one period stale when the last bar completes a period (AAPL monthly P 313.26 vs 329.42) | `technicals_service.py:381-411` |
| M-20 | Treemap double-counts dual-class issuers (GOOGL + GOOG ≈ 8.4T of area) | `yfinance_service.get_market_caps` |
| M-21 | Analyst "Forward Estimates" print raw numbers (revenue `113624521680.00`, growth `0.07`, counts `27.00`) | `AnalystPanel.tsx:402-405` |
| M-22 | Overview risk cards show the first ticker only, with no ticker, horizon (1-day) or sample size label | `markets/page.tsx:289-309` |
| M-23 | Bank metrics shown as normal (JPM DSO 224 days, FCF margin −81 %); Piotroski bands not scaled to maxScore 7 | `metrics.py:196-223`; `fundamentals.py:536-578`; `ValuationKpiPanel.tsx:68-82` |

### Status of the Medium findings (Phase 54, M-10 in Phase 55, 2026-10-02)

All reproduced. Live values after the fix are from the rebuilt stack on 2026-10-02 (cache cleared first); "before" is the audit's or the fixing agent's live value. A fresh-context spec review of the whole diff found seven more wrong outputs, fixed with tests (listed under the table).

| ID | Status | Before → after (live) | Tests |
|---|---|---|---|
| M-06 | ✅ fixed | AAPL quote card −1.53 % vs Treemap −1.22 % (from `fast_info.previous_close`) → quote −0.81 % = Treemap −0.81 % (last two daily closes) | `test_yf_quotes_m06_m12_m20.py` |
| M-07 | ✅ fixed | XLE YTD 38.38 % (first January close) → 43.02 % in the table **and** the Sectors heatmap (prior year-end close). The heatmap's own endpoint still used the January base (40.07 %) until the live gate caught it. | `test_sector_returns_m07_m08.py` (incl. `test_sector_chart_endpoint_ytd_uses_prior_year_end`) |
| M-08 | ✅ fixed | XLK 3M table 7.14 % vs chart 8.91 % → 9.66 % in both (63 sessions) | `test_sector_returns_m07_m08.py` |
| M-09 | ✅ fixed | Samsung ERP 4.46 % (US) → 4.869 % (Korea), tax 21 % → 26.4 % | `TestKoreaMapping` |
| M-10 | ✅ fixed (Phase 55, owner chose option B + Blume) | ASML.AS rf 5.26 % (US DGS10) → 3.285 % (NL 10Y, Aug 2026, labelled); beta 2.235 → 1.83 Blume (raw 2.24 vs ^AEX); ke 14.72 % → 11.03 %; WACC 14.68 % → 11.01 %, all EUR. Samsung uses the Korean 10Y 4.286 %. 0700.HK: no FRED 10Y → rf, ke, WACC null with the reason, models lock on it (the US rate is never substituted). USD-priced listings (AAPL, TSM ADR) unchanged on DGS10. `.BR` now maps to ^BFX (was Brazil's ^BVSP), plus 12 more local indexes. | `test_local_discount_rate_m10.py` |
| M-11 | ✅ fixed | Live Damodaran parse read the 'Country Lookup' calculator (always fell back to the static file), `log` undefined → reads 'Regional breakdown' (157 countries, matches the static JSON), `log` defined, 30 s timeout | `TestLiveDamodaranParse` |
| M-12 | ✅ fixed | Samsung forward EPS ₩47,965 (`0y`) → ₩71,030 (`+1y`) | `test_yf_quotes_m06_m12_m20.py` |
| M-13 | ✅ fixed | Snowflake Piotroski 3/4 → full 9 tests; TSM "sector peers" 527 (whole universe) → 84 GICS peers (or none + `peerGroup.reason`, shown on the card); FCF coverage 0.067 → 6.7× | `test_snowflake_m13.py` |
| M-14 | ✅ fixed | AAPL Beneish "not available" → −2.29, "not flagged" (reuses `/corporate/health`, cut-off −2.22, quarterly prior-year fallback); null + note for banks | `test_fundamentals_m14_m15.py` |
| M-15 | ✅ fixed | Ohlson SIZE in statement currency → USD (null + reason without an FX rate); "P(default) 9.8 %" green → neutral band 5–50 % | `test_fundamentals_m14_m15.py` |
| M-16 | ✅ fixed | AAPL DcfPanel defaulted to WACC 9 % / g 8 % → seeded from the engine's DCF: grid $168.40 = panel default $168.40; region selector relabelled "Cost of equity (β = 1)" | tsc + live browser check |
| M-17 | ✅ fixed | Three unlabelled betas → "Beta (5y mo.)", "Beta (2y daily, local index)" (Blume-adj. for non-USD), Ratios "1y daily vs ^GSPC, n=250" | tsc + live browser check |
| M-18 | ✅ fixed | Sharpe/Sortino on mean log returns with a hard-coded 4 % → simple returns, rf FRED DGS3MO 4.20 % (`riskFree`/`riskFreeSource` in the response); MSFT Sharpe −0.14 → +0.04 | `test_ratios_m18_m23.py` |
| M-19 | ✅ fixed | AAPL monthly pivot P 313.26 → 329.42 (last completed month) | `test_technicals_m19.py` |
| M-20 | ✅ fixed | Treemap GOOGL + GOOG (≈8.4T of area) → GOOGL only (also BRK-A/FOX/NWS…; Black-Litterman keeps every class) | `test_yf_quotes_m06_m12_m20.py` |
| M-21 | ✅ fixed | Forward estimates `113624521680.00`, `0.07`, `27.00` → compact money, 7.0 %, 27 (top-level growth fractions and forward EPS too) | tsc |
| M-22 | ✅ fixed | Overview risk cards for the first ticker only → one block per ticker: "1y window · 250 daily returns", "1-day VaR 95%", rf and source, beta basis | tsc + live browser check |
| M-23 | ✅ fixed | JPM DSO 224 days, FCF margin −81 % → n/a "not meaningful for banks: …"; Piotroski bands scaled to maxScore (and a 0-of-0 score is neutral, not green) | `test_ratios_m18_m23.py`, `test_fundamentals_m14_m15.py` |

None rejected. Spec review findings, fixed: Beneish lacked `/corporate/health`'s quarterly prior-year fallback; Ohlson read a converted bundle as USD when its FX lookup failed; Snowflake scored Piotroski 0/10 when no test could be evaluated; the rf label was looked up separately from the rate (a FRED retry could label the 4 % fallback "FRED DGS3MO"); top-level growth fractions printed raw; the Sharpe/Sortino guide still said log returns; the DCF panel dropped the region override on a ticker switch. Low items fixed alongside: P3-16 (Bollinger ddof 0), P3-17 shift (Senkou displaced 26), P3-27, P3-28. Follow-ups are P3-29 … P3-34 in `ACTIVE_ISSUES.md`.

## Low
Bollinger uses sample std (ddof=1); Ichimoku cloud shifted 25 not 26 and the forward
cloud is never emitted; Fibonacci always measured from the swing high, on closes;
52-week range differs between tabs (closes vs intraday); Net Debt/EBITDA ignores
short-term investments; ROE FY vs TTM and ROIC tax 21 % vs WACC tax 25 %;
`debtToEquity` percent fallback (untriggered); analyst surprise fallback is a fraction;
Fama-French `asOf` says today while data ends 2026-08-31; short-interest "sp500" is a
44-ticker list; JPM "TTM FCF" is the annual statement; Sortino guide text says MAR 0
while the code uses rf.

## Verified correct (recomputed to rounding)
Annualised vol, historical VaR95, beta, Sortino downside deviation; MACD 12/26/9, Wilder
RSI(14), ATR, Williams %R, StochRSI, CMF, SMA50/200, Tenkan/Kijun/Senkou B; DCF arithmetic
(all 5 tickers), CAPM ke, WACC weights, Graham, Lynch, EV/EBITDA, EPV, composite weights;
Piotroski (manual prior-year), Altman Z, DuPont, ROIC, CCC, current ratio, Ohlson O
(AAPL −2.2229); KPI P/E and dividend yield units; analyst upside; sector 1d–1y returns in
the chart; Treemap 1d and constituent count; Fama-French regression (exact OLS match).

## Not verified
13F / Form 4 / insider (blocked by P1-13, EDGAR identity); news sentiment (heuristic, no
ground truth); Treemap 1w–1y (known P2-31); Damodaran sector multiples (static file);
Risk-page GARCH/Hurst/OU (not on Markets).

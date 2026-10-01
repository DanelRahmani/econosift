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

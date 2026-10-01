# Phase 54 — checkpoint / handoff (2026-10-01)

Session paused near the 5-hour usage limit. Resume from here; the plan is still
[`2026-10-markets-audit-fixes-prompt.md`](./2026-10-markets-audit-fixes-prompt.md) (Phase 54 section)
plus [`2026-10-markets-audit-phase54-prompt.md`](./2026-10-markets-audit-phase54-prompt.md).

## Orchestrator decisions already made (keep them)

M-18 / M-17 / M-22 contract, shared by backend and frontend:
- `metrics.risk_metrics` — Sharpe/Sortino from **simple** daily returns (arithmetic mean × 252),
  Sortino downside vs `rf/252` on simple returns; vol/VaR/CVaR/beta stay log-return based (audit
  verified them). Output gains `nObs` (0 in the empty case).
- rf = `discount_rates.short_risk_free_rate()` (FRED DGS3MO, fallback 0.04 not cached) +
  `short_risk_free_rate_is_fallback()` — written by Agent F.
- `/api/ratios/{t}` and `/api/market/risk`: `risk_free: float | None = None` → live short rate;
  responses add `riskFree`, `riskFreeSource` (`"FRED DGS3MO"` / `"fallback 4%"` / `"request parameter"`).
  Ratios also adds `betaBasis: {period, frequency: "daily", benchmark, nObs}`.
- Frontend: `types.ts` optional fields + `api.risk(…, riskFree?, …)` are committed; `markets/page.tsx`
  must stop sending 0.04.

## Status per agent

| Agent | Findings | State |
|---|---|---|
| G | M-07, M-08 | ✅ done, committed in the checkpoint. XLE YTD 38.38 % → 41.29 % (prior year-end base); XLK 3M 7.14 % → 8.91 % (63 sessions, = chart). Tests `tests/test_sector_returns_m07_m08.py`. Shared helpers `ytd_base`, `session_base` in `sector_service.py`; treemap YTD drops a symbol with no prior-year close. |
| E | M-06, M-12, M-20 (`yfinance_service.py`) | ✅ done, committed `827004b`. AAPL quote −1.53 % → −1.22 % (last two daily bars, = treemap); Samsung fwd EPS 47,965 → 71,030 (+1y); `get_market_caps(…, one_per_issuer=True)` drops GOOG/BRK-A/FOX/NWS/… (portfolio BL passes False). Tests `tests/test_yf_quotes_m06_m12_m20.py`. |
| F | M-09, M-11, M-10 options, `short_risk_free_rate` | ✅ done, committed `c25f4e6`. Samsung ERP 4.46 % (US) → 4.869 %, tax 21 % → 26.4 %; Damodaran live parse reads 'Regional breakdown' (matches static JSON for 157 countries), `log` defined, 30 s timeout. Tests `tests/test_discount_rates_m09_m11.py`. **M-10 → owner decision, see below.** Follow-ups: `_BENCHMARK_BY_SUFFIX` maps `.BR` (Brussels) to ^BVSP (Brazil is `.SA`) — one-liner in yfinance_service; `static_erp` fixture could go if conftest stubs `_download_damodaran_xlsx`. |
| H | M-19 (+ P3-16 Bollinger ddof, P3-17 Ichimoku shift 26) | ✅ done, committed in the checkpoint. AAPL monthly pivot now from the last *completed* period (`_last_completed`, injectable `_today()`); Bollinger ddof=0 (upper 346.39 → 346.01); Senkou A/B displaced 26 (`_displace_senkou`). Tests `tests/test_technicals_m19.py` (2 need pandas_ta → container only). Follow-ups: forward cloud still not emitted (needs `ichimoku(append=False)` span frame); Chikou displaced 25 not 26 (one-line `shift(-1)`); daily pivot stale when market closed. |
| I | M-13, M-14, M-15, M-18, M-23 (+ P3-28) | ✅ done, committed with `market.py` in the last checkpoint. AAPL health Piotroski 3/4 → full 9; TSM sectorPeers 527 → GICS-mapped peers (or 0 + `peerGroup.reason`); FCF coverage 0.067 → 6.7×; Beneish AAPL null → ≈−2.29 (reuses `corporate_health_service._beneish`); Ohlson SIZE in USD; Sharpe/Sortino simple returns + DGS3MO; JPM DSO/receivables turnover/FCF margin → null + reason; `dcf_target` null for FCF ≤ 0/banks. Tests `test_ratios_m18_m23.py`, `test_fundamentals_m14_m15.py`, `test_snowflake_m13.py`. |
| J | M-16, M-17, M-21, M-22, UI parts of M-14/M-15/M-23/M-18, P3-27 | ✅ done, committed `09213a3` (tsc + eslint clean; no live UI check yet). DcfPanel seeds from `/valuation/full` DCF `detail.inputs` (AAPL grid $169.17 = panel default after fix, was $174.83). Caveats: Yahoo beta labelled "5y mo." by documentation; analyst estimate currency = price currency. Needs backend keys `unavailable["efficiency.dso"]`, `unavailable["profitability.fcfMargin"]` for banks (sent to I). |

After the rebuild, check in the browser: grid DCF == panel default (Valuation), one risk row per
ticker (Overview), beta basis label (Ratios).

Orchestrator's own uncommitted change: `backend/backend/routers/market.py` (`/market/risk` live rf,
`riskFree`/`riskFreeSource`, provenance text says simple returns). Needs a router test once I's
`risk_metrics` change lands.

## M-10 — owner chose **B + Blume interim** (2026-10-01); implement as its own phase after 54

Live ASML.AS: rf 5.26 % (US DGS10), ERP 4.23 % (NL), β 2.235 vs ^AEX (Yahoo β 1.36), ke 14.72 %, WACC 14.68 %, EUR.
- **A** keep, label "USD rf, local-index beta" — smallest, still inconsistent.
- **B** local 10Y rf (FRED/OECD `IRLTLT01xxM156N`, already served by `/api/valuation/risk-free-rates`; monthly, ~2-month lag) + local-index beta + country ERP, all local currency — medium effort, self-consistent. *Agent F's recommendation, with D's Blume adjustment as an interim.*
- **C** USD CAPM: US rf + global (ACWI) beta + Damodaran mature ERP + CRP, USD-converted cash flows — most defensible for multinationals, largest change.
- **D** keep local-index beta but Blume-adjust (0.67β + 0.33) — trims outliers, not theoretically clean.

## On resume

0. Small frontend follow-ups from I's new fields (ValuationKpiPanel/SnowflakeChart): Beneish badge
   must use the emitted `manipulationLikely` (backend cut-off −2.22; panel hard-codes −1.78);
   show `peerGroup.reason` on the Snowflake card; `cashConversionCycle.unavailable.ccc` via NaReason.
   Optional: Piotroski bank criteria → None; `.BR` → ^BFX one-liner; Chikou shift.
1. `git status` — anything uncommitted is agent work in an unknown state. Review each file's diff
   against its finding; rerun that group's tests; redo a group whose diff is partial.
2. Then the remaining orchestrator steps: spec-verifier (raw diff + verbatim Medium rows + test
   commands) → gate (container pytest with `-e DATABASE_URL=sqlite:////tmp/pytest.db`, `tsc`, Docker
   build + recreate, `POST /api/admin/cache/clear`, live curls one ticker at a time) → audit file +
   ACTIVE_ISSUES "Recently Fixed" → CHANGELOG line → commit "Phase 54 — Markets audit: Medium
   findings" → push `DEV`.
3. Ask the owner before M-10, before merging DEV → main, and before starting P1-19 / P1-18.

# Phase 64: status note (checkpoint, 2026-10-07)

The owner had to leave mid-phase. This note lets a fresh session resume. Prompt: `docs/plans/2026-10-07-phase64-prompt.md`.
Approved plan (orchestrator): `C:\Users\danel\.claude\plans\pasted-content-id-1c66-b-lively-perlis.md`. Packets (the specs the agents
ran): the session scratchpad `packets/` folder. That folder may be gone; the key content is summarised below.

## Owner decisions (Step 0, 2026-10-07). Copy each one word for word into its row when you commit that item.
| ID | Decision |
|----|----------|
| Scope | Full Phase 64 (A + B + C) |
| P2-41 | (a) Prune non-members: the nightly rebuild deletes rows for symbols in no tracked index (S&P 500/NDX/Dow). A member whose fetch merely failed is kept. |
| P2-35 | (a) Point-in-time members: use constituents.members_as_of per session. Caveat: delisted names that Yahoo no longer serves still drop out, so a residual is labelled. |
| P2-29 | (c) BIS rates + per-row labels: official rates from the BIS policy-rate CSV for all banks, with the OECD/FRED proxy kept only as a labelled fallback; each row shows its rate type, and the ECB uses the deposit facility rate. |
| P2-30 | (a) Rank/score wording: present the output as a relative risk score/rank and drop the "probability" wording. Numbers unchanged. |
| P2-27 | (a) Relabel as merger news: no acquirer/target/value claims unless parsed with certainty. |
| P2-26 | (a) Document the definition on the panel and in the Wiki. No code change. |
| P2-42 | (b) `[` / `]` move to the previous/next tab on every tabbed page. |
| P2-34 unmounted | (a) Delete after repo-scout. Already confirmed: all 7 are referenced only in their own files (PositioningTab, FundingLiquidityTab, RankingsTab, RiskMetricsTable, PortfolioTab, ScreenerTab, FxRatesPanel). |
| P2-10 / P2-15 | (a) Skipped this phase; they stay open. |

## Committed and pushed? Committed on DEV (push the last commits if not yet pushed)
| ID | Commit | Test |
|----|--------|------|
| P2-41 | 55c345e | backend/tests/test_screener_prune.py (6) |
| P2-30 | e71df98 | backend/tests/test_sovereign_default_score.py (8) |
| P2-34 A4 (theme tokens, NaN%) | d1ebd59 | frontend/tests/e2e/theme-tokens.spec.ts (static) |
| P2-34 A2 part (CAPM tile no daily-alpha fallback) | 3f69523 | frontend/tests/e2e/capm-alpha.spec.ts (static) |
| P2-34 A1 (IV30 total variance, Calmar CAGR, GK overnight, MC seed) | a2f99a4 | test_options_engine / test_advanced_risk / test_realized_moments_service |
| P2-42 | c3941f0 | keyboard-shortcuts.spec.ts (new `[`/`]` test; NOT yet run against Docker) |

The ACTIVE_ISSUES rows for P2-41 and P2-30 already carry their owner decision; they are not marked resolved yet (that happens at the gate).

## In flight / uncommitted (review before committing; do NOT commit blind)
- **P2-34 A3 (macro/stability, 9 items):** the agent finished and reported its DoD green (63 tests + tsc). **Not yet reviewed by the
  orchestrator.**
  - Files: yield_curve_service, banking_stability_service, credit_market, macro_expansion_service, sector_service, routers/macro.py;
    SectorRotationClock, BankingStabilityPanel, CurrencyCrisisPanel; new backend/tests/test_macro_honesty_p64.py.
  - Review points:
    - (1) yield_curve_service now downloads the BIS `WS_LONG_CPI` zip for monthly CPI. Check it is cached, and that the existing
      test_yield_curve_service tests don't hit the network (they now try BIS offline, ~5s each): patch the fetcher in those tests.
    - (2) The agent kept the closed-recession `end` = first month back at 0 (existing behaviour); that's fine.
  - Orchestrator follow-ups:
    - Change the yield page label at frontend/app/yield/page.tsx:257 to: "Real yield = nominal 10Y − latest CPI inflation (monthly BIS
      year-on-year when available, otherwise the World Bank annual average; the basis used is shown per country as cpiBasis)."
    - In types.ts, make `SectorRotation.confidence` `number | null` and add `cpiBasis?: string | null` to the yield row type.
- **P2-34 A2 rest (DDM forward dividend grown once; unknown quote currency → null + reason, never USD; Technicals `$` →
  `currencySymbol(data.currency)`; `currencySymbol(undefined)` → ""):** packet-executor (sonnet) was **still running** at checkpoint.
  - Its files: valuation_engine, dcf_engine, analyst_service, fundamentals, discount_rates, yfinance_service, technicals_service,
    routers/valuation.py, lib/format.ts, markets components (TechnicalsTab, ValuationKpiPanel, …); tests test_valuation_p64.py,
    test_valuation_audit_m02_m03_m05.py (adapted), frontend/tests/e2e/currency-symbol.spec.ts.
  - Check: did it finish? Review the diff, then run
    `cd backend && python -m pytest tests/ -q -p no:warnings -k "valuation or dcf or analyst or fundamentals or discount or technicals or dividend or yfinance"`
    + `tsc` + the currency-symbol spec.
- **P2-29 (BIS policy rates):** packet-executor (sonnet) was **still running** at checkpoint.
  - Files: sources/source_bis.py (`get_policy_rates_bulk`, daily series preferred), services/policy_service.py, tests/test_policy_service.py,
    components/policy/PolicyDivergenceTable.tsx.
  - Facts: BIS XM = deposit facility rate since 18 Sep 2024; US = target-range midpoint; the daily series is current (JP 1.25 on
    2026-09-29), the monthly series lags.
- **frontend/lib/types.ts (orchestrator, uncommitted):** pre-applied shared type changes for the in-flight packets:
  - `ongoing?: boolean` on the recession-period types (A3)
  - `TechnicalsResponse.currency?: string | null` (A2)
  - `PolicyDivergenceEntry.rateType / rateSource / asOf / stale` (P2-29)
  - Commit each part with its item.
- `frontend/tsconfig.tsbuildinfo` and `AGENTS.md` were already dirty before the phase; leave them.

## Rejected / reclassified after reproduction
- A2 "DDM grows the forward dividend twice": **confirmed** in valuation_engine.py:301 (`dividendRate` is Yahoo's forward rate × (1+g)). The
  dividend_service DDM (TTM × (1+g)) is correct. The scout's "not reproduced" verdict was wrong.
- A1 "GK ignores the overnight gap": **confirmed** (the scout said not reproduced; the formula had no ln(O/C_prev) term).
- CAPM: the valuation-engine tile is already annualised; the bug was the portfolio CAPMAttribution fallback (fixed in 3f69523).

## Not started
- Wave 2: P3-36 (IMF/Fama-French file_time stamps).
- Wave 3: P2-35 (breadth PIT). The packet is fully written in the scratchpad (`packets/p2-35.md`). Contract: union download, a `member` bool
  mask in `_ohlc_frames` (prices unmasked, counting masked), `membership` block in the response, movers limited to the last session's
  members. Known-value test: A always a member, B added d3, C removed d4.
- Wave 4: P2-27 (merger-news relabel + ma_service guard), P2-26 (definition text on the breadth panel + wikiData; after P2-35).
- Wave 5: P2-34 unmounted deletion (haiku), P3-37 (desktop build script refresh of target/release/binaries), DESK-01-V (local installer
  build, if possible).
- Gate (all steps): spec-verifier, Docker rebuild + recreate, container pytest, tsc, live checks, Playwright (delegated), docs/rows/CHANGELOG.
  P2-41 only shows live after the next startup warm (the prune runs at the end of `warm_all`).

## Resume checklist
1. `git status`. If A2 / P2-29 agent files are complete, review + test + commit each item; if half-edited, re-dispatch from the packet.
2. Review and commit A3 (see the review points above), then apply the yield label and type follow-ups.
3. Continue waves 2–5, then the gate.

# Phase 64: status note (checkpoint 2, 2026-10-07)

Second checkpoint, written when the 5-hour plan limit reached 95%. It lets a fresh session resume. Prompt: `docs/plans/2026-10-07-phase64-prompt.md`.
The packet specs the agents ran were in the session scratchpad `packets/` folder, which may be gone; the key content is summarised below.

## Owner decisions (Step 0, 2026-10-07). Each is copied word for word into its row when that item is committed.
| ID | Decision |
|----|----------|
| Scope | Full Phase 64 (A + B + C) |
| P2-41 | (a) Prune non-members (the nightly rebuild deletes rows for symbols in no tracked index; a member whose fetch failed is kept) |
| P2-35 | (a) Point-in-time members; the residual (delisted names that Yahoo no longer serves) is labelled |
| P2-29 | (c) BIS official rates + per-row rate-type labels; proxy only as a labelled fallback; ECB on the deposit facility rate |
| P2-30 | (a) Relative risk score/rank, no "probability" wording, numbers unchanged |
| P2-27 | (a) Relabel as merger news: no acquirer/target/value claims unless parsed with certainty |
| P2-26 | (a) Document the definition on the panel + Wiki, no code change |
| P2-42 | (b) `[` / `]` previous/next tab on every tabbed page |
| P2-34 unmounted | (a) Delete after repo-scout |
| P2-10 / P2-15 | (a) Skipped this phase; they stay open |

## Committed on DEV (pushed up to f52c227)
| ID | Commit | Test |
|----|--------|------|
| P2-41 prune screener non-members | 55c345e | test_screener_prune.py |
| P2-30 sovereign risk score + rank | e71df98 | test_sovereign_default_score.py |
| P2-34 A4 theme tokens + NaN% | d1ebd59 | e2e/theme-tokens.spec.ts (static) |
| P2-34 A2 part: CAPM tile, no daily-alpha fallback | 3f69523 | e2e/capm-alpha.spec.ts (static) |
| P2-34 A1 IV30 total variance, Calmar CAGR, GK overnight, MC seed | a2f99a4 | options/advanced_risk/realized_moments tests |
| P2-42 `[`/`]` tab keys | c3941f0 | e2e/keyboard-shortcuts.spec.ts (not yet run vs Docker) |
| P2-34 A3 macro/stability (9 items) | 9d57722 | test_macro_honesty_p64.py |
| P2-34 unmounted components deleted | 866f747 | grep: each referenced only by itself |
| P2-29 BIS policy rates | b2579d2 | test_policy_service.py |
| P2-35 breadth point-in-time members | b09094f | test_breadth_pit.py |
| P2-26 highs/lows definition | f52c227 | text only (tile title + Wiki) |

The rows carry their owner decisions; none is marked RESOLVED yet (that happens at the gate).

## In flight / uncommitted at checkpoint (review before committing; never commit blind)
- **P2-34 A2 rest** (packet-executor, sonnet; resumed once after an interruption).
  - Scope: DDM uses Yahoo's forward `dividendRate` as D1 (no second growth); an unknown quote currency → null + reason, never USD;
    `technicals_service` returns `currency`; TechnicalsTab uses `currencySymbol(data.currency)`; `currencySymbol(undefined)` → "".
  - Files: valuation_engine, dcf_engine, analyst_service, fundamentals, discount_rates, yfinance_service, technicals_service,
    routers/valuation.py, lib/format.ts, markets components; tests test_valuation_p64.py, test_valuation_audit_m02_m03_m05.py,
    frontend/tests/e2e/currency-symbol.spec.ts.
  - **Types:** `frontend/lib/types.ts` still has the uncommitted `TechnicalsResponse.currency?: string | null` (orchestrator, belongs to
    this item).
  - Verify: `cd backend && python -m pytest tests/ -q -p no:warnings -k "valuation or dcf or analyst or fundamentals or discount or technicals or dividend or yfinance"`,
    then tsc and `npx playwright test tests/e2e/currency-symbol.spec.ts tests/e2e/percent-format.spec.ts`.
- **P2-27 merger news** (packet-executor, haiku; backend only). **Backend DONE after the checkpoint (agent reports 7/7 tests in test_ma_service.py), not yet reviewed; uncommitted on purpose: it changes the response shape, so commit it together with the page rewrite.**
  - ma_service returns `{asOf, source, news:[{date|null, headline, related[], sector|null, source, url}], monthlyCount, sectorCount}`.
    No acquirer/target/value, and no "today" stand-in date. Test: backend/tests/test_ma_service.py.
  - **The orchestrator must then rewrite** `frontend/app/mergers/page.tsx` + `MADeal`/`MAData` in types.ts to the new shape: title "Merger
    news", columns Date / Headline / Tagged tickers / Sector / Source, KPIs news items + tagged sectors, no value KPI or column,
    monthly chart = count. Then tsc.
- **P3-37** (orchestrator, uncommitted).
  - desktop/build-windows.ps1 now also refreshes `src-tauri/target/release/binaries/econosift-backend` (and drops the stale `axiom-backend`)
    after staging; desktop/README.md documents local testing and the repo-root warning.
  - Still to do: run `powershell -ExecutionPolicy Bypass -File desktop\build-windows.ps1` (prereqs exist: backend/.venv pyinstaller,
    cargo), confirm `target/release/binaries/econosift-backend` is the new copy and the backend honours ECONOSIFT_DATA_DIR. Then
    commit. The same build serves DESK-01-V: install, launch, check `%APPDATA%/AxiomFinance|EconoSift/backend.log` gets uvicorn lines,
    uninstall.

## Not started
- **P3-36:** IMF WEO / Fama-French file_time stamps.
  - Add `imf_path` / `famafrench_path` next to `bulk_data_service.worldbank_path`, and stamp the refs in atlas_service (IMF ref
    ~L447), source_imf, source_datareader and fama_french consumers.
  - Bundled JSON (`backend/backend/data/damodaran_erp_2026.json`, `doing_business.json`, `sector_multiples.json`, cb_meetings) gets
    the file's own retrieved date or "bundled with the app".
  - Overlaps the A2 files (discount_rates, valuation_engine, routers/valuation.py), so run it after A2 is committed.
- **DESK-01-V:** see P3-37.
- **Gate:**
  1. spec-verifier (sonnet) on `git diff f14442c..HEAD` + the rows + decisions.
  2. Docker rebuild + recreate.
  3. Container pytest, then tsc.
  4. Live checks, one at a time:
     - `/api/policy/tracker`: rateType, ECB ≈ 2.5 DFR.
     - `/api/sovereign/default-prob`: score/rank.
     - `/api/mergers`: news shape.
     - `/api/dashboard/breadth`: membership block.
     - Screener stale-row count: 0 only after the startup warm runs `prune_non_members`.
     - One ticker for IV30/DDM.
     - Pages return 200.
  5. Playwright, delegated.
  6. Docs: rows → "✅ … RESOLVED (Phase 64)", Recently Fixed entries, one CHANGELOG line.
  7. Commit + push; report table; ask before any PR.

## Reproduction notes worth keeping
- Two scout verdicts were wrong; both findings were confirmed:
  - DDM double growth: valuation_engine.py `_model_ddm`, forward dividendRate × (1+g).
  - Garman-Klass had no overnight term.
- BIS WS_CBPOL: XM is the deposit facility rate since 18 Sep 2024 and US is the target-range midpoint. Daily series are current.
- Live screener had 9 stale rows (INSM, ZS, CAG, AVB, EA, EQR, BLDR, TAP, TTD).

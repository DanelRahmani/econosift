# Prompt — fix the Markets calculation audit findings (parallel sub-agents)

Paste everything below the line into a fresh Claude Code session in `C:\Users\danel\Coding\axiomfinance`.

---

Fix the findings in `docs/audit/2026-10-markets-audit.md` (EconoSift, FastAPI + Next.js 14, Docker
Compose). You are the **orchestrator**. Dispatch parallel sub-agents on **disjoint file sets**, then
integrate, verify and commit yourself. Read `CLAUDE.md`, the audit file and the "Phase 51+" section of
`CHANGELOG.md` before dispatching anything.

## Ground rules (they apply to every agent)

- Branch `DEV`. Only you, the orchestrator, run git. Sub-agents never commit, push or touch `main`.
- **The audit findings are not yet independently verified.** For each item, the agent first
  reproduces it against the live stack (`http://localhost/api/...`, Docker is running) or with a
  direct computation. If it does not reproduce, the agent reports it as **rejected**, with the
  evidence, and changes nothing.
- **Write the failing known-value test first.** Use a hand-computable fixture (exact numbers in the
  assertion, a comment showing the arithmetic), see it fail, then fix it. Use no network in tests.
  Mock yfinance and other sources the way the existing tests do (`backend/tests/`).
- Make surgical changes: touch only the files your group owns. If a fix needs a change to a file
  another group owns, or to a shared file (`main.py`, `frontend/lib/api.ts`, `frontend/lib/types.ts`,
  routers outside your list), **do not edit it**. Describe the exact change in your report and the
  orchestrator applies it.
- Never fabricate data, and never scrape HTML. When a number cannot be computed honestly (a bank
  DCF, a missing price), return `null` plus a reason and let the UI show "n/a — reason". Do not
  return a plausible-looking number.
- yfinance safety: always use `.get()` with fallbacks.
- Each agent finishes by running `cd backend && python -m pytest -q -p no:warnings tests/<its test files>`
  and `python -m pyflakes <changed files>` (frontend agents: `cd frontend && npx tsc --noEmit`).
  It reports one line per finding:
  `ID | reproduced? (live value) | fixed / rejected / needs-owner | test name | files`.

## Phase 53 — High findings (M-01 … M-05)

Dispatch these four agents **in parallel** (`subagent_type: general-purpose`, `model: sonnet`). Each
prompt you send must contain the ground rules above, the agent's findings copied verbatim from the
audit table (ID, finding, where, example), and its file list.

| Agent | Findings | Owns (may edit) |
|---|---|---|
| **A — Valuation models** | M-02 (DCF/composite for banks and FCF ≤ 0; negative EV/FCF ranked as best value in Snowflake), M-03 (DDM perpetual growth: use a sustainable dividend growth, capped at long-run nominal GDP / rf, never earnings growth), M-05 (RIM: normalise ROE, fade it toward ke, account for buybacks) | `backend/backend/services/valuation_engine.py`, `dcf_engine.py`, `snowflake_service.py` and their tests |
| **B — Currency mix** | M-01 (ADRs/cross-listings: convert statement-currency FCF, revenue, EBITDA and liabilities to the price currency before any ratio with the USD market cap or price; stop passing Yahoo's ADR multiples through unchecked) | `backend/backend/services/metrics.py`, `backend/backend/routers/valuation.py` (`_kpis` only) and their tests. Reuse the existing `to_price_currency`; do not add a second FX path |
| **C — Technicals** | M-04 (1mo/3mo/6mo HTTP 500 from a tz-naive vs tz-aware compare; 1y/2y windows must be calendar windows, not row counts) | `backend/backend/services/technicals_service.py` and its tests |
| **D — Frontend guard** | Show "n/a — reason" wherever A/B now return `null`: DCF, composite, DDM, RIM, the FCF-based ratios | `frontend/components/markets/**` valuation panels only. Start after A and B have reported their new field contracts; until then this agent only reads |

Expected outcomes, as known-value checks to rerun live after the fix:
- TSM FCF yield is about 1 %, not 30.9 %. NVO EV/EBITDA is about 6.9, not 1.5.
- JPM: DCF is `null` with the reason "not meaningful for banks"; the composite is never negative;
  Snowflake value is not 9.2 from a negative EV/FCF.
- MSFT DDM is no longer $855 against a $513 price.
- AAPL RIM is no longer $341 from a 148.8 % ROE.
- `GET /api/technicals?ticker=AAPL&period=1mo|3mo|6mo` returns 200, and 1y starts within a
  few days of one calendar year ago.

Then, as orchestrator:
1. Apply any shared-file changes the agents requested.
2. Run a fresh-context review: `subagent_type: spec-verifier` with only the raw `git diff`, the
   verbatim High rows of the audit and the test commands. Fix what it confirms.
3. Run the gate:
   - full `pytest` (inside the container use `-e DATABASE_URL=sqlite:////tmp/pytest.db`, because the
     default wipes the live cache);
   - `npx tsc --noEmit`;
   - `docker compose build backend frontend && docker compose up -d --force-recreate`;
   - live curls of every expected outcome above, plus `/markets` returning HTTP 200.
   On any Docker error run `powershell -c "[console]::beep(880,600)"` and stop.
4. For each fixed item, mark it fixed in the audit file (with the test name) and add a row under
   "✅ Recently Fixed" in `ACTIVE_ISSUES.md`. Put rejected items in the audit file with the
   evidence.
5. Add one CHANGELOG entry ("Phase 53 — Markets audit: High findings"), make one commit (message
   about the why), and push to `DEV`.

## Phase 54 — Medium findings (M-06 … M-23)

Dispatch in parallel. The groups are split by file, so no two agents edit the same file:

| Agent | Findings | Owns |
|---|---|---|
| **E — Quotes & estimates** | M-06 (change % from the last two daily closes, not `fast_info.previous_close`), M-12 (forward EPS fallback `+1y`, not `0y`), M-20 (treemap: one area per issuer for dual-class stocks) | `backend/backend/services/yfinance_service.py` |
| **F — Discount rates** | M-09 (South Korea → Damodaran "Korea"), M-11 (live ERP download reads the wrong sheet; undefined `log` → NameError). **M-10 needs owner confirmation**: report the options, do not change it | `backend/backend/services/discount_rates.py` |
| **G — Sectors & treemap** | M-07 (YTD base = prior year-end close), M-08 (3M/6M table off by one session vs the chart) | `backend/backend/services/sector_service.py`, `treemap_service.py` |
| **H — Technicals** | M-19 (pivot points one period stale when the last bar completes a period) | `technicals_service.py` |
| **I — Health scores & risk** | M-13 (Snowflake health: full Piotroski; real GICS peers, not the whole universe), M-14 (Beneish on Markets: reuse the `/corporate/health` computation), M-15 (Ohlson SIZE in USD), M-18 (Sharpe/Sortino: simple returns, rf from FRED DGS3MO or the existing rf source, not a hard-coded 4 %), M-23 (bank metrics: hide DSO/FCF margin for financials; Piotroski bands scaled to `maxScore`) | `fundamentals.py`, `metrics.py`, `snowflake_service.py`, `ratios.py`. Run I **after** Phase 53 is committed, because metrics and Snowflake overlap with A/B |
| **J — Frontend** | M-16 (one DCF per tab; the panel's defaults come from the backend WACC; the region selector is relabelled "Cost of equity (β = 1)" or made correct), M-17 (label each beta with its window and index), M-21 (format forward estimates), M-22 (risk cards name the ticker, horizon and sample size), plus the badge/colour parts of M-14/M-15/M-23 | `frontend/components/markets/**`, `frontend/app/markets/page.tsx`, `frontend/lib/ratioGuide.ts` |

Repeat the Phase 53 orchestrator steps: shared-file changes, spec-verifier, the gate, docs, one
commit "Phase 54 — Markets audit: Medium findings", push. If the phase is large, split it into 54a
(backend) and 54b (frontend), each with its own commit and CHANGELOG line.

## Low findings

Do not fix them in these phases. Add the Low list to `ACTIVE_ISSUES.md` as P3 rows (one row per
item) unless one turns out to be a one-line fix inside a file an agent already owns. In that case
include it, with a test.

## Ask the owner before

- Changing M-10 (rf and beta index for non-US tickers).
- Merging `DEV` → `main`. Open the PR only when asked.
- Anything outward-facing.

When finished, report a table of `ID | before → after (live) | test | commit`, plus the rejected and
owner-decision items. Remind the owner to run /compact.

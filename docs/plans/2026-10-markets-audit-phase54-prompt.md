# Next session — Phase 54 (Markets audit, Medium findings) and what follows

Paste the block below into a fresh session. It continues
[`2026-10-markets-audit-fixes-prompt.md`](./2026-10-markets-audit-fixes-prompt.md) — read that file
too: its ground rules, agent table for Phase 54 (agents E–J), and orchestrator steps still apply.

---

Continue the Markets audit fixes (EconoSift, FastAPI + Next.js 14, Docker Compose). Phase 53 (High
findings M-01…M-05) is done and merged; its status table is in `docs/audit/2026-10-markets-audit.md`.
Now do **Phase 54 — Medium findings M-06 … M-23** exactly as specified in
`docs/plans/2026-10-markets-audit-fixes-prompt.md` (agents E–J, same ground rules, same orchestrator
steps: shared-file changes → spec-verifier → gate → docs → commit → push DEV). Read CLAUDE.md, the
audit file, the "Phase 51+" section of CHANGELOG.md and both prompt files before dispatching.

What Phase 53 changed that Phase 54 agents must know:
- **New contracts.** `metrics.market_multiples(bundle)` is the one place multiples are built for
  ADRs (it goes through `dcf_engine.to_price_currency`; `_fx_rate` now handles GBp/ZAc/ILA minor
  units). Nulls carry reasons in `kpis.unavailable` (valuation/full) and top-level `unavailable`
  (ratios, keyed `"valuation.psRatio"`, `"zScore"`). Locked models use `{value: null, locked: true,
  reason}`; composite has `reason`. Frontend renders them with `components/markets/NaReason.tsx`.
- **Agent I** (metrics.py, snowflake_service.py, fundamentals.py, ratios.py) edits files Phase 53
  touched heavily — have it read the Phase 53 diff (`git show` of the Phase 53 commit) first.
- **Agent E** owns `yfinance_service.py`: `get_info` now retries a failed/half-failed `Ticker.info`
  and never caches it (`_info_failed`). Keep that intact.
- **Agent F** (discount_rates.py, M-11): `log` is undefined in the Damodaran download error path —
  a test fixture (`static_erp` in `test_valuation_audit_m02_m03_m05.py`) currently papers over it.
  **M-10 needs the owner's decision — ask before changing it.**

Gate tips learned in Phase 53:
- Docker rebuild is now ~20–80 s (`backend/.dockerignore`). After recreating, **clear the cache**
  (`POST /api/admin/cache/clear`) or old results are served stale, then curl tickers **one at a
  time** — a parallel burst makes Yahoo drop half of `Ticker.info` (sector, debt, ROE missing;
  see P2-39). If a ticker looks degraded, wait ~20 s and re-request.
- Local (Windows) pytest lacks `fredapi`, and `test_advanced_risk` cointegration fails on a clean
  HEAD too — use the container run as the authoritative gate:
  `docker compose exec -T -e DATABASE_URL=sqlite:////tmp/pytest.db backend python -m pytest -q -p no:warnings`
  (prefix `MSYS_NO_PATHCONV=1` from Git Bash).
- Low findings are already P3-16 … P3-28 in ACTIVE_ISSUES.md; fix one only if it is a one-liner
  inside a file an agent already owns (e.g. Ichimoku shift 26 or Bollinger ddof for Agent H, the
  Sortino guide text for Agent J), with a test.

After Phase 54, the owner's queued work (ask before starting each):
1. **P1-19 — AI summaries are written from model memory.** `ai_service.py` sends no app data and no
   `google_search` grounding tool, so macro/company/dashboard summaries invent numbers and sources.
   Present the options (feed the app's cached data into the prompt / enable Google Search
   grounding and show its real source URLs / both) and let the owner choose.
2. **P1-18 — global search / command bar** (Ctrl/⌘+K + navbar button): fuzzy-match the 25 pages,
   their sub-tabs, Wiki terms and tickers, navigate on Enter. Build it as its own phase with a
   Playwright test.

Ask the owner before: changing M-10, merging DEV → main, anything outward-facing. Finish with a
table `ID | before → after (live) | test | commit`, the rejected and owner-decision items, and a
reminder to run /compact.

# Prompt — EconoSift data-layer refactor (run locally, full internet)

_Paste everything below the line into a Claude Code session on the owner's machine, in the
EconoSift repo._

---

You are continuing the EconoSift performance refactor. The app is feature-complete, but it is
slow and things break, because every page fetches market data live from Yahoo, per ticker, and
we get rate-limited. The goal is an app that **feels snappy**, without changing how it looks.

## Setup
1. First, run these commands yourself (stash or commit any local changes first if `git status`
   isn't clean):
   ```bash
   git status
   git fetch origin
   git checkout refactor/data-layer
   git pull origin refactor/data-layer
   git log --oneline -3   # should show the "Prompt: spell out the branch checkout commands…" and "Plan: run refactor…" commits
   ```
   Do **all** work on this branch. Commit one item per commit (message about the "why") and
   push after each with `git push origin refactor/data-layer`. Never push to `DEV`, `main` or
   `PRODUCTION`; open a PR only when I ask.
2. Read `CLAUDE.md` (working agreements: Docker gate, CRLF line endings, never scrape HTML,
   never fabricate data, don't spend the Gemini quota, never trigger `build-desktop.yml`) and
   then **`docs/plans/REFACTOR_PROPOSALS.md`**. That file is the plan. Follow it.

## Decisions already made (don't reopen them)
- Keep Python/FastAPI and TypeScript/Next.js. No Rust, Svelte or Vite.
- **One database: SQLite**, one file `econosift.db`, for everything (prices, fundamentals,
  macro, portfolio, settings, AI summaries, cache). Replaces `axiomfinance.db`,
  `screener_cache.db` and the Parquet files.
- **No data migration.** There are no users; build the new DB fresh and drop the old files.
- **No new dependencies** unless one replaces an old one (try to drop `pyarrow`).
- **One throttled fetcher thread inside the backend** is the only code allowed to call
  Yahoo/SEC/etc. API requests only read the DB and return `asOf`; missing data → queue a fetch
  and return `status: "pending"`.
- Index prices (S&P 500 / NDX / Dow) via a **bulk snapshot every ~15 min** in US market hours,
  plus stored daily bars.
- **Keyless sources first**, with optional free keys pasted in Admin as fallbacks. Nothing paid.

## Phase 65.0 — verify the APIs first (you have internet; the planning session didn't)
Work through the checklist in §7 of the plan with **throwaway** REPL/curl checks. Don't commit
probe scripts and don't add tests for this. Send SEC requests with a `User-Agent` that includes
a contact, and stay under 10 req/s. Be gentle with Yahoo (≤1 req/s except in the deliberate
rate test, and stop at the first 429).
- Record the results in **§8 Verification results**: works or not, real limits, response
  fields, and S&P 500 coverage numbers.
- Where something doesn't work, revise the plan (e.g. pick the WebSocket or chunked-download
  snapshot instead of `yf.screen`, or add SEC concept fallbacks) and set the fetcher's
  token-bucket rate from what you measured.
- Commit the updated plan. **Then stop and show me a short summary of what works and what
  changed before writing any app code.**

## Phase 65 — stop the bleeding (after my OK)
Do the Phase 65 row of the plan, one commit per item, test-first where practical:
1. The cache must never store an empty `pd.DataFrame`/`Series` (`cache.py` `_is_empty_result`).
2. Fix the ~25 `async def` routes that call blocking sync code (use `await asyncio.to_thread`
   or make them plain `def`). Start with `routers/technicals.py`, `snowflake.py`,
   `scenario.py`, `atlas.py`, `corporate.py`, `dividend.py`, `market_data.py`, `research.py`,
   `macro.py`, and `screener.py`.
3. nginx: remove `timeout` from `proxy_next_upstream` (no re-sending slow requests).
4. A global per-source rate limiter + circuit breaker wrapped around the existing yfinance
   calls, at the rate measured in 65.0.
5. Startup: no screener warm-up or immediate Yahoo jobs at boot; stagger them and move
   crons out of US market hours.
6. Frontend: react-query `retry` 6 → 1 (keep the long retry only while `/health` reports the
   desktop backend is starting); a 25 s timeout in `lib/api.ts get()`; per-tab error
   boundaries so one panel can't blank a page.

Run the CLAUDE.md gate (pytest + `tsc` + Docker rebuild/recreate + curl checks + page 200s).
Measure the performance targets in §0 of the plan before and after, and report them. Add a
CHANGELOG line. Then continue with Phases 66 → 70 in order, using the same per-phase gate and
CHANGELOG line, and pushing after each commit.
**Stop for my review after Phase 67** (the point where pages read from the DB), and whenever
a verified fact contradicts the plan.

## Quality bar
- Every changed line traces to the plan; no speculative features.
- yfinance fields may be `None`; always use `.get()` with fallbacks.
- On a source failure: log it, serve the last stored data with its `asOf`, and surface it.
  Never cache an empty result and never fabricate data.
- Before each push, re-read your diff adversarially, and run backend tests + typecheck.

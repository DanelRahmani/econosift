# Prompt: Phase 63 — plumbing and UX

Paste everything below the line into a fresh Claude Code session in `C:\Users\danel\Coding\axiomfinance`.
This is the "Phase 60 — plumbing and UX" block of `docs/plans/2026-10-open-issues-prompt.md`, renumbered:
Phases 60–62 went to the Refresh button, the UI refresh and two small fixes. The model-quality block of that
plan ("Phase 61") becomes Phase 64.

---

Run **Phase 63** for EconoSift (FastAPI + Next.js 14, Docker Compose) on `DEV`. Read `CLAUDE.md`,
`ACTIVE_ISSUES.md`, the "Phase 51+" section of `CHANGELOG.md`, and the **Ground rules** and **Gate** sections of
`docs/plans/2026-10-open-issues-prompt.md` first. They apply to this phase unchanged: reproduce first, a failing
known-value test before each fix, never fabricate data or scrape HTML, surgical changes, sub-agents
(Backend/Frontend/Math = sonnet) only on disjoint file sets, and only the orchestrator runs git and edits shared
files (`main.py`, `frontend/lib/api.ts`, `frontend/lib/types.ts`, pages).

## Items, in this order

1. **P2-36**: `tests/conftest.py` pins its own throwaway SQLite DB, so pytest can never wipe the live cache, even
   without the `DATABASE_URL` override or inside the container. Add a test that asserts the path. Do this first:
   the rest of the phase relies on it.
2. **P2-18**: stale JS after a redeploy. nginx cache headers: `no-cache` for HTML, long-lived `immutable` for
   hashed `/_next/static`. Verify with a rebuild plus a page load without a hard refresh.
3. **P3-35**: endpoints that serve a stored snapshot outside `@cached` stamp provenance `fetchedAt` with the
   request time, so the Navbar's "Data as of" can look newer than the data. Find the routers that read DB
   snapshots or bulk datasets (the screener universe was fixed in Phase 60 by stamping its `asOf`) and set
   `fetchedAt` from the build time. One test per endpoint fixed.
4. **P2-20**: one percent formatter, one convention (fraction in, percent out). Remove the `fmtPct(v * 100)`
   double-scaling call sites and pin it with a known-value assertion.
5. **P2-32 / P2-33**: provenance maps for the bare-list endpoints named in the row. In Admin, show the
   "Clear cache & re-warm" hint when cached entries lack provenance.
6. **P2-16**: country labels on vertical bar charts with 18+ bars (`interval={0}` plus height scaling).
7. **P2-07 (remainder)**: number keys switch tabs and ←/→ change the period on pages with those controls, via
   `useKeyboardShortcuts`, never while typing in an input. Playwright test.
8. **P2-37**: 13F quarter-on-quarter change (keep the previous quarter's reduced data set; the ~100 MB download
   happens only on request) and % of float (shares outstanding from cached `info`).
9. **DESK-02**: a Windows Job Object with `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE` in `desktop/src-tauri/src/lib.rs`,
   so a force-kill also ends `econosift-backend.exe`. Verify with `Stop-Process -Force` on a local Windows build.
   If a desktop build isn't possible this session, skip it and say so.

## Lessons from Phases 59–62 (follow them)

- **Playwright must target Docker**: `cd frontend && PLAYWRIGHT_BASE_URL=http://localhost npx playwright test`.
  Without the variable it starts `npm run dev` on :3000 and nearly every test times out. If that happens, stop
  the dev server it started.
- **Local pytest**: `DATABASE_URL=sqlite:///$TMP/pytest_local.db` until P2-36 lands. Locally `fredapi` is not
  installed and two cointegration tests fail; both pass in the container. Treat the container run as the gate.
- **Python edit scripts on Windows**: open files with `encoding="utf-8", newline=""` and keep the file's own line
  endings. The default cp1252 codec crashed on an emoji and truncated a file to 0 bytes. Never `sed` regex
  backslashes.
- **Refresh button (P1-20)**: a new panel that loads data on page open must add `useRefreshNonce()` to its effect
  dependencies. An effect behind Calculate / Run Analysis / Analyze must not (compute tiers 🟡/🔴).
- **UI (Phase 61)**: new UI uses the shared layer (`.card`, `.btn`, `.input`, `.skeleton`, `TabButton`,
  `ToggleChip`) and theme tokens, never hard-coded colours, so the light/dark themes and the Admin theme maker
  keep working. Respect `prefers-reduced-motion`.
- **The Screener universe is a nightly snapshot.** Screener metric changes (e.g. the Phase 62 ROIC) appear only
  after its rebuild. Say so in live checks rather than calling it unverified.
- **Don't spend the owner's Gemini quota** to verify AI changes. Test with the fake client in
  `tests/test_ai_grounding.py`, or render stored summaries.

## Finish

- **Gate**: run steps 1–7 from the plan.
- **Report**: a table `ID | before → after (live) | test | commit`, the rejected items with evidence, the open
  decisions, and any new issues found.
- **Next**: Phase 64 (model quality: P2-29, P2-30, P2-35, P2-26, P2-27, P2-34). It needs the owner's choice on
  each option before any code.
- Watch `get_usage`. Near the 5-hour limit, commit finished work and write a status note under `docs/plans/`.
- Ask the owner before merging `DEV` → `main` (PR only when asked) and before anything outward-facing.
- Remind the owner to run /compact.

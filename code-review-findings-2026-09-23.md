# Code Review — Axiom Finance — 2026-09-23

## Summary

Read-only review of the current checkout, focusing on the desktop startup path, security configuration, known-issue tracking, and major user workflows. No tests were run. The last commit is `84b7f64` (`Make desktop release builds more reliable`); the working tree was clean before this report.

- Critical: 0
- Warning: 2
- Info: 2

The breadth of functionality is a strength: the app includes market, portfolio, macro, risk, options, research, and corporate analysis, with a substantial backend test suite. The main risks surfaced in this pass are a desktop startup timeout disagreement and the desktop webview having no Content Security Policy.

## Warnings

### `frontend/components/providers.tsx:29` — Frontend gives up before desktop backend startup check

- Why it matters: the frontend stops waiting after 45 seconds and renders the app, while Tauri continues checking the backend for up to 60 seconds (`desktop/src-tauri/src/lib.rs:92`). During a slow first launch, users can land on a dashboard whose initial API queries have already failed; the backend can then become healthy after the UI has released its startup gate.
- Fix: use one shared startup budget (or let the frontend remain in an explicit recoverable error state) and retry failed queries after health becomes ready. For example, align `MAX_WAIT` with Tauri's 60-second budget plus a small scheduling margin, and show a Retry action if the limit expires.

### `desktop/src-tauri/tauri.conf.json:27` — Desktop webview Content Security Policy is disabled

- Why it matters: `"csp": null` turns off the webview's CSP defense in depth. The frontend currently uses an inline theme initialization script (`frontend/app/layout.tsx`), so a strict policy needs to account for it; however, leaving CSP disabled means any future script injection flaw has fewer browser-side constraints in the shipped desktop app.
- Fix: define a minimal Tauri CSP with only required local assets and backend connections, and authorize the theme bootstrap with a hash or nonce. Validate both Windows and Linux origins and the static export before release.

## Info / Suggestions

### `ACTIVE_ISSUES.md:37` and `ACTIVE_ISSUES.md:39` — Feature tracker lists shipped features as open

- Why it matters: P3-01 says price alerts and P3-04 says transaction logging are missing, but the current app contains watchlist price-alert UI (`frontend/components/Watchlist.tsx`) and a transaction log (`frontend/components/portfolio/TransactionLog.tsx`). This makes the roadmap less reliable and can cause duplicate work.
- Fix: verify the shipped behavior against the descriptions, then mark these resolved or rewrite the entries to name the remaining gaps (for example, alert delivery across app restarts or durable transaction backup).

### `ACTIVE_ISSUES.md:24` — Accessibility and navigation are good candidates for the next polish pass

- Why it matters: the product has many dense analytics views, and the active issue list already records missing keyboard navigation. A large surface area increases the time needed for users to reach and compare information.
- Fix / feature ideas:
  - Add a global keyboard command palette for ticker/page navigation and common actions, with visible shortcut discovery and focus management.
  - Add exportable research snapshots (CSV for tables and a printable/shareable report for a selected ticker or portfolio) with source and as-of timestamps, so calculations can be reviewed outside the app.
  - Add a guided first-run workspace that helps users configure API keys, pin a watchlist, and select a default dashboard; keep the existing local-only setup as the default.

## Quick wins

1. Align the frontend and Tauri startup timeouts and give users a retry path after backend startup failure.
2. Reconcile P3-01/P3-04 in `ACTIVE_ISSUES.md` with the features already present in the UI.
3. Specify and validate a restrictive CSP for the Tauri webview, including the existing theme bootstrap script.
4. Prioritize the command palette and research export based on user feedback; they improve navigation and make the analytics easier to retain and share.

## Scope and confidence

This was a shallow source and documentation review, not a line-by-line audit or live desktop run. The startup timeout mismatch and roadmap mismatch are directly visible in the current source. The CSP finding is a defense-in-depth concern; this review did not establish an exploitable script-injection path.

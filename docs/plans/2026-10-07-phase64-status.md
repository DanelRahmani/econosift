# Phase 64: final status (2026-10-08)

Phase 64 is done and pushed to `DEV`. No PR yet: the owner opens `DEV` → `main` when ready.

## Owner decisions (Step 0, 2026-10-07; recorded in each row)
- P2-41 (a) prune non-members.
- P2-35 (a) point-in-time members.
- P2-29 (c) BIS rates + per-row labels.
- P2-30 (a) score/rank wording.
- P2-27 (a) relabel as merger news.
- P2-26 (a) document the definition.
- P2-42 (b) `[` / `]`.
- P2-34 unmounted components: (a) delete.
- P2-10 / P2-15: (a) skipped; still open.
- Later decisions:
  - Disable the Git LFS lock verify for this repo (the push was blocked).
  - Do not install over the existing EconoSift desktop install; verify with the frozen exe instead.

## Delivered (all on DEV)
| ID | Before → after (live) | Test |
|----|-----------------------|------|
| P2-29 | ECB 2.65 MRO → 2.50 BIS deposit facility rate; BoJ 0.977 interbank → 1.25; Fed 3.75 effective → 3.875 target midpoint; all rows from BIS. Cold-cache parse 125 s → 5.5 s | test_policy_service.py |
| P2-41 | 527 screener rows, 9 stale → 518, none stale; also prunes on every `refresh_universe` | test_screener_prune.py |
| P2-35 | Breadth over point-in-time members; 16 former members without Yahoo data reported | test_breadth_pit.py |
| P2-30 | `prob1y` / `prob5y` → `score` / `rank`; signal from the unrounded score | test_sovereign_default_score.py |
| P2-27 | acquirer "FDUSD" / target "CSLM" guessed from a headline → merger news with Finnhub ticker tags | test_ma_service.py |
| P2-34 | IV30 total variance, Calmar CAGR, GK overnight term, MC seed, DDM single growth, unknown currency null, CAPM tile, monthly-CPI real yields, banking fields, recession/TOTCI/rotation, theme tokens, NaN%, 7 dead components | several (see the ACTIVE_ISSUES Recently Fixed rows) |
| P2-42 | `[` / `]` step tabs on every tabbed page | keyboard-shortcuts.spec.ts |
| P2-26 | Definition in the served Wiki entry and as a caption on the breadth panel | test_wiki_p64.py |
| P3-36 | IMF / FF bulk files, Damodaran JSON, CB meetings, Doing Business dated by their own file/date | test_provenance_files_p64.py |
| P3-37 | The build refreshes target/release/binaries; verified on a local build | (build check) |

## Gate
- **Spec review:** a fresh-context spec-verifier review found 3 blockers (Wiki edited in the wrong file, wrong Macro tabs in the e2e test, prune only at startup), all fixed with tests.
- **Docker:** rebuilt and recreated; the cache was cleared because response shapes changed.
- **Container pytest:** green except `test_insider_aggregate_does_not_block_the_event_loop`, a flaky timing test (P3-38).
- **tsc:** clean.
- **Playwright:** 40/40 against Docker.
- **Live checks:** one endpoint/ticker at a time; all pages 200.

## Open / next
- **DESK-01-V: RESOLVED 2026-10-08.** The rebuilt frozen exe, started with a scratch `ECONOSIFT_DATA_DIR`, writes "Uvicorn running on http://127.0.0.1:8000" (and the other startup lines) to `backend.log`; the working folder stays empty. The last installer build's NSIS packaging step (makensis) exited 4. The backend and app exe built fine, so this is not a code issue; rerun `desktopuild-windows.ps1` when an installer is needed (close any open Explorer window on the bundle folder).
- **New issues:**
  - P2-43: DDM blows up when g is capped at ke − 0.5 pp (KO 424 vs ~86).
  - P2-44: the Central Banks tab and FX carry are still on MRO/OECD.
  - P3-38: flaky timing test.
  - P3-39: breadth membership note not shown.
  - P3-40: AltGr `[` / `]`, no shortcut hint.
  - P3-41: Dividends `$` axis; `macro_service.data_provenance` dead code.
- **Uncommitted, intentionally:**
  - `desktop/src-tauri/Cargo.toml`: line endings rewritten by the build.
  - `frontend/tsconfig.tsbuildinfo` and `AGENTS.md`: pre-existing.

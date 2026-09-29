# EconoSift Rebrand Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task. Track each step with checkbox syntax.

**Goal:** Rebrand the self-hosted financial research app from Axiom Finance to EconoSift across the interface, docs, persisted identifiers, desktop/container packaging, and GitHub repository while preserving user data and working links.

**Architecture:** Treat EconoSift as the single public product name and `econosift` as the new package slug. Update visible branding and build metadata directly, retain backward-compatible reads for existing Axiom-named app data, environment variables, and browser storage, and keep API route paths, response keys, database schema, and calculations exactly stable.

**Tech Stack:** Next.js 14, React, TypeScript, FastAPI, Python 3.12, SQLAlchemy/SQLite, Tauri v2/Rust, PyInstaller, Docker Compose, Nginx, GitHub Actions, NSIS/DEB packaging.

**Spec:** User request in the current Codex thread; product name `EconoSift`, chosen logo concept A, and original proposed palette (deep navy, muted teal, restrained amber) are recorded in this plan.

## Global Constraints

- Use `EconoSift` for user-facing product branding and `econosift` for new package and executable slugs. Update the repository slug only after the remote rename succeeds.
- Use deep navy `#142A43`, muted teal `#2F8F83`, and restrained amber `#D99A36`; dark mode uses near-white `#F2F4F7` for wordmark contrast. Update default app accents to navy/teal and use amber for warnings.
- Do not imply affiliation with Axiom Digital or another company.
- Preserve existing user state: SQLite data, settings, API keys, browser preferences, theme selection, and portfolio transaction logs.
- Accept legacy `AXIOM_*` environment variables and existing Axiom Finance app-data paths during migration; do not delete old data automatically.
- Keep API route paths, request parameters, response keys (including legacy `axiomFairValue`), database schema, and financial computations unchanged. Rebrand only presentation labels and internal TypeScript/Rust/Python symbols.
- Keep historical changelog statements factually accurate; annotate legacy identifiers as historical where replacing them would falsify old build records.
- No root `LICENSE` file is present, so the public tagline describes the product as self-hosted research and makes no open-source licensing claim until a license is added.
- Do not rename the active checkout directory while a task is running from it. Treat local folder rename as an optional post-migration housekeeping step.

## Review Focus

- Existing desktop installs must continue using their prior SQLite database, settings, and `.env` paths; prefer selecting the existing directory in place over copying the database.
- Existing browser users must retain transaction history, theme choice, and preferences when local-storage keys gain new names; migrate old keys idempotently.
- Existing Docker users must retain their named volume and environment configuration; do not rename a volume in a way that creates a fresh empty database.
- Every current API path and response key must remain byte-for-byte the same; `axiomFairValue` remains as a legacy JSON key for client compatibility while its UI label changes.
- GitHub rename must update the local `origin`, clone instructions, badges, release links, and workflow references; old GitHub redirects are a fallback, not the canonical link.

---

## Current Surface Map

- Main interface: `frontend/app/layout.tsx`, `frontend/components/Navbar.tsx`, `frontend/components/MobileNav.tsx`, `frontend/components/Footer.tsx`, `frontend/components/ThemeProvider.tsx`, `frontend/app/globals.css`.
- Valuation branding and contracts: `frontend/components/markets/AxiomGauge.tsx`, `frontend/components/markets/ValuationEngine.tsx`, `frontend/components/markets/ValuationTab.tsx`, `frontend/lib/types.ts`, related backend valuation router/service/wiki strings.
- Logo assets already created in this thread and present as untracked files: `frontend/public/econosift-logo-light.png`, `frontend/public/econosift-logo-dark.png`. Preserve and reuse these; do not overwrite them.
- Frontend package identity: `frontend/package.json`, `frontend/package-lock.json`, `desktop/package.json`, `desktop/package-lock.json`, and any metadata references found by the final sweep.
- Runtime identity and persistence: `backend/backend/config.py`, `backend/run.py`, `desktop/src-tauri/tauri.conf.json`, `desktop/src-tauri/Cargo.toml`, `desktop/src-tauri/Cargo.lock`, `desktop/src-tauri/src/main.rs`, `desktop/src-tauri/src/lib.rs`, `desktop/src-tauri/capabilities/default.json`, `backend/build.spec`, `desktop/build-windows.ps1`, `desktop/src-tauri/binaries/`.
- Deployment and release identity: `.env.example`, `docker-compose.yml`, `nginx/default.conf`, `.github/workflows/ci.yml`, `.github/workflows/build-desktop.yml`, `RELEASE_PLAN.md`, `TAURI_BUILD.md`, `TAURI_PROGRESS.md`, `releases/`.
- Documentation: `README.md`, `CLAUDE.md`, `CHANGELOG.md`, `ACTIVE_ISSUES.md`, `FIN_TERMS.md`, `IDEA_LIST.md`, `API_suggestions.md`, `INFO/`, `desktop/README.md`, and other tracked Markdown found by the final search.
- Brand references embedded in source/data: `frontend/components/markets/AxiomGauge.tsx`, `frontend/components/portfolio/TransactionLog.tsx`, `backend/backend/services/wiki_service.py`, backend valuation modules and tests, plus strings found by a repository-wide, generated-file-excluded search.
- GitHub repo and local `origin` now use `https://github.com/DanelRahmani/econosift`.

## Task 1: Establish the Rebrand Inventory and Canonical Naming Contract

**Files:**
- Create/update this plan: `docs/superpowers/plans/2026-09-29-econosift-rebrand.md`
- Inspect, do not rename: all tracked project files except generated outputs and dependency trees.

- [ ] Record canonical display name `EconoSift`, slug `econosift`, executable stem `econosift-backend`, Tauri identifier `com.econosift.app`, and default tagline `Open-source macro and investment research` in this plan before changing code.
- [ ] Run `rg -n -i --hidden --glob '!**/node_modules/**' --glob '!**/.next/**' --glob '!**/out/**' --glob '!**/.venv/**' --glob '!**/.git/**' --glob '!**/tsconfig.tsbuildinfo' 'axiom|axiomfinance' .` and save the resulting file list into the implementation review notes.
- [ ] Classify every hit as visible branding, package/runtime identity, persistence/migration compatibility, historical record, or unrelated term; exclude generated build artifacts and finance-domain words where the substring is accidental.
- [ ] Confirm brand colors and the two already-created logo asset paths above; preserve historical legacy names only where needed for compatibility or factual changelog records.

## Task 2: Apply the EconoSift Visual Brand to Web and Desktop UI

**Files:**
- Modify: `frontend/app/layout.tsx`
- Modify: `frontend/components/Navbar.tsx`, `frontend/components/MobileNav.tsx`, `frontend/components/Footer.tsx`
- Modify: `frontend/components/markets/AxiomGauge.tsx` and imports, renaming it to `EconoSiftGauge.tsx` if the component is kept brand-specific
- Use: `frontend/public/econosift-logo-light.png`, `frontend/public/econosift-logo-dark.png`
- Modify: `desktop/src-tauri/tauri.conf.json` window title and product display name
- Modify: `desktop/src-tauri/icons/*` only if regenerated from the selected EconoSift mark; keep original dimensions/formats expected by Tauri.

- [ ] Set browser metadata title and description to EconoSift and an accurate product description.
- [ ] Replace navbar wordmark with the provided logo files; choose the light/dark asset from the existing theme state and provide meaningful alt text. Use a compact icon-only rendering where the mobile header cannot fit the horizontal mark.
- [ ] Update footer, mobile navigation branding, browser/PWA manifest, favicon, and any OpenGraph/title assets found during inventory.
- [ ] Preserve current theme behavior and colors; update theme-maker reset labels/help text so no Axiom company signature remains in user-visible copy.
- [ ] Update Tauri window title and installer display name to EconoSift; create the app icon from concept A only if the source artwork is sufficiently crisp, otherwise use the approved icon assets after deterministic export.
- [ ] Confirm the logo has adequate contrast in both themes and readable fallback behavior when images are unavailable.

## Task 3: Rename Branded Source Concepts and Keep API Contracts Synchronized

**Files:**
- Rename/update: `frontend/components/markets/AxiomGauge.tsx`, its imports, and `frontend/lib/types.ts`
- Modify: `frontend/components/markets/ValuationEngine.tsx`, `frontend/components/markets/ValuationTab.tsx`
- Modify: `backend/backend/routers/valuation.py`, `backend/backend/services/valuation_engine.py`, `backend/backend/services/wiki_service.py`, related backend response models/tests
- Modify other source files surfaced by Task 1, including `frontend/components/portfolio/TransactionLog.tsx` and brand-sensitive service descriptions.

- [ ] Rename `AxiomFairValue` and `AxiomGauge` to EconoSift-neutral names such as `CompositeFairValue` and `EconoSiftGauge`; update producer, consumer, tests, and documentation together.
- [ ] Replace user-visible “Axiom Fair Value” labels with “EconoSift Composite Fair Value” without changing valuation math.
- [ ] Rename branded comments, log messages, generated export filenames, and user-facing errors; keep generic technical concepts and external provider names unchanged.
- [ ] Preserve API route paths. If response keys are currently branded, introduce a transition that emits the new key and reads the old key where needed, then document a removal condition rather than silently breaking clients.
- [ ] Add/adjust focused contract checks only where an API key or data-migration behavior changes; do not rewrite unrelated tests or calculations.

## Task 4: Rename Package, Runtime, Desktop, and Deployment Identifiers Safely

**Files:**
- Modify: `frontend/package.json`, `frontend/package-lock.json`
- Modify: `desktop/package.json`, `desktop/package-lock.json`
- Modify: `desktop/src-tauri/tauri.conf.json`, `desktop/src-tauri/Cargo.toml`, `desktop/src-tauri/Cargo.lock`, `desktop/src-tauri/src/main.rs`, `desktop/src-tauri/src/lib.rs`, `desktop/src-tauri/capabilities/default.json`
- Modify: `backend/backend/config.py`, `backend/run.py`, `backend/build.spec`, `desktop/build-windows.ps1`, `docker-compose.yml`, `.env.example`, `RELEASE_PLAN.md`, `TAURI_BUILD.md`, `.github/workflows/build-desktop.yml`
- Modify resource paths under: `desktop/src-tauri/binaries/` and `releases/` when those paths are tracked or generated by scripts.

- [ ] Rename package/crate/lib identifiers, bundle identifier, PyInstaller output binary, staged backend resource directory, installer filename stem, capability descriptions, app-data path, and release artifact labels to EconoSift.
- [ ] Keep the Docker `sqlite_data` named volume stable so deployments do not start with an empty database; update only genuinely user-visible service/image/container labels.
- [ ] Implement data-path discovery in this order: explicit `ECONOSIFT_DATA_DIR`, legacy `AXIOM_DATA_DIR`, existing EconoSift app-data directory, then existing Axiom Finance app-data directory, then the new EconoSift default. Never create an empty new database before checking for the old one.
- [ ] At Tauri startup, select an existing `%APPDATA%/AxiomFinance` or platform-specific legacy directory in place before creating the new EconoSift directory. This avoids database copy races and keeps settings, `.env`, logs, and SQLite WAL/SHM together.
- [ ] Accept legacy environment variables such as `AXIOM_DATA_DIR` and `AXIOM_CORS_ORIGINS` as fallbacks while updating examples and docs to `ECONOSIFT_*`; do not rewrite real user `.env` files in place without a backup.
- [ ] Update PyInstaller paths and Tauri resource lookups atomically; ensure Linux and Windows suffixes continue to resolve correctly.
- [ ] Keep API addresses, ports, routes, Tauri permissions, and license unchanged.

## Task 5: Preserve and Migrate Browser and User Data Keys

**Files:**
- Modify: `frontend/components/portfolio/TransactionLog.tsx`
- Modify: `frontend/components/ThemeProvider.tsx` and other frontend storage consumers found during the inventory.
- Modify: targeted frontend tests under `frontend/tests/` and backend tests only if the app-data resolver is changed.

- [ ] Search all `localStorage`, `sessionStorage`, IndexedDB, export/import, and settings keys; distinguish branded keys from neutral product state.
- [ ] For each renamed key, read the EconoSift key first; if absent, migrate the Axiom key once, validate its shape, write the new key, and leave the old value untouched until migration is confirmed.
- [ ] Preserve existing transaction JSON downloads and imports; change future export filenames to `econosift_transactions_<date>.json` while continuing to import the existing `axiom_transactions` format.
- [ ] Add focused migration coverage for an existing Axiom transaction log, theme selection, and preference state; verify repeated startup does not duplicate or reset data.

## Task 6: Rebrand Documentation, Links, and Release Content

**Files:**
- Modify: `README.md`, `CLAUDE.md`, `CHANGELOG.md`, `ACTIVE_ISSUES.md`, `FIN_TERMS.md`, `IDEA_LIST.md`, `API_suggestions.md`
- Modify: `desktop/README.md`, `RELEASE_PLAN.md`, `TAURI_BUILD.md`, `TAURI_PROGRESS.md`, `INFO/**/*.md`, `.github/workflows/*.yml`, `releases/` metadata and links.
- Modify: `frontend/public/*` manifest and icon references, if present.

- [ ] Replace current product identity, install/clone instructions, screenshots, badges, download names, app-data paths, and logo references with EconoSift and the canonical repository URL.
- [ ] Change “Axiom Fair Value” glossary and wiki text to the selected EconoSift valuation term; update generated documentation sources where they are maintained in code.
- [ ] Keep old phase entries historically accurate; add a dated EconoSift rebrand entry and mark retained Axiom identifiers as legacy compatibility details.
- [ ] Update release workflow display names and artifact names without changing protected branch names, signing secrets, release gates, or deployment behavior.
- [ ] Include the new logos in documentation or release notes only where useful; do not replace app UI copy with internal implementation details.

## Task 7: Validate the Migration Before Publishing

**Files:**
- Review all modified paths, especially persistence compatibility and generated lockfiles.

- [ ] Run focused frontend type-check/build, backend test suite, desktop Rust/Tauri build, and existing Playwright E2E suite using the repository’s established commands.
- [ ] Install/launch a renamed desktop build against a fixture copied from the old Axiom app-data location; confirm DB records, saved API keys, logs, and browser-side transaction data are still available.
- [ ] Start the Docker stack using the current named volume and confirm health endpoints and core pages work without creating a replacement empty volume.
- [ ] Run a final tracked-source sweep for `Axiom`, `axiom`, `AXIOM`, and `axiomfinance`, excluding explicit legacy fallback code, historical changelog entries, build outputs, vendored files, and finance-domain false positives; document every remaining hit and why it stays.
- [ ] Inspect `git diff --check`, review package-lock changes, and confirm both logos are tracked in the final patch.

## Task 8: Rename the GitHub Repository and Update the Local Remote

**Files/actions:**
- GitHub repository settings for `DanelRahmani/axiomfinance`
- Local Git remote `origin`
- Canonical URL references in README, badges, CI links, release downloads, and clone instructions.

- [ ] Confirm `DanelRahmani/econosift` is available before initiating the rename.
- [ ] Rename the GitHub repository to `econosift` only after the code/docs release is ready and the owner account has permission; preserve issues, pull requests, releases, Actions secrets, and branch protections.
- [ ] Update the local remote with `git remote set-url origin https://github.com/DanelRahmani/econosift.git` after GitHub confirms the rename.
- [ ] Verify the canonical repository page, clone URL, latest release links, badge URLs, and workflow status links resolve at the new location; retain old-link redirects as a safety net.
- [ ] If GitHub settings access is unavailable, leave the local repo untouched and provide the exact owner action needed. Current `gh auth status` could not read the GitHub CLI config due a local access-denied error at `%APPDATA%/GitHub CLI/config.yml`; revisit only if authentication becomes available.

## Completion Criteria

- The app, desktop installer, browser metadata, logos, and current documentation present EconoSift with no Axiom Digital affiliation.
- New package/build/repository identifiers use `econosift`; necessary old identifiers remain only as explicit data-preserving fallbacks or historical records.
- Existing database, settings, API keys, browser preferences, and transaction logs survive upgrade without user data loss.
- Existing test/build gates pass, deployment links work, and the final branding sweep has no unexplained Axiom references.
- GitHub repository URL and `origin` use the new slug if GitHub access permits; otherwise the blocker and owner steps are recorded.


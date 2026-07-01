# GitHub Autobuild Failure — Diagnosis

Investigated 2026-07-01. This is a **read-only diagnosis** — no source files
were touched. Fix in a later session.

## TL;DR

The **`Build Desktop App`** workflow (`.github/workflows/build-desktop.yml`,
on `PRODUCTION`) fails on every run because it looks for a PyInstaller
**onefile** output (`backend/dist/axiom-backend.exe`), but `backend/build.spec`
was switched to **onedir** mode and now produces a *directory*
(`backend/dist/axiom-backend/axiom-backend.exe`) instead. The file the
workflow expects never exists, so the "Rename binary for Tauri sidecar" step
exits 1 immediately after PyInstaller succeeds.

A second, newer workflow — **`Build Windows Desktop`**
(`.github/workflows/build-windows.yml`) — was added later and *does* handle
the onedir layout correctly, and its runs are green. `build-desktop.yml` was
never updated or removed, so it's a stale duplicate that fails on every push
to `PRODUCTION`.

## Evidence

- `backend/build.spec` (current `PRODUCTION` HEAD) builds in onedir mode:
  ```python
  exe = EXE(
      pyz, a.scripts, [],
      exclude_binaries=True,   # onedir: binaries collected by COLLECT below
      name="axiom-backend",
      ...
  )
  coll = COLLECT(exe, a.binaries, a.zipfiles, a.datas, name="axiom-backend")
  ```
  Output lands at `backend/dist/axiom-backend/` (a folder), not
  `backend/dist/axiom-backend.exe`.

- `build-desktop.yml`'s copy step assumes onefile output:
  ```bash
  SRC="backend/dist/axiom-backend${{ matrix.binary_suffix }}"   # → backend/dist/axiom-backend.exe
  if [ ! -f "$SRC" ]; then
    echo "ERROR: PyInstaller output not found at $SRC"
    exit 1
  fi
  ```

- Actual failure log (run #27, `28530301529`, commit
  `Rebuild Windows installer with data-dir fix`, 2026-07-01T15:58–15:59 UTC):
  ```
  246300 INFO: Building COLLECT COLLECT-00.toc completed successfully.
  254216 INFO: Build complete! The results are available in: D:\a\axiomfinance\axiomfinance\backend\dist
  ...
  ERROR: PyInstaller output not found at backend/dist/axiom-backend.exe
  total 4
  drwxr-xr-x 1 runneradmin 197121 0 Jul  1 15:59 .
  drwxr-xr-x 1 runneradmin 197121 0 Jul  1 15:55 ..
  drwxr-xr-x 1 runneradmin 197121 0 Jul  1 15:59 axiom-backend      <- it's a directory, not axiom-backend.exe
  ##[error]Process completed with exit code 1.
  ```

- `build-windows.yml`'s equivalent step correctly copies the whole onedir
  folder and checks for the exe *inside* it, and its runs succeed:
  ```powershell
  $stage = "desktop/src-tauri/binaries/axiom-backend"
  Copy-Item backend/dist/axiom-backend $stage -Recurse -Force
  if (-not (Test-Path "$stage/axiom-backend.exe")) { throw "backend not staged" }
  ```
  Runs #1 (`28526729331`) and #2 (`28528975843`) on `build-windows.yml`:
  `conclusion: success`.

## History (build-desktop.yml, `.github/workflows/build-desktop.yml`)

28 runs total on `PRODUCTION` as of this writing. Pattern:

- Runs 1–5 (2026-06-30, Phase 36/37 packaging): failures/cancellations while
  iterating on PyInstaller hidden imports (`uvicorn` submodules missing, then
  `None` stdout/stderr under `console=False`, etc.) — since fixed.
- Runs 6–19 (2026-06-30 evening): mostly `cancelled` (rapid-fire pushes
  superseding each other) or `success` once icon/path/import issues were
  resolved — this is when the workflow was still onefile-compatible.
- Run 21 (`Rework Tauri desktop build: onedir backend freeze + resource
  bundling`, 2026-07-01T14:25): `build.spec` switched to onedir here, but
  `build-desktop.yml`'s copy step was **not** updated to match. Every run
  since has failed with the same "PyInstaller output not found at
  backend/dist/axiom-backend.exe" error.
- Runs 22–27 (2026-07-01, LFS installer add, data-dir fixes, etc.): all
  `failure`, same root cause each time — none of these commits touched
  `build-desktop.yml` or the copy-step assumption.

Meanwhile `build-windows.yml` was added at run 21's timeframe (commit "Add
GitHub Actions workflow to build Windows installer in CI", 2026-07-01T14:56)
specifically written against the onedir layout, and has been green since.

## Fix options for next session

1. **Delete `.github/workflows/build-desktop.yml`** — it's superseded by
   `build-windows.yml` (same purpose: Windows Tauri + PyInstaller build),
   and its macOS/Linux matrix entries were never actually enabled (matrix
   only lists `windows-latest`), so it adds no coverage `build-windows.yml`
   doesn't already provide.
2. **Or fix its copy step** to match `build-windows.yml`'s onedir-aware
   logic (copy the `backend/dist/axiom-backend` directory recursively into
   `desktop/src-tauri/binaries/axiom-backend-<target>/`, adjusting the Tauri
   sidecar path/`tauri.conf.json` externalBin naming to match a directory
   sidecar rather than a single renamed binary — onedir sidecars need a
   differently-shaped Tauri config than onefile ones).

Given `build-windows.yml` already does this correctly and is actively
maintained, deleting `build-desktop.yml` is the simpler and lower-risk fix.

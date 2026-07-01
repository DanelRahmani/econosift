# Axiom Finance — Windows Desktop (Tauri)

Packages Axiom Finance as a native Windows app: a Tauri shell hosting the static
Next.js frontend, with the FastAPI backend bundled as a child process on
`http://127.0.0.1:8000`.

## Architecture

```
axiom-finance.exe (Tauri/Rust)
 ├─ loads frontend static export  (frontend/out, bundled as frontendDist)
 └─ spawns  binaries/axiom-backend/axiom-backend.exe  (PyInstaller onedir)
        └─ FastAPI/uvicorn on 127.0.0.1:8000
```

- The backend is frozen with **PyInstaller onedir** (`backend/build.spec`) using
  `collect_all()` over the whole dependency stack, then bundled into the app via
  Tauri `bundle.resources` and spawned from `src-tauri/src/lib.rs`.
- App data (SQLite DB, `backend.log`, `settings.json`) lives in
  `%APPDATA%/AxiomFinance/` (passed to the backend via `AXIOM_DATA_DIR`).
- A startup splash (`frontend/components/providers.tsx`) polls `/api/health`
  before mounting, so panels don't fire before the backend is ready.

## Prerequisites (one-time)

- **Python venv** at `backend/.venv` with deps installed:
  `pip install -r backend/requirements.txt -r backend/requirements-build.txt`
- **Rust** (stable-msvc): `rustup default stable-msvc`
- **VS C++ Build Tools** (MSVC linker) — VS 2022 Build Tools with the
  "Desktop development with C++" workload.
- **Node** (for the frontend export + Tauri CLI): `cd desktop && npm install`

## Build

```powershell
powershell -ExecutionPolicy Bypass -File desktop\build-windows.ps1
```

Produces `desktop/src-tauri/target/release/bundle/nsis/Axiom Finance_<ver>_x64-setup.exe`.

The script runs the three stages (freeze backend → stage into resources →
`tauri build`). To run stages manually, see the commands inside the script.

## Notes

- **Auto-updater is disabled** (`tauri.conf.json`) — it needs signing keys +
  release infra. Re-enable when publishing signed releases.
- Build artifacts (`backend/dist`, `backend/build`, `src-tauri/binaries`,
  `src-tauri/target`) are gitignored. The published installer is tracked via
  **Git LFS** under `releases/`.
- Backend is built windowless (`console=False`). Crash diagnostics are *meant*
  to go to `%APPDATA%/AxiomFinance/backend.log`, but that file is currently not
  being written under `console=False` (see **DESK-01** in `ACTIVE_ISSUES.md`).
- **Known caveats:** DESK-01 (no `backend.log`) and DESK-02 (backend orphaned if
  the app is force-killed rather than closed normally) — tracked in
  `ACTIVE_ISSUES.md`.

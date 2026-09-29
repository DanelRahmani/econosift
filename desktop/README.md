# EconoSift — Windows and Linux Desktop (Tauri)

Packages EconoSift as a native Windows or Linux app: a Tauri shell hosting the static
Next.js frontend, with the FastAPI backend bundled as a child process on
`http://127.0.0.1:8000`.

## Architecture

```
econosift (Tauri/Rust; `.exe` on Windows)
 ├─ loads frontend static export  (frontend/out, bundled as frontendDist)
 └─ spawns  binaries/econosift-backend/econosift-backend[.exe]  (PyInstaller onedir)
        └─ FastAPI/uvicorn on 127.0.0.1:8000
```

- The backend is frozen with **PyInstaller onedir** (`backend/build.spec`) using
  `collect_all()` over the whole dependency stack, then bundled into the app via
  Tauri `bundle.resources` and spawned from `src-tauri/src/lib.rs`.
- App data (SQLite DB, `backend.log`, `settings.json`) lives in the OS app-data
  directory (`%APPDATA%/EconoSift/` on Windows, `~/.local/share/EconoSift/`
  on Linux), passed to the backend via `ECONOSIFT_DATA_DIR`. Existing
  `%APPDATA%/AxiomFinance/` and `~/.local/share/AxiomFinance/` data directories
  continue to be selected when present; the legacy `AXIOM_DATA_DIR` variable
  is also accepted.
- A startup splash (`frontend/components/providers.tsx`) polls `/api/health`
  before mounting, so panels don't fire before the backend is ready.

## Prerequisites (one-time)

- **Python venv** at `backend/.venv` with deps installed:
  `pip install -r backend/requirements.txt -r backend/requirements-build.txt`
- **Rust** (stable)
- **Windows:** VS 2022 C++ Build Tools with the "Desktop development with C++" workload.
- **Linux:** Tauri's Linux build dependencies, including WebKitGTK 4.1, GTK,
  AppIndicator, OpenSSL, and a C/C++ toolchain (see the CI workflow for the
  Ubuntu package list).
- **Node** (for the frontend export + Tauri CLI): `cd desktop && npm install`

## Build

```powershell
powershell -ExecutionPolicy Bypass -File desktop\build-windows.ps1
```

On Windows, produces `desktop/src-tauri/target/release/bundle/nsis/EconoSift_<ver>_x64-setup.exe`.
Linux `.deb` installers are built in CI on `ubuntu-latest`. macOS packaging is
deferred and is not included in the release matrix.

The script runs the three stages (freeze backend → stage into resources →
`tauri build`). To run stages manually, see the commands inside the script.

## Notes

- **Auto-updater is disabled** (`tauri.conf.json`) — it needs signing keys.
- Build artifacts (`backend/dist`, `backend/build`, `src-tauri/binaries`,
  `src-tauri/target`) are gitignored. CI uploads installers as Actions artifacts
  and attaches them to a GitHub Release after both supported platforms build.
  Pushes to `PRODUCTION` create numbered prereleases; `v*` tags create stable
  releases.
- Backend is built windowless (`console=False`). Crash diagnostics are *meant*
  to go to `%APPDATA%/AxiomFinance/backend.log`, but that file is currently not
  being written under `console=False` (see **DESK-01** in `ACTIVE_ISSUES.md`).
- **Known caveats:** DESK-01 (no `backend.log`) and DESK-02 (backend orphaned if
  the app is force-killed rather than closed normally) — tracked in
  `ACTIVE_ISSUES.md`.

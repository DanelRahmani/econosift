# Tauri Desktop Package — Progress (Windows)

Goal: ship a Windows installer that launches Axiom Finance as a desktop app — a
Tauri shell hosting the static-exported Next.js frontend, with the FastAPI backend
spawned as a bundled child process on `http://127.0.0.1:8000`.

Full plan: `.claude/plans/snappy-yawning-sprout.md` (local, not committed).

## Root cause of the previous failure ("build works, app does nothing")

1. **Errors were invisible** — `build.spec` used `console=False` and `run.py`
   redirected stdout/stderr to `os.devnull`, so backend crashes produced no output.
2. **Incomplete dependency capture** — the spec hand-listed a handful of
   `hiddenimports` and **zero data files**. The backend imports ~25 third-party
   packages (numpy/scipy/pandas/pyarrow/arch/statsmodels + data-bearing libs like
   pycountry, financedatabase, edgartools, pandas_ta, wbgapi, certifi …). Missing
   submodules/data caused the `ModuleNotFoundError`s.
3. **onefile fragility** — heavy native DLLs (MKL, pyarrow) loaded from a onefile
   temp-extraction is a classic silent-crash source.

## Approach

- PyInstaller **onedir** build (folder = `axiom-backend.exe` + `_internal/`), using
  `collect_all()` for every third-party package (submodules + data + native libs).
- Bundle that folder into Tauri via `bundle.resources` (not the sidecar mechanism),
  spawned from Rust with a resource-resolved path.
- **Staged bring-up**: get the backend exe running standalone with a console + file
  logging *before* wiring Tauri — turns "silent nothing" into a fixable error list.
- Windows-only, local build.

## Status

| Phase | Status | Notes |
|-------|--------|-------|
| A. Backend freeze (build.spec, run.py) | ✅ Done | onedir + `collect_all`; verified standalone |
| Toolchain (Python deps, Rust, VS C++ Build Tools) | ✅ Done | Rust 1.96.1 stable-msvc; MSVC 14.44 `cl.exe` |
| B. Frontend static export | ✅ Done | `npm install` + `npm run build` → `frontend/out/` (25 pages) |
| C. Tauri wiring (resources, lib.rs spawn, capabilities) | ✅ Done | sidecar → resources; updater disabled |
| D. Full `tauri build` + installer | ✅ Built | NSIS installer produced (166 MB), pushed via Git LFS to `releases/` |
| D. Installer smoke-test (install + run) | ⏳ Pending | not yet installed/run end-to-end |
| E. Finalize (console=False, README, commit) | ⏳ Pending | current installer is the debug build (console=True) |

### Build output (Phase D)

- `desktop/src-tauri/target/release/axiom-finance.exe` (Rust build, 6m02s)
- Installer: `Axiom Finance_1.0.0_x64-setup.exe` (166 MB) →
  committed as `releases/AxiomFinance-1.0.0-x64-setup.exe` via **Git LFS**
  (exceeds GitHub's 100 MB raw-file limit).

> ⚠️ The committed installer is the **debug build** (`console=True`) — a console
> window will appear on launch. Phase E rebuilds it windowless. It has **not** yet
> been installed + run end-to-end.

### Phase A verification (passed)

Standalone `dist/axiom-backend/axiom-backend.exe` (~60 MB exe, onedir folder):
- `GET /api/health` → `{"status":"ok"}` in ~3s
- `GET /api/search?q=AAPL` → live yfinance results (proves certifi/SSL bundled)
- `GET /api/macro/countries`, `/api/macro/indicators` → OK

## Key fixes made

- **`backend/build.spec`** — rewritten: onedir `COLLECT`, `collect_all()` over all
  deps, `console=True`/`upx=False` for bring-up. Critically, do **not** exclude
  `unittest`/`test` — `scipy`→`numpy.testing` imports `unittest` at runtime (this
  was the first standalone crash).
- **`backend/run.py`** — logs to `%APPDATA%/AxiomFinance/backend.log` instead of
  devnull; binds `127.0.0.1` (localhost-only, no firewall prompt).
- **`desktop/src-tauri/tauri.conf.json`** — `externalBin` sidecar → `resources`
  (`binaries/axiom-backend/**/*`); `beforeBuildCommand` builds the frontend; NSIS
  target; auto-updater disabled (needs signing infra — deferred).
- **`desktop/src-tauri/src/lib.rs`** — spawn backend via
  `app.path().resolve("binaries/axiom-backend/axiom-backend.exe", Resource)` +
  `shell().command(...)`; health-poll timeout 30s → 60s (heavy cold start).
- **`desktop/src-tauri/capabilities/default.json`** — dropped `updater:*` perms.
- **`desktop/src-tauri/Cargo.toml`** — removed `tauri-plugin-updater`.

## Build steps (local Windows)

```powershell
# 1. Backend freeze
cd backend
.venv\Scripts\pip install -r requirements.txt -r requirements-build.txt
.venv\Scripts\pyinstaller build.spec --noconfirm

# 2. Stage backend into Tauri resources
Copy-Item backend\dist\axiom-backend desktop\src-tauri\binaries\axiom-backend -Recurse -Force

# 3. Full desktop build (frontend export + Rust + NSIS bundle)
cd desktop
npm install
$env:PATH = "$env:USERPROFILE\.cargo\bin;$env:PATH"
npm run build
# → desktop/src-tauri/target/release/bundle/nsis/*-setup.exe
```

## Remaining / TODO

- [ ] Confirm `tauri build` produces the NSIS installer.
- [ ] Install + smoke-test: window opens, backend spawns, data loads, DB+log written
      to `%APPDATA%/AxiomFinance/`, no orphan `axiom-backend.exe` on close.
- [ ] Phase E: flip `console=True` → `False` in `build.spec`; add `desktop/README.md`;
      wrap the 3 build steps in `desktop/build-windows.ps1`.
- [ ] (Later) re-enable auto-updater with proper signing keys for releases.

## Notes

- Build artifacts are gitignored: `backend/build/`, `backend/dist/`,
  `desktop/src-tauri/binaries/`, `desktop/src-tauri/target/`, `backend/data/`.
- The local `.venv` / frontend `node_modules` were partial (app normally runs in
  Docker) — a full `pip install` and `npm install` were needed for the freeze/export.

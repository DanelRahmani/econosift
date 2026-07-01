# Making a MAIN build Tauri-ready, and releasing it

This repo ships **two ways** from one codebase:

- **Web / Docker** — the normal FastAPI + Next.js app you develop on `main`.
- **Desktop** — the same app wrapped in a [Tauri](https://tauri.app/) v2 shell
  (`desktop/`) that spawns the PyInstaller-frozen backend as a local child
  process. Built for Windows, macOS and Linux by CI.

This file explains (1) what a feature on `main` must respect so it stays
packageable as a desktop app, and (2) how to cut a desktop release.

---

## 1. Keep `main` Tauri-convertible

The desktop build reuses the *exact* backend and frontend from `main` — there is
no separate desktop codebase. To avoid breaking it, any feature on `main` must
honour these four contracts:

1. **All writable paths go through `config.DATA_DIR`** — never hardcode `./data`,
   `/app/...`, or a CWD-relative path. The frozen desktop exe runs from an
   unpredictable working directory, so anything that writes (SQLite DB, `.env`
   API keys, bulk-data files, caches) must resolve under `config.DATA_DIR`
   (`AXIOM_DATA_DIR` env var → OS app-data dir). See `backend/backend/config.py`
   and `database.py`. A hardcoded Docker path is exactly what broke bulk-data on
   desktop (see `ACTIVE_ISSUES.md` DESK-05).

2. **The frontend must build as a static export.** `frontend/next.config.js`
   sets `output: "export"`. That means: no server components doing runtime data
   fetches, no API routes, no `next/image` loader that needs a server. Dynamic
   routes must pre-generate **every** param in `generateStaticParams` (e.g.
   `app/country/[iso2]` enumerates the full ISO list via `lib/iso2Codes.ts`) —
   an un-generated route 404s and falls back to `index.html` (→ redirect to
   `/dashboard`). See `ACTIVE_ISSUES.md` BUG-A4.

3. **The backend talks to the frontend only over `http://127.0.0.1:8000`.** The
   Tauri shell (`desktop/src-tauri/src/lib.rs`) spawns the backend, passes
   `AXIOM_DATA_DIR`, and the frontend gates on `/api/health` before rendering
   (`frontend/components/providers.tsx`). Don't assume a reverse proxy, cookies
   from a specific origin, or absolute URLs.

4. **New Python dependencies must survive PyInstaller.** The freeze
   (`backend/build.spec`, PyInstaller **onedir**) uses `collect_all()` over the
   dependency stack to catch lazy/dynamic imports and data files. If you add a
   library that loads data files or does dynamic imports (like `pycountry`,
   `financedatabase`, `edgartools`), add it to the `collect_all` / `datas` list
   in `build.spec` or the desktop build will launch and then crash on import.

If a change respects these four, it will package for desktop with no extra work.

---

## 2. Cut a desktop release (gated promote)

`main` is for feature development and **does not build installers**. Desktop
builds are cut from `PRODUCTION`:

```
develop on main  ──►  Promote to PRODUCTION (one click)  ──►  3-OS Tauri build
```

**To release:**

1. Get your features merged into `main` as usual.
2. Go to **Actions ▸ "Promote main → PRODUCTION" ▸ Run workflow**.
   - It merges `main` into `PRODUCTION`, pushes, and then triggers the build.
   - (Equivalent by hand: `git push origin main:PRODUCTION` when it fast-forwards.)
3. **Actions ▸ "Build Windows Desktop"** runs on `PRODUCTION` and produces:

   | OS | Artifact | Notes |
   |----|----------|-------|
   | Windows | NSIS `*-setup.exe` | |
   | macOS | `*.dmg` (Apple Silicon) | Unsigned — first launch: right-click ▸ Open |
   | Linux | `*.deb` (amd64) | AppImage not shipped — see `ACTIVE_ISSUES.md` P3-13 |

   Download them from the run's **Artifacts**. Tagging a `v*` release also
   attaches the installers to the GitHub Release.

**Versioning:** bump the version in `desktop/src-tauri/tauri.conf.json` (and the
installer name references in `README.md` / `releases/`) before promoting.

### Workflows involved

- `.github/workflows/promote-to-production.yml` — the manual promote button.
- `.github/workflows/build-windows.yml` — the 3-OS matrix build (freeze backend
  → stage into Tauri resources → `tauri build`). Triggers on push to
  `PRODUCTION`, on `v*` tags, and via manual dispatch.

> Note: the promote job pushes with the default `GITHUB_TOKEN`, which by design
> does **not** trigger `build-windows.yml`'s `on: push` — so the promote job
> dispatches the build explicitly as its last step.

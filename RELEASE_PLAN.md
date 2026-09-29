# RELEASE_PLAN.md — Cross-Platform Desktop Builds via GitHub Actions

**Status:** Plan only — no source files have been changed on this branch yet.
This is a work order for a future Claude session to execute.

**Constraint driving this plan:** the developer has no macOS or Linux
hardware, so macOS/Linux builds must happen entirely on GitHub-hosted
runners (`macos-latest`, `ubuntu-latest`) — there is no way to build or
test them locally. Windows builds can still be tested locally too.

See [`GITBUILD.md`](./GITBUILD.md) for the full diagnosis this plan is based
on: why `build-desktop.yml` currently fails (onefile vs onedir PyInstaller
mismatch), and the itemized list of why the app is Windows-only today.

## Goal

One GitHub Actions workflow, triggered on push to `RELEASE` (and version
tags), that builds and uploads installers for Windows (`.exe` via NSIS),
macOS (`.dmg`), and Linux (`.deb` + `.AppImage`) — all on GitHub's own
runners, no local Mac/Linux needed at any point.

## Step-by-step

### 1. Retire the broken workflow
Delete `.github/workflows/build-desktop.yml`. It's a stale duplicate of
`build-desktop.yml` with the onefile/onedir bug described in `GITBUILD.md`
and has failed on every run since 2026-07-01. Confirm no other workflow or
doc references it before deleting (check `README.md` badges, `CLAUDE.md`).

### 2. Make the Rust shell OS-aware
`desktop/src-tauri/src/lib.rs` currently hardcodes:
```rust
"binaries/econosift-backend/econosift-backend.exe"
```
Change to resolve the exe name conditionally:
```rust
let exe_name = if cfg!(windows) { "econosift-backend.exe" } else { "econosift-backend" };
let backend_exe = app.path().resolve(
    format!("binaries/econosift-backend/{exe_name}"),
    BaseDirectory::Resource,
)
```
No other Rust changes should be needed — `Cargo.toml` deps (`tauri`,
`reqwest`, `dirs`, `tokio`, etc.) are already cross-platform. Verify this by
reading `Cargo.toml` again once implementing, in case something changed.

### 3. Open up the Tauri bundle targets
`desktop/src-tauri/tauri.conf.json` currently has:
```json
"bundle": { "targets": ["nsis"], ... }
```
Change `"targets"` to `"all"` so Tauri's CLI picks the right bundler for
whichever host OS it's running on (`nsis` on Windows, `dmg`+`app` on macOS,
`deb`+`appimage` on Linux) — no per-OS config branching needed here.

Leave `bundle.macOS.minimumSystemVersion` and `bundle.linux.deb.depends` as
they are unless the build surfaces a concrete problem with them.

### 4. Rewrite the CI workflow as a 3-OS matrix
Take `build-desktop.yml` as the base (it's already onedir-correct) and add
a matrix dimension instead of hardcoding `windows-latest`:

```yaml
strategy:
  fail-fast: false
  matrix:
    include:
      - os: windows-latest
        exe_suffix: ".exe"
      - os: macos-latest
        exe_suffix: ""
      - os: ubuntu-latest
        exe_suffix: ""
```

Key changes needed inside the job:

- **Linux system deps** — add a step, Linux-only (`if: matrix.os ==
  'ubuntu-latest'`), before the Tauri build:
  ```yaml
  - if: matrix.os == 'ubuntu-latest'
    run: sudo apt-get update && sudo apt-get install -y \
      libwebkit2gtk-4.1-dev libayatana-appindicator3-dev librsvg2-dev \
      build-essential libssl-dev libgtk-3-dev
  ```

- **Stage step** — keep the existing `shell: pwsh` block from
  `build-desktop.yml` (PowerShell Core is preinstalled on all three
  GitHub-hosted runner images), just parametrize the exe suffix instead of
  hardcoding `.exe`:
  ```powershell
  $exeSuffix = if ($IsWindows) { ".exe" } else { "" }
  $stage = "desktop/src-tauri/binaries/econosift-backend"
  if (Test-Path $stage) { Remove-Item $stage -Recurse -Force }
  New-Item -ItemType Directory -Force -Path (Split-Path $stage) | Out-Null
  Copy-Item backend/dist/econosift-backend $stage -Recurse -Force
  if (-not $IsWindows) { chmod +x "$stage/econosift-backend" }
  if (-not (Test-Path "$stage/econosift-backend$exeSuffix")) { throw "backend not staged" }
  ```
  (`chmod` needs to run via a Unix shell call from pwsh, e.g.
  `& chmod +x "$stage/econosift-backend"` — verify this actually executes with
  correct permissions when implementing; pwsh's own `Set-ItemProperty`
  doesn't set the Unix exec bit.)

- **Upload step** — glob the whole bundle dir instead of a format-specific
  pattern, since the format now varies by OS:
  ```yaml
  - uses: actions/upload-artifact@v4
    with:
      name: EconoSift-${{ matrix.os }}-installer
      path: desktop/src-tauri/target/release/bundle/**/*
      if-no-files-found: error
  ```

- **Release-attach step** (tag builds) — same glob-everything approach, or
  list the specific extensions (`*.exe`, `*.dmg`, `*.deb`, `*.AppImage`)
  explicitly if `softprops/action-gh-release` needs concrete paths rather
  than a bundle-tree wildcard.

### 5. Don't attempt code signing / notarization in this pass
Unsigned macOS builds will trigger a Gatekeeper "unidentified developer"
warning; users can still open them via right-click → Open (no paid Apple
Developer account needed for that — only needed for notarization, which
removes the warning entirely). Document this caveat in `desktop/README.md`
rather than trying to solve it — an Apple Developer Program membership
($99/yr) is a prerequisite for notarization and is out of scope unless the
user decides to pursue it separately.

### 6. Verify
Since none of this can be tested locally on Mac/Linux:
- Push to `RELEASE` and watch all three matrix legs on GitHub Actions.
- Confirm each leg's `tauri build` step succeeds and produces the expected
  installer artifact.
- Download each artifact from the Actions run and sanity-check the file
  exists and is non-trivial in size (a broken build sometimes still
  produces a near-empty output).
- Windows leg can additionally be smoke-tested locally by the developer.
- macOS/Linux legs rely entirely on the CI logs + artifact presence/size as
  the verification signal — there's no way to actually launch and click
  through the app on those OSes in this environment. Say so explicitly if
  reporting results back to the user; don't claim the app "works" on
  macOS/Linux beyond "it built".

### 7. Update docs
- `CLAUDE.md`'s "Windows Desktop Package (Tauri)" section (see the note it
  currently only describes Windows) → broaden to describe all three
  platforms once they build.
- `desktop/README.md` → add macOS/Linux build-from-source notes and the
  Gatekeeper caveat from step 5.
- `README.md` → update the "Windows Desktop App" section title/badges if it
  references Windows specifically.
- `CHANGELOG.md` → add an entry once shipped.

## Open questions for the user (ask before or during implementation, don't guess)

- **Apple Silicon vs Intel Mac**: `macos-latest` runners are Apple Silicon
  (arm64). Ship arm64-only, or also add an `x86_64-apple-darwin` /
  `macos-13` leg for Intel Macs? Doubles the macOS build matrix and CI time
  for a shrinking user base — worth confirming intent first.
- **Release cadence**: should this workflow build on every push to
  `RELEASE`, or only on version tags (`v*.*.*`)? Building on every push
  triples CI minutes usage vs. Windows-only today.

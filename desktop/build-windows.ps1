# Build the EconoSift Windows desktop app end-to-end.
#
#   1. Freeze the FastAPI backend with PyInstaller (onedir)
#   2. Stage it into the Tauri resources folder
#   3. Run `tauri build` (frontend export + Rust + NSIS installer)
#
# Prereqs (one-time): Python venv with requirements, Rust (stable-msvc) +
# VS C++ Build Tools, Node. See desktop/README.md.
#
# Usage:  powershell -ExecutionPolicy Bypass -File desktop\build-windows.ps1

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot          # repo root
$backend = Join-Path $root "backend"
$desktop = Join-Path $root "desktop"
$stage = Join-Path $desktop "src-tauri\binaries\econosift-backend"

Write-Host "==> [1/3] Freezing backend (PyInstaller onedir)..." -ForegroundColor Cyan
Push-Location $backend
& ".venv\Scripts\pyinstaller.exe" build.spec --noconfirm
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed" }
Pop-Location

Write-Host "==> [2/3] Staging backend into Tauri resources..." -ForegroundColor Cyan
if (Test-Path $stage) { Remove-Item $stage -Recurse -Force }
Copy-Item (Join-Path $backend "dist\econosift-backend") $stage -Recurse -Force
if (-not (Test-Path (Join-Path $stage "econosift-backend.exe"))) { throw "Backend exe not staged" }

# A plain `cargo build --release` (or `tauri dev`) resolves resources from
# target\release\binaries, which `tauri build` only refreshes when it bundles.
# Replace that copy too, and drop the pre-rename axiom-backend, so a local
# test never runs a stale backend that ignores ECONOSIFT_DATA_DIR (P3-37).
$targetBin = Join-Path $desktop "src-tauri\target\release\binaries"
if (Test-Path $targetBin) {
    foreach ($old in @("econosift-backend", "axiom-backend")) {
        $p = Join-Path $targetBin $old
        if (Test-Path $p) { Remove-Item $p -Recurse -Force }
    }
    Copy-Item $stage (Join-Path $targetBin "econosift-backend") -Recurse -Force
}

Write-Host "==> [3/3] tauri build (frontend + Rust + NSIS)..." -ForegroundColor Cyan
$env:PATH = "$env:USERPROFILE\.cargo\bin;$env:PATH"
Push-Location $desktop
npm run build
if ($LASTEXITCODE -ne 0) { throw "tauri build failed" }
Pop-Location

$installer = Get-ChildItem (Join-Path $desktop "src-tauri\target\release\bundle\nsis\*-setup.exe") |
    Select-Object -First 1
Write-Host "`nDONE. Installer: $($installer.FullName)" -ForegroundColor Green

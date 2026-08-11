# Native backend dev runner (NO Docker). Requires Python 3.12 on PATH.
#
#   powershell -ExecutionPolicy Bypass -File scripts\dev-backend.ps1
#
# First run creates a local venv and installs requirements (~1 min). Uses
# config.settings_dev (SQLite + in-memory, no Postgres/Redis). Ctrl+C to stop.
$ErrorActionPreference = "Stop"
$backend = Join-Path $PSScriptRoot "..\backend" | Resolve-Path
Set-Location $backend

$venvPy = Join-Path $backend ".venv\Scripts\python.exe"

# Recreate the venv if missing or broken (the repo may carry a stale .venv).
$ok = $false
if (Test-Path $venvPy) { try { & $venvPy --version *> $null; $ok = $true } catch {} }
if (-not $ok) {
    Write-Host "Setting up a fresh Python venv (one-time)..." -ForegroundColor Cyan
    if (Test-Path (Join-Path $backend ".venv")) { Remove-Item -Recurse -Force (Join-Path $backend ".venv") }
    python -m venv .venv
    & $venvPy -m pip install --upgrade pip
    & $venvPy -m pip install -r requirements.txt
}

$env:DJANGO_SETTINGS_MODULE = "config.settings_dev"
& $venvPy manage.py migrate --settings=config.settings_dev
Write-Host "`nBackend on http://localhost:8000  (frontend: run 'npm run dev' in ./frontend)`n" -ForegroundColor Green
& $venvPy manage.py runserver 0.0.0.0:8000 --settings=config.settings_dev

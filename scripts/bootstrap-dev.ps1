[CmdletBinding()]
param(
    [switch]$SkipInstall
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$backendDir = Join-Path $repoRoot "backend"
$venvDir = Join-Path $backendDir ".venv"
$venvPython = Join-Path $venvDir "Scripts\python.exe"

function Test-Python([string]$Executable) {
    if (-not (Test-Path -LiteralPath $Executable)) { return $false }
    try {
        & $Executable --version *> $null
        return $LASTEXITCODE -eq 0
    } catch {
        return $false
    }
}

if ((Test-Path -LiteralPath $venvDir) -and -not (Test-Python $venvPython)) {
    $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $backup = "$venvDir.broken-$stamp"
    Move-Item -LiteralPath $venvDir -Destination $backup
    Write-Warning "Preserved the invalid virtual environment at $backup"
}

if (-not (Test-Python $venvPython)) {
    $launcher = Get-Command py -ErrorAction SilentlyContinue
    if ($launcher) {
        & $launcher.Source -3.12 -m venv $venvDir
    } else {
        $python = Get-Command python -ErrorAction SilentlyContinue
        if (-not $python) {
            throw "Python 3.12 is required. Install it, then rerun this script."
        }
        & $python.Source -m venv $venvDir
    }
}

if (-not $SkipInstall) {
    & $venvPython -m pip install --upgrade pip
    & $venvPython -m pip install -r (Join-Path $backendDir "requirements.txt")
}

& $venvPython --version
Write-Host "Backend environment ready: $venvDir"

# Desporto & Cia. — one-command launcher (Windows PowerShell).
# First run: creates the Python environment and builds the UI. Then serves everything on http://localhost:8000
#   .\start.ps1            start (builds the UI only if it was never built)
#   .\start.ps1 -Rebuild   rebuild the UI first (after changing frontend code)
param([switch]$Rebuild)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$py = Join-Path $root "backend\.venv\Scripts\python.exe"

if (-not (Test-Path $py)) {
    Write-Host "Creating Python environment..."
    python -m venv (Join-Path $root "backend\.venv")
    & $py -m pip install --quiet -e "$(Join-Path $root 'backend')[dev,anthropic]"
}

$dist = Join-Path $root "frontend\dist\index.html"
if ($Rebuild -or -not (Test-Path $dist)) {
    Write-Host "Building the UI..."
    Push-Location (Join-Path $root "frontend")
    if (-not (Test-Path "node_modules")) { npm install --no-audit --no-fund }
    npm run build
    Pop-Location
}

Write-Host "Desporto & Cia. is opening at http://localhost:8000 (Ctrl+C to stop; the game autosaves weekly)."
Start-Process "http://localhost:8000"
Push-Location (Join-Path $root "backend")
& $py -m uvicorn app.main:app --port 8000
Pop-Location

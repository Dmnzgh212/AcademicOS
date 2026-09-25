$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

Write-Host "AcademicOS first-run bootstrap" -ForegroundColor Cyan

if (-not (Test-Path ".git")) {
    throw "Run this script from the AcademicOS repository root."
}

$venvPython = Join-Path $PWD ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    Write-Host "Creating Python 3.11 virtual environment..."
    py -3.11 -m venv .venv
}

Write-Host "Installing AcademicOS with Brightspace + mail support..."
& $venvPython -m pip install --upgrade pip
& $venvPython -m pip install -e ".[brightspace,mail]"

if (-not (Test-Path "config.local.toml")) {
    Copy-Item "config.example.toml" "config.local.toml"
    Write-Host "Created config.local.toml from example." -ForegroundColor Green
} else {
    Write-Host "Keeping existing config.local.toml." -ForegroundColor Yellow
}

Write-Host "Running local-only doctor..." -ForegroundColor Cyan
& (Join-Path $PWD ".venv\Scripts\academicos-doctor.exe") --local-only --config config.local.toml

Write-Host ""
Write-Host "Local bootstrap complete." -ForegroundColor Green
Write-Host "Next: review config.local.toml, then run:"
Write-Host ".\.venv\Scripts\academicos-doctor.exe --live --bootstrap-auth --config config.local.toml" -ForegroundColor White

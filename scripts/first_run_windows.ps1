$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

Write-Host "AcademicOS first-run bootstrap" -ForegroundColor Cyan

if (-not (Test-Path ".git")) {
    throw "Run this script from the AcademicOS repository root."
}

$venvPython = Join-Path $PWD ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    Write-Host "Creating Python virtual environment..."

    $created = $false
    foreach ($version in @("3.12", "3.11")) {
        try {
            & py "-$version" -m venv .venv 2>$null
            if ($LASTEXITCODE -eq 0 -and (Test-Path $venvPython)) {
                Write-Host "Using Python $version." -ForegroundColor Green
                $created = $true
                break
            }
        } catch {
            # Try the next supported interpreter.
        }
    }

    if (-not $created) {
        try {
            & python -c "import sys; assert sys.version_info >= (3, 11)" 2>$null
            if ($LASTEXITCODE -eq 0) {
                & python -m venv .venv
                $created = Test-Path $venvPython
            }
        } catch {
            $created = $false
        }
    }

    if (-not $created) {
        throw "Python 3.11 or newer was not found. Install Python 3.11/3.12 and rerun."
    }
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
Write-Host ""
Write-Host "Real-account validation sequence:" -ForegroundColor Cyan
Write-Host "1. .\.venv\Scripts\academicos-doctor.exe --live --bootstrap-auth --config config.local.toml" -ForegroundColor White
Write-Host "2. .\.venv\Scripts\academicos-capabilities.exe --json-out data\audits\capabilities.json" -ForegroundColor White
Write-Host "3. .\.venv\Scripts\academicos-coverage.exe" -ForegroundColor White
Write-Host "4. .\.venv\Scripts\academicos-sync.exe --config config.local.toml" -ForegroundColor White
Write-Host ""
Write-Host "The doctor/capability reports are designed to omit tokens, cookies, email addresses, and academic response values." -ForegroundColor DarkGray

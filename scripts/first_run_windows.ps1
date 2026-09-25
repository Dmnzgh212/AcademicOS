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
Write-Host "Recommended real-account validation:" -ForegroundColor Cyan
Write-Host ".\.venv\Scripts\academicos-audit.exe --live --bootstrap-auth --config config.local.toml" -ForegroundColor White
Write-Host ""
Write-Host "After the live audit succeeds:" -ForegroundColor Cyan
Write-Host ".\.venv\Scripts\academicos-sync.exe --config config.local.toml" -ForegroundColor White
Write-Host ".\.venv\Scripts\academicos-health.exe" -ForegroundColor White
Write-Host ".\.venv\Scripts\academicos-coverage.exe" -ForegroundColor White
Write-Host ""
Write-Host "academicos-audit writes one timestamped sanitized JSON bundle under the configured data\audits directory." -ForegroundColor DarkGray
Write-Host "The bundle excludes raw academic content, tokens, cookies, email addresses, grades, and downloaded files." -ForegroundColor DarkGray

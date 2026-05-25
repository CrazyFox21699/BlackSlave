$ErrorActionPreference = "Stop"
$AgentDir = Split-Path -Parent $PSScriptRoot
Set-Location $AgentDir

Write-Host "Daily Tracking Agent setup"
Write-Host "AgentDir: $AgentDir"

$python = Get-Command "python" -ErrorAction SilentlyContinue
if (-not $python) {
    throw "Python was not found. Install Python 3.11+ and make sure 'python' is available in PATH."
}

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Write-Host "Creating local virtual environment..."
    & $python.Source -m venv .venv
}

Write-Host "Installing Python requirements..."
& ".venv\Scripts\python.exe" -m pip install --upgrade pip
& ".venv\Scripts\python.exe" -m pip install -r requirements.txt
& ".venv\Scripts\python.exe" -m pip check

Write-Host ""
Write-Host "Setup done. Edit config.yaml, then run TEST_CONFIG.bat."

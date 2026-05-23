$ErrorActionPreference = "Stop"
$AgentDir = Split-Path -Parent $PSScriptRoot
Set-Location $AgentDir

Write-Host "Daily Tracking Agent portable setup"
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

$ollama = Get-Command "ollama" -ErrorAction SilentlyContinue
if ($ollama) {
    Write-Host "Ollama found: $($ollama.Source)"
    Write-Host "Starting Ollama service for model check..."
    try {
        Invoke-WebRequest -Uri "http://localhost:11434/api/tags" -UseBasicParsing -TimeoutSec 2 | Out-Null
    } catch {
        Start-Process -FilePath $ollama.Source -ArgumentList "serve" -WindowStyle Minimized | Out-Null
        Start-Sleep -Seconds 5
    }
    Write-Host "Optional: pulling qwen2.5:7b model. This can take a while on first setup."
    & $ollama.Source pull qwen2.5:7b
} else {
    Write-Warning "Ollama was not found. Install Ollama for local AI review, or run rule-based mode only."
}

Write-Host ""
Write-Host "Setup done. Edit config.yaml, then double-click RUN_DAILY_WITH_OLLAMA.bat."

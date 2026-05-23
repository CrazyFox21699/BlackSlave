param(
    [string]$ConfigPath = "",
    [switch]$DryRun,
    [switch]$NoTeams
)

$ErrorActionPreference = "Stop"
$AgentDir = Split-Path -Parent $PSScriptRoot
if (-not $ConfigPath) {
    $ConfigPath = Join-Path $AgentDir "config.yaml"
}
$PythonExe = Join-Path $AgentDir ".venv\Scripts\python.exe"
if (-not (Test-Path $PythonExe)) {
    $PythonExe = "python"
}

function Test-OllamaReady {
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:11434/api/tags" -UseBasicParsing -TimeoutSec 2
        return ($response.StatusCode -ge 200 -and $response.StatusCode -lt 300)
    } catch {
        return $false
    }
}

function Start-OllamaIfNeeded {
    if (Test-OllamaReady) {
        Write-Host "Ollama API already running."
        return $true
    }

    $ollama = Get-Command "ollama" -ErrorAction SilentlyContinue
    if (-not $ollama) {
        Write-Warning "Ollama command not found. Running rule-based report without Ollama."
        return $false
    }

    Write-Host "Starting Ollama..."
    Start-Process -FilePath $ollama.Source -ArgumentList "serve" -WindowStyle Minimized | Out-Null
    for ($i = 1; $i -le 30; $i++) {
        Start-Sleep -Seconds 1
        if (Test-OllamaReady) {
            Write-Host "Ollama API is ready."
            return $true
        }
    }

    Write-Warning "Ollama did not become ready in time. Running rule-based report without Ollama."
    return $false
}

$ollamaReady = Start-OllamaIfNeeded
$argsList = @((Join-Path $AgentDir "main.py"), "--config", $ConfigPath)
if ($ollamaReady) {
    $argsList += "--with-ollama"
} else {
    $argsList += "--no-ollama"
}
if ($DryRun) {
    $argsList += "--dry-run"
}
if ($NoTeams) {
    $argsList += "--no-teams"
}

Write-Host "Running Daily Tracking Agent..."
& $PythonExe @argsList
exit $LASTEXITCODE

param(
    [Parameter(Mandatory = $true)]
    [string]$Question,
    [string]$ConfigPath = "",
    [switch]$SendToTeams
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

$ollama = Get-Command "ollama" -ErrorAction SilentlyContinue
if (-not (Test-OllamaReady) -and $ollama) {
    Start-Process -FilePath $ollama.Source -ArgumentList "serve" -WindowStyle Minimized | Out-Null
    for ($i = 1; $i -le 20; $i++) {
        Start-Sleep -Seconds 1
        if (Test-OllamaReady) { break }
    }
}

$argsList = @((Join-Path $AgentDir "main.py"), "--config", $ConfigPath, "--ask", $Question)
if (Test-OllamaReady) {
    $argsList += "--with-ollama"
} else {
    $argsList += "--no-ollama"
}
if ($SendToTeams) {
    $argsList += "--send-answer-to-teams"
}

& $PythonExe @argsList
exit $LASTEXITCODE

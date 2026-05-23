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

$argsList = @((Join-Path $AgentDir "main.py"), "--config", $ConfigPath, "--urgent-impact-only", "--no-ollama")
if ($DryRun) {
    $argsList += "--dry-run"
}
if ($NoTeams) {
    $argsList += "--no-teams"
}

& $PythonExe @argsList
exit $LASTEXITCODE

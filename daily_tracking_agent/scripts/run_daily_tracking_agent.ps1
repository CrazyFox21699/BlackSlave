param(
    [string]$AgentDir = "",
    [string]$PythonExe = "",
    [string]$ConfigPath = "",
    [switch]$DryRun,
    [switch]$NoTeams
)

if (-not $AgentDir) {
    $AgentDir = Split-Path -Parent $PSScriptRoot
}
if (-not $PythonExe) {
    $PythonExe = Join-Path $AgentDir ".venv\Scripts\python.exe"
}
if (-not (Test-Path $PythonExe)) {
    $PythonExe = "python"
}
if (-not $ConfigPath) {
    $ConfigPath = Join-Path $AgentDir "config.yaml"
}

Set-Location $AgentDir
$argsList = @("$AgentDir\main.py", "--config", $ConfigPath)
if ($DryRun) {
    $argsList += "--dry-run"
}
if ($NoTeams) {
    $argsList += "--no-teams"
}
& $PythonExe @argsList
exit $LASTEXITCODE

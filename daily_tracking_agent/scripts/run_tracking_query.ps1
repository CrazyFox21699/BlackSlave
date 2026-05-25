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

$argsList = @((Join-Path $AgentDir "main.py"), "--config", $ConfigPath, "--ask", $Question)
if ($SendToTeams) {
    $argsList += "--send-answer-to-teams"
}

& $PythonExe @argsList
exit $LASTEXITCODE

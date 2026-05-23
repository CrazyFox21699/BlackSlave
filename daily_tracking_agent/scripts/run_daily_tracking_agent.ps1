param(
    [string]$AgentDir = "",
    [string]$PythonExe = "",
    [string]$ConfigPath = ""
)

if (-not $AgentDir) {
    $AgentDir = Split-Path -Parent $PSScriptRoot
}
if (-not $PythonExe) {
    $PythonExe = Join-Path $AgentDir ".venv\Scripts\python.exe"
}
if (-not $ConfigPath) {
    $ConfigPath = Join-Path $AgentDir "config.yaml"
}

Set-Location $AgentDir
& $PythonExe "$AgentDir\main.py" --config $ConfigPath
exit $LASTEXITCODE

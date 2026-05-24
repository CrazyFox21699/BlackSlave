param(
    [string]$TaskName = "Daily Tracking Command Inbox",
    [string]$RunScript = "",
    [string]$StartTime = "07:30",
    [string]$EndTime = "19:30",
    [int]$IntervalMinutes = 1
)

if (-not $RunScript) {
    $AgentDir = Split-Path -Parent $PSScriptRoot
    $RunScript = Join-Path $AgentDir "scripts\run_command_inbox.ps1"
}

$Action = "powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$RunScript`""

schtasks.exe /Create `
    /TN $TaskName `
    /TR $Action `
    /SC MINUTE `
    /MO $IntervalMinutes `
    /ST $StartTime `
    /ET $EndTime `
    /F | Out-Host

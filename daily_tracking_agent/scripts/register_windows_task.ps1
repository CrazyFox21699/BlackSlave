param(
    [string]$TaskName = "Daily Tracking Control Report",
    [string]$RunScript = "",
    [string]$StartTime = "08:00"
)

if (-not $RunScript) {
    $AgentDir = Split-Path -Parent $PSScriptRoot
    $RunScript = Join-Path $AgentDir "scripts\run_daily_with_ollama.ps1"
}

$Action = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$RunScript`""

$Trigger = New-ScheduledTaskTrigger -Daily -At $StartTime
$Settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 30)

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $Action `
    -Trigger $Trigger `
    -Settings $Settings `
    -Description "Runs local Daily Tracking Agent and sends Teams summary through webhook." `
    -Force

param(
  [string]$TaskName = "Enix Casablanca Lead Scraper",
  [string]$Time = "07:30"
)

$ErrorActionPreference = "Stop"
$runner = Join-Path $PSScriptRoot "run_daily.ps1"
if (-not (Test-Path $runner)) { throw "Cannot find $runner" }

$timeValue = [DateTime]::ParseExact($Time, "HH:mm", $null)
$escapedRunner = "`"$runner`""
$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -ExecutionPolicy Bypass -File $escapedRunner"
$trigger = New-ScheduledTaskTrigger -Daily -At $timeValue
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -Description "Runs the Enix Casablanca Google Maps lead scraper and qualification pipeline daily." -Force

Write-Host "Installed scheduled task: $TaskName"
Write-Host "Daily time: $Time"
Write-Host "Runner: $runner"

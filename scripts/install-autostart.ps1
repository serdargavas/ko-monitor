<#
.SYNOPSIS
  Registers the "KO Monitor" Task Scheduler task: starts the agent and phone API at logon,
  restarts it every minute if it fails.

.NOTES
  The user runs this once, from the project root, in a normal (non-admin) PowerShell:
      powershell -ExecutionPolicy Bypass -File scripts\install-autostart.ps1
  Start now:  Start-ScheduledTask -TaskName "KO Monitor"
  Remove:     Unregister-ScheduledTask -TaskName "KO Monitor" -Confirm:$false
#>
[CmdletBinding()]
param(
    [string]$TaskName = "KO Monitor"
)

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $projectRoot ".venv\Scripts\pythonw.exe"  # pythonw: no console window
if (-not (Test-Path $python)) {
    throw "Sanal ortam bulunamadi: $python (once docs\setup.md adim 1)"
}
if (-not (Test-Path (Join-Path $projectRoot "config.toml"))) {
    Write-Warning "config.toml yok; varsayilan ayarlar kullanilacak (docs\setup.md adim 2)"
}

$user = "$env:USERDOMAIN\$env:USERNAME"
$action = New-ScheduledTaskAction -Execute $python -Argument "-m ko_monitor run" -WorkingDirectory $projectRoot
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $user
# Screen capture needs the user's desktop session, so the task runs interactively as this user.
$principal = New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet `
    -RestartCount 999 `
    -RestartInterval (New-TimeSpan -Minutes 1) `
    -ExecutionTimeLimit ([TimeSpan]::Zero) `
    -StartWhenAvailable `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -MultipleInstances IgnoreNew

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Principal $principal `
    -Settings $settings -Description "KO Monitor: oyun izleme ajani ve telefon API'si" -Force | Out-Null

Write-Host "Gorev kaydedildi: $TaskName"
Write-Host "Hemen baslatmak icin: Start-ScheduledTask -TaskName '$TaskName'"

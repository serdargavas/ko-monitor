<#
.SYNOPSIS
  Registers the "KO Monitor" Task Scheduler task: starts the agent and phone API at logon,
  and starts it again within a minute whenever it is not running (crash, non-zero exit).

.NOTES
  The user runs this once, from the project root, in a normal (non-admin) PowerShell:
      powershell -ExecutionPolicy Bypass -File scripts\install-autostart.ps1
  Start now:  Start-ScheduledTask -TaskName "KO Monitor"
  Pause:      Disable-ScheduledTask -TaskName "KO Monitor"; Stop-ScheduledTask -TaskName "KO Monitor"
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
$logonTrigger = New-ScheduledTaskTrigger -AtLogOn -User $user
# Watchdog: RestartCount/RestartInterval only cover a failed launch, not a process that starts and
# later exits non-zero (agent loop stopped, port in use, crash). This trigger fires every minute;
# with -MultipleInstances IgnoreNew it is ignored while the agent runs and starts it when it is not.
# The duration is explicit and very long (10 years) instead of relying on the default when omitted.
$watchdogTrigger = New-ScheduledTaskTrigger -Once -At (Get-Date) `
    -RepetitionInterval (New-TimeSpan -Minutes 1) `
    -RepetitionDuration (New-TimeSpan -Days 3650)
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

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger @($logonTrigger, $watchdogTrigger) `
    -Principal $principal -Settings $settings `
    -Description "KO Monitor: oyun izleme ajani ve telefon API'si" -Force | Out-Null

Write-Host "Gorev kaydedildi: $TaskName"
Write-Host "Hemen baslatmak icin: Start-ScheduledTask -TaskName '$TaskName'"

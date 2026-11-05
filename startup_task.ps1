param(
    [ValidateSet("enable", "disable")]
    [string]$Action = "enable",
    [string]$InstalledExePath = ""
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$taskName = "AuraAssistant"

if ($Action -eq "disable") {
    if (Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue) {
        Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
        Write-Host "[Aura] Startup task removed: $taskName"
    } else {
        Write-Host "[Aura] Startup task not found: $taskName"
    }
    return
}

$projectRoot = $PSScriptRoot
$distOneFileExe = Join-Path $projectRoot "dist\Aura.exe"
$distOneDirExe = Join-Path $projectRoot "dist\Aura\Aura.exe"
$venvPython = Join-Path $projectRoot ".venv\Scripts\python.exe"

$exeCandidate = ""
if ($InstalledExePath -and (Test-Path $InstalledExePath)) {
    $exeCandidate = $InstalledExePath
} elseif (Test-Path $distOneFileExe) {
    $exeCandidate = $distOneFileExe
} elseif (Test-Path $distOneDirExe) {
    $exeCandidate = $distOneDirExe
}

if ($exeCandidate) {
    $actionDef = New-ScheduledTaskAction -Execute $exeCandidate -Argument "--tray --minimized" -WorkingDirectory (Split-Path $exeCandidate)
} elseif (Test-Path $venvPython) {
    $actionDef = New-ScheduledTaskAction -Execute $venvPython -Argument "run.py --tray --minimized" -WorkingDirectory $projectRoot
} else {
    throw "No startup target found. Build Aura.exe or create .venv first."
}

$trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable

Register-ScheduledTask -TaskName $taskName -Action $actionDef -Trigger $trigger -Settings $settings -Description "Start Aura assistant at user logon" -Force | Out-Null

Write-Host "[Aura] Startup task enabled: $taskName"

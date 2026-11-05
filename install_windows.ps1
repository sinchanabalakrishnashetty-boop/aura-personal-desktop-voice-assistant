$ErrorActionPreference = "Stop"

Set-Location $PSScriptRoot

$projectRoot = $PSScriptRoot
$distOneFileExe = Join-Path $projectRoot "dist\Aura.exe"
$distOneDirExe = Join-Path $projectRoot "dist\Aura\Aura.exe"
$distOneDirRoot = Join-Path $projectRoot "dist\Aura"
$installDir = Join-Path $env:LOCALAPPDATA "AuraDesktop"
$installedExe = ""

Write-Host "[Aura] Windows one-click installer"

if (-not (Test-Path $distOneFileExe) -and -not (Test-Path $distOneDirExe)) {
    Write-Host "[Aura] No built executable found. Building now..."
    & (Join-Path $projectRoot "build_desktop.ps1")
}

if (-not (Test-Path $distOneFileExe) -and -not (Test-Path $distOneDirExe)) {
    throw "Build failed: neither dist\\Aura.exe nor dist\\Aura\\Aura.exe was created."
}

New-Item -ItemType Directory -Force -Path $installDir | Out-Null

if (Test-Path $distOneFileExe) {
    $installedExe = Join-Path $installDir "Aura.exe"
    Copy-Item -Force $distOneFileExe $installedExe
} elseif (Test-Path $distOneDirExe) {
    $targetAppDir = Join-Path $installDir "Aura"
    if (Test-Path $targetAppDir) {
        try {
            Remove-Item -Recurse -Force $targetAppDir
        } catch {
            Write-Warning "[Aura] Could not fully clean install folder; continuing with in-place update."
        }
    }
    New-Item -ItemType Directory -Force -Path $targetAppDir | Out-Null
    Copy-Item -Recurse -Force (Join-Path $distOneDirRoot "*") $targetAppDir
    $installedExe = Join-Path $targetAppDir "Aura.exe"
}

if (-not $installedExe -or -not (Test-Path $installedExe)) {
    throw "Install failed: executable was not copied to install directory."
}

$projectEnv = Join-Path $projectRoot ".env"
if (Test-Path $projectEnv) {
    $installEnv = Join-Path (Split-Path $installedExe) ".env"
    Copy-Item -Force $projectEnv $installEnv
}

$desktopShortcut = Join-Path ([Environment]::GetFolderPath("Desktop")) "Aura.lnk"
$wsh = New-Object -ComObject WScript.Shell
$shortcut = $wsh.CreateShortcut($desktopShortcut)
$shortcut.TargetPath = $installedExe
$shortcut.Arguments = "--tray --minimized"
$shortcut.WorkingDirectory = Split-Path $installedExe


$iconLocation = $installedExe

if ($env:AURA_SHORTCUT_ICON -and (Test-Path $env:AURA_SHORTCUT_ICON)) {
    $iconLocation = $env:AURA_SHORTCUT_ICON
} else {
    $projectIcon = Join-Path $projectRoot "assets\AuraShortcut.ico"
    $installedIcon = Join-Path (Split-Path $installedExe) "AuraShortcut.ico"
    if (Test-Path $projectIcon) {
        $iconLocation = $projectIcon
    } elseif (Test-Path $installedIcon) {
        $iconLocation = $installedIcon
    }
}

$shortcut.IconLocation = "$iconLocation,0"
$shortcut.Save()

& (Join-Path $projectRoot "startup_task.ps1") -Action enable -InstalledExePath $installedExe

Write-Host "[Aura] Installed successfully"
Write-Host "[Aura] Executable: $installedExe"
Write-Host "[Aura] Desktop shortcut: $desktopShortcut"
Write-Host "[Aura] Startup at login: enabled"
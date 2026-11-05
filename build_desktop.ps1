$ErrorActionPreference = "Stop"

Write-Host "[Aura] Preparing desktop build..."

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    throw "Virtual environment not found at .venv. Create it first."
}

$python = ".venv\Scripts\python.exe"

Write-Host "[Aura] Installing/Updating PyInstaller..."
& $python -m pip install --upgrade pip pyinstaller
if (Test-Path "build") { Remove-Item -Recurse -Force "build" }
if (Test-Path "dist") { Remove-Item -Recurse -Force "dist" }
Write-Host "[Aura] Building Aura.exe..."
& $python -m PyInstaller `
  --noconfirm `
  --clean `
  --name Aura `
  --windowed `
  --add-data "aura;aura" `
  --add-data "data;data" `
  --add-data "credentials;credentials" `
  --add-data "models;models" `
  --hidden-import "pystray" `
  --hidden-import "PIL" `
  run.py

Write-Host "[Aura] Build complete: dist\Aura.exe"
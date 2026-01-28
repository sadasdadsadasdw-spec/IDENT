# ========================================================================
# IDENT -> Bitrix24 Integration - EXE Builder
# ========================================================================
#
# Builds standalone EXE using PyInstaller
#
# ========================================================================

Write-Host "========================================================================" -ForegroundColor Cyan
Write-Host "BUILDING EXE: IDENT -> Bitrix24 Integration" -ForegroundColor Cyan
Write-Host "========================================================================" -ForegroundColor Cyan
Write-Host ""

# Check if PyInstaller is installed
$PyInstallerCheck = python -m PyInstaller --version 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: PyInstaller not installed!" -ForegroundColor Red
    Write-Host ""
    Write-Host "Install it with:" -ForegroundColor Yellow
    Write-Host "  pip install pyinstaller" -ForegroundColor White
    Write-Host ""
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host "PyInstaller version: $PyInstallerCheck" -ForegroundColor Green
Write-Host ""

# Clean previous build
Write-Host "Cleaning previous build..." -ForegroundColor Cyan
if (Test-Path "dist") {
    Remove-Item -Recurse -Force "dist"
}
if (Test-Path "build") {
    Remove-Item -Recurse -Force "build"
}
if (Test-Path "ident_sync.spec") {
    Remove-Item -Force "ident_sync.spec"
}
Write-Host "Clean complete" -ForegroundColor Green
Write-Host ""

# Build EXE
Write-Host "Building EXE (this may take 2-3 minutes)..." -ForegroundColor Cyan
Write-Host ""

pyinstaller `
    --name="ident_sync" `
    --onefile `
    --windowed `
    --add-data="config.ini;." `
    --hidden-import=pyodbc `
    --hidden-import=requests `
    --hidden-import=configparser `
    --hidden-import=pathlib `
    --collect-all=pyodbc `
    --noconfirm `
    main.py

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "========================================================================" -ForegroundColor Red
    Write-Host "ERROR: Build failed!" -ForegroundColor Red
    Write-Host "========================================================================" -ForegroundColor Red
    Write-Host ""
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host ""
Write-Host "========================================================================" -ForegroundColor Green
Write-Host "BUILD SUCCESSFUL!" -ForegroundColor Green
Write-Host "========================================================================" -ForegroundColor Green
Write-Host ""

# Check output
$ExePath = "dist\ident_sync.exe"
if (Test-Path $ExePath) {
    $ExeInfo = Get-Item $ExePath
    $SizeMB = [math]::Round($ExeInfo.Length / 1MB, 2)

    Write-Host "EXE file created:" -ForegroundColor Cyan
    Write-Host "  Path: $ExePath" -ForegroundColor White
    Write-Host "  Size: $SizeMB MB" -ForegroundColor White
    Write-Host ""

    Write-Host "Next steps:" -ForegroundColor Cyan
    Write-Host "  1. Test the EXE: .\dist\ident_sync.exe" -ForegroundColor Yellow
    Write-Host "  2. Install task: .\install_task.ps1" -ForegroundColor Yellow
    Write-Host ""
} else {
    Write-Host "WARNING: EXE file not found at expected location" -ForegroundColor Yellow
    Write-Host ""
}

Read-Host "Press Enter to exit"

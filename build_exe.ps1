# Build IDENT -> Bitrix24 Integration Executable
# Creates standalone EXE using PyInstaller

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Building IDENT Integration EXE" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check Python
$PythonCmd = "python"
try {
    $PythonVersion = & $PythonCmd --version 2>&1
    Write-Host "Python: $PythonVersion" -ForegroundColor Green
} catch {
    Write-Host "ERROR: Python not found" -ForegroundColor Red
    Write-Host ""
    Read-Host "Press Enter to exit"
    exit 1
}

# Check config.ini
if (-not (Test-Path "config.ini")) {
    Write-Host "ERROR: config.ini not found" -ForegroundColor Red
    Write-Host ""
    Read-Host "Press Enter to exit"
    exit 1
}

# Check main.py
if (-not (Test-Path "main.py")) {
    Write-Host "ERROR: main.py not found" -ForegroundColor Red
    Write-Host ""
    Read-Host "Press Enter to exit"
    exit 1
}

# Install PyInstaller if needed
Write-Host "Checking PyInstaller..." -ForegroundColor Cyan
$PyInstallerInstalled = & $PythonCmd -m pip list 2>&1 | Select-String "pyinstaller"
if (-not $PyInstallerInstalled) {
    Write-Host "Installing PyInstaller..." -ForegroundColor Yellow
    & $PythonCmd -m pip install pyinstaller
    Write-Host ""
}

# Clean previous build
if (Test-Path "dist") {
    Write-Host "Cleaning dist..." -ForegroundColor Yellow
    Remove-Item -Path "dist" -Recurse -Force
}
if (Test-Path "build") {
    Write-Host "Cleaning build..." -ForegroundColor Yellow
    Remove-Item -Path "build" -Recurse -Force
}
if (Test-Path "*.spec") {
    Write-Host "Cleaning spec files..." -ForegroundColor Yellow
    Remove-Item -Path "*.spec" -Force
}

Write-Host ""
Write-Host "Building EXE..." -ForegroundColor Cyan
Write-Host ""

# Build with PyInstaller
& pyinstaller `
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
    Write-Host "ERROR: Build failed" -ForegroundColor Red
    Write-Host ""
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "Build Complete" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "EXE location: dist\ident_sync.exe" -ForegroundColor White
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "  1. Test: .\dist\ident_sync.exe" -ForegroundColor White
Write-Host "  2. Install: .\install_task.ps1" -ForegroundColor White
Write-Host ""
Read-Host "Press Enter to exit"

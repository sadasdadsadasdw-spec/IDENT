# Quick Setup: Create config.ini with interactive prompts
# Run this script to quickly configure a new filial

$ErrorActionPreference = "Stop"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "IDENT Integration - Quick Setup" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check if config.ini already exists
if (Test-Path "config.ini") {
    Write-Host "WARNING: config.ini already exists!" -ForegroundColor Yellow
    Write-Host ""
    $Overwrite = Read-Host "Overwrite existing config? (y/n)"
    if ($Overwrite -ne 'y') {
        Write-Host "Setup cancelled" -ForegroundColor Yellow
        exit 0
    }
    Write-Host ""
}

# Check if example exists
if (-not (Test-Path "config.example.ini")) {
    Write-Host "ERROR: config.example.ini not found!" -ForegroundColor Red
    Write-Host "Please ensure you are in the correct directory" -ForegroundColor Yellow
    exit 1
}

Write-Host "This wizard will help you create config.ini" -ForegroundColor Green
Write-Host ""

# Collect parameters
Write-Host "1. DATABASE CONFIGURATION" -ForegroundColor Cyan
Write-Host "===========================" -ForegroundColor Cyan

$DbServer = Read-Host "SQL Server instance (e.g., .\PZSQLSERVER or 192.168.1.100)"
$DbName = Read-Host "Database name (default: IdentDB)"
if ([string]::IsNullOrWhiteSpace($DbName)) { $DbName = "IdentDB" }

$DbUser = Read-Host "SQL Server username (default: ident_user)"
if ([string]::IsNullOrWhiteSpace($DbUser)) { $DbUser = "ident_user" }

$DbPassword = Read-Host "SQL Server password" -AsSecureString
$DbPasswordPlain = [Runtime.InteropServices.Marshal]::PtrToStringAuto(
    [Runtime.InteropServices.Marshal]::SecureStringToBSTR($DbPassword)
)

Write-Host ""
Write-Host "2. BITRIX24 CONFIGURATION" -ForegroundColor Cyan
Write-Host "==========================" -ForegroundColor Cyan

$WebhookUrl = Read-Host "Bitrix24 webhook URL (e.g., https://portal.bitrix24.ru/rest/1/token/)"

Write-Host ""
Write-Host "3. SYNC CONFIGURATION" -ForegroundColor Cyan
Write-Host "======================" -ForegroundColor Cyan

Write-Host "Filial ID must be unique for each location!" -ForegroundColor Yellow
Write-Host "Existing filials:" -ForegroundColor Gray
Write-Host "  Filial 1 = ID 1" -ForegroundColor Gray
Write-Host "  Filial 2 = ID 2" -ForegroundColor Gray
Write-Host "  etc..." -ForegroundColor Gray

do {
    $FilialId = Read-Host "Filial ID (1-5)"
} while ($FilialId -notmatch '^[1-5]$')

$IntervalMinutes = Read-Host "Sync interval in minutes (default: 2)"
if ([string]::IsNullOrWhiteSpace($IntervalMinutes)) { $IntervalMinutes = "2" }

Write-Host ""
Write-Host "Creating config.ini..." -ForegroundColor Cyan

# Copy template
Copy-Item "config.example.ini" "config.ini" -Force

# Replace parameters
$ConfigContent = Get-Content "config.ini" -Raw

$ConfigContent = $ConfigContent -replace '^server = .*$', "server = $DbServer" -replace '(?m)'
$ConfigContent = $ConfigContent -replace '^database = .*$', "database = $DbName" -replace '(?m)'
$ConfigContent = $ConfigContent -replace '^username = .*$', "username = $DbUser" -replace '(?m)'
$ConfigContent = $ConfigContent -replace '^password = .*$', "password = $DbPasswordPlain" -replace '(?m)'
$ConfigContent = $ConfigContent -replace '^webhook_url = .*$', "webhook_url = $WebhookUrl" -replace '(?m)'
$ConfigContent = $ConfigContent -replace '^interval_minutes = .*$', "interval_minutes = $IntervalMinutes" -replace '(?m)'
$ConfigContent = $ConfigContent -replace '^filial_id = .*$', "filial_id = $FilialId" -replace '(?m)'

Set-Content "config.ini" -Value $ConfigContent -Force

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "Configuration created successfully!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""

Write-Host "Configuration summary:" -ForegroundColor White
Write-Host "  Database:    $DbServer\$DbName" -ForegroundColor Gray
Write-Host "  Username:    $DbUser" -ForegroundColor Gray
Write-Host "  Webhook:     $WebhookUrl" -ForegroundColor Gray
Write-Host "  Filial ID:   $FilialId" -ForegroundColor Gray
Write-Host "  Interval:    $IntervalMinutes minutes" -ForegroundColor Gray
Write-Host ""

Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "  1. Create logs and data directories:" -ForegroundColor White
Write-Host "     New-Item -ItemType Directory -Path 'logs','data' -Force" -ForegroundColor Gray
Write-Host ""
Write-Host "  2. Test configuration:" -ForegroundColor White
Write-Host "     .\dist\ident_sync\ident_sync.exe" -ForegroundColor Gray
Write-Host ""
Write-Host "  3. Install scheduled task:" -ForegroundColor White
Write-Host "     .\install_task_onedir.ps1" -ForegroundColor Gray
Write-Host ""

$CreateDirs = Read-Host "Create logs and data directories now? (y/n)"
if ($CreateDirs -eq 'y') {
    New-Item -ItemType Directory -Path "logs" -Force | Out-Null
    New-Item -ItemType Directory -Path "data" -Force | Out-Null
    Write-Host "Directories created successfully" -ForegroundColor Green
    Write-Host ""
}

Write-Host "Setup complete!" -ForegroundColor Green
Write-Host ""
Read-Host "Press Enter to exit"

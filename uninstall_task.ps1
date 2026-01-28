# Uninstall IDENT -> Bitrix24 Integration from Windows Scheduled Task
# Run as Administrator

$ErrorActionPreference = "Stop"

$TaskName = "IdentBitrix24Integration"
$TaskPath = "\IDENT\"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Uninstalling IDENT Integration" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check if running as Administrator
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "ERROR: This script must be run as Administrator" -ForegroundColor Red
    Write-Host ""
    Read-Host "Press Enter to exit"
    exit 1
}

# Check if task exists
$existingTask = Get-ScheduledTask -TaskName $TaskName -TaskPath $TaskPath -ErrorAction SilentlyContinue
if (-not $existingTask) {
    Write-Host "Task '$TaskName' not found" -ForegroundColor Yellow
    Write-Host ""
    Read-Host "Press Enter to exit"
    exit 0
}

Write-Host "Task found: $TaskName" -ForegroundColor White
Write-Host "Current state: $($existingTask.State)" -ForegroundColor White
Write-Host ""

# Confirm uninstall
$Response = Read-Host "Are you sure you want to uninstall? (y/n)"
if ($Response -ne 'y') {
    Write-Host "Uninstall cancelled" -ForegroundColor Yellow
    exit 0
}

# Stop task if running
if ($existingTask.State -eq "Running") {
    Write-Host "Stopping task..." -ForegroundColor Cyan
    Stop-ScheduledTask -TaskName $TaskName -TaskPath $TaskPath
    Start-Sleep -Seconds 2
    Write-Host "Task stopped" -ForegroundColor Green
    Write-Host ""
}

# Unregister task
Write-Host "Removing task from Task Scheduler..." -ForegroundColor Cyan
Unregister-ScheduledTask -TaskName $TaskName -TaskPath $TaskPath -Confirm:$false
Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "Uninstall Complete" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Task '$TaskName' has been removed" -ForegroundColor White
Write-Host ""
Write-Host "To reinstall: .\install_task.ps1" -ForegroundColor Yellow
Write-Host ""
Read-Host "Press Enter to exit"

# ========================================================================
# IDENT -> Bitrix24 Integration - Task Uninstall
# ========================================================================
#
# Removes task from Windows Task Scheduler
# Requires administrator privileges
#
# ========================================================================

# Check administrator privileges
if (-NOT ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole] "Administrator")) {
    Write-Host "========================================================================" -ForegroundColor Red
    Write-Host "ERROR: Administrator privileges required!" -ForegroundColor Red
    Write-Host "========================================================================" -ForegroundColor Red
    Write-Host ""
    Write-Host "Run PowerShell as Administrator:" -ForegroundColor Yellow
    Write-Host "  1. Right-click on PowerShell" -ForegroundColor Yellow
    Write-Host "  2. Select 'Run as Administrator'" -ForegroundColor Yellow
    Write-Host ""
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host "========================================================================" -ForegroundColor Cyan
Write-Host "TASK REMOVAL: IDENT -> Bitrix24 Integration" -ForegroundColor Cyan
Write-Host "========================================================================" -ForegroundColor Cyan
Write-Host ""

# Settings
$TaskName = "IdentBitrix24Integration"
$TaskPath = "\IDENT\"

# Check if task exists
$Task = Get-ScheduledTask -TaskName $TaskName -TaskPath $TaskPath -ErrorAction SilentlyContinue
if (-not $Task) {
    Write-Host "WARNING: Task '$TaskName' not found!" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Task may already be removed." -ForegroundColor Yellow
    Write-Host ""
    Read-Host "Press Enter to exit"
    exit 0
}

# Show task information
$TaskInfo = Get-ScheduledTaskInfo -TaskName $TaskName -TaskPath $TaskPath
Write-Host "Task information:" -ForegroundColor Cyan
Write-Host "  Name:         $($Task.TaskName)" -ForegroundColor White
Write-Host "  State:        $($Task.State)" -ForegroundColor White
Write-Host "  Last run:     $($TaskInfo.LastRunTime)" -ForegroundColor White
Write-Host "  Result:       $($TaskInfo.LastTaskResult)" -ForegroundColor White
Write-Host ""

# Confirm removal
$Response = Read-Host "Are you sure you want to remove this task? (y/n)"
if ($Response -ne 'y') {
    Write-Host "Removal cancelled." -ForegroundColor Yellow
    exit 0
}

Write-Host ""

# Stop task if running
if ($Task.State -eq "Running") {
    Write-Host "Stopping task..." -ForegroundColor Yellow
    Stop-ScheduledTask -TaskName $TaskName -TaskPath $TaskPath
    Start-Sleep -Seconds 2

    $Task = Get-ScheduledTask -TaskName $TaskName -TaskPath $TaskPath
    if ($Task.State -ne "Running") {
        Write-Host "Task stopped" -ForegroundColor Green
    } else {
        Write-Host "WARNING: Could not stop task, state: $($Task.State)" -ForegroundColor Yellow
    }
    Write-Host ""
}

# Remove task
Write-Host "Removing task..." -ForegroundColor Cyan

try {
    Unregister-ScheduledTask -TaskName $TaskName -TaskPath $TaskPath -Confirm:$false

    Write-Host ""
    Write-Host "========================================================================" -ForegroundColor Green
    Write-Host "TASK SUCCESSFULLY REMOVED!" -ForegroundColor Green
    Write-Host "========================================================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "Notes:" -ForegroundColor Cyan
    Write-Host "  * Project files NOT removed" -ForegroundColor White
    Write-Host "  * Logs preserved in logs/ folder" -ForegroundColor White
    Write-Host "  * To reinstall, run install_task.ps1" -ForegroundColor White
    Write-Host ""
} catch {
    Write-Host ""
    Write-Host "========================================================================" -ForegroundColor Red
    Write-Host "ERROR REMOVING TASK" -ForegroundColor Red
    Write-Host "========================================================================" -ForegroundColor Red
    Write-Host ""
    Write-Host "Error: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host ""
    Write-Host "Try:" -ForegroundColor Yellow
    Write-Host "  1. Make sure task is fully stopped" -ForegroundColor White
    Write-Host "  2. Close Task Scheduler if open" -ForegroundColor White
    Write-Host "  3. Restart computer" -ForegroundColor White
    Write-Host "  4. Run this script again" -ForegroundColor White
    Write-Host ""
    Write-Host "Or remove manually via Task Scheduler:" -ForegroundColor Yellow
    Write-Host "  Win+R -> taskschd.msc -> find task -> Delete" -ForegroundColor White
    Write-Host ""
}

Read-Host "Press Enter to exit"

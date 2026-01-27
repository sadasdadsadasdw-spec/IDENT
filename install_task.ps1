# ========================================================================
# IDENT -> Bitrix24 Integration - Task Scheduler Installation
# ========================================================================
#
# Registers task in Windows Task Scheduler
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
Write-Host "INSTALLATION: IDENT -> Bitrix24 Integration" -ForegroundColor Cyan
Write-Host "========================================================================" -ForegroundColor Cyan
Write-Host ""

# Settings
$TaskName = "IdentBitrix24Integration"
$TaskPath = "\IDENT\"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$PythonExe = (Get-Command python).Source
$ServiceScript = Join-Path $ScriptDir "run_service.py"
$LogDir = Join-Path $ScriptDir "logs"

# Create logs directory
if (-not (Test-Path $LogDir)) {
    New-Item -ItemType Directory -Path $LogDir | Out-Null
    Write-Host "Created logs directory: $LogDir" -ForegroundColor Green
}

# Check Python
if (-not $PythonExe) {
    Write-Host "ERROR: Python not found in PATH!" -ForegroundColor Red
    Write-Host ""
    Write-Host "Make sure Python is installed and added to PATH" -ForegroundColor Yellow
    Write-Host ""
    Read-Host "Press Enter to exit"
    exit 1
}

# Check run_service.py
if (-not (Test-Path $ServiceScript)) {
    Write-Host "ERROR: run_service.py not found!" -ForegroundColor Red
    Write-Host "Expected path: $ServiceScript" -ForegroundColor Yellow
    Write-Host ""
    Read-Host "Press Enter to exit"
    exit 1
}

# Check config.ini
$ConfigFile = Join-Path $ScriptDir "config.ini"
if (-not (Test-Path $ConfigFile)) {
    Write-Host "WARNING: config.ini not found!" -ForegroundColor Yellow
    Write-Host "Path: $ConfigFile" -ForegroundColor Gray
    Write-Host ""
    $Response = Read-Host "Continue installation without config? (y/n)"
    if ($Response -ne 'y') {
        Write-Host "Installation cancelled." -ForegroundColor Yellow
        exit 0
    }
}

Write-Host "Task configuration:" -ForegroundColor Cyan
Write-Host "  Task name:         $TaskName" -ForegroundColor White
Write-Host "  Task path:         $TaskPath" -ForegroundColor White
Write-Host "  Python:            $PythonExe" -ForegroundColor White
Write-Host "  Working directory: $ScriptDir" -ForegroundColor White
Write-Host "  Script:            $ServiceScript" -ForegroundColor White
Write-Host ""

# Check if task exists
$ExistingTask = Get-ScheduledTask -TaskName $TaskName -TaskPath $TaskPath -ErrorAction SilentlyContinue
if ($ExistingTask) {
    Write-Host "WARNING: Task '$TaskName' already exists!" -ForegroundColor Yellow
    Write-Host ""
    $Response = Read-Host "Reinstall task? (y/n)"
    if ($Response -ne 'y') {
        Write-Host "Installation cancelled." -ForegroundColor Yellow
        exit 0
    }

    Write-Host "Removing existing task..." -ForegroundColor Yellow
    Unregister-ScheduledTask -TaskName $TaskName -TaskPath $TaskPath -Confirm:$false
    Write-Host "Existing task removed" -ForegroundColor Green
    Write-Host ""
}

# Create task
Write-Host "Creating task in Task Scheduler..." -ForegroundColor Cyan

# Action: Run Python script
$Action = New-ScheduledTaskAction `
    -Execute $PythonExe `
    -Argument "`"$ServiceScript`"" `
    -WorkingDirectory $ScriptDir

# Trigger: At system startup
$Trigger = New-ScheduledTaskTrigger -AtStartup

# Settings
$Settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 1) `
    -ExecutionTimeLimit (New-TimeSpan -Days 0) `
    -Priority 4

# Principal: Run as SYSTEM with highest privileges
$Principal = New-ScheduledTaskPrincipal `
    -UserId "SYSTEM" `
    -LogonType ServiceAccount `
    -RunLevel Highest

# Description
$Description = "Automatic synchronization of data from IDENT database to Bitrix24 CRM. Runs continuously in background."

# Register task
try {
    Register-ScheduledTask `
        -TaskName $TaskName `
        -TaskPath $TaskPath `
        -Action $Action `
        -Trigger $Trigger `
        -Settings $Settings `
        -Principal $Principal `
        -Description $Description `
        -Force | Out-Null

    Write-Host "Task successfully registered!" -ForegroundColor Green
    Write-Host ""
} catch {
    Write-Host "ERROR registering task: $($_.Exception.Message)" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

# Start task
Write-Host "Starting task..." -ForegroundColor Cyan
try {
    Start-ScheduledTask -TaskName $TaskName -TaskPath $TaskPath
    Start-Sleep -Seconds 3

    # Check status
    $Task = Get-ScheduledTask -TaskName $TaskName -TaskPath $TaskPath
    $TaskInfo = Get-ScheduledTaskInfo -TaskName $TaskName -TaskPath $TaskPath

    Write-Host ""
    Write-Host "========================================================================" -ForegroundColor Green
    Write-Host "TASK SUCCESSFULLY STARTED!" -ForegroundColor Green
    Write-Host "========================================================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "Task information:" -ForegroundColor Cyan
    Write-Host "  Name:          $($Task.TaskName)" -ForegroundColor White
    Write-Host "  State:         $($Task.State)" -ForegroundColor Green
    Write-Host "  Last run:      $($TaskInfo.LastRunTime)" -ForegroundColor White
    Write-Host "  Next run:      $($TaskInfo.NextRunTime)" -ForegroundColor White
    Write-Host ""
    Write-Host "Logs directory:" -ForegroundColor Cyan
    Write-Host "  $LogDir" -ForegroundColor White
    Write-Host ""
    Write-Host "Task features:" -ForegroundColor Cyan
    Write-Host "  * Runs continuously in background" -ForegroundColor White
    Write-Host "  * Auto-starts on Windows boot" -ForegroundColor White
    Write-Host "  * Auto-restarts on failure (3 attempts, 1 min interval)" -ForegroundColor White
    Write-Host "  * Continues after RDP disconnect" -ForegroundColor White
    Write-Host ""
    Write-Host "Task management:" -ForegroundColor Cyan
    Write-Host "  Stop:      Stop-ScheduledTask -TaskName '$TaskName' -TaskPath '$TaskPath'" -ForegroundColor Yellow
    Write-Host "  Start:     Start-ScheduledTask -TaskName '$TaskName' -TaskPath '$TaskPath'" -ForegroundColor Yellow
    Write-Host "  Status:    Get-ScheduledTask -TaskName '$TaskName' -TaskPath '$TaskPath'" -ForegroundColor Yellow
    Write-Host "  Check:     .\check_task.ps1" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "  Or open Task Scheduler: Win+R -> taskschd.msc" -ForegroundColor Yellow
    Write-Host ""

} catch {
    Write-Host ""
    Write-Host "========================================================================" -ForegroundColor Yellow
    Write-Host "TASK CREATED BUT NOT STARTED" -ForegroundColor Yellow
    Write-Host "========================================================================" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Error: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host ""
    Write-Host "Try starting manually:" -ForegroundColor Yellow
    Write-Host "  Start-ScheduledTask -TaskName '$TaskName' -TaskPath '$TaskPath'" -ForegroundColor White
    Write-Host ""
    Write-Host "Or check logs:" -ForegroundColor Yellow
    Write-Host "  $LogDir" -ForegroundColor White
    Write-Host ""
}

Read-Host "Press Enter to exit"

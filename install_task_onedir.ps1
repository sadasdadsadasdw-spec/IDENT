# Install IDENT -> Bitrix24 Integration to Windows Scheduled Task (ONEDIR mode)
# Run as Administrator

$ErrorActionPreference = "Stop"

$TaskName = "IdentBitrix24Integration"
$TaskPath = "\IDENT\"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ExePath = Join-Path $ScriptDir "dist\ident_sync\ident_sync.exe"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Installing IDENT Integration (ONEDIR)" -ForegroundColor Cyan
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

# Check if EXE exists
if (-not (Test-Path $ExePath)) {
    Write-Host "ERROR: ident_sync.exe not found" -ForegroundColor Red
    Write-Host "Expected: $ExePath" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Build first: .\build_exe_onedir.ps1" -ForegroundColor Yellow
    Write-Host ""
    Read-Host "Press Enter to exit"
    exit 1
}

# Check if task already exists
$existingTask = Get-ScheduledTask -TaskName $TaskName -TaskPath $TaskPath -ErrorAction SilentlyContinue
if ($existingTask) {
    Write-Host "Task already exists" -ForegroundColor Yellow
    Write-Host ""
    $Response = Read-Host "Uninstall and reinstall? (y/n)"
    if ($Response -ne 'y') {
        Write-Host "Install cancelled" -ForegroundColor Yellow
        exit 0
    }

    Write-Host ""
    Write-Host "Stopping existing task..." -ForegroundColor Cyan
    Stop-ScheduledTask -TaskName $TaskName -TaskPath $TaskPath -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 2

    Write-Host "Killing any running processes..." -ForegroundColor Cyan
    Get-Process -Name "ident_sync" -ErrorAction SilentlyContinue | Stop-Process -Force
    Start-Sleep -Seconds 2

    Write-Host "Removing existing task..." -ForegroundColor Cyan
    Unregister-ScheduledTask -TaskName $TaskName -TaskPath $TaskPath -Confirm:$false
    Start-Sleep -Seconds 1
    Write-Host ""
}

Write-Host "Creating scheduled task..." -ForegroundColor Cyan
Write-Host ""

# Task action - path to ONEDIR EXE
$Action = New-ScheduledTaskAction `
    -Execute $ExePath `
    -WorkingDirectory $ScriptDir

# Task trigger - at system startup
$Trigger = New-ScheduledTaskTrigger -AtStartup

# Task settings - NO restart, single instance
$Settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -RunOnlyIfNetworkAvailable `
    -MultipleInstances IgnoreNew `
    -RestartCount 0 `
    -ExecutionTimeLimit (New-TimeSpan -Hours 0)

# Task principal - run as SYSTEM
$Principal = New-ScheduledTaskPrincipal `
    -UserId "SYSTEM" `
    -LogonType ServiceAccount `
    -RunLevel Highest

# Register task
Register-ScheduledTask `
    -TaskName $TaskName `
    -TaskPath $TaskPath `
    -Action $Action `
    -Trigger $Trigger `
    -Settings $Settings `
    -Principal $Principal `
    -Description "IDENT to Bitrix24 integration service (ONEDIR - single process)" | Out-Null

Write-Host "========================================" -ForegroundColor Green
Write-Host "Install Complete" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Task: $TaskPath$TaskName" -ForegroundColor White
Write-Host "EXE:  $ExePath" -ForegroundColor White
Write-Host ""
Write-Host "Task will start automatically at system startup" -ForegroundColor Yellow
Write-Host ""
Write-Host "Commands:" -ForegroundColor Cyan
Write-Host "  Status:    .\check_task.ps1" -ForegroundColor White
Write-Host "  Start:     Start-ScheduledTask -TaskName '$TaskName' -TaskPath '$TaskPath'" -ForegroundColor White
Write-Host "  Stop:      Stop-ScheduledTask -TaskName '$TaskName' -TaskPath '$TaskPath'" -ForegroundColor White
Write-Host "  Uninstall: .\uninstall_task.ps1" -ForegroundColor White
Write-Host ""

$Response = Read-Host "Start task now? (y/n)"
if ($Response -eq 'y') {
    Write-Host ""
    Write-Host "Starting task..." -ForegroundColor Cyan
    Start-ScheduledTask -TaskName $TaskName -TaskPath $TaskPath
    Start-Sleep -Seconds 3

    $TaskInfo = Get-ScheduledTaskInfo -TaskName $TaskName -TaskPath $TaskPath
    $Task = Get-ScheduledTask -TaskName $TaskName -TaskPath $TaskPath

    Write-Host "Task state: $($Task.State)" -ForegroundColor Green
    Write-Host ""

    # Check for processes
    Start-Sleep -Seconds 2
    $Processes = Get-Process -Name "ident_sync" -ErrorAction SilentlyContinue
    if ($Processes) {
        $ProcessCount = @($Processes).Count
        Write-Host "Running processes: $ProcessCount" -ForegroundColor $(if ($ProcessCount -eq 1) { "Green" } else { "Red" })
        $Processes | Format-Table Id, ProcessName, StartTime

        if ($ProcessCount -eq 1) {
            Write-Host "SUCCESS: Single process running!" -ForegroundColor Green
        } else {
            Write-Host "WARNING: Multiple processes detected!" -ForegroundColor Red
        }
    } else {
        Write-Host "No ident_sync processes found" -ForegroundColor Yellow
        Write-Host "Check logs for errors" -ForegroundColor Yellow
    }
}

Write-Host ""
Read-Host "Press Enter to exit"

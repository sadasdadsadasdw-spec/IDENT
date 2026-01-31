# Check IDENT -> Bitrix24 Integration Task Status

$ErrorActionPreference = "Stop"

$TaskName = "IdentBitrix24Integration"
$TaskPath = "\IDENT\"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$LogDir = Join-Path $ScriptDir "logs"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "IDENT Integration Status" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check if task exists
$Task = Get-ScheduledTask -TaskName $TaskName -TaskPath $TaskPath -ErrorAction SilentlyContinue
if (-not $Task) {
    Write-Host "ERROR: Task '$TaskName' not found" -ForegroundColor Red
    Write-Host ""
    Write-Host "To install: .\install_task.ps1" -ForegroundColor Yellow
    Write-Host ""
    Read-Host "Press Enter to exit"
    exit 1
}

# Get task info
$TaskInfo = Get-ScheduledTaskInfo -TaskName $TaskName -TaskPath $TaskPath

Write-Host "Task Status:" -ForegroundColor Cyan
Write-Host "  Name:          $($Task.TaskName)" -ForegroundColor White
Write-Host "  State:         $($Task.State)" -ForegroundColor $(if ($Task.State -eq "Running") { "Green" } else { "Yellow" })
Write-Host "  Last run:      $($TaskInfo.LastRunTime)" -ForegroundColor White
Write-Host "  Last result:   $($TaskInfo.LastTaskResult) $(if ($TaskInfo.LastTaskResult -eq 0) { '(Success)' } else { '(Error)' })" -ForegroundColor $(if ($TaskInfo.LastTaskResult -eq 0) { "Green" } else { "Red" })
Write-Host "  Next run:      $($TaskInfo.NextRunTime)" -ForegroundColor White
Write-Host ""

# Check logs
if (Test-Path $LogDir) {
    $LatestLog = Get-ChildItem $LogDir -Filter "*.log" -ErrorAction SilentlyContinue |
                 Sort-Object LastWriteTime -Descending |
                 Select-Object -First 1

    if ($LatestLog) {
        Write-Host "Latest Log:" -ForegroundColor Cyan
        Write-Host "  File:          $($LatestLog.Name)" -ForegroundColor White
        Write-Host "  Modified:      $($LatestLog.LastWriteTime)" -ForegroundColor White
        Write-Host "  Size:          $([math]::Round($LatestLog.Length / 1KB, 2)) KB" -ForegroundColor White
        Write-Host ""

        Write-Host "Last 10 log entries:" -ForegroundColor Cyan
        Write-Host "----------------------------------------" -ForegroundColor Gray
        Get-Content $LatestLog.FullName -Tail 10 -ErrorAction SilentlyContinue | ForEach-Object {
            if ($_ -match "ERROR") {
                Write-Host $_ -ForegroundColor Red
            } elseif ($_ -match "WARNING") {
                Write-Host $_ -ForegroundColor Yellow
            } else {
                Write-Host $_ -ForegroundColor White
            }
        }
        Write-Host "----------------------------------------" -ForegroundColor Gray
        Write-Host ""
    } else {
        Write-Host "No log files found in $LogDir" -ForegroundColor Yellow
        Write-Host ""
    }
} else {
    Write-Host "Logs directory not found: $LogDir" -ForegroundColor Yellow
    Write-Host ""
}

Write-Host "Task Actions:" -ForegroundColor Cyan
Write-Host "  Start:     Start-ScheduledTask -TaskName '$TaskName' -TaskPath '$TaskPath'" -ForegroundColor Yellow
Write-Host "  Stop:      Stop-ScheduledTask -TaskName '$TaskName' -TaskPath '$TaskPath'" -ForegroundColor Yellow
Write-Host "  Restart:   Stop-ScheduledTask -TaskName '$TaskName' -TaskPath '$TaskPath'; Start-ScheduledTask -TaskName '$TaskName' -TaskPath '$TaskPath'" -ForegroundColor Yellow
Write-Host ""
Write-Host "  Or open Task Scheduler: Win+R -> taskschd.msc" -ForegroundColor Yellow
Write-Host ""
Read-Host "Press Enter to exit"

# ========================================================================
# IDENT -> Bitrix24 Integration - Task Health Check
# ========================================================================
#
# Checks task status and health
# Shows detailed information about state
#
# ========================================================================

$TaskName = "IdentBitrix24Integration"
$TaskPath = "\IDENT\"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$LogDir = Join-Path $ScriptDir "logs"
$ConfigFile = Join-Path $ScriptDir "config.ini"

Write-Host "========================================================================" -ForegroundColor Cyan
Write-Host "HEALTH CHECK: IDENT -> Bitrix24 Integration" -ForegroundColor Cyan
Write-Host "========================================================================" -ForegroundColor Cyan
Write-Host ""

# 1. Check if task exists
Write-Host "1. TASK CHECK" -ForegroundColor Cyan
Write-Host "---------------------------------------------------------------------" -ForegroundColor DarkGray

$Task = Get-ScheduledTask -TaskName $TaskName -TaskPath $TaskPath -ErrorAction SilentlyContinue

if (-not $Task) {
    Write-Host "ERROR: Task '$TaskName' is not installed!" -ForegroundColor Red
    Write-Host ""
    Write-Host "To install, run: .\install_task.ps1" -ForegroundColor Yellow
    Write-Host ""
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host "Task is installed" -ForegroundColor Green
Write-Host ""

# 2. Task status
Write-Host "2. TASK STATUS" -ForegroundColor Cyan
Write-Host "---------------------------------------------------------------------" -ForegroundColor DarkGray

$TaskInfo = Get-ScheduledTaskInfo -TaskName $TaskName -TaskPath $TaskPath

Write-Host "  Name:         $($Task.TaskName)" -ForegroundColor White
Write-Host "  Path:         $($Task.TaskPath)" -ForegroundColor White

if ($Task.State -eq "Running") {
    Write-Host "  State:        " -NoNewline -ForegroundColor White
    Write-Host "Running" -ForegroundColor Green
} elseif ($Task.State -eq "Ready") {
    Write-Host "  State:        " -NoNewline -ForegroundColor White
    Write-Host "Ready (not running)" -ForegroundColor Yellow
} elseif ($Task.State -eq "Disabled") {
    Write-Host "  State:        " -NoNewline -ForegroundColor White
    Write-Host "Disabled" -ForegroundColor Red
} else {
    Write-Host "  State:        " -NoNewline -ForegroundColor White
    Write-Host "$($Task.State)" -ForegroundColor Yellow
}

Write-Host "  Last run:     $($TaskInfo.LastRunTime)" -ForegroundColor White

# Last result code
$LastResult = $TaskInfo.LastTaskResult
if ($LastResult -eq 0) {
    Write-Host "  Result:       0 (Success)" -ForegroundColor Green
} elseif ($LastResult -eq 267009) {
    Write-Host "  Result:       267009 (Running)" -ForegroundColor Green
} elseif ($LastResult -eq 267011) {
    Write-Host "  Result:       267011 (Ready)" -ForegroundColor Green
} else {
    Write-Host "  Result:       $LastResult (Error)" -ForegroundColor Red
}

Write-Host "  Next run:     $($TaskInfo.NextRunTime)" -ForegroundColor White

# Missed runs
if ($TaskInfo.NumberOfMissedRuns -gt 0) {
    Write-Host "  Missed runs:  $($TaskInfo.NumberOfMissedRuns)" -ForegroundColor Yellow
}

Write-Host ""

# 3. Python process
if ($Task.State -eq "Running") {
    Write-Host "3. PYTHON PROCESS" -ForegroundColor Cyan
    Write-Host "---------------------------------------------------------------------" -ForegroundColor DarkGray

    # Find Python process
    $PythonProcesses = Get-Process python* -ErrorAction SilentlyContinue | Where-Object {
        $_.CommandLine -like "*run_service.py*"
    }

    if ($PythonProcesses) {
        foreach ($Proc in $PythonProcesses) {
            Write-Host "  PID:          $($Proc.Id)" -ForegroundColor White
            Write-Host "  CPU:          $([math]::Round($Proc.CPU, 2))s" -ForegroundColor White

            $MemoryMB = [math]::Round($Proc.WorkingSet64 / 1MB, 2)
            Write-Host "  Memory:       $MemoryMB MB" -ForegroundColor White

            Write-Host "  Start time:   $($Proc.StartTime.ToString('yyyy-MM-dd HH:mm:ss'))" -ForegroundColor White

            $Uptime = (Get-Date) - $Proc.StartTime
            Write-Host "  Uptime:       $($Uptime.Days)d $($Uptime.Hours)h $($Uptime.Minutes)m" -ForegroundColor White
        }
    } else {
        Write-Host "  WARNING: Python process not found" -ForegroundColor Yellow
        Write-Host "  (task may have just started or stopped)" -ForegroundColor Gray
    }

    Write-Host ""
}

# 4. Logs
Write-Host "4. LOG FILES" -ForegroundColor Cyan
Write-Host "---------------------------------------------------------------------" -ForegroundColor DarkGray

if (Test-Path $LogDir) {
    $LogFiles = @(
        @{ Name = "Main log"; Path = Join-Path $LogDir "ident_integration.log" },
        @{ Name = "Error log"; Path = Join-Path $LogDir "ident_integration_error.log" },
        @{ Name = "Service Runner"; Path = Join-Path $LogDir "service_runner.log" }
    )

    foreach ($LogFile in $LogFiles) {
        if (Test-Path $LogFile.Path) {
            $FileInfo = Get-Item $LogFile.Path
            $SizeMB = [math]::Round($FileInfo.Length / 1MB, 2)
            $LastWrite = $FileInfo.LastWriteTime.ToString("yyyy-MM-dd HH:mm:ss")

            Write-Host "  $($LogFile.Name)" -ForegroundColor Green
            Write-Host "     Size:        $SizeMB MB" -ForegroundColor Gray
            Write-Host "     Modified:    $LastWrite" -ForegroundColor Gray

            # Check freshness
            $TimeSinceUpdate = (Get-Date) - $FileInfo.LastWriteTime
            if ($TimeSinceUpdate.TotalMinutes -lt 5) {
                Write-Host "     Activity:    Active (recently updated)" -ForegroundColor Green
            } elseif ($TimeSinceUpdate.TotalHours -lt 1) {
                Write-Host "     Activity:    Updated $([math]::Round($TimeSinceUpdate.TotalMinutes, 0)) min ago" -ForegroundColor Yellow
            } else {
                Write-Host "     Activity:    Updated $([math]::Round($TimeSinceUpdate.TotalHours, 1)) h ago" -ForegroundColor Yellow
            }
        } else {
            Write-Host "  $($LogFile.Name)" -ForegroundColor Yellow
            Write-Host "     File not found" -ForegroundColor Gray
        }
        Write-Host ""
    }
} else {
    Write-Host "  WARNING: Logs directory not found: $LogDir" -ForegroundColor Yellow
    Write-Host ""
}

# 5. Recent errors
Write-Host "5. RECENT ERRORS (last hour)" -ForegroundColor Cyan
Write-Host "---------------------------------------------------------------------" -ForegroundColor DarkGray

$ErrorLog = Join-Path $LogDir "ident_integration_error.log"
if (Test-Path $ErrorLog) {
    $RecentErrors = Get-Content $ErrorLog -Tail 100 -ErrorAction SilentlyContinue | Where-Object {
        $_ -match "^\d{4}-\d{2}-\d{2}" -and
        (Get-Date) - [DateTime]::ParseExact($_.Substring(0, 19), "yyyy-MM-dd HH:mm:ss", $null) -lt (New-TimeSpan -Hours 1)
    }

    if ($RecentErrors) {
        Write-Host "  WARNING: Found $($RecentErrors.Count) errors" -ForegroundColor Yellow
        Write-Host ""
        Write-Host "  Last 5 errors:" -ForegroundColor Yellow
        $RecentErrors | Select-Object -Last 5 | ForEach-Object {
            Write-Host "    $_" -ForegroundColor Red
        }
        Write-Host ""
        Write-Host "  To view all errors: Get-Content '$ErrorLog'" -ForegroundColor Gray
    } else {
        Write-Host "  No errors in last hour" -ForegroundColor Green
    }
} else {
    Write-Host "  Error log not yet created" -ForegroundColor Gray
}

Write-Host ""

# 6. Configuration
Write-Host "6. CONFIGURATION" -ForegroundColor Cyan
Write-Host "---------------------------------------------------------------------" -ForegroundColor DarkGray

if (Test-Path $ConfigFile) {
    Write-Host "  config.ini found" -ForegroundColor Green

    # Check file size
    $ConfigInfo = Get-Item $ConfigFile
    if ($ConfigInfo.Length -lt 100) {
        Write-Host "  WARNING: Config file is very small ($($ConfigInfo.Length) bytes)" -ForegroundColor Yellow
        Write-Host "     May not be configured properly!" -ForegroundColor Yellow
    }
} else {
    Write-Host "  ERROR: config.ini not found!" -ForegroundColor Red
    Write-Host "     Task cannot work without configuration" -ForegroundColor Red
}

Write-Host ""

# Overall status
Write-Host "========================================================================" -ForegroundColor Cyan
Write-Host "OVERALL STATUS" -ForegroundColor Cyan
Write-Host "========================================================================" -ForegroundColor Cyan

if ($Task.State -eq "Running") {
    # Check health indicators
    $IsHealthy = $true
    $Issues = @()

    # Check process
    if (-not (Get-Process python* -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -like "*run_service.py*" })) {
        $IsHealthy = $false
        $Issues += "Python process not found"
    }

    # Check logs
    $MainLog = Join-Path $LogDir "ident_integration.log"
    if (Test-Path $MainLog) {
        $LogInfo = Get-Item $MainLog
        $TimeSinceUpdate = (Get-Date) - $LogInfo.LastWriteTime
        if ($TimeSinceUpdate.TotalMinutes -gt 10) {
            $IsHealthy = $false
            $Issues += "Log not updated for $([math]::Round($TimeSinceUpdate.TotalMinutes, 0)) minutes"
        }
    }

    # Check errors
    if (Test-Path $ErrorLog) {
        $RecentErrors = Get-Content $ErrorLog -Tail 50 -ErrorAction SilentlyContinue | Where-Object {
            $_ -match "^\d{4}-\d{2}-\d{2}" -and
            (Get-Date) - [DateTime]::ParseExact($_.Substring(0, 19), "yyyy-MM-dd HH:mm:ss", $null) -lt (New-TimeSpan -Minutes 10)
        }
        if ($RecentErrors) {
            $Issues += "$($RecentErrors.Count) errors in last 10 minutes"
        }
    }

    if ($IsHealthy -and $Issues.Count -eq 0) {
        Write-Host "TASK IS RUNNING NORMALLY" -ForegroundColor Green
    } else {
        Write-Host "TASK IS RUNNING WITH ISSUES" -ForegroundColor Yellow
        Write-Host ""
        Write-Host "Issues detected:" -ForegroundColor Yellow
        foreach ($Issue in $Issues) {
            Write-Host "  * $Issue" -ForegroundColor Red
        }
    }
} elseif ($Task.State -eq "Ready") {
    Write-Host "TASK IS NOT RUNNING" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "To start: Start-ScheduledTask -TaskName '$TaskName' -TaskPath '$TaskPath'" -ForegroundColor Yellow
} elseif ($Task.State -eq "Disabled") {
    Write-Host "TASK IS DISABLED" -ForegroundColor Red
    Write-Host ""
    Write-Host "To enable: Enable-ScheduledTask -TaskName '$TaskName' -TaskPath '$TaskPath'" -ForegroundColor Yellow
} else {
    Write-Host "TASK STATE: $($Task.State)" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "========================================================================" -ForegroundColor Cyan
Write-Host ""

# Management commands
Write-Host "MANAGEMENT COMMANDS:" -ForegroundColor Cyan
Write-Host "  Start:    Start-ScheduledTask -TaskName '$TaskName' -TaskPath '$TaskPath'" -ForegroundColor Yellow
Write-Host "  Stop:     Stop-ScheduledTask -TaskName '$TaskName' -TaskPath '$TaskPath'" -ForegroundColor Yellow
Write-Host "  Enable:   Enable-ScheduledTask -TaskName '$TaskName' -TaskPath '$TaskPath'" -ForegroundColor Yellow
Write-Host "  Disable:  Disable-ScheduledTask -TaskName '$TaskName' -TaskPath '$TaskPath'" -ForegroundColor Yellow
Write-Host "  Remove:   .\uninstall_task.ps1" -ForegroundColor Yellow
Write-Host ""
Write-Host "  Open Task Scheduler: Win+R -> taskschd.msc" -ForegroundColor Yellow
Write-Host ""

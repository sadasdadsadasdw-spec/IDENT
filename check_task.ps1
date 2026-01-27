# ========================================================================
# IDENT → Bitrix24 Integration - Task Health Check
# ========================================================================
#
# Проверка статуса и работоспособности задачи
# Показывает детальную информацию о состоянии
#
# ========================================================================

$TaskName = "IdentBitrix24Integration"
$TaskPath = "\IDENT\"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$LogDir = Join-Path $ScriptDir "logs"
$ConfigFile = Join-Path $ScriptDir "config.ini"

Write-Host "========================================================================" -ForegroundColor Cyan
Write-Host "🔍 ПРОВЕРКА ЗАДАЧИ: IDENT → Bitrix24 Integration" -ForegroundColor Cyan
Write-Host "========================================================================" -ForegroundColor Cyan
Write-Host ""

# 1. Проверка существования задачи
Write-Host "📋 1. ПРОВЕРКА ЗАДАЧИ" -ForegroundColor Cyan
Write-Host "─────────────────────────────────────────────────────────────────────" -ForegroundColor DarkGray

$Task = Get-ScheduledTask -TaskName $TaskName -TaskPath $TaskPath -ErrorAction SilentlyContinue

if (-not $Task) {
    Write-Host "❌ Задача '$TaskName' не установлена!" -ForegroundColor Red
    Write-Host ""
    Write-Host "Для установки запустите: .\install_task.ps1" -ForegroundColor Yellow
    Write-Host ""
    Read-Host "Нажмите Enter для выхода"
    exit 1
}

Write-Host "✅ Задача установлена" -ForegroundColor Green
Write-Host ""

# 2. Статус задачи
Write-Host "📊 2. СТАТУС ЗАДАЧИ" -ForegroundColor Cyan
Write-Host "─────────────────────────────────────────────────────────────────────" -ForegroundColor DarkGray

$TaskInfo = Get-ScheduledTaskInfo -TaskName $TaskName -TaskPath $TaskPath

Write-Host "  Имя:           $($Task.TaskName)" -ForegroundColor White
Write-Host "  Путь:          $($Task.TaskPath)" -ForegroundColor White

if ($Task.State -eq "Running") {
    Write-Host "  Состояние:     " -NoNewline -ForegroundColor White
    Write-Host "Running ✅" -ForegroundColor Green
} elseif ($Task.State -eq "Ready") {
    Write-Host "  Состояние:     " -NoNewline -ForegroundColor White
    Write-Host "Ready (не запущена) ⚠️" -ForegroundColor Yellow
} elseif ($Task.State -eq "Disabled") {
    Write-Host "  Состояние:     " -NoNewline -ForegroundColor White
    Write-Host "Disabled (отключена) ❌" -ForegroundColor Red
} else {
    Write-Host "  Состояние:     " -NoNewline -ForegroundColor White
    Write-Host "$($Task.State) ⚠️" -ForegroundColor Yellow
}

Write-Host "  Последний запуск: $($TaskInfo.LastRunTime)" -ForegroundColor White

# Код результата последнего запуска
$LastResult = $TaskInfo.LastTaskResult
if ($LastResult -eq 0) {
    Write-Host "  Результат:     0 (Success) ✅" -ForegroundColor Green
} elseif ($LastResult -eq 267009) {
    Write-Host "  Результат:     267009 (Running) ✅" -ForegroundColor Green
} elseif ($LastResult -eq 267011) {
    Write-Host "  Результат:     267011 (Ready) ✅" -ForegroundColor Green
} else {
    Write-Host "  Результат:     $LastResult (Error) ❌" -ForegroundColor Red
}

Write-Host "  Следующий запуск: $($TaskInfo.NextRunTime)" -ForegroundColor White

# Количество пропущенных запусков
if ($TaskInfo.NumberOfMissedRuns -gt 0) {
    Write-Host "  Пропущено:     $($TaskInfo.NumberOfMissedRuns) запусков ⚠️" -ForegroundColor Yellow
}

Write-Host ""

# 3. Процесс Python
if ($Task.State -eq "Running") {
    Write-Host "⚙️  3. ПРОЦЕСС PYTHON" -ForegroundColor Cyan
    Write-Host "─────────────────────────────────────────────────────────────────────" -ForegroundColor DarkGray

    # Ищем процесс Python
    $PythonProcesses = Get-Process python* -ErrorAction SilentlyContinue | Where-Object {
        $_.CommandLine -like "*run_service.py*"
    }

    if ($PythonProcesses) {
        foreach ($Proc in $PythonProcesses) {
            Write-Host "  PID:           $($Proc.Id)" -ForegroundColor White
            Write-Host "  CPU:           $([math]::Round($Proc.CPU, 2))s" -ForegroundColor White

            $MemoryMB = [math]::Round($Proc.WorkingSet64 / 1MB, 2)
            Write-Host "  Память:        $MemoryMB MB" -ForegroundColor White

            Write-Host "  Время старта:  $($Proc.StartTime.ToString('yyyy-MM-dd HH:mm:ss'))" -ForegroundColor White

            $Uptime = (Get-Date) - $Proc.StartTime
            Write-Host "  Аптайм:        $($Uptime.Days)д $($Uptime.Hours)ч $($Uptime.Minutes)м" -ForegroundColor White
        }
    } else {
        Write-Host "  ⚠️  Процесс Python не найден" -ForegroundColor Yellow
        Write-Host "  (задача может только что запуститься или завершиться)" -ForegroundColor Gray
    }

    Write-Host ""
}

# 4. Логи
Write-Host "📁 4. ФАЙЛЫ ЛОГОВ" -ForegroundColor Cyan
Write-Host "─────────────────────────────────────────────────────────────────────" -ForegroundColor DarkGray

if (Test-Path $LogDir) {
    $LogFiles = @(
        @{ Name = "Основной лог"; Path = Join-Path $LogDir "ident_integration.log" },
        @{ Name = "Лог ошибок"; Path = Join-Path $LogDir "ident_integration_error.log" },
        @{ Name = "Service Runner"; Path = Join-Path $LogDir "service_runner.log" }
    )

    foreach ($LogFile in $LogFiles) {
        if (Test-Path $LogFile.Path) {
            $FileInfo = Get-Item $LogFile.Path
            $SizeMB = [math]::Round($FileInfo.Length / 1MB, 2)
            $LastWrite = $FileInfo.LastWriteTime.ToString("yyyy-MM-dd HH:mm:ss")

            Write-Host "  ✅ $($LogFile.Name)" -ForegroundColor Green
            Write-Host "     Размер:         $SizeMB MB" -ForegroundColor Gray
            Write-Host "     Изменен:        $LastWrite" -ForegroundColor Gray

            # Проверяем свежесть последней записи
            $TimeSinceUpdate = (Get-Date) - $FileInfo.LastWriteTime
            if ($TimeSinceUpdate.TotalMinutes -lt 5) {
                Write-Host "     Активность:     Активный (обновлен недавно) ✅" -ForegroundColor Green
            } elseif ($TimeSinceUpdate.TotalHours -lt 1) {
                Write-Host "     Активность:     Обновлен $([math]::Round($TimeSinceUpdate.TotalMinutes, 0)) мин назад" -ForegroundColor Yellow
            } else {
                Write-Host "     Активность:     Обновлен $([math]::Round($TimeSinceUpdate.TotalHours, 1)) ч назад ⚠️" -ForegroundColor Yellow
            }
        } else {
            Write-Host "  ⚠️  $($LogFile.Name)" -ForegroundColor Yellow
            Write-Host "     Файл не найден" -ForegroundColor Gray
        }
        Write-Host ""
    }
} else {
    Write-Host "  ⚠️  Директория логов не найдена: $LogDir" -ForegroundColor Yellow
    Write-Host ""
}

# 5. Последние ошибки
Write-Host "❌ 5. ПОСЛЕДНИЕ ОШИБКИ (за последний час)" -ForegroundColor Cyan
Write-Host "─────────────────────────────────────────────────────────────────────" -ForegroundColor DarkGray

$ErrorLog = Join-Path $LogDir "ident_integration_error.log"
if (Test-Path $ErrorLog) {
    $RecentErrors = Get-Content $ErrorLog -Tail 100 -ErrorAction SilentlyContinue | Where-Object {
        $_ -match "^\d{4}-\d{2}-\d{2}" -and
        (Get-Date) - [DateTime]::ParseExact($_.Substring(0, 19), "yyyy-MM-dd HH:mm:ss", $null) -lt (New-TimeSpan -Hours 1)
    }

    if ($RecentErrors) {
        Write-Host "  ⚠️  Найдено ошибок: $($RecentErrors.Count)" -ForegroundColor Yellow
        Write-Host ""
        Write-Host "  Последние 5 ошибок:" -ForegroundColor Yellow
        $RecentErrors | Select-Object -Last 5 | ForEach-Object {
            Write-Host "    $_" -ForegroundColor Red
        }
        Write-Host ""
        Write-Host "  Для просмотра всех ошибок: Get-Content '$ErrorLog'" -ForegroundColor Gray
    } else {
        Write-Host "  ✅ Нет ошибок за последний час" -ForegroundColor Green
    }
} else {
    Write-Host "  ℹ️  Файл ошибок еще не создан" -ForegroundColor Gray
}

Write-Host ""

# 6. Конфигурация
Write-Host "⚙️  6. КОНФИГУРАЦИЯ" -ForegroundColor Cyan
Write-Host "─────────────────────────────────────────────────────────────────────" -ForegroundColor DarkGray

if (Test-Path $ConfigFile) {
    Write-Host "  ✅ Файл config.ini найден" -ForegroundColor Green

    # Проверяем размер файла
    $ConfigInfo = Get-Item $ConfigFile
    if ($ConfigInfo.Length -lt 100) {
        Write-Host "  ⚠️  Файл конфигурации очень маленький ($($ConfigInfo.Length) байт)" -ForegroundColor Yellow
        Write-Host "     Возможно не настроен!" -ForegroundColor Yellow
    }
} else {
    Write-Host "  ❌ Файл config.ini не найден!" -ForegroundColor Red
    Write-Host "     Задача не сможет работать без конфигурации" -ForegroundColor Red
}

Write-Host ""

# Итоговый статус
Write-Host "========================================================================" -ForegroundColor Cyan
Write-Host "📊 ИТОГОВЫЙ СТАТУС" -ForegroundColor Cyan
Write-Host "========================================================================" -ForegroundColor Cyan

if ($Task.State -eq "Running") {
    # Проверяем признаки здоровья
    $IsHealthy = $true
    $Issues = @()

    # Проверка процесса
    if (-not (Get-Process python* -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -like "*run_service.py*" })) {
        $IsHealthy = $false
        $Issues += "Процесс Python не найден"
    }

    # Проверка логов
    $MainLog = Join-Path $LogDir "ident_integration.log"
    if (Test-Path $MainLog) {
        $LogInfo = Get-Item $MainLog
        $TimeSinceUpdate = (Get-Date) - $LogInfo.LastWriteTime
        if ($TimeSinceUpdate.TotalMinutes -gt 10) {
            $IsHealthy = $false
            $Issues += "Лог не обновлялся $([math]::Round($TimeSinceUpdate.TotalMinutes, 0)) минут"
        }
    }

    # Проверка ошибок
    if (Test-Path $ErrorLog) {
        $RecentErrors = Get-Content $ErrorLog -Tail 50 -ErrorAction SilentlyContinue | Where-Object {
            $_ -match "^\d{4}-\d{2}-\d{2}" -and
            (Get-Date) - [DateTime]::ParseExact($_.Substring(0, 19), "yyyy-MM-dd HH:mm:ss", $null) -lt (New-TimeSpan -Minutes 10)
        }
        if ($RecentErrors) {
            $Issues += "$($RecentErrors.Count) ошибок за последние 10 минут"
        }
    }

    if ($IsHealthy -and $Issues.Count -eq 0) {
        Write-Host "✅ ЗАДАЧА РАБОТАЕТ НОРМАЛЬНО" -ForegroundColor Green
    } else {
        Write-Host "⚠️  ЗАДАЧА РАБОТАЕТ С ПРОБЛЕМАМИ" -ForegroundColor Yellow
        Write-Host ""
        Write-Host "Обнаруженные проблемы:" -ForegroundColor Yellow
        foreach ($Issue in $Issues) {
            Write-Host "  • $Issue" -ForegroundColor Red
        }
    }
} elseif ($Task.State -eq "Ready") {
    Write-Host "⚠️  ЗАДАЧА НЕ ЗАПУЩЕНА" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Для запуска: Start-ScheduledTask -TaskName '$TaskName' -TaskPath '$TaskPath'" -ForegroundColor Yellow
} elseif ($Task.State -eq "Disabled") {
    Write-Host "❌ ЗАДАЧА ОТКЛЮЧЕНА" -ForegroundColor Red
    Write-Host ""
    Write-Host "Для включения: Enable-ScheduledTask -TaskName '$TaskName' -TaskPath '$TaskPath'" -ForegroundColor Yellow
} else {
    Write-Host "⚠️  ЗАДАЧА В СОСТОЯНИИ: $($Task.State)" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "========================================================================" -ForegroundColor Cyan
Write-Host ""

# Команды управления
Write-Host "📝 КОМАНДЫ УПРАВЛЕНИЯ:" -ForegroundColor Cyan
Write-Host "  Запустить:     Start-ScheduledTask -TaskName '$TaskName' -TaskPath '$TaskPath'" -ForegroundColor Yellow
Write-Host "  Остановить:    Stop-ScheduledTask -TaskName '$TaskName' -TaskPath '$TaskPath'" -ForegroundColor Yellow
Write-Host "  Включить:      Enable-ScheduledTask -TaskName '$TaskName' -TaskPath '$TaskPath'" -ForegroundColor Yellow
Write-Host "  Отключить:     Disable-ScheduledTask -TaskName '$TaskName' -TaskPath '$TaskPath'" -ForegroundColor Yellow
Write-Host "  Удалить:       .\uninstall_task.ps1" -ForegroundColor Yellow
Write-Host ""
Write-Host "  Открыть Task Scheduler: Win+R → taskschd.msc" -ForegroundColor Yellow
Write-Host ""

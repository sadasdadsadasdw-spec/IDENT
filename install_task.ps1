# ========================================================================
# IDENT → Bitrix24 Integration - Task Scheduler Installation
# ========================================================================
#
# Регистрирует задачу в Windows Task Scheduler
# Требует права администратора
#
# ========================================================================

# Проверка прав администратора
if (-NOT ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole] "Administrator")) {
    Write-Host "========================================================================" -ForegroundColor Red
    Write-Host "❌ ОШИБКА: Требуются права администратора!" -ForegroundColor Red
    Write-Host "========================================================================" -ForegroundColor Red
    Write-Host ""
    Write-Host "Запустите PowerShell от имени администратора:" -ForegroundColor Yellow
    Write-Host "  1. ПКМ на PowerShell" -ForegroundColor Yellow
    Write-Host "  2. 'Запустить от имени администратора'" -ForegroundColor Yellow
    Write-Host ""
    Read-Host "Нажмите Enter для выхода"
    exit 1
}

Write-Host "========================================================================" -ForegroundColor Cyan
Write-Host "🚀 УСТАНОВКА ЗАДАЧИ: IDENT → Bitrix24 Integration" -ForegroundColor Cyan
Write-Host "========================================================================" -ForegroundColor Cyan
Write-Host ""

# Настройки
$TaskName = "IdentBitrix24Integration"
$TaskPath = "\IDENT\"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$PythonExe = (Get-Command python).Source
$ServiceScript = Join-Path $ScriptDir "run_service.py"
$LogDir = Join-Path $ScriptDir "logs"

# Создаем директорию для логов
if (-not (Test-Path $LogDir)) {
    New-Item -ItemType Directory -Path $LogDir | Out-Null
    Write-Host "✅ Создана директория для логов: $LogDir" -ForegroundColor Green
}

# Проверка наличия Python
if (-not $PythonExe) {
    Write-Host "❌ ОШИБКА: Python не найден в PATH!" -ForegroundColor Red
    Write-Host ""
    Write-Host "Убедитесь что Python установлен и добавлен в PATH" -ForegroundColor Yellow
    Write-Host ""
    Read-Host "Нажмите Enter для выхода"
    exit 1
}

# Проверка наличия run_service.py
if (-not (Test-Path $ServiceScript)) {
    Write-Host "❌ ОШИБКА: run_service.py не найден!" -ForegroundColor Red
    Write-Host "Ожидаемый путь: $ServiceScript" -ForegroundColor Yellow
    Write-Host ""
    Read-Host "Нажмите Enter для выхода"
    exit 1
}

# Проверка наличия config.ini
$ConfigFile = Join-Path $ScriptDir "config.ini"
if (-not (Test-Path $ConfigFile)) {
    Write-Host "⚠️  ПРЕДУПРЕЖДЕНИЕ: config.ini не найден!" -ForegroundColor Yellow
    Write-Host "Путь: $ConfigFile" -ForegroundColor Gray
    Write-Host ""
    $Response = Read-Host "Продолжить установку без конфигурации? (y/n)"
    if ($Response -ne 'y') {
        Write-Host "Установка отменена." -ForegroundColor Yellow
        exit 0
    }
}

Write-Host "📋 Конфигурация задачи:" -ForegroundColor Cyan
Write-Host "  Имя задачи:        $TaskName" -ForegroundColor White
Write-Host "  Путь в планировщике: $TaskPath" -ForegroundColor White
Write-Host "  Python:            $PythonExe" -ForegroundColor White
Write-Host "  Рабочая директория: $ScriptDir" -ForegroundColor White
Write-Host "  Скрипт:            $ServiceScript" -ForegroundColor White
Write-Host ""

# Проверка существования задачи
$ExistingTask = Get-ScheduledTask -TaskName $TaskName -TaskPath $TaskPath -ErrorAction SilentlyContinue
if ($ExistingTask) {
    Write-Host "⚠️  Задача '$TaskName' уже существует!" -ForegroundColor Yellow
    Write-Host ""
    $Response = Read-Host "Переустановить задачу? (y/n)"
    if ($Response -ne 'y') {
        Write-Host "Установка отменена." -ForegroundColor Yellow
        exit 0
    }

    Write-Host "Удаляем существующую задачу..." -ForegroundColor Yellow
    Unregister-ScheduledTask -TaskName $TaskName -TaskPath $TaskPath -Confirm:$false
    Write-Host "✅ Существующая задача удалена" -ForegroundColor Green
    Write-Host ""
}

# Создание задачи
Write-Host "📦 Создание задачи в Task Scheduler..." -ForegroundColor Cyan

# Action: Запуск Python скрипта
$Action = New-ScheduledTaskAction `
    -Execute $PythonExe `
    -Argument "`"$ServiceScript`"" `
    -WorkingDirectory $ScriptDir

# Trigger: При запуске системы
$Trigger = New-ScheduledTaskTrigger -AtStartup

# Settings: Настройки поведения
$Settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 1) `
    -ExecutionTimeLimit (New-TimeSpan -Days 0) `
    -Priority 4

# Principal: Запуск от SYSTEM с наивысшими правами
$Principal = New-ScheduledTaskPrincipal `
    -UserId "SYSTEM" `
    -LogonType ServiceAccount `
    -RunLevel Highest

# Описание задачи
$Description = "Автоматическая синхронизация данных из базы IDENT в Bitrix24 CRM. Работает непрерывно в фоновом режиме."

# Регистрация задачи
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

    Write-Host "✅ Задача успешно зарегистрирована!" -ForegroundColor Green
    Write-Host ""
} catch {
    Write-Host "❌ ОШИБКА при регистрации задачи: $($_.Exception.Message)" -ForegroundColor Red
    Read-Host "Нажмите Enter для выхода"
    exit 1
}

# Запуск задачи
Write-Host "🚀 Запуск задачи..." -ForegroundColor Cyan
try {
    Start-ScheduledTask -TaskName $TaskName -TaskPath $TaskPath
    Start-Sleep -Seconds 3

    # Проверка статуса
    $Task = Get-ScheduledTask -TaskName $TaskName -TaskPath $TaskPath
    $TaskInfo = Get-ScheduledTaskInfo -TaskName $TaskName -TaskPath $TaskPath

    Write-Host ""
    Write-Host "========================================================================" -ForegroundColor Green
    Write-Host "✅ ЗАДАЧА УСПЕШНО ЗАПУЩЕНА!" -ForegroundColor Green
    Write-Host "========================================================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "📊 Информация о задаче:" -ForegroundColor Cyan
    Write-Host "  Имя:           $($Task.TaskName)" -ForegroundColor White
    Write-Host "  Состояние:     $($Task.State)" -ForegroundColor Green
    Write-Host "  Последний запуск: $($TaskInfo.LastRunTime)" -ForegroundColor White
    Write-Host "  Следующий запуск: $($TaskInfo.NextRunTime)" -ForegroundColor White
    Write-Host ""
    Write-Host "📁 Логи сохраняются в:" -ForegroundColor Cyan
    Write-Host "  $LogDir" -ForegroundColor White
    Write-Host ""
    Write-Host "🎯 Задача будет:" -ForegroundColor Cyan
    Write-Host "  ✅ Работать постоянно в фоне" -ForegroundColor White
    Write-Host "  ✅ Автоматически запускаться при старте Windows" -ForegroundColor White
    Write-Host "  ✅ Автоматически перезапускаться при сбоях (3 попытки с интервалом 1 мин)" -ForegroundColor White
    Write-Host "  ✅ Продолжать работу после закрытия RDP" -ForegroundColor White
    Write-Host ""
    Write-Host "📝 Управление задачей:" -ForegroundColor Cyan
    Write-Host "  Остановить:    Stop-ScheduledTask -TaskName '$TaskName' -TaskPath '$TaskPath'" -ForegroundColor Yellow
    Write-Host "  Запустить:     Start-ScheduledTask -TaskName '$TaskName' -TaskPath '$TaskPath'" -ForegroundColor Yellow
    Write-Host "  Статус:        Get-ScheduledTask -TaskName '$TaskName' -TaskPath '$TaskPath'" -ForegroundColor Yellow
    Write-Host "  Проверить:     .\check_task.ps1" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "  Или откройте Task Scheduler: Win+R → taskschd.msc" -ForegroundColor Yellow
    Write-Host ""

} catch {
    Write-Host ""
    Write-Host "========================================================================" -ForegroundColor Yellow
    Write-Host "⚠️  ЗАДАЧА СОЗДАНА, НО НЕ ЗАПУЩЕНА" -ForegroundColor Yellow
    Write-Host "========================================================================" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Ошибка: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host ""
    Write-Host "Попробуйте запустить вручную:" -ForegroundColor Yellow
    Write-Host "  Start-ScheduledTask -TaskName '$TaskName' -TaskPath '$TaskPath'" -ForegroundColor White
    Write-Host ""
    Write-Host "Или проверьте логи:" -ForegroundColor Yellow
    Write-Host "  $LogDir" -ForegroundColor White
    Write-Host ""
}

Read-Host "Нажмите Enter для выхода"

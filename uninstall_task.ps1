# ========================================================================
# IDENT → Bitrix24 Integration - Task Uninstall
# ========================================================================
#
# Удаляет задачу из Windows Task Scheduler
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
Write-Host "🗑️  УДАЛЕНИЕ ЗАДАЧИ: IDENT → Bitrix24 Integration" -ForegroundColor Cyan
Write-Host "========================================================================" -ForegroundColor Cyan
Write-Host ""

# Настройки
$TaskName = "IdentBitrix24Integration"
$TaskPath = "\IDENT\"

# Проверка существования задачи
$Task = Get-ScheduledTask -TaskName $TaskName -TaskPath $TaskPath -ErrorAction SilentlyContinue
if (-not $Task) {
    Write-Host "⚠️  Задача '$TaskName' не найдена!" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Возможно задача уже удалена." -ForegroundColor Yellow
    Write-Host ""
    Read-Host "Нажмите Enter для выхода"
    exit 0
}

# Показываем информацию о задаче
$TaskInfo = Get-ScheduledTaskInfo -TaskName $TaskName -TaskPath $TaskPath
Write-Host "📋 Информация о задаче:" -ForegroundColor Cyan
Write-Host "  Имя:              $($Task.TaskName)" -ForegroundColor White
Write-Host "  Состояние:        $($Task.State)" -ForegroundColor White
Write-Host "  Последний запуск: $($TaskInfo.LastRunTime)" -ForegroundColor White
Write-Host "  Результат:        $($TaskInfo.LastTaskResult)" -ForegroundColor White
Write-Host ""

# Подтверждение удаления
$Response = Read-Host "Вы уверены что хотите удалить задачу? (y/n)"
if ($Response -ne 'y') {
    Write-Host "Удаление отменено." -ForegroundColor Yellow
    exit 0
}

Write-Host ""

# Останавливаем задачу если она запущена
if ($Task.State -eq "Running") {
    Write-Host "⏸️  Остановка задачи..." -ForegroundColor Yellow
    Stop-ScheduledTask -TaskName $TaskName -TaskPath $TaskPath
    Start-Sleep -Seconds 2

    $Task = Get-ScheduledTask -TaskName $TaskName -TaskPath $TaskPath
    if ($Task.State -ne "Running") {
        Write-Host "✅ Задача остановлена" -ForegroundColor Green
    } else {
        Write-Host "⚠️  Не удалось остановить задачу, состояние: $($Task.State)" -ForegroundColor Yellow
    }
    Write-Host ""
}

# Удаление задачи
Write-Host "🗑️  Удаление задачи..." -ForegroundColor Cyan

try {
    Unregister-ScheduledTask -TaskName $TaskName -TaskPath $TaskPath -Confirm:$false

    Write-Host ""
    Write-Host "========================================================================" -ForegroundColor Green
    Write-Host "✅ ЗАДАЧА УСПЕШНО УДАЛЕНА!" -ForegroundColor Green
    Write-Host "========================================================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "📝 Примечания:" -ForegroundColor Cyan
    Write-Host "  • Файлы проекта НЕ удалены" -ForegroundColor White
    Write-Host "  • Логи сохранены в папке logs/" -ForegroundColor White
    Write-Host "  • Для переустановки запустите install_task.ps1" -ForegroundColor White
    Write-Host ""
} catch {
    Write-Host ""
    Write-Host "========================================================================" -ForegroundColor Red
    Write-Host "❌ ОШИБКА ПРИ УДАЛЕНИИ ЗАДАЧИ" -ForegroundColor Red
    Write-Host "========================================================================" -ForegroundColor Red
    Write-Host ""
    Write-Host "Ошибка: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host ""
    Write-Host "Попробуйте:" -ForegroundColor Yellow
    Write-Host "  1. Убедитесь что задача полностью остановлена" -ForegroundColor White
    Write-Host "  2. Закройте Task Scheduler если он открыт" -ForegroundColor White
    Write-Host "  3. Перезагрузите компьютер" -ForegroundColor White
    Write-Host "  4. Запустите скрипт снова" -ForegroundColor White
    Write-Host ""
    Write-Host "Или удалите вручную через Task Scheduler:" -ForegroundColor Yellow
    Write-Host "  Win+R → taskschd.msc → найдите задачу → Delete" -ForegroundColor White
    Write-Host ""
}

Read-Host "Нажмите Enter для выхода"

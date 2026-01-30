# ============================================================
# ТЕСТОВЫЕ POWERSHELL КОМАНДЫ ДЛЯ ПОИСКА ЛИДА ПО ТЕЛЕФОНУ
# ============================================================
#
# ИНСТРУКЦИЯ:
# 1. Замените YOUR_WEBHOOK_URL на ваш webhook из config.ini
# 2. Замените PHONE_NUMBER на реальный номер телефона лида
# 3. Откройте PowerShell и выполните команды
#

# ЗАМЕНИТЕ ЭТИ ЗНАЧЕНИЯ:
$WebhookUrl = "YOUR_WEBHOOK_URL"  # Например: https://your-portal.bitrix24.ru/rest/1/xxxxx
$PhoneNumber = "PHONE_NUMBER"      # Например: +79991234567

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "ТЕСТ 1: Поиск лида по телефону" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "URL: $WebhookUrl/crm.lead.list"
Write-Host "Телефон: $PhoneNumber"
Write-Host ""

# Запрос 1: Обычный поиск через crm.lead.list
Write-Host "Запрос через crm.lead.list..." -ForegroundColor Yellow

$Body1 = @{
    filter = @{
        PHONE = $PhoneNumber
    }
    select = @("ID", "TITLE", "STATUS_ID", "CONTACT_ID", "PHONE")
} | ConvertTo-Json -Depth 10

try {
    $Response1 = Invoke-RestMethod -Uri "$WebhookUrl/crm.lead.list" `
        -Method Post `
        -ContentType "application/json" `
        -Body $Body1

    Write-Host "РЕЗУЛЬТАТ:" -ForegroundColor Green
    $Response1 | ConvertTo-Json -Depth 10

    if ($Response1.result -and $Response1.result.Count -gt 0) {
        Write-Host ""
        Write-Host "✅ Найдено лидов: $($Response1.result.Count)" -ForegroundColor Green
        $LeadId = $Response1.result[0].ID
        $ContactId = $Response1.result[0].CONTACT_ID
        Write-Host "   Лид ID: $LeadId" -ForegroundColor Green
        Write-Host "   Контакт ID: $ContactId" -ForegroundColor Green
    } else {
        Write-Host ""
        Write-Host "❌ Лиды не найдены" -ForegroundColor Red
    }
} catch {
    Write-Host "ОШИБКА: $_" -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
}

Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "ТЕСТ 2: Batch запрос (как в коде)" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

# URL-кодируем телефон
$EncodedPhone = [System.Web.HttpUtility]::UrlEncode($PhoneNumber)

$Body2 = @{
    halt = 0
    cmd = @{
        $PhoneNumber = "crm.lead.list?filter[PHONE]=$EncodedPhone&select[]=ID&select[]=STATUS_ID&select[]=CONTACT_ID"
    }
} | ConvertTo-Json -Depth 10

Write-Host "Запрос через batch..." -ForegroundColor Yellow

try {
    $Response2 = Invoke-RestMethod -Uri "$WebhookUrl/batch" `
        -Method Post `
        -ContentType "application/json" `
        -Body $Body2

    Write-Host "РЕЗУЛЬТАТ:" -ForegroundColor Green
    $Response2 | ConvertTo-Json -Depth 10

    if ($Response2.result.result.$PhoneNumber) {
        $LeadData = $Response2.result.result.$PhoneNumber
        Write-Host ""
        Write-Host "✅ Batch нашел лидов: $($LeadData.Count)" -ForegroundColor Green
        if ($LeadData.Count -gt 0) {
            Write-Host "   Лид ID: $($LeadData[0].ID)" -ForegroundColor Green
            Write-Host "   Контакт ID: $($LeadData[0].CONTACT_ID)" -ForegroundColor Green
        }
    } else {
        Write-Host ""
        Write-Host "❌ Batch не нашел лидов" -ForegroundColor Red
    }
} catch {
    Write-Host "ОШИБКА: $_" -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
}

Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "ГОТОВО!" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

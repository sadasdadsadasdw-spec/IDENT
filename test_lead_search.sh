#!/bin/bash

# ИНСТРУКЦИЯ:
# 1. Замените YOUR_WEBHOOK_URL на ваш реальный webhook URL из config.ini
#    Например: https://your-portal.bitrix24.ru/rest/1/xxxxxxxxxxxxx
# 2. Замените PHONE_NUMBER на реальный номер телефона лида с контактом
#    Например: +79991234567 или 79991234567
# 3. Запустите: bash test_lead_search.sh

WEBHOOK_URL="YOUR_WEBHOOK_URL"  # Замените на реальный URL
PHONE_NUMBER="PHONE_NUMBER"      # Замените на реальный телефон

echo "=========================================="
echo "ТЕСТ 1: Поиск лида по телефону"
echo "=========================================="
echo "URL: ${WEBHOOK_URL}/crm.lead.list"
echo "Телефон: ${PHONE_NUMBER}"
echo ""

# URL-кодируем телефон (+ становится %2B)
ENCODED_PHONE=$(echo "$PHONE_NUMBER" | sed 's/+/%2B/g')

# Запрос 1: Поиск лида через filter[PHONE]
echo "Запрос через filter[PHONE]:"
curl -s -X POST "${WEBHOOK_URL}/crm.lead.list" \
  -H "Content-Type: application/json" \
  -d '{
    "filter": {
      "PHONE": "'$PHONE_NUMBER'"
    },
    "select": ["ID", "TITLE", "STATUS_ID", "CONTACT_ID", "PHONE"]
  }' | python3 -m json.tool

echo ""
echo "=========================================="
echo "ТЕСТ 2: Поиск через batch (как в коде)"
echo "=========================================="

# Запрос 2: Batch запрос (как в нашем коде)
curl -s -X POST "${WEBHOOK_URL}/batch" \
  -H "Content-Type: application/json" \
  -d '{
    "halt": 0,
    "cmd": {
      "'$PHONE_NUMBER'": "crm.lead.list?filter[PHONE]='$ENCODED_PHONE'&select[]=ID&select[]=STATUS_ID&select[]=CONTACT_ID&select[]=PHONE"
    }
  }' | python3 -m json.tool

echo ""
echo "=========================================="
echo "ТЕСТ 3: Получение лида по ID (если нашли)"
echo "=========================================="
echo "Введите ID лида из результата выше (или нажмите Enter чтобы пропустить):"
read LEAD_ID

if [ ! -z "$LEAD_ID" ]; then
  curl -s -X POST "${WEBHOOK_URL}/crm.lead.get" \
    -H "Content-Type: application/json" \
    -d '{
      "id": "'$LEAD_ID'"
    }' | python3 -m json.tool
fi

echo ""
echo "=========================================="
echo "ГОТОВО!"
echo "=========================================="

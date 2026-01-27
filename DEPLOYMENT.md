# Развертывание IDENT → Bitrix24 Integration на Windows Server

Это руководство описывает как развернуть интеграцию на Windows Server для постоянной работы в фоновом режиме.

## Преимущества решения

- **Без внешних зависимостей**: Использует встроенный Windows Task Scheduler
- **Без VPN**: Не требует скачивания сторонних утилит
- **Автоматический запуск**: При старте Windows Server
- **Автоперезапуск**: При сбоях (3 попытки с интервалом 1 минута)
- **Работа без RDP**: Продолжает работать после закрытия сеанса
- **Простое управление**: PowerShell скрипты и GUI Task Scheduler

---

## Быстрый старт

### 1. Подготовка окружения

```powershell
# Клонируйте репозиторий или скопируйте файлы проекта
cd C:\Path\To\IDENT

# Установите зависимости Python
pip install -r requirements.txt

# Настройте config.ini с вашими параметрами
notepad config.ini
```

### 2. Установка задачи

```powershell
# Запустите PowerShell от имени администратора
# (ПКМ на PowerShell → "Запустить от имени администратора")

cd C:\Path\To\IDENT

# Установите задачу в Task Scheduler
.\install_task.ps1
```

### 3. Проверка работы

```powershell
# Проверьте статус задачи
.\check_task.ps1

# Просмотрите логи
Get-Content logs\ident_integration.log -Tail 50
```

**Готово!** Интеграция работает в фоне. Можете закрыть RDP.

---

## Структура файлов

```
IDENT/
├── run_service.py           # Wrapper с автоперезапуском
├── install_task.ps1         # Установка задачи в Task Scheduler
├── uninstall_task.ps1       # Удаление задачи
├── check_task.ps1           # Проверка статуса и диагностика
├── main.py                  # Основной код интеграции
├── config.ini               # Конфигурация
├── requirements.txt         # Python зависимости
└── logs/                    # Директория логов
    ├── ident_integration.log       # Основной лог
    ├── ident_integration_error.log # Только ошибки
    └── service_runner.log          # Лог wrapper'а
```

---

## Управление задачей

### PowerShell команды

```powershell
# Проверить статус
.\check_task.ps1

# Запустить задачу
Start-ScheduledTask -TaskName "IdentBitrix24Integration" -TaskPath "\IDENT\"

# Остановить задачу
Stop-ScheduledTask -TaskName "IdentBitrix24Integration" -TaskPath "\IDENT\"

# Отключить задачу (не удаляя)
Disable-ScheduledTask -TaskName "IdentBitrix24Integration" -TaskPath "\IDENT\"

# Включить задачу
Enable-ScheduledTask -TaskName "IdentBitrix24Integration" -TaskPath "\IDENT\"

# Удалить задачу полностью
.\uninstall_task.ps1
```

### Через GUI

1. Нажмите `Win+R`
2. Введите `taskschd.msc`
3. Откройте папку `IDENT`
4. Найдите задачу `IdentBitrix24Integration`
5. ПКМ → Start/Stop/Disable/Delete

---

## Настройки задачи

### Автоматический запуск

- **Триггер**: При запуске системы (At Startup)
- **Пользователь**: SYSTEM (работает без входа в систему)
- **Права**: Highest (максимальные права)

### Автоматический перезапуск

- **Попытки**: 3 раза
- **Интервал**: 1 минута между попытками
- **Защита**: Не более 5 быстрых перезапусков за 60 секунд (в run_service.py)

### Ограничения

- **Время выполнения**: Без ограничений (работает бесконечно)
- **Батарея**: Работает даже на батарее (для ноутбуков)
- **Приоритет**: Normal (приоритет 4)

---

## Мониторинг и логи

### Просмотр логов

```powershell
# Основной лог (все события)
Get-Content logs\ident_integration.log -Tail 50 -Wait

# Только ошибки
Get-Content logs\ident_integration_error.log -Tail 50 -Wait

# Лог wrapper'а
Get-Content logs\service_runner.log -Tail 50 -Wait

# Последние 100 строк
Get-Content logs\ident_integration.log -Tail 100
```

### Проверка процесса

```powershell
# Найти процесс Python
Get-Process python* | Where-Object { $_.CommandLine -like "*run_service.py*" }

# Показать использование ресурсов
Get-Process python* | Format-Table Name, Id, CPU, @{Name="RAM(MB)";Expression={[math]::Round($_.WorkingSet64/1MB,2)}}
```

### Логи Task Scheduler

```powershell
# Логи Windows Event Log
Get-WinEvent -LogName "Microsoft-Windows-TaskScheduler/Operational" -MaxEvents 50 |
    Where-Object { $_.Message -like "*IdentBitrix24*" }
```

---

## Производительность

### Потребление ресурсов

- **RAM**: ~80-130 MB (зависит от количества записей)
- **CPU**: <5% в среднем (пики при синхронизации)
- **Диск**: Логи ротируются автоматически, ~50-200 MB

### Оптимизации включены

- Stream processing (не загружает все в память)
- Batch API (2 запроса вместо N*2)
- Connection pooling с health check throttling
- LRU cache для treatment plans (10K limit)

### Метрики производительности

Проверить метрики можно в логах:
```
Performance Metrics (last 100 operations):
  sync_to_bitrix24: avg 2.32s, min 0.89s, max 5.12s (85 calls)
  batch_find_contacts: avg 0.53s (4 calls)
  batch_find_deals: avg 0.56s (4 calls)
```

---

## Troubleshooting

### Задача не запускается

1. **Проверьте права администратора**
   ```powershell
   # Запустите PowerShell от имени администратора
   .\install_task.ps1
   ```

2. **Проверьте Python в PATH**
   ```powershell
   python --version
   # Должно вывести версию Python 3.8+
   ```

3. **Проверьте наличие config.ini**
   ```powershell
   Test-Path .\config.ini
   # Должно быть True
   ```

### Задача запущена, но не работает

1. **Проверьте логи ошибок**
   ```powershell
   Get-Content logs\ident_integration_error.log -Tail 50
   ```

2. **Проверьте процесс Python**
   ```powershell
   .\check_task.ps1
   # Смотрите раздел "ПРОЦЕСС PYTHON"
   ```

3. **Проверьте подключение к БД**
   - Убедитесь что SQL Server доступен
   - Проверьте строку подключения в config.ini
   - Проверьте права пользователя БД

4. **Проверьте подключение к Bitrix24**
   - Проверьте webhook URL в config.ini
   - Проверьте доступ к интернету с сервера

### Задача постоянно перезапускается

1. **Проверьте лог service_runner.log**
   ```powershell
   Get-Content logs\service_runner.log -Tail 100
   ```

2. **Защита от бесконечного цикла**
   - Если более 5 перезапусков за 60 секунд → задача остановится
   - Исправьте проблему в логах
   - Запустите задачу вручную

### Высокое потребление RAM/CPU

1. **Проверьте метрики в логах**
2. **Уменьшите SYNC_INTERVAL в config.ini** (увеличьте паузу между циклами)
3. **Уменьшите API_BATCH_SIZE** в main.py (по умолчанию 20)

### Логи не обновляются

1. **Проверьте процесс Python**
   ```powershell
   Get-Process python*
   ```

2. **Проверьте статус задачи**
   ```powershell
   Get-ScheduledTask -TaskName "IdentBitrix24Integration" -TaskPath "\IDENT\"
   ```

3. **Перезапустите задачу**
   ```powershell
   Stop-ScheduledTask -TaskName "IdentBitrix24Integration" -TaskPath "\IDENT\"
   Start-ScheduledTask -TaskName "IdentBitrix24Integration" -TaskPath "\IDENT\"
   ```

---

## Обновление кода

Когда нужно обновить код интеграции:

```powershell
# 1. Остановите задачу
Stop-ScheduledTask -TaskName "IdentBitrix24Integration" -TaskPath "\IDENT\"

# 2. Обновите код (git pull, копирование файлов и т.д.)
git pull origin main

# 3. Обновите зависимости если нужно
pip install -r requirements.txt --upgrade

# 4. Запустите задачу
Start-ScheduledTask -TaskName "IdentBitrix24Integration" -TaskPath "\IDENT\"

# 5. Проверьте что все работает
.\check_task.ps1
```

---

## Безопасность

### Рекомендации

1. **Храните config.ini в безопасности**
   - Содержит пароли БД и Bitrix24 webhook
   - Ограничьте доступ к файлу
   ```powershell
   icacls config.ini /inheritance:r /grant:r "SYSTEM:(F)" "Administrators:(F)"
   ```

2. **Используйте отдельного пользователя БД**
   - Создайте пользователя с минимальными правами
   - Только SELECT на нужные таблицы

3. **Регулярно проверяйте логи**
   - Следите за ошибками подключения
   - Следите за неудачными попытками синхронизации

4. **Настройте backup логов**
   - Логи могут содержать важную диагностическую информацию

---

## FAQ

**Q: Будет ли работать после перезагрузки сервера?**
A: Да, задача настроена на автозапуск при старте системы.

**Q: Нужно ли держать RDP сессию открытой?**
A: Нет, задача работает от пользователя SYSTEM и не требует активной сессии.

**Q: Как узнать что интеграция работает?**
A: Запустите `.\check_task.ps1` - покажет статус, процесс, логи, ошибки.

**Q: Можно ли временно отключить интеграцию?**
A: Да, используйте `Disable-ScheduledTask` или кнопку "Disable" в Task Scheduler GUI.

**Q: Как изменить расписание синхронизации?**
A: Измените `SYNC_INTERVAL` в `config.ini` (в секундах).

**Q: Сколько RAM потребляет?**
A: ~80-130 MB. Благодаря stream processing не зависит от количества записей.

**Q: Что делать если задача "зависла"?**
A: Остановите задачу, проверьте логи, исправьте проблему, запустите снова.

**Q: Можно ли запустить несколько экземпляров?**
A: Не рекомендуется - будут конфликты при записи в Bitrix24. Используйте один экземпляр.

---

## Контакты и поддержка

При возникновении проблем:

1. Проверьте раздел **Troubleshooting**
2. Просмотрите логи в `logs/`
3. Запустите диагностику `.\check_task.ps1`
4. Проверьте метрики производительности в логах

---

## Changelog

### v2.0 (2026-01)
- Добавлен Windows Task Scheduler deployment
- Автоматический перезапуск при сбоях
- Защита от бесконечного цикла перезапусков
- Batch API оптимизации (5x ускорение)
- Stream processing (67% экономия RAM)
- LRU cache для treatment plans
- Health check throttling
- Комментарии в прямом поле вместо timeline

### v1.0 (2025-12)
- Первая версия интеграции
- Базовая синхронизация IDENT → Bitrix24

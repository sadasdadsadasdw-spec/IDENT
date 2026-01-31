# FAQ для разработчиков IDENT → Bitrix24 Integration

## Оглавление
- [Быстрый старт](#быстрый-старт)
- [Изменение кода](#изменение-кода)
- [Сборка проекта](#сборка-проекта)
- [Управление задачей Windows](#управление-задачей-windows)
- [Отладка и логи](#отладка-и-логи)
- [Работа с очередью](#работа-с-очередью)
- [Типичные проблемы](#типичные-проблемы)
- [Структура проекта](#структура-проекта)

---

## Быстрый старт

### Требования

- **Windows** 10/11 или Windows Server 2016+
- **Python** 3.8+ (рекомендуется 3.11)
- **SQL Server** (для БД IDENT)
- **PowerShell** 5.1+ (встроен в Windows)
- **Права администратора** (для установки задачи)

### Установка зависимостей

```powershell
# 1. Клонировать/скачать проект
cd C:\Path\To\IDENT

# 2. Создать виртуальное окружение (опционально, но рекомендуется)
python -m venv venv
.\venv\Scripts\Activate.ps1

# 3. Установить зависимости
pip install -r requirements.txt
```

### Настройка конфигурации

```powershell
# 1. Скопировать пример конфига
copy config.example.ini config.ini

# 2. Отредактировать config.ini
notepad config.ini
```

**Обязательные параметры:**
```ini
[Database]
server = localhost
database = IdentDB
username = ident_user
password = your_password

[Bitrix24]
webhook_url = https://your-portal.bitrix24.ru/rest/1/xxxxxxxxxx/
token = your_webhook_token

[Sync]
filial_id = 1  # ВАЖНО: номер филиала (1-5)
```

### Первый запуск (тестирование)

```powershell
# Запуск в консоли (для проверки)
python main.py
```

**Что должно произойти:**
1. Создание ключа шифрования (`config.ini` обновится)
2. Подключение к БД IDENT
3. Подключение к Bitrix24 API
4. Синхронизация записей
5. Логи в консоли и в `logs/integration_log_*.txt`

**Для выхода:** `Ctrl+C`

---

## Изменение кода

### Где находится основная логика?

| Файл | Описание | Что изменять |
|------|----------|--------------|
| `main.py` | Основной файл синхронизации | Логика поиска/обновления сделок |
| `src/bitrix/api_client.py` | API клиент Bitrix24 | Методы работы с CRM (контакты, сделки, лиды) |
| `src/database/db_manager.py` | Работа с БД IDENT | SQL запросы, подключение к БД |
| `src/transformer/data_transformer.py` | Трансформация данных | Маппинг стадий, преобразование полей |
| `src/queue/queue_manager.py` | Очередь повторных попыток | Логика retry, хранение неотправленных записей |
| `src/treatment_plan/plan_manager.py` | Синхронизация планов лечения | Работа с услугами и товарами |

### Пример: Изменение логики поиска

**Файл:** `main.py`
**Метод:** `sync_reception_to_bitrix24()` (строка ~254)

```python
def sync_reception_to_bitrix24(self, transformed_data: dict) -> bool:
    """
    ЛОГИКА ПОИСКА И ОБНОВЛЕНИЯ:
    1. Ищем сделку по IDENT ID
    2. Ищем контакт по телефону + ФИО
    3. Ищем сделку без IDENT ID для контакта
    4. Создаем новую сделку
    """
    unique_id = transformed_data['unique_id']
    # ... ваш код здесь
```

**Что можно изменить:**
- Порядок поиска
- Фильтры поиска
- Условия создания/обновления
- Логирование

**Что НЕ рекомендуется менять:**
- Структуру `transformed_data` (может сломать другие части)
- Обработку ошибок (try/except блоки)
- Механизм retry (очередь)

### Пример: Добавление нового поля в сделку

**1. Изменить трансформер**

**Файл:** `src/transformer/data_transformer.py`

```python
def transform_reception_to_deal(self, reception: dict) -> dict:
    # ...существующий код...

    deal_data = {
        # ...существующие поля...
        'uf_crm_new_field': reception.get('NewField'),  # НОВОЕ ПОЛЕ
    }

    return deal_data
```

**2. Изменить SQL запрос (если нужно)**

**Файл:** `src/database/db_manager.py`

```python
def get_new_receptions(self, hours: int = 2) -> List[dict]:
    query = """
        SELECT
            ReceptionID,
            -- ...существующие поля...
            NewField  -- НОВОЕ ПОЛЕ
        FROM Receptions
        -- ...
    """
```

**3. Обновить маппинг полей (если нужно пользовательское поле Bitrix24)**

Узнать ID пользовательского поля в Bitrix24:
```
https://your-portal.bitrix24.ru/crm/deal/show/1/
→ Открыть консоль браузера (F12)
→ Вкладка Elements
→ Найти input нужного поля
→ Атрибут name будет содержать ID (например, UF_CRM_1234567890)
```

---

## Сборка проекта

### Зачем нужна сборка в .exe?

- **Простота развертывания** - не нужен Python на целевой машине
- **Автоматический запуск** - работает как Windows служба (через Task Scheduler)
- **Изоляция** - все зависимости упакованы внутри

### Режим сборки: ONEDIR (рекомендуется)

**Почему ONEDIR, а не ONEFILE?**
- ONEFILE создает 2 процесса (bootloader + main) - может дублировать синхронизацию
- ONEDIR создает 1 процесс - гарантирует единственный экземпляр

### Команды сборки

#### Вариант 1: Автоматическая сборка (рекомендуется)

```powershell
# Запустить скрипт сборки
.\build_exe_onedir.ps1
```

**Что делает скрипт:**
1. Проверяет наличие Python
2. Проверяет наличие config.ini
3. Устанавливает PyInstaller (если нужно)
4. Очищает предыдущую сборку (dist/, build/, *.spec)
5. Запускает PyInstaller с нужными параметрами
6. Выводит путь к готовому .exe

**Результат:**
```
dist/
└── ident_sync/
    ├── ident_sync.exe       ← Основной файл
    ├── config.ini           ← Конфигурация
    ├── _internal/           ← Зависимости
    ├── base_library.zip
    └── python311.dll
```

#### Вариант 2: Ручная сборка

```powershell
# Очистка
Remove-Item -Path dist, build -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item -Path *.spec -Force -ErrorAction SilentlyContinue

# Сборка
pyinstaller `
    --name="ident_sync" `
    --onedir `
    --console `
    --add-data="config.ini;." `
    --hidden-import=pyodbc `
    --hidden-import=requests `
    --hidden-import=configparser `
    --collect-all=pyodbc `
    --noconfirm `
    main.py
```

**Параметры PyInstaller:**
- `--name="ident_sync"` - имя exe файла
- `--onedir` - режим папки (НЕ --onefile!)
- `--console` - показывать окно консоли
- `--add-data="config.ini;."` - включить config.ini в сборку
- `--hidden-import=...` - явно указать импорты (для pyodbc и др.)
- `--collect-all=pyodbc` - собрать все файлы pyodbc
- `--noconfirm` - перезаписывать без подтверждения

### Тестирование собранного .exe

```powershell
# Запустить вручную
.\dist\ident_sync\ident_sync.exe

# Проверить логи
Get-Content .\dist\ident_sync\logs\integration_log_*.txt -Tail 50
```

### Повторная сборка после изменения кода

```powershell
# ВАЖНО: Перед пересборкой остановить задачу Windows!
Stop-ScheduledTask -TaskName "IDENT_Bitrix24_Sync"

# Пересобрать
.\build_exe_onedir.ps1

# Скопировать новый .exe в место установки (если отличается от dist/)
# Обычно установка в: C:\IDENT_Integration\
Copy-Item -Path .\dist\ident_sync\* -Destination C:\IDENT_Integration\ -Recurse -Force

# Запустить задачу снова
Start-ScheduledTask -TaskName "IDENT_Bitrix24_Sync"
```

---

## Управление задачей Windows

Интеграция работает как автоматическая задача Windows (Task Scheduler), запускающаяся **каждые 2 минуты**.

### Установка задачи

```powershell
# ВАЖНО: Запустить PowerShell от имени Администратора!

# 1. Собрать проект (если еще не собрано)
.\build_exe_onedir.ps1

# 2. Установить задачу
.\install_task_onedir.ps1
```

**Что делает скрипт установки:**
1. Проверяет наличие `dist\ident_sync\ident_sync.exe`
2. Копирует файлы в `C:\IDENT_Integration\`
3. Создает задачу в Task Scheduler:
   - Имя: `IDENT_Bitrix24_Sync`
   - Запуск каждые 2 минуты
   - Пользователь: SYSTEM (или текущий)
   - Режим: Только если компьютер простаивает = **НЕТ**

### Проверка статуса задачи

```powershell
# Вариант 1: Через скрипт
.\check_task.ps1

# Вариант 2: Вручную
Get-ScheduledTask -TaskName "IDENT_Bitrix24_Sync"

# Вариант 3: GUI
taskschd.msc
# → Библиотека планировщика заданий → IDENT_Bitrix24_Sync
```

**Статусы:**
- `Ready` - задача готова к запуску
- `Running` - задача выполняется СЕЙЧАС
- `Disabled` - задача отключена

### Управление задачей

```powershell
# Запустить задачу немедленно (вручную)
Start-ScheduledTask -TaskName "IDENT_Bitrix24_Sync"

# Остановить задачу
Stop-ScheduledTask -TaskName "IDENT_Bitrix24_Sync"

# Отключить задачу (НЕ удаляя)
Disable-ScheduledTask -TaskName "IDENT_Bitrix24_Sync"

# Включить задачу
Enable-ScheduledTask -TaskName "IDENT_Bitrix24_Sync"

# Удалить задачу полностью
.\uninstall_task.ps1
# ИЛИ
Unregister-ScheduledTask -TaskName "IDENT_Bitrix24_Sync" -Confirm:$false
```

### Изменение интервала запуска

**Способ 1: Через GUI**
1. Открыть Task Scheduler (`taskschd.msc`)
2. Найти задачу `IDENT_Bitrix24_Sync`
3. Правой кнопкой → Свойства
4. Вкладка "Триггеры" → Изменить
5. Изменить интервал (например, с 2 минут на 5 минут)

**Способ 2: Через PowerShell**
```powershell
# Создать новый триггер (каждые 5 минут)
$Trigger = New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Minutes 5)

# Обновить задачу
Set-ScheduledTask -TaskName "IDENT_Bitrix24_Sync" -Trigger $Trigger
```

**Способ 3: Изменить config.ini**
```ini
[Sync]
interval_minutes = 5  # Изменить интервал (НЕ влияет на Task Scheduler!)
```
**ВНИМАНИЕ:** Параметр `interval_minutes` в config.ini НЕ влияет на расписание Task Scheduler! Он управляет внутренней логикой (например, для режима `--loop`).

### Просмотр истории выполнения

```powershell
# Последние 10 запусков
Get-ScheduledTaskInfo -TaskName "IDENT_Bitrix24_Sync" |
    Select-Object -ExpandProperty LastRunTime

# История выполнения (из Event Log)
Get-WinEvent -LogName "Microsoft-Windows-TaskScheduler/Operational" -MaxEvents 50 |
    Where-Object {$_.Message -like "*IDENT_Bitrix24_Sync*"}
```

---

## Отладка и логи

### Где находятся логи?

**Путь:** `logs/integration_log_YYYY-MM-DD.txt`

**Пример:** `logs/integration_log_2025-01-29.txt`

### Структура лога

```
2025-01-29 14:30:15 - INFO - ================================================================================
2025-01-29 14:30:15 - INFO - Начало синхронизации: 2025-01-29 14:30:15
2025-01-29 14:30:16 - INFO - Получено 5 новых записей из БД
2025-01-29 14:30:17 - INFO - Найден контакт 12345: Иванов Иван Иванович
2025-01-29 14:30:18 - INFO - Обновляем сделку 67890 для F1_12345
2025-01-29 14:30:18 - INFO - Успешно синхронизировано: 5 / 5
```

### Уровни логирования

**Настройка:** `config.ini`

```ini
[Logging]
level = INFO  # DEBUG, INFO, WARNING, ERROR, CRITICAL
```

**Рекомендации:**
- `DEBUG` - для разработки и отладки (ОЧЕНЬ подробно)
- `INFO` - для продакшена (нормальная детализация)
- `WARNING` - только предупреждения и ошибки
- `ERROR` - только ошибки

### Ключевые слова для поиска в логах

```powershell
# Ошибки
Select-String -Path .\logs\*.txt -Pattern "ERROR" | Select-Object -Last 20

# Автопривязка
Select-String -Path .\logs\*.txt -Pattern "АВТОПРИВЯЗКА"

# Множественные сделки (требуют проверки)
Select-String -Path .\logs\*.txt -Pattern "МНОЖЕСТВЕННЫЕ СДЕЛКИ"

# Игнорирование закрытых сделок
Select-String -Path .\logs\*.txt -Pattern "IGNORE"

# Защищенные стадии
Select-String -Path .\logs\*.txt -Pattern "PROTECTED"

# Очередь
Select-String -Path .\logs\*.txt -Pattern "QUEUE"
```

### Просмотр логов в реальном времени

```powershell
# Аналог tail -f
Get-Content .\logs\integration_log_2025-01-29.txt -Wait -Tail 20
```

### Ротация логов

**Автоматическая:** Старые логи удаляются автоматически

**Настройка:** `config.ini`
```ini
[Logging]
rotation_days = 30          # Хранить логи 30 дней
max_file_size_mb = 100      # Максимальный размер файла лога
```

**Ручная очистка:**
```powershell
# Удалить логи старше 7 дней
Get-ChildItem .\logs\*.txt |
    Where-Object {$_.LastWriteTime -lt (Get-Date).AddDays(-7)} |
    Remove-Item
```

### Маскировка персональных данных

**Настройка:** `config.ini`
```ini
[Logging]
mask_personal_data = True  # Маскировать ФИО, телефоны в логах
```

**Пример:**
```
# mask_personal_data = True
Создан контакт для И**** И**** И*******, телефон +7999***4567

# mask_personal_data = False
Создан контакт для Иванов Иван Иванович, телефон +79991234567
```

---

## Работа с очередью

### Что такое очередь?

Очередь (`PersistentQueue`) сохраняет записи, которые не удалось отправить в Bitrix24 (например, из-за ошибок сети).

**Файл очереди:** `data/queue.db` (SQLite)

### Просмотр очереди

```powershell
# Вариант 1: SQLite Browser (GUI)
# Скачать: https://sqlitebrowser.org/
# Открыть: data/queue.db

# Вариант 2: PowerShell + SQLite CLI
sqlite3 data\queue.db "SELECT * FROM queue;"

# Вариант 3: Python скрипт
python -c "
from src.queue.queue_manager import PersistentQueue
queue = PersistentQueue('data/queue.db')
print(f'Items in queue: {len(queue.items)}')
for uid, item in queue.items.items():
    print(f'{uid}: {item.status}, retries: {item.retry_count}')
"
```

### Параметры очереди

**Файл:** `config.ini`

```ini
[Queue]
queue_db_path = data/queue.db
max_queue_size = 1000              # Максимум элементов в очереди
process_interval_minutes = 5       # Интервал обработки очереди
```

### Очистка очереди

**Автоматическая:** Старые элементы (COMPLETED и FAILED) удаляются автоматически каждые N дней

**Ручная очистка:**
```powershell
# Удалить БД очереди (ОПАСНО - потеря неотправленных данных!)
Remove-Item data\queue.db

# Очередь пересоздастся автоматически при следующем запуске
```

### Повторная обработка очереди

Очередь обрабатывается автоматически при каждой синхронизации. Если элемент в очереди:
- **PENDING** - будет отправлен при следующей попытке
- **FAILED** (исчерпаны попытки) - удаляется через N дней
- **COMPLETED** - удаляется через N дней

**Параметры retry:**
```ini
[Bitrix24]
max_retries = 3                  # Максимум попыток
retry_delays = 30,60,300         # Задержки между попытками (сек)
```

---

## Типичные проблемы

### Проблема 1: Двойной запуск интеграции

**Симптомы:**
- Дубликаты сделок в Bitrix24
- В логах одна запись обрабатывается дважды

**Причина:**
- Использовался режим `--onefile` (создает 2 процесса)

**Решение:**
```powershell
# 1. Остановить задачу
Stop-ScheduledTask -TaskName "IDENT_Bitrix24_Sync"

# 2. Пересобрать в режиме ONEDIR
.\build_exe_onedir.ps1

# 3. Переустановить задачу
.\uninstall_task.ps1
.\install_task_onedir.ps1
```

### Проблема 2: Ошибка подключения к БД IDENT

**Симптомы:**
```
ERROR: Ошибка подключения к БД: [08001] [Microsoft][ODBC Driver]...
```

**Решение:**
```powershell
# 1. Проверить параметры в config.ini
notepad config.ini

# 2. Проверить доступность SQL Server
Test-NetConnection -ComputerName <SQL_SERVER_IP> -Port 1433

# 3. Проверить драйвер ODBC
odbcad32.exe
# → Драйверы → Проверить наличие "ODBC Driver 17 for SQL Server"

# 4. Установить драйвер (если отсутствует)
# Скачать: https://learn.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server
```

### Проблема 3: Ошибка API Bitrix24 (429 Too Many Requests)

**Симптомы:**
```
ERROR: API ошибка: QUERY_LIMIT_EXCEEDED
```

**Причина:** Превышен лимит запросов к API (2 запроса/сек для вебхуков)

**Решение:**
```ini
# config.ini
[Bitrix24]
rate_limit = 1  # Уменьшить с 2 до 1 запроса/сек
```

### Проблема 4: Очередь переполнена

**Симптомы:**
```
WARNING: Queue size limit reached (1000)
```

**Решение:**
```powershell
# 1. Проверить причину ошибок
Select-String -Path .\logs\*.txt -Pattern "ERROR" | Select-Object -Last 50

# 2. Исправить причину (обычно - недоступен Bitrix24 API)

# 3. Увеличить лимит очереди (если нужно)
# config.ini
[Queue]
max_queue_size = 5000  # Увеличить с 1000

# 4. Или очистить очередь (ПОТЕРЯ ДАННЫХ!)
Remove-Item data\queue.db
```

### Проблема 5: Задача не запускается автоматически

**Диагностика:**
```powershell
# 1. Проверить статус задачи
Get-ScheduledTask -TaskName "IDENT_Bitrix24_Sync"

# 2. Проверить последний запуск
Get-ScheduledTaskInfo -TaskName "IDENT_Bitrix24_Sync"

# 3. Проверить Event Log
Get-WinEvent -LogName "Microsoft-Windows-TaskScheduler/Operational" -MaxEvents 10 |
    Where-Object {$_.Message -like "*IDENT_Bitrix24_Sync*"}
```

**Решение:**
```powershell
# Включить задачу
Enable-ScheduledTask -TaskName "IDENT_Bitrix24_Sync"

# Запустить вручную (для проверки)
Start-ScheduledTask -TaskName "IDENT_Bitrix24_Sync"

# Проверить права пользователя задачи
# taskschd.msc → IDENT_Bitrix24_Sync → Properties → General
# "Run whether user is logged on or not" должно быть включено
```

### Проблема 6: Дубликаты контактов/сделок

**Причины:**
1. Неточное совпадение ФИО (опечатки, разные регистры)
2. Множественные сделки без IDENT ID
3. Двойной запуск интеграции (см. Проблему 1)

**Решение:**
```powershell
# 1. Проверить логи на "МНОЖЕСТВЕННЫЕ СДЕЛКИ"
Select-String -Path .\logs\*.txt -Pattern "МНОЖЕСТВЕННЫЕ СДЕЛКИ"

# 2. Вручную привязать лишние сделки к другим записям IDENT

# 3. Проверить точность ФИО в IDENT и Bitrix24
# Пробелы, регистр, опечатки должны совпадать ТОЧНО
```

---

## Структура проекта

```
IDENT/
├── main.py                          # Основной файл запуска
├── config.ini                       # Конфигурация (НЕ коммитить!)
├── config.example.ini               # Пример конфигурации
├── requirements.txt                 # Зависимости Python
├── build_exe_onedir.ps1             # Скрипт сборки в .exe
├── install_task_onedir.ps1          # Скрипт установки задачи Windows
├── uninstall_task.ps1               # Скрипт удаления задачи
├── check_task.ps1                   # Скрипт проверки статуса задачи
├── SEARCH_LOGIC.md                  # Документация логики поиска
├── DEVELOPER_FAQ.md                 # Этот файл
├── README.md                        # Общее описание проекта
│
├── src/                             # Исходный код
│   ├── bitrix/
│   │   └── api_client.py            # API клиент Bitrix24
│   ├── database/
│   │   └── db_manager.py            # Работа с БД IDENT
│   ├── transformer/
│   │   └── data_transformer.py      # Трансформация данных
│   ├── queue/
│   │   └── queue_manager.py         # Очередь повторных попыток
│   ├── treatment_plan/
│   │   └── plan_manager.py          # Синхронизация планов лечения
│   └── utils/
│       ├── config_manager.py        # Работа с config.ini
│       ├── crypto.py                # Шифрование токенов
│       └── logger.py                # Логирование
│
├── logs/                            # Логи (создается автоматически)
│   └── integration_log_*.txt
│
├── data/                            # Данные (создается автоматически)
│   └── queue.db                     # БД очереди (SQLite)
│
├── dist/                            # Собранный .exe (после build)
│   └── ident_sync/
│       ├── ident_sync.exe
│       └── ...
│
└── build/                           # Временные файлы сборки
    └── ...
```

---

## Чек-лист изменения кода

Используйте этот чек-лист при внесении изменений в проект:

### Перед изменением

- [ ] Остановить задачу Windows: `Stop-ScheduledTask -TaskName "IDENT_Bitrix24_Sync"`
- [ ] Создать резервную копию config.ini и data/queue.db
- [ ] Создать git ветку для изменений (если используется git)

### После изменения

- [ ] Протестировать в режиме разработки: `python main.py`
- [ ] Проверить логи на ошибки
- [ ] Пересобрать проект: `.\build_exe_onedir.ps1`
- [ ] Протестировать .exe: `.\dist\ident_sync\ident_sync.exe`
- [ ] Обновить установленную версию (скопировать в C:\IDENT_Integration\)
- [ ] Запустить задачу: `Start-ScheduledTask -TaskName "IDENT_Bitrix24_Sync"`
- [ ] Наблюдать логи в течение 10-15 минут
- [ ] Проверить результаты в Bitrix24

### При возникновении проблем

- [ ] Откатить изменения
- [ ] Восстановить резервную копию
- [ ] Проверить логи: `Select-String -Path .\logs\*.txt -Pattern "ERROR"`
- [ ] Проанализировать стек-трейс ошибки

---

## Полезные команды PowerShell

### Мониторинг

```powershell
# Следить за логами в реальном времени
Get-Content .\logs\integration_log_$(Get-Date -Format yyyy-MM-dd).txt -Wait -Tail 20

# Статистика за день
$LogFile = ".\logs\integration_log_$(Get-Date -Format yyyy-MM-dd).txt"
Write-Host "Успешно синхронизировано:"
(Select-String -Path $LogFile -Pattern "Успешно синхронизировано").Count
Write-Host "Ошибок:"
(Select-String -Path $LogFile -Pattern "ERROR").Count

# Проверка процессов (если задача запущена)
Get-Process ident_sync -ErrorAction SilentlyContinue
```

### Очистка

```powershell
# Очистка сборки
Remove-Item -Path dist, build -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item -Path *.spec -Force -ErrorAction SilentlyContinue

# Очистка логов старше 30 дней
Get-ChildItem .\logs\*.txt |
    Where-Object {$_.LastWriteTime -lt (Get-Date).AddDays(-30)} |
    Remove-Item

# Очистка очереди (ОСТОРОЖНО!)
Remove-Item data\queue.db -Force
```

### Тестирование

```powershell
# Тест подключения к БД
python -c "from src.database.db_manager import IdentDBManager; db = IdentDBManager(); print('DB OK')"

# Тест подключения к Bitrix24
python -c "from src.bitrix.api_client import Bitrix24APIClient; from src.utils.config_manager import ConfigManager; cfg = ConfigManager(); b24 = Bitrix24APIClient(cfg.get('Bitrix24', 'webhook_url'), cfg.get('Bitrix24', 'token')); print('Bitrix24 OK')"

# Тест очереди
python -c "from src.queue.queue_manager import PersistentQueue; q = PersistentQueue('data/queue.db'); print(f'Queue items: {len(q.items)}')"
```

---

## Дополнительные ресурсы

### Документация Bitrix24 REST API
- [CRM (Контакты, Сделки, Лиды)](https://dev.1c-bitrix.ru/rest_help/crm/index.php)
- [Batch запросы](https://dev.1c-bitrix.ru/rest_help/general/batch.php)
- [Лимиты API](https://dev.1c-bitrix.ru/rest_help/general/limits.php)

### PyInstaller
- [Официальная документация](https://pyinstaller.org/en/stable/)
- [Решение проблем](https://pyinstaller.org/en/stable/when-things-go-wrong.html)

### Windows Task Scheduler
- [PowerShell командлеты](https://learn.microsoft.com/en-us/powershell/module/scheduledtasks/)

---

## Контакты и поддержка

При возникновении проблем:
1. Проверьте логи (`logs/integration_log_*.txt`)
2. Проверьте очередь (`data/queue.db`)
3. Используйте ключевые слова для поиска в логах (см. раздел "Отладка и логи")
4. Обратитесь к разделу "Типичные проблемы"

**Последнее обновление:** 2025-01-29

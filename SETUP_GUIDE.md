# Руководство по настройке интеграции для нового филиала

## Шаг 1: Создайте config.ini

```powershell
# В PowerShell в директории C:\Projects\Ident-gitpro
Copy-Item config.example.ini config.ini
```

## Шаг 2: Отредактируйте config.ini

Откройте `config.ini` в текстовом редакторе и заполните:

### [Database] - Подключение к БД IDENT

```ini
[Database]
# Для именованных экземпляров SQL Server (например, .\PZSQLSERVER)
server = .\PZSQLSERVER
# ИЛИ для сетевых: server = 192.168.1.100

# Порт (обычно 1433, но для именованных экземпляров не используется)
port = 1433

# Имя базы данных IDENT
database = IdentDB

# Логин пользователя SQL Server
username = ident_user

# Пароль (будет зашифрован автоматически при первом запуске)
password = ваш_пароль

# Таймауты (обычно не нужно менять)
connection_timeout = 10
query_timeout = 30
```

### [Bitrix24] - Подключение к Bitrix24

```ini
[Bitrix24]
# URL вебхука (получите в Битрикс24: Приложения → Вебхуки → Входящий вебхук)
# Пример: https://testmillident.bitrix24.ru/rest/1/56onh3uktsxeunvg/
webhook_url = https://ваш-портал.bitrix24.ru/rest/1/ваш_токен/

# Токен уже есть в URL вебхука, оставьте пустым
token =

# Максимум попыток при ошибках API
max_retries = 3

# Задержки между повторами (секунды)
retry_delays = 30,60,300

# Ограничение запросов в секунду
rate_limit = 2

# ID ответственного по умолчанию (опционально)
# Оставьте пустым, чтобы использовать владельца вебхука
default_assigned_by_id =
```

### [Sync] - Настройки синхронизации

```ini
[Sync]
# Интервал синхронизации (в минутах)
interval_minutes = 2

# Размер пакета для обработки
batch_size = 50

# Глубина начальной синхронизации (дни)
initial_sync_days = 7

# ⚠️ ВАЖНО: ID филиала (1-5)
# Для каждого филиала должен быть уникальный ID!
# Филиал 1 = 1, Филиал 2 = 2, и т.д.
filial_id = 2
```

### [Logging] - Логирование

```ini
[Logging]
# Уровень логирования (DEBUG покажет больше деталей)
level = INFO

# Путь к директории логов
log_dir = logs

# Формат имени файла
log_filename = integration_log_{date}.txt

# Хранение логов (дни)
rotation_days = 30

# Максимальный размер файла (МБ)
max_file_size_mb = 100

# Маскировка персональных данных (рекомендуется True)
mask_personal_data = True
```

### Остальные секции
Обычно не требуют изменений, оставьте значения по умолчанию.

---

## Шаг 3: Проверьте конфигурацию

Запустите тестовый скрипт для проверки:

```powershell
# Тест подключения к БД и Bitrix24
python main.py --test-connection
```

Или запустите вручную для просмотра ошибок:

```powershell
.\dist\ident_sync\ident_sync.exe
```

---

## Шаг 4: Проверьте параметры БД

Если не уверены в параметрах подключения к БД:

### Узнать имя SQL Server экземпляра:

```sql
-- В SQL Server Management Studio выполните:
SELECT @@SERVERNAME AS ServerName
```

Результат может быть:
- `COMPUTER\PZSQLSERVER` - именованный экземпляр
- `COMPUTER` - стандартный экземпляр
- `192.168.1.100` - сетевой сервер

### Узнать имя базы данных:

```sql
-- Список всех баз:
SELECT name FROM sys.databases WHERE name LIKE '%Ident%'
```

### Проверить логин:

```sql
-- Текущий пользователь:
SELECT SYSTEM_USER, USER_NAME()
```

---

## Шаг 5: Получить webhook Bitrix24

1. Откройте ваш портал Bitrix24
2. Перейдите: **Приложения** → **Вебхуки** → **Входящий вебхук**
3. Создайте новый вебхук или используйте существующий
4. **Права доступа** (минимально необходимые):
   - CRM (crm): Чтение, Запись
   - Контакты (contact): Чтение, Запись
   - Лиды (lead): Чтение, Запись
   - Сделки (deal): Чтение, Запись

5. Скопируйте URL вебхука:
   ```
   https://ваш-портал.bitrix24.ru/rest/1/токен/
   ```

6. Вставьте в `config.ini` → `[Bitrix24]` → `webhook_url`

---

## Шаг 6: Проверьте настройки filial_id

⚠️ **КРИТИЧЕСКИ ВАЖНО:** Каждый филиал должен иметь уникальный `filial_id`!

| Филиал | filial_id | Префикс записей |
|--------|-----------|------------------|
| Филиал 1 | 1 | F1_12345 |
| Филиал 2 | 2 | F2_12345 |
| Филиал 3 | 3 | F3_12345 |
| Филиал 4 | 4 | F4_12345 |
| Филиал 5 | 5 | F5_12345 |

**Почему это важно:**
- `filial_id` используется для генерации уникальных идентификаторов записей
- Если два филиала используют одинаковый ID - произойдут конфликты данных
- Записи одного филиала начнут перезаписывать записи другого!

---

## Шаг 7: Создайте директорию для данных

```powershell
# Создайте директории для логов и данных
New-Item -ItemType Directory -Path "logs" -Force
New-Item -ItemType Directory -Path "data" -Force
```

---

## Шаг 8: Переустановите задачу

```powershell
# Переустановите задачу в планировщике
.\install_task_onedir.ps1
```

При запросе "Start task now?" выберите **y** и проверьте что:
- ✅ Task state: Running
- ✅ Running processes: 1
- ✅ Логи создаются в `logs/`

---

## Диагностика проблем

### Проблема: "No ident_sync processes found"

**Причины:**
1. Нет `config.ini` (создайте из шаблона)
2. Ошибка в `config.ini` (неправильные параметры)
3. Не подключается к БД (проверьте server/database/username/password)
4. Не подключается к Bitrix24 (проверьте webhook_url)

**Решение:**
```powershell
# Запустите вручную чтобы увидеть ошибку:
.\dist\ident_sync\ident_sync.exe

# Проверьте логи (если создались):
Get-Content logs\integration_log_*.txt -Tail 50

# Проверьте Event Viewer:
Get-EventLog -LogName Application -Source "Application" -Newest 10 | Where-Object {$_.Message -like "*ident*"}
```

### Проблема: "Last result: 1 (Error)"

Код выхода 1 означает ошибку. Проверьте:

1. **Логи приложения:**
   ```powershell
   ls logs\
   Get-Content logs\integration_log_2026-01-30.txt
   ```

2. **Event Viewer:**
   ```powershell
   # PowerShell:
   Get-WinEvent -LogName Application -MaxEvents 20 | Where-Object {$_.Message -like "*ident*" -or $_.Message -like "*python*"}

   # Или GUI:
   Win+R → eventvwr.msc → Windows Logs → Application
   ```

3. **Права доступа:**
   - Задача запускается от имени SYSTEM
   - Проверьте что SYSTEM имеет доступ к БД

---

## Проверка работоспособности

После запуска задачи проверьте:

### 1. Процесс запущен
```powershell
Get-Process -Name "ident_sync" -ErrorAction SilentlyContinue
```

Должен показать 1 процесс.

### 2. Логи создаются
```powershell
ls logs\
Get-Content logs\integration_log_*.txt -Tail 20
```

Должны видеть:
```
ЗАПУСК ИНТЕГРАЦИИ IDENT → BITRIX24
Инициализация подключения к БД Ident...
Инициализация клиента Bitrix24...
Проверка подключений
Подключение к БД OK
Подключение к Bitrix24 OK
Запуск синхронизации по расписанию
```

### 3. Синхронизация работает
```powershell
# Через 2 минуты после запуска должны увидеть:
Get-Content logs\integration_log_*.txt | Select-String "Начало синхронизации"
```

### 4. Записи находятся
```powershell
# Если есть записи в БД, должно быть:
Get-Content logs\integration_log_*.txt | Select-String "Извлечено записей"
```

Если видите "Извлечено записей: 0" - запустите `debug_check_db_records.sql` для диагностики БД.

---

## Частые ошибки

| Ошибка | Причина | Решение |
|--------|---------|---------|
| "Cannot find config.ini" | Нет конфига | Создайте из config.example.ini |
| "ConnectionError: Unable to connect" | Неверные параметры БД | Проверьте server/database/username/password |
| "Bitrix24AuthError" | Неверный webhook | Проверьте webhook_url |
| "api-ms-win-crt-runtime-l1-1-0.dll missing" | Нет VC++ Redistributable | Установите VC++ 2015-2022 |
| "Access denied" | Нет прав на БД | Проверьте права пользователя SQL |
| "filial_id must be 1-5" | Неверный filial_id | Укажите значение от 1 до 5 |

---

## Контрольный чеклист

- [ ] `config.ini` создан из `config.example.ini`
- [ ] Заполнены параметры БД (server, database, username, password)
- [ ] Заполнен webhook_url Bitrix24
- [ ] Указан уникальный filial_id (отличается от других филиалов!)
- [ ] Создана директория `logs/`
- [ ] Создана директория `data/`
- [ ] Тест подключения пройден (`python main.py --test-connection`)
- [ ] Задача установлена (`.\install_task_onedir.ps1`)
- [ ] Процесс запущен (1 экземпляр ident_sync.exe)
- [ ] Логи создаются и показывают успешные подключения
- [ ] Синхронизация находит записи (или выводит предупреждение)

---

## Поддержка

При проблемах предоставьте:
1. Содержимое логов: `logs\integration_log_*.txt`
2. Результаты проверки: `.\check_task.ps1`
3. Результаты теста БД: выполните `debug_check_db_records.sql`
4. Версию Windows и SQL Server

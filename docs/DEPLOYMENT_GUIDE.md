# Руководство по развертыванию интеграции Ident-Битрикс24

## Оглавление
1. [Предварительные требования](#предварительные-требования)
2. [Подготовка серверного ПК](#подготовка-серверного-пк)
3. [Установка зависимостей](#установка-зависимостей)
4. [Развертывание проекта](#развертывание-проекта)
5. [Настройка конфигурации](#настройка-конфигурации)
6. [Тестирование](#тестирование)
7. [Установка как службы Windows](#установка-как-службы-windows)
8. [Мониторинг и обслуживание](#мониторинг-и-обслуживание)
9. [Устранение неполадок](#устранение-неполадок)

---

## Предварительные требования

### Информация которую нужно подготовить:

**Доступы к серверному ПК:**
- IP-адрес или имя сервера
- Логин и пароль администратора Windows
- Порт RDP (по умолчанию 3389)

**Данные для подключения к БД Ident:**
- Адрес SQL Server (обычно localhost или 127.0.0.1)
- Название базы данных
- Логин и пароль для доступа к БД
- Порт SQL Server (по умолчанию 1433)

**Данные Битрикс24:**
- URL вашего портала (например: `https://your-company.bitrix24.ru`)
- Webhook токен (получить в Битрикс24: Настройки → Интеграции → Входящий webhook)

**ID филиала:**
- Номер филиала (от 1 до 5)

---

## Подготовка серверного ПК

### Шаг 1: Подключение по RDP

#### На Windows:

1. Нажмите `Win + R`
2. Введите: `mstsc`
3. Введите адрес сервера и нажмите "Подключить"
4. Введите логин и пароль

**Пример:**
```
Компьютер: 192.168.1.100
Имя пользователя: Administrator
Пароль: ********
```

#### На macOS:

1. Установите Microsoft Remote Desktop из App Store
2. Создайте новое подключение
3. Введите данные сервера
4. Подключитесь

#### На Linux:

```bash
# Установите Remmina (если не установлен)
sudo apt install remmina remmina-plugin-rdp

# Запустите
remmina
# Создайте новое RDP подключение
```

### Шаг 2: Проверка доступа к БД Ident

После подключения по RDP проверьте доступ к БД:

1. Откройте SQL Server Management Studio (SSMS) или любой SQL клиент
2. Попробуйте подключиться к БД с учетными данными
3. Выполните тестовый запрос:
   ```sql
   SELECT COUNT(*) FROM Receptions
   SELECT COUNT(*) FROM Patients
   SELECT COUNT(*) FROM TreatmentPlans
   ```

### Шаг 3: Проверка интернет-соединения

```powershell
# В PowerShell проверьте доступ к Битрикс24
Test-NetConnection bitrix24.ru -Port 443

# Проверьте скорость интернета
# Минимум: 1 Мбит/с
```

---

## Установка зависимостей

### Шаг 1: Установка Python 3.10+

1. Скачайте Python с официального сайта:
   - https://www.python.org/downloads/
   - Версия: Python 3.10 или выше

2. Запустите установщик

3. **ВАЖНО:** Отметьте галочки:
   - ✅ Add Python to PATH
   - ✅ Install pip
   - ✅ Install for all users

4. Выберите "Customize installation"
   - Отметьте все опции
   - В "Advanced Options" выберите путь: `C:\Python310`

5. Проверьте установку:
   ```powershell
   python --version
   # Должно показать: Python 3.10.x или выше

   pip --version
   # Должно показать версию pip
   ```

### Шаг 2: Установка ODBC Driver для SQL Server

1. Скачайте ODBC Driver 17 для SQL Server:
   - https://learn.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server

2. Запустите установщик: `msodbcsql.msi`

3. Следуйте инструкциям установщика

4. Проверьте установку:
   ```powershell
   # Откройте "ODBC Data Sources (64-bit)"
   odbcad32

   # Перейдите на вкладку "Drivers"
   # Должен быть "ODBC Driver 17 for SQL Server"
   ```

### Шаг 3: Установка Git (опционально)

Если планируете клонировать проект через Git:

1. Скачайте Git for Windows:
   - https://git-scm.com/download/win

2. Установите с настройками по умолчанию

3. Проверьте:
   ```powershell
   git --version
   ```

---

## Развертывание проекта

### Вариант A: Клонирование через Git

```powershell
# Создайте директорию для проекта
cd C:\
mkdir Projects
cd Projects

# Клонируйте репозиторий
git clone https://github.com/sadasdadsadasdw-spec/IDENT.git
cd IDENT

# Перейдите на ветку с вашим филиалом (если нужно)
git checkout claude/general-session-kbSc1
```

### Вариант B: Копирование файлов

1. На вашем локальном компьютере заархивируйте проект:
   ```bash
   cd /path/to/project
   zip -r ident-integration.zip .
   ```

2. Скопируйте архив на сервер через RDP:
   - В RDP сессии откройте Проводник
   - Перетащите файл `ident-integration.zip` с локального ПК
   - Или используйте общую папку в настройках RDP

3. Распакуйте на сервере:
   ```powershell
   # Создайте директорию
   cd C:\
   mkdir Projects
   cd Projects

   # Распакуйте архив
   Expand-Archive -Path "C:\Users\Administrator\Downloads\ident-integration.zip" -DestinationPath "C:\Projects\IDENT"
   ```

### Шаг 2: Установка Python зависимостей

```powershell
cd C:\Projects\IDENT

# Обновите pip
python -m pip install --upgrade pip

# Установите зависимости
pip install -r requirements.txt

# Дождитесь завершения установки (может занять 2-5 минут)
```

**Возможные проблемы:**

Если возникает ошибка при установке `pywin32`:
```powershell
# Установите вручную
pip install pywin32==306

# Выполните постустановочный скрипт
python Scripts/pywin32_postinstall.py -install
```

Если ошибка при установке `pyodbc`:
```powershell
# Установите Build Tools for Visual Studio
# Скачайте: https://visualstudio.microsoft.com/downloads/
# Выберите "Build Tools for Visual Studio 2022"
# Установите "C++ build tools"

# Или скачайте готовую сборку:
pip install --only-binary :all: pyodbc
```

---

## Настройка конфигурации

### Шаг 1: Создание файла конфигурации

```powershell
cd C:\Projects\IDENT

# Скопируйте пример конфигурации
copy config.example.ini config.ini

# Откройте в текстовом редакторе
notepad config.ini
```

### Шаг 2: Заполнение параметров

Отредактируйте `config.ini`:

```ini
[Database]
# Адрес SQL Server (обычно localhost для локальной БД)
server = localhost
port = 1433

# Название базы данных Ident
database = IdentDB

# Учетные данные для подключения
username = ident_user
password = your_password_here

# Таймауты (можно оставить по умолчанию)
connection_timeout = 10
query_timeout = 30

[Bitrix24]
# URL вашего портала с REST API (БЕЗ последнего слэша)
# Пример: https://your-company.bitrix24.ru/rest/1/abc123xyz456
webhook_url = https://your-company.bitrix24.ru/rest/1/YOUR_WEBHOOK_TOKEN

# Токен (он же последняя часть webhook_url)
# Будет автоматически зашифрован при первом запуске
token = YOUR_WEBHOOK_TOKEN

# Настройки повторных попыток (можно оставить по умолчанию)
max_retries = 3
retry_delays = 30,60,300
rate_limit = 2

[Sync]
# Интервал синхронизации в минутах
interval_minutes = 2

# Размер пакета записей за один цикл
batch_size = 50

# Глубина начальной синхронизации (дней назад)
initial_sync_days = 7

# ID вашего филиала (1-5)
# ВАЖНО: Установите правильный номер для каждого филиала!
filial_id = 1

[Logging]
# Уровень логирования: DEBUG, INFO, WARNING, ERROR, CRITICAL
level = INFO

# Директория для логов
log_dir = C:\Projects\IDENT\logs

# Шаблон имени файла
log_filename = integration_log_{date}.txt

# Хранить логи (дней)
rotation_days = 30

# Максимальный размер файла (МБ)
max_file_size_mb = 100

# Маскировать персональные данные (рекомендуется True)
mask_personal_data = True

[Queue]
# Путь к базе очереди
queue_db_path = C:\Projects\IDENT\data\queue.db

# Максимальный размер очереди
max_queue_size = 1000

# Интервал обработки очереди (минут)
process_interval_minutes = 5

[Monitoring]
# Включить веб-интерфейс мониторинга
enabled = True

# Адрес и порт
host = localhost
port = 8080

# Debug режим (только для разработки!)
debug = False

[Notifications]
# Email администратора для уведомлений
admin_email = admin@your-clinic.ru

# SMTP настройки (если нужны email-уведомления)
smtp_server = smtp.gmail.com
smtp_port = 587
smtp_username = your_email@gmail.com
smtp_password = your_app_password

# Пороги для уведомлений
error_threshold_percent = 10
error_threshold_count = 5
```

### Шаг 3: Получение Webhook токена Битрикс24

1. Войдите в свой Битрикс24 портал

2. Перейдите: **Настройки → Интеграции → Входящие вебхуки**

3. Нажмите "Добавить вебхук"

4. Настройте права доступа:
   - ✅ CRM (crm)
   - ✅ Контакты (crm.contact)
   - ✅ Сделки (crm.deal)
   - ✅ Лиды (crm.lead)

5. Скопируйте URL вебхука, например:
   ```
   https://your-company.bitrix24.ru/rest/1/abc123xyz456789/
   ```

6. Вставьте в `config.ini`:
   ```ini
   webhook_url = https://your-company.bitrix24.ru/rest/1/abc123xyz456789
   token = abc123xyz456789
   ```

### Шаг 4: Создание необходимых директорий

```powershell
cd C:\Projects\IDENT

# Создайте директории
mkdir logs
mkdir data

# Проверьте структуру
tree /F
```

---

## Тестирование

### Шаг 1: Тест подключения к БД

```powershell
cd C:\Projects\IDENT

# Запустите тестовый скрипт
python -c "from src.database.ident_connector import IdentConnector; from src.config.config_manager import get_config; config = get_config(); db_config = config.get_database_config(); conn = IdentConnector(**db_config); print('Тестирование подключения...'); result = conn.test_connection(); print('✓ Подключение успешно!' if result else '✗ Ошибка подключения')"
```

**Ожидаемый результат:**
```
Тестирование подключения...
✓ Подключение успешно!
```

### Шаг 2: Тест извлечения данных

Создайте файл `test_integration.py`:

```python
"""Тестовый скрипт для проверки интеграции"""

from src.config.config_manager import get_config
from src.database.ident_connector import IdentConnector
from src.logger.custom_logger import get_logger

def main():
    print("=== Тест интеграции Ident-Битрикс24 ===\n")

    # Загрузка конфигурации
    print("1. Загрузка конфигурации...")
    try:
        config = get_config()
        print("   ✓ Конфигурация загружена")
    except Exception as e:
        print(f"   ✗ Ошибка: {e}")
        return

    # Инициализация логгера
    print("\n2. Инициализация логгера...")
    try:
        log_config = config.get_logging_config()
        logger = get_logger(**log_config)
        logger.info("Тестовое сообщение в лог")
        print("   ✓ Логгер инициализирован")
        print(f"   Логи сохраняются в: {log_config['log_dir']}")
    except Exception as e:
        print(f"   ✗ Ошибка: {e}")
        return

    # Подключение к БД
    print("\n3. Подключение к БД Ident...")
    try:
        db_config = config.get_database_config()
        connector = IdentConnector(**db_config)
        connector.test_connection()
        print("   ✓ Подключение установлено")
    except Exception as e:
        print(f"   ✗ Ошибка: {e}")
        return

    # Получение статистики БД
    print("\n4. Получение статистики БД...")
    try:
        stats = connector.get_statistics()
        print("   ✓ Статистика получена:")
        for key, value in stats.items():
            print(f"      {key}: {value}")
    except Exception as e:
        print(f"   ✗ Ошибка: {e}")
        return

    # Извлечение записей
    print("\n5. Извлечение записей (последние 5)...")
    try:
        receptions = connector.get_receptions(batch_size=5)
        print(f"   ✓ Получено записей: {len(receptions)}")
        if receptions:
            first = receptions[0]
            print(f"\n   Пример записи:")
            print(f"      ID: {first.get('ReceptionID')}")
            print(f"      Пациент: {first.get('PatientFullName')}")
            print(f"      Телефон: {first.get('PatientPhone')}")
            print(f"      Врач: {first.get('DoctorFullName')}")
            print(f"      Филиал: {first.get('Filial')}")
            print(f"      Дата: {first.get('StartTime')}")
            print(f"      Услуги: {first.get('Services')}")
            print(f"      Сумма: {first.get('TotalAmount')}")
    except Exception as e:
        print(f"   ✗ Ошибка: {e}")
        return

    print("\n=== ✓ Все тесты пройдены успешно! ===")
    print("\nСистема готова к работе.")
    print("Следующий шаг: Установка как службы Windows")

if __name__ == "__main__":
    main()
```

Запустите тест:

```powershell
python test_integration.py
```

**Ожидаемый результат:**
```
=== Тест интеграции Ident-Битрикс24 ===

1. Загрузка конфигурации...
   ✓ Конфигурация загружена

2. Инициализация логгера...
   ✓ Логгер инициализирован
   Логи сохраняются в: C:\Projects\IDENT\logs

3. Подключение к БД Ident...
   ✓ Подключение установлено

4. Получение статистики БД...
   ✓ Статистика получена:
      total_receptions: 15234
      total_patients: 5678
      total_treatment_plans: 890
      receptions_today: 45
      receptions_this_week: 234

5. Извлечение записей (последние 5)...
   ✓ Получено записей: 5

   Пример записи:
      ID: 12345
      Пациент: Иванов Иван Иванович
      Телефон: +79161234567
      Врач: Петров Петр Петрович
      Филиал: Филиал Фучика
      Дата: 2026-01-21 14:30:00
      Услуги: Консультация, Лечение кариеса
      Сумма: 5500.00

=== ✓ Все тесты пройдены успешно! ===

Система готова к работе.
Следующий шаг: Установка как службы Windows
```

### Шаг 3: Проверка веб-интерфейса мониторинга

После того как реализуем главный модуль, можно будет проверить:

```powershell
# Запустите интеграцию
python main.py

# В браузере откройте
http://localhost:8080
```

---

## Установка как службы Windows

### Способ 1: Windows Service (Рекомендуется)

Создайте файл `install_service.py`:

```python
"""Установка интеграции как службы Windows"""

import win32serviceutil
import win32service
import win32event
import servicemanager
import socket
import sys
import os

# Добавляем путь к проекту
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

class IdentBitrix24Service(win32serviceutil.ServiceFramework):
    _svc_name_ = "IdentBitrix24Integration"
    _svc_display_name_ = "Интеграция Ident-Битрикс24"
    _svc_description_ = "Автоматическая синхронизация данных из Ident в Битрикс24"

    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.stop_event = win32event.CreateEvent(None, 0, 0, None)
        socket.setdefaulttimeout(60)
        self.is_alive = True

    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        win32event.SetEvent(self.stop_event)
        self.is_alive = False

    def SvcDoRun(self):
        servicemanager.LogMsg(
            servicemanager.EVENTLOG_INFORMATION_TYPE,
            servicemanager.PYS_SERVICE_STARTED,
            (self._svc_name_, '')
        )
        self.main()

    def main(self):
        """Основной код службы"""
        try:
            # Импортируем главный модуль
            from main import run_integration

            # Запускаем интеграцию
            run_integration(service_mode=True)

        except Exception as e:
            servicemanager.LogErrorMsg(f"Ошибка в службе: {e}")

if __name__ == '__main__':
    if len(sys.argv) == 1:
        servicemanager.Initialize()
        servicemanager.PrepareToHostSingle(IdentBitrix24Service)
        servicemanager.StartServiceCtrlDispatcher()
    else:
        win32serviceutil.HandleCommandLine(IdentBitrix24Service)
```

Установите службу:

```powershell
# Откройте PowerShell от имени администратора
# ПКМ на PowerShell → "Запуск от имени администратора"

cd C:\Projects\IDENT

# Установите службу
python install_service.py install

# Настройте автозапуск
python install_service.py --startup=auto install

# Запустите службу
python install_service.py start

# Проверьте статус
python install_service.py status
```

### Способ 2: Task Scheduler (Альтернатива)

Если не получается установить Windows Service:

1. Откройте Task Scheduler: `Win + R` → `taskschd.msc`

2. Создайте новую задачу:
   - **Действия → Создать задачу...**

3. Вкладка "Общие":
   - Имя: `Интеграция Ident-Битрикс24`
   - Описание: `Автоматическая синхронизация данных`
   - ✅ Выполнять вне зависимости от регистрации пользователя
   - ✅ Выполнять с наивысшими правами

4. Вкладка "Триггеры":
   - Нажмите "Создать..."
   - Начать задачу: **При запуске**
   - ✅ Включено

5. Вкладка "Действия":
   - Нажмите "Создать..."
   - Действие: **Запуск программы**
   - Программа: `C:\Python310\python.exe`
   - Аргументы: `C:\Projects\IDENT\main.py`
   - Рабочая папка: `C:\Projects\IDENT`

6. Вкладка "Условия":
   - ❌ Запускать задачу при питании от электросети
   - ✅ Пробуждать компьютер для выполнения задачи

7. Вкладка "Параметры":
   - ✅ Разрешить выполнение задачи по требованию
   - ❌ Останавливать задачу, если она выполняется более: (отключить)
   - Если задача уже выполняется: **Не запускать новый экземпляр**

8. Нажмите "ОК"

Проверьте запуск:

```powershell
# Запустите вручную
schtasks /run /tn "Интеграция Ident-Битрикс24"

# Проверьте статус
schtasks /query /tn "Интеграция Ident-Битрикс24"
```

---

## Мониторинг и обслуживание

### Проверка работы службы

```powershell
# Статус службы
sc query IdentBitrix24Integration

# Или через Task Scheduler
# Смотрите "Последний результат выполнения"
```

### Просмотр логов

```powershell
cd C:\Projects\IDENT\logs

# Последний лог
type integration_log_2026-01-21.txt

# Следить за логом в реальном времени
Get-Content integration_log_2026-01-21.txt -Wait -Tail 50
```

### Веб-интерфейс мониторинга

Откройте в браузере на сервере:
```
http://localhost:8080
```

Там вы увидите:
- Статус синхронизации (Running/Stopped)
- Последняя синхронизация (время)
- Обработано записей (всего)
- Успешных операций (%)
- Текущие ошибки (количество)
- Размер очереди неотправленных данных

### Ручной запуск синхронизации

Если нужно запустить синхронизацию вручную:

```powershell
cd C:\Projects\IDENT

# Разовая синхронизация
python -c "from main import sync_once; sync_once()"
```

### Обновление конфигурации

После изменения `config.ini` перезапустите службу:

```powershell
# Для Windows Service
python install_service.py restart

# Для Task Scheduler
schtasks /end /tn "Интеграция Ident-Битрикс24"
schtasks /run /tn "Интеграция Ident-Битрикс24"
```

### Резервное копирование

Регулярно делайте бэкап:

```powershell
# Создайте бэкап
$date = Get-Date -Format "yyyy-MM-dd_HHmmss"
$backupPath = "C:\Backups\IDENT_$date"
Copy-Item -Path "C:\Projects\IDENT" -Destination $backupPath -Recurse

# Исключите логи и временные файлы
Remove-Item "$backupPath\logs\*" -Recurse -Force
Remove-Item "$backupPath\data\queue.db" -Force
```

---

## Устранение неполадок

### Проблема 1: Не запускается служба

**Симптомы:**
```
Error 1053: The service did not respond to the start or control request in a timely fashion
```

**Решение:**
1. Проверьте логи Windows:
   ```powershell
   eventvwr.msc
   # Журналы Windows → Приложение
   ```

2. Запустите вручную для отладки:
   ```powershell
   python main.py
   # Смотрите ошибки в консоли
   ```

3. Проверьте права доступа:
   ```powershell
   # Служба должна работать от учетной записи с правами на БД
   ```

### Проблема 2: Ошибка подключения к БД

**Симптомы:**
```
Error: [Microsoft][ODBC Driver 17 for SQL Server][SQL Server]Login failed
```

**Решение:**
1. Проверьте учетные данные в `config.ini`
2. Проверьте SQL Server Authentication:
   ```sql
   -- В SSMS выполните
   USE master;
   SELECT name, type_desc, is_disabled
   FROM sys.server_principals
   WHERE name = 'ident_user';
   ```

3. Включите SQL Server Authentication:
   - SSMS → ПКМ на сервер → Свойства
   - Безопасность → Режим проверки подлинности сервера
   - Выберите "Проверка подлинности SQL Server и Windows"

### Проблема 3: Ошибка доступа к Битрикс24 API

**Симптомы:**
```
Error 401: Unauthorized
Error 403: Forbidden
```

**Решение:**
1. Проверьте webhook токен в Битрикс24
2. Убедитесь что webhook не истек
3. Проверьте права доступа webhook (должны быть CRM права)
4. Проверьте URL (не должно быть лишних слэшей)

### Проблема 4: Высокая нагрузка на CPU

**Симптомы:**
- CPU постоянно > 20%
- Медленная работа сервера

**Решение:**
1. Увеличьте интервал синхронизации в `config.ini`:
   ```ini
   [Sync]
   interval_minutes = 5  # Вместо 2
   ```

2. Уменьшите размер пакета:
   ```ini
   batch_size = 25  # Вместо 50
   ```

3. Добавьте паузу между пакетами:
   ```ini
   [Performance]
   batch_pause = 2  # секунды
   ```

### Проблема 5: Переполнение диска логами

**Симптомы:**
- Диск заполнен
- Много старых логов

**Решение:**
1. Уменьшите срок хранения:
   ```ini
   [Logging]
   rotation_days = 7  # Вместо 30
   ```

2. Очистите старые логи вручную:
   ```powershell
   cd C:\Projects\IDENT\logs
   Get-ChildItem -Filter "*.txt" |
       Where-Object {$_.LastWriteTime -lt (Get-Date).AddDays(-30)} |
       Remove-Item
   ```

### Проблема 6: Дублирование записей в Битрикс24

**Симптомы:**
- Одна запись создается несколько раз

**Решение:**
1. Проверьте уникальные идентификаторы
2. Убедитесь что не запущено несколько экземпляров службы:
   ```powershell
   Get-Process python
   # Должен быть только один процесс интеграции
   ```

3. Проверьте логи на повторную обработку одних и тех же ID

---

## Чеклист развертывания

Используйте этот чеклист для проверки:

### Предварительная подготовка
- [ ] Получен доступ к серверному ПК (RDP)
- [ ] Получены учетные данные БД Ident
- [ ] Получен webhook токен Битрикс24
- [ ] Определен ID филиала (1-5)

### Установка ПО
- [ ] Python 3.10+ установлен
- [ ] ODBC Driver 17 for SQL Server установлен
- [ ] Git установлен (опционально)

### Развертывание проекта
- [ ] Проект скопирован на сервер
- [ ] Python зависимости установлены
- [ ] Создан файл config.ini
- [ ] Все параметры заполнены корректно

### Тестирование
- [ ] Подключение к БД Ident работает
- [ ] Извлечение записей работает
- [ ] Webhook Битрикс24 доступен
- [ ] Тестовая отправка в Битрикс24 успешна

### Установка службы
- [ ] Служба Windows установлена
- [ ] Служба запускается автоматически
- [ ] Служба работает корректно

### Мониторинг
- [ ] Веб-интерфейс доступен
- [ ] Логи пишутся корректно
- [ ] Синхронизация выполняется по расписанию

### Документация
- [ ] Создана документация по серверу (IP, учетки)
- [ ] Созданы резервные копии конфигурации
- [ ] Обучены ответственные сотрудники

---

## Контакты поддержки

**При возникновении проблем:**

1. Проверьте логи: `C:\Projects\IDENT\logs\`
2. Проверьте веб-интерфейс: `http://localhost:8080`
3. Обратитесь к этому руководству
4. Свяжитесь с технической поддержкой

**Техническая поддержка:**
- Email: support@example.com
- Telegram: @support_bot
- Телефон: +7 (XXX) XXX-XX-XX

---

*Версия документа: 1.0*
*Дата последнего обновления: 2026-01-21*

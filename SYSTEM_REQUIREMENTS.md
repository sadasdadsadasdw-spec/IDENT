# Системные требования IDENT Integration

## Минимальные требования

### Операционная система
- **Windows 10 (64-bit)** или новее
- **Windows Server 2016** или новее

### Зависимости

#### ⚠️ ОБЯЗАТЕЛЬНО: Visual C++ Redistributable
**Microsoft Visual C++ Redistributable 2015-2022 (x64)**

**Скачать:**
- https://aka.ms/vs/17/release/vc_redist.x64.exe

**Размер:** ~25 MB

**Почему это нужно:**
- Приложение использует Python 3.14, который требует Visual C++ Runtime
- Критические компоненты (pyodbc, SSL, криптография) зависят от UCRT (Universal C Runtime)
- Без этого приложение не запустится!

---

## Типичные ошибки и решения

### ❌ Ошибка: "api-ms-win-crt-runtime-l1-1-0.dll is missing"

**Симптомы:**
```
The program can't start because api-ms-win-crt-runtime-l1-1-0.dll
is missing from your computer. Try reinstalling the program to fix this problem.
```

**Причина:**
Не установлен Visual C++ Redistributable 2015-2022.

**Решение:**
1. Скачайте: https://aka.ms/vs/17/release/vc_redist.x64.exe
2. Запустите установщик с правами администратора
3. Перезапустите приложение

---

### ❌ Ошибка: Множество DLL отсутствуют

**Список недостающих DLL (если нет VC++ Redistributable):**
- `api-ms-win-crt-runtime-l1-1-0.dll`
- `api-ms-win-crt-stdio-l1-1-0.dll`
- `api-ms-win-crt-string-l1-1-0.dll`
- `api-ms-win-crt-heap-l1-1-0.dll`
- `api-ms-win-crt-filesystem-l1-1-0.dll`
- `api-ms-win-crt-time-l1-1-0.dll`
- `api-ms-win-crt-math-l1-1-0.dll`
- `api-ms-win-crt-convert-l1-1-0.dll`
- И другие...

**Решение:**
Установите Visual C++ Redistributable (см. выше).

---

## Проверка зависимостей

### PowerShell скрипт для проверки:

```powershell
# Проверка Visual C++ Redistributable
$VCRedist = Get-ItemProperty "HKLM:\SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64" -ErrorAction SilentlyContinue

if ($VCRedist -and $VCRedist.Installed -eq 1) {
    Write-Host "✓ Visual C++ Redistributable установлен: v$($VCRedist.Version)" -ForegroundColor Green
} else {
    Write-Host "✗ Visual C++ Redistributable НЕ УСТАНОВЛЕН!" -ForegroundColor Red
    Write-Host "  Скачайте: https://aka.ms/vs/17/release/vc_redist.x64.exe" -ForegroundColor Yellow
}
```

---

## Warnings при сборке (для разработчиков)

При сборке PyInstaller вы увидите множество warnings:
```
WARNING: Library not found: could not resolve 'api-ms-win-crt-*.dll'
```

**Это нормально!** Эти DLL:
- Являются API Set Forwarders для Visual C++ Runtime
- Не включаются в EXE (требуют установки на целевой системе)
- Присутствуют на машине сборки (Windows Server 2022)

**Важно:**
- На машине **сборки** (Windows Server 2022) - всё работает ✓
- На машине **развертывания** - требуется Visual C++ Redistributable ⚠️

---

## Автоматическая проверка при установке

Скрипт `install_task_onedir.ps1` автоматически проверяет наличие Visual C++ Redistributable:

```powershell
.\install_task_onedir.ps1
```

Если зависимости отсутствуют, вы увидите предупреждение:
```
WARNING: Visual C++ Redistributable 2015-2022 (x64) not found!

Download: https://aka.ms/vs/17/release/vc_redist.x64.exe

Without it, the application may fail with:
  'api-ms-win-crt-runtime-l1-1-0.dll is missing'

Continue anyway? (y/n)
```

---

## Дополнительные требования

### Сеть
- Доступ к Bitrix24 API (HTTPS)
- Доступ к базе данных IDENT (MS SQL Server)

### Права доступа
- Права администратора для установки Scheduled Task
- Права на чтение базы данных IDENT
- Доступ к webhook Bitrix24

### База данных
- Microsoft SQL Server (любая версия с поддержкой ODBC)
- ODBC драйвер SQL Server (обычно предустановлен в Windows)

---

## Развертывание на чистой системе

### Шаг 1: Установите Visual C++ Redistributable
```powershell
# Скачайте и установите
Invoke-WebRequest -Uri "https://aka.ms/vs/17/release/vc_redist.x64.exe" -OutFile "vc_redist.x64.exe"
Start-Process -FilePath "vc_redist.x64.exe" -ArgumentList "/quiet", "/norestart" -Wait
```

### Шаг 2: Настройте конфигурацию
Отредактируйте `config.yaml` с учетом вашего окружения.

### Шаг 3: Установите задачу
```powershell
.\install_task_onedir.ps1
```

---

## Поддерживаемые платформы

| Платформа | Поддержка | Примечания |
|-----------|-----------|------------|
| Windows 10 (64-bit) | ✅ Да | Требуется VC++ Redistributable |
| Windows 11 (64-bit) | ✅ Да | Требуется VC++ Redistributable |
| Windows Server 2016+ | ✅ Да | Требуется VC++ Redistributable |
| Windows 8/8.1 | ⚠️ Возможно | Не тестировалось, требуется VC++ |
| Windows 7 | ❌ Нет | Не поддерживается |
| Windows 32-bit | ❌ Нет | Только x64 |

---

## Часто задаваемые вопросы

### Q: Можно ли запустить без Visual C++ Redistributable?
**A:** Нет. Приложение использует Python 3.14 и C-расширения, которые жестко зависят от UCRT.

### Q: Почему warnings при сборке?
**A:** PyInstaller не может автоматически включить API Set DLL. Это нормально, они должны быть установлены на целевой системе через VC++ Redistributable.

### Q: Какая версия VC++ Redistributable нужна?
**A:** 2015-2022 (x64). Все версии с 2015 по 2022 совместимы между собой.

### Q: Можно ли включить DLL в EXE?
**A:** Технически возможно, но:
- Нарушает лицензию Microsoft
- Увеличивает размер EXE на ~20 MB
- Не рекомендуется Microsoft

### Q: Приложение работает на машине сборки, но не на другой
**A:** Установите Visual C++ Redistributable на целевой машине.

---

## Контакты

При возникновении проблем с зависимостями:
1. Убедитесь, что установлен Visual C++ Redistributable
2. Проверьте логи приложения
3. Проверьте Event Viewer → Windows Logs → Application

---

*Дата обновления: 2026-01-30*

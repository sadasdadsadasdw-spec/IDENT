-- СКРИПТ ДЛЯ ДИАГНОСТИКИ: Почему система находит 0 записей
-- Выполните этот запрос в SQL Server Management Studio или Azure Data Studio

-- Параметр: Время последней синхронизации (замените на значение из логов)
DECLARE @last_sync_time DATETIME = '2026-01-30 13:36:04.556'

PRINT '========================================='
PRINT 'ДИАГНОСТИКА: Поиск записей для синхронизации'
PRINT '========================================='
PRINT ''
PRINT 'Время последней синхронизации: ' + CONVERT(VARCHAR, @last_sync_time, 121)
PRINT 'Текущее время сервера: ' + CONVERT(VARCHAR, GETDATE(), 121)
PRINT ''

-- 1. Проверяем общее количество записей
PRINT '1. ОБЩАЯ СТАТИСТИКА:'
PRINT '-------------------'
SELECT
    COUNT(*) AS TotalReceptions,
    MIN(DateTimeAdded) AS OldestRecord,
    MAX(DateTimeAdded) AS NewestRecord
FROM Receptions
PRINT ''

-- 2. Записи за последние 24 часа
PRINT '2. ЗАПИСИ ЗА ПОСЛЕДНИЕ 24 ЧАСА:'
PRINT '--------------------------------'
SELECT
    COUNT(*) AS RecordsLast24Hours,
    MIN(DateTimeAdded) AS OldestInLast24h,
    MAX(DateTimeAdded) AS NewestInLast24h
FROM Receptions
WHERE DateTimeAdded >= DATEADD(HOUR, -24, GETDATE())
PRINT ''

-- 3. Записи которые ДОЛЖНЫ попасть в синхронизацию (используем >= как в исправленном коде)
PRINT '3. ЗАПИСИ ДЛЯ СИНХРОНИЗАЦИИ (>= last_sync_time):'
PRINT '-------------------------------------------------'
SELECT
    COUNT(*) AS RecordsToSync,
    MIN(CASE
        WHEN DateTimeAdded >= @last_sync_time THEN DateTimeAdded
        WHEN DateTimeChanged >= @last_sync_time THEN DateTimeChanged
        WHEN PatientAppeared >= @last_sync_time THEN PatientAppeared
        WHEN ReceptionStarted >= @last_sync_time THEN ReceptionStarted
        WHEN ReceptionEnded >= @last_sync_time THEN ReceptionEnded
        WHEN ReceptionCanceled >= @last_sync_time THEN ReceptionCanceled
    END) AS EarliestChangeTime
FROM Receptions
WHERE
    DateTimeAdded >= @last_sync_time
    OR DateTimeChanged >= @last_sync_time
    OR PatientAppeared >= @last_sync_time
    OR ReceptionStarted >= @last_sync_time
    OR ReceptionEnded >= @last_sync_time
    OR ReceptionCanceled >= @last_sync_time
PRINT ''

-- 4. Детальный анализ временных меток
PRINT '4. ДЕТАЛЬНЫЙ АНАЛИЗ ВРЕМЕННЫХ МЕТОК:'
PRINT '-------------------------------------'
SELECT
    COUNT(*) AS RecordCount,
    SUM(CASE WHEN DateTimeAdded >= @last_sync_time THEN 1 ELSE 0 END) AS ByDateTimeAdded,
    SUM(CASE WHEN DateTimeChanged >= @last_sync_time THEN 1 ELSE 0 END) AS ByDateTimeChanged,
    SUM(CASE WHEN PatientAppeared >= @last_sync_time THEN 1 ELSE 0 END) AS ByPatientAppeared,
    SUM(CASE WHEN ReceptionStarted >= @last_sync_time THEN 1 ELSE 0 END) AS ByReceptionStarted,
    SUM(CASE WHEN ReceptionEnded >= @last_sync_time THEN 1 ELSE 0 END) AS ByReceptionEnded,
    SUM(CASE WHEN ReceptionCanceled >= @last_sync_time THEN 1 ELSE 0 END) AS ByReceptionCanceled
FROM Receptions
WHERE
    DateTimeAdded >= @last_sync_time
    OR DateTimeChanged >= @last_sync_time
    OR PatientAppeared >= @last_sync_time
    OR ReceptionStarted >= @last_sync_time
    OR ReceptionEnded >= @last_sync_time
    OR ReceptionCanceled >= @last_sync_time
PRINT ''

-- 5. Последние 5 записей (независимо от времени)
PRINT '5. ПОСЛЕДНИЕ 5 ЗАПИСЕЙ В БД (для проверки):'
PRINT '--------------------------------------------'
SELECT TOP 5
    ID AS ReceptionID,
    PlanStart,
    DateTimeAdded,
    DateTimeChanged,
    PatientAppeared,
    ReceptionStarted,
    ReceptionEnded,
    ReceptionCanceled,
    CASE
        WHEN ReceptionCanceled IS NOT NULL THEN 'Отменен'
        WHEN CheckIssued IS NOT NULL THEN 'Завершен (счет выдан)'
        WHEN ReceptionEnded IS NOT NULL THEN 'Завершен'
        WHEN ReceptionStarted IS NOT NULL THEN 'В процессе'
        WHEN PatientAppeared IS NOT NULL THEN 'Пациент пришел'
        ELSE 'Запланирован'
    END AS Status
FROM Receptions
ORDER BY ID DESC
PRINT ''

-- 6. Проверка: обновляется ли DateTimeChanged при изменении статусов?
PRINT '6. ПРОВЕРКА: DateTimeChanged vs временные метки статусов:'
PRINT '----------------------------------------------------------'
SELECT TOP 10
    ID AS ReceptionID,
    DateTimeAdded,
    DateTimeChanged,
    PatientAppeared,
    ReceptionStarted,
    ReceptionEnded,
    ReceptionCanceled,
    -- Проверяем корректность DateTimeChanged
    CASE
        WHEN DateTimeChanged < ISNULL(PatientAppeared, '1900-01-01')
            OR DateTimeChanged < ISNULL(ReceptionStarted, '1900-01-01')
            OR DateTimeChanged < ISNULL(ReceptionEnded, '1900-01-01')
            OR DateTimeChanged < ISNULL(ReceptionCanceled, '1900-01-01')
        THEN 'НЕ ОБНОВЛЯЕТСЯ!'
        ELSE 'OK'
    END AS DateTimeChangedStatus
FROM Receptions
WHERE
    PatientAppeared IS NOT NULL
    OR ReceptionStarted IS NOT NULL
    OR ReceptionEnded IS NOT NULL
    OR ReceptionCanceled IS NOT NULL
ORDER BY ID DESC
PRINT ''

PRINT '========================================='
PRINT 'ДИАГНОСТИКА ЗАВЕРШЕНА'
PRINT '========================================='
PRINT ''
PRINT 'ИНТЕРПРЕТАЦИЯ РЕЗУЛЬТАТОВ:'
PRINT ''
PRINT 'Если "ЗАПИСИ ДЛЯ СИНХРОНИЗАЦИИ" = 0:'
PRINT '  - В БД нет записей, измененных после last_sync_time'
PRINT '  - Это нормально если не было новых приемов/изменений'
PRINT '  - Попробуйте: создать новую запись или изменить статус существующей'
PRINT ''
PRINT 'Если DateTimeChanged НЕ ОБНОВЛЯЕТСЯ:'
PRINT '  - Значит БД не обновляет это поле при изменении статусов'
PRINT '  - Решение: использовать только временные метки статусов (уже реализовано)'
PRINT '  - Текущий код использует OR для всех временных меток'
PRINT ''
PRINT 'Если есть записи но синхронизация их не видит:'
PRINT '  - Проверьте часовые пояса (сервер БД vs сервер приложения)'
PRINT '  - Проверьте формат времени в логах приложения'
PRINT '  - Убедитесь что используется >= а не > в SQL запросе'

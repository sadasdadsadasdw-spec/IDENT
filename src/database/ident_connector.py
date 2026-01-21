"""
Модуль подключения к БД Ident и извлечения данных
Поддерживает:
- Подключение к SQL Server через ODBC
- Извлечение записей (Receptions)
- Извлечение планов лечения (TreatmentPlans)
- Инкрементальную синхронизацию
"""

import pyodbc
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from contextlib import contextmanager


class IdentConnector:
    """Коннектор к БД Ident"""

    def __init__(
        self,
        server: str,
        database: str,
        username: str,
        password: str,
        port: int = 1433,
        connection_timeout: int = 10,
        query_timeout: int = 30
    ):
        self.server = server
        self.database = database
        self.username = username
        self.password = password
        self.port = port
        self.connection_timeout = connection_timeout
        self.query_timeout = query_timeout

        self.connection_string = (
            f"DRIVER={{ODBC Driver 17 for SQL Server}};"
            f"SERVER={self.server},{self.port};"
            f"DATABASE={self.database};"
            f"UID={self.username};"
            f"PWD={self.password};"
            f"Connection Timeout={self.connection_timeout};"
        )

    @contextmanager
    def get_connection(self):
        """Контекстный менеджер для подключения к БД"""
        conn = None
        try:
            conn = pyodbc.connect(self.connection_string)
            conn.timeout = self.query_timeout
            yield conn
        finally:
            if conn:
                conn.close()

    def test_connection(self) -> bool:
        """Тестирует подключение к БД"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 1")
                cursor.fetchone()
            return True
        except Exception as e:
            raise ConnectionError(f"Не удалось подключиться к БД Ident: {e}")

    def get_receptions(
        self,
        last_sync_time: Optional[datetime] = None,
        batch_size: int = 50,
        initial_days: int = 7
    ) -> List[Dict[str, Any]]:
        """
        Извлекает записи из БД Ident

        Args:
            last_sync_time: Время последней синхронизации (для инкрементальной выборки)
            batch_size: Размер пакета
            initial_days: Глубина начальной синхронизации (дней)

        Returns:
            Список записей
        """
        # Если это первая синхронизация, берем данные за initial_days дней
        if last_sync_time is None:
            last_sync_time = datetime.now() - timedelta(days=initial_days)

        query = """
        SELECT TOP (?)
            -- ID записи
            r.ID AS ReceptionID,

            -- Временные данные записи
            r.DateTimeStartAppointment AS StartTime,
            r.DateTimeEndAppointment AS EndTime,
            r.DateTimeAdded AS CreatedAt,
            r.PatientAppeared AS PatientAppeared,
            r.ReceptionStarted AS ReceptionStarted,
            r.ReceptionEnded AS ReceptionEnded,
            r.ReceptionCanceled AS ReceptionCanceled,
            r.CheckIssued AS CheckIssued,

            -- Данные пациента
            p.ID AS PatientID,
            p.MedCardNumber AS CardNumber,
            p.Surname AS PatientSurname,
            p.Name AS PatientName,
            p.Patronymic AS PatientPatronymic,
            COALESCE(pc1.Value, pc2.Value, pc3.Value) AS PatientPhone,

            -- Данные врача
            d.Surname AS DoctorSurname,
            d.Name AS DoctorName,
            d.Patronymic AS DoctorPatronymic,
            s.Name AS Speciality,

            -- Филиал и кабинет
            COALESCE(oc_order.Name, oc_armchair.Name, 'Не указан') AS Filial,
            a.Name AS Armchair,

            -- Услуги (агрегированные)
            (
                SELECT STRING_AGG(si.Name, ', ') WITHIN GROUP (ORDER BY osr.ID)
                FROM OrderServiceRelation osr
                INNER JOIN ServiceItemPrices sip ON osr.ID_ServicePrices = sip.ID
                INNER JOIN ServiceItems si ON sip.ID_ServiceItems = si.ID
                WHERE osr.ID_Orders = o.ID AND osr.IsDeleted = 0
            ) AS Services,

            -- Сумма
            (
                SELECT ISNULL(SUM(osr.CountService * sip.Price - ISNULL(osr.DiscountSum, 0)), 0)
                FROM OrderServiceRelation osr
                INNER JOIN ServiceItemPrices sip ON osr.ID_ServicePrices = sip.ID
                WHERE osr.ID_Orders = o.ID AND osr.IsDeleted = 0
            ) AS TotalAmount,

            -- Комментарий и причина отмены
            r.Commentt AS Comment,
            r.ReasonCancellation AS CancelReason,

            -- Источник записи
            rs.Name AS ReceptionSource

        FROM Receptions r

        -- Пациент
        INNER JOIN Patients p ON r.ID_Patients = p.ID

        -- Телефоны пациента (приоритет: мобильный, рабочий, домашний)
        LEFT JOIN PatientContacts pc1 ON p.ID = pc1.ID_Patients
            AND pc1.ID_ContactTypes = 1 AND pc1.IsDeleted = 0  -- Мобильный
        LEFT JOIN PatientContacts pc2 ON p.ID = pc2.ID_Patients
            AND pc2.ID_ContactTypes = 2 AND pc2.IsDeleted = 0  -- Рабочий
        LEFT JOIN PatientContacts pc3 ON p.ID = pc3.ID_Patients
            AND pc3.ID_ContactTypes = 3 AND pc3.IsDeleted = 0  -- Домашний

        -- Врач
        INNER JOIN Doctors d ON r.ID_Doctors = d.ID
        INNER JOIN Specialities s ON d.ID_Specialities = s.ID

        -- Кабинет
        LEFT JOIN Armchairs a ON r.ID_Armchairs = a.ID

        -- Филиал через кабинет
        LEFT JOIN OwnCompanies oc_armchair ON a.ID_OwnCompanies = oc_armchair.ID

        -- Заказ
        LEFT JOIN Orders o ON r.ID = o.ID_Receptions

        -- Филиал через заказ
        LEFT JOIN OwnCompanies oc_order ON o.ID_OwnCompanies = oc_order.ID

        -- Источник записи
        LEFT JOIN ReceptionSources rs ON r.ID_ReceptionSources = rs.ID

        WHERE
            -- Только не удаленные записи
            r.IsDeleted = 0
            AND p.IsDeleted = 0

            -- Инкрементальная выборка
            AND (
                r.DateTimeAdded > ?
                OR r.DateTimeChanged > ?
                OR r.PatientAppeared > ?
                OR r.ReceptionStarted > ?
                OR r.ReceptionEnded > ?
                OR r.ReceptionCanceled > ?
            )

        ORDER BY r.DateTimeAdded DESC, r.ID DESC
        """

        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    query,
                    (
                        batch_size,
                        last_sync_time, last_sync_time, last_sync_time,
                        last_sync_time, last_sync_time, last_sync_time
                    )
                )

                columns = [column[0] for column in cursor.description]
                results = []

                for row in cursor.fetchall():
                    results.append(dict(zip(columns, row)))

                return results

        except Exception as e:
            raise RuntimeError(f"Ошибка при извлечении записей из БД Ident: {e}")

    def get_treatment_plans_by_patient_name(
        self,
        patient_full_name: str
    ) -> List[Dict[str, Any]]:
        """
        Извлекает планы лечения пациента по ФИО

        Args:
            patient_full_name: Полное ФИО пациента

        Returns:
            Список планов лечения
        """
        # Разбиваем ФИО
        name_parts = patient_full_name.strip().split()
        surname = name_parts[0] if len(name_parts) > 0 else ""
        name = name_parts[1] if len(name_parts) > 1 else ""
        patronymic = name_parts[2] if len(name_parts) > 2 else ""

        query = """
        SELECT
            -- План лечения
            tp.ID AS PlanID,
            tp.Name AS PlanName,
            tp.DateCreating AS CreatedAt,

            -- Пациент
            p.Surname + ' ' + p.Name + ISNULL(' ' + p.Patronymic, '') AS PatientFullName,

            -- Врач
            d.Surname + ' ' + d.Name + ISNULL(' ' + d.Patronymic, '') AS DoctorFullName,

            -- Этап
            tps.Name AS StageName,
            tps.OrderNumber AS StageOrder,

            -- Элемент плана
            tpi.Name AS ItemName,

            -- Услуга
            si.Name AS ServiceName,
            tpisi.CountTooth AS ToothCount,

            -- Статус
            tpisi.StatusDone AS StatusDone,

            -- Цена и скидка
            sip.Price AS Price,
            tpisi.DiscountSum AS DiscountAmount,
            (tpisi.CountTooth * sip.Price - ISNULL(tpisi.DiscountSum, 0)) AS TotalAmount

        FROM TreatmentPlans tp

        -- Пациент
        INNER JOIN Patients p ON tp.ID_Patients = p.ID

        -- Врач
        INNER JOIN Doctors d ON tp.ID_Doctors = d.ID

        -- Этапы плана
        INNER JOIN TreatmentPlanStages tps ON tp.ID = tps.ID_TreatmentPlans

        -- Элементы этапа
        INNER JOIN TreatmentPlanItems tpi ON tps.ID = tpi.ID_TreatmentPlanStages

        -- Услуги в элементе
        INNER JOIN TreatmentPlanItemServiceItems tpisi ON tpi.ID = tpisi.ID_TreatmentPlanItems

        -- Прайс услуги
        INNER JOIN ServiceItemPrices sip ON tpisi.ID_ServiceItemPrices = sip.ID

        -- Услуга
        INNER JOIN ServiceItems si ON sip.ID_ServiceItems = si.ID

        WHERE
            -- Фильтр по пациенту
            p.Surname = ?
            AND p.Name = ?
            AND (? = '' OR p.Patronymic = ?)

            -- Только не удаленные
            AND tp.IsDeleted = 0
            AND p.IsDeleted = 0
            AND tps.IsDeleted = 0
            AND tpi.IsDeleted = 0
            AND tpisi.IsDeleted = 0

        ORDER BY
            tp.DateCreating DESC,
            tps.OrderNumber,
            tpi.ID,
            tpisi.ID
        """

        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    query,
                    (surname, name, patronymic, patronymic)
                )

                columns = [column[0] for column in cursor.description]
                results = []

                for row in cursor.fetchall():
                    results.append(dict(zip(columns, row)))

                return results

        except Exception as e:
            raise RuntimeError(f"Ошибка при извлечении планов лечения из БД Ident: {e}")

    def get_treatment_plan_by_id(self, plan_id: int) -> List[Dict[str, Any]]:
        """
        Извлекает конкретный план лечения по ID

        Args:
            plan_id: ID плана лечения

        Returns:
            Список записей плана (этапы, элементы, услуги)
        """
        query = """
        SELECT
            -- План лечения
            tp.ID AS PlanID,
            tp.Name AS PlanName,
            tp.DateCreating AS CreatedAt,

            -- Пациент
            p.Surname + ' ' + p.Name + ISNULL(' ' + p.Patronymic, '') AS PatientFullName,

            -- Врач
            d.Surname + ' ' + d.Name + ISNULL(' ' + d.Patronymic, '') AS DoctorFullName,

            -- Этап
            tps.Name AS StageName,
            tps.OrderNumber AS StageOrder,

            -- Элемент плана
            tpi.Name AS ItemName,

            -- Услуга
            si.Name AS ServiceName,
            tpisi.CountTooth AS ToothCount,

            -- Статус
            tpisi.StatusDone AS StatusDone,

            -- Цена и скидка
            sip.Price AS Price,
            tpisi.DiscountSum AS DiscountAmount,
            (tpisi.CountTooth * sip.Price - ISNULL(tpisi.DiscountSum, 0)) AS TotalAmount

        FROM TreatmentPlans tp

        -- Пациент
        INNER JOIN Patients p ON tp.ID_Patients = p.ID

        -- Врач
        INNER JOIN Doctors d ON tp.ID_Doctors = d.ID

        -- Этапы плана
        INNER JOIN TreatmentPlanStages tps ON tp.ID = tps.ID_TreatmentPlans

        -- Элементы этапа
        INNER JOIN TreatmentPlanItems tpi ON tps.ID = tpi.ID_TreatmentPlanStages

        -- Услуги в элементе
        INNER JOIN TreatmentPlanItemServiceItems tpisi ON tpi.ID = tpisi.ID_TreatmentPlanItems

        -- Прайс услуги
        INNER JOIN ServiceItemPrices sip ON tpisi.ID_ServiceItemPrices = sip.ID

        -- Услуга
        INNER JOIN ServiceItems si ON sip.ID_ServiceItems = si.ID

        WHERE
            tp.ID = ?
            AND tp.IsDeleted = 0

        ORDER BY
            tps.OrderNumber,
            tpi.ID,
            tpisi.ID
        """

        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, (plan_id,))

                columns = [column[0] for column in cursor.description]
                results = []

                for row in cursor.fetchall():
                    results.append(dict(zip(columns, row)))

                return results

        except Exception as e:
            raise RuntimeError(f"Ошибка при извлечении плана лечения из БД Ident: {e}")

    def check_plan_exists(self, plan_id: int) -> bool:
        """Проверяет существование плана лечения"""
        query = "SELECT COUNT(*) FROM TreatmentPlans WHERE ID = ? AND IsDeleted = 0"

        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, (plan_id,))
                count = cursor.fetchone()[0]
                return count > 0

        except Exception as e:
            raise RuntimeError(f"Ошибка при проверке существования плана: {e}")

    def get_statistics(self) -> Dict[str, int]:
        """Возвращает статистику БД"""
        queries = {
            'total_receptions': "SELECT COUNT(*) FROM Receptions WHERE IsDeleted = 0",
            'total_patients': "SELECT COUNT(*) FROM Patients WHERE IsDeleted = 0",
            'total_treatment_plans': "SELECT COUNT(*) FROM TreatmentPlans WHERE IsDeleted = 0",
            'receptions_today': """
                SELECT COUNT(*) FROM Receptions
                WHERE CAST(DateTimeStartAppointment AS DATE) = CAST(GETDATE() AS DATE)
                AND IsDeleted = 0
            """,
            'receptions_this_week': """
                SELECT COUNT(*) FROM Receptions
                WHERE DateTimeStartAppointment >= DATEADD(WEEK, DATEDIFF(WEEK, 0, GETDATE()), 0)
                AND IsDeleted = 0
            """
        }

        stats = {}

        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()

                for key, query in queries.items():
                    cursor.execute(query)
                    stats[key] = cursor.fetchone()[0]

                return stats

        except Exception as e:
            raise RuntimeError(f"Ошибка при получении статистики БД: {e}")


if __name__ == "__main__":
    # Тестирование модуля
    from src.config.config_manager import get_config

    try:
        config = get_config("config.example.ini")
        db_config = config.get_database_config()

        connector = IdentConnector(
            server=db_config['server'],
            database=db_config['database'],
            username=db_config['username'],
            password=db_config['password'],
            port=db_config['port'],
            connection_timeout=db_config['connection_timeout'],
            query_timeout=db_config['query_timeout']
        )

        print("Тестирование подключения...")
        if connector.test_connection():
            print("✓ Подключение установлено успешно")

            print("\nПолучение статистики БД...")
            stats = connector.get_statistics()
            for key, value in stats.items():
                print(f"  {key}: {value}")

            print("\nПолучение записей за последние 7 дней...")
            receptions = connector.get_receptions(batch_size=5)
            print(f"  Найдено записей: {len(receptions)}")

            if receptions:
                print("\n  Пример записи:")
                first = receptions[0]
                print(f"    ID: {first['ReceptionID']}")
                print(f"    Пациент: {first['PatientSurname']} {first['PatientName']}")
                print(f"    Врач: {first['DoctorSurname']} {first['DoctorName']}")
                print(f"    Филиал: {first['Filial']}")
                print(f"    Услуги: {first['Services']}")

    except FileNotFoundError as e:
        print(f"Ошибка: {e}")
        print("Создайте файл config.ini на основе config.example.ini")
    except ConnectionError as e:
        print(f"Ошибка подключения: {e}")
    except Exception as e:
        print(f"Неожиданная ошибка: {e}")
        import traceback
        traceback.print_exc()

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
            -- Данные записи
            r.ID AS ReceptionID,
            r.PlanStart AS StartTime,
            r.PlanEnd AS EndTime,

            -- Пациент
            p.Surname + ' ' + p.Name + ISNULL(' ' + p.Patronymic, '') AS PatientFullName,
            p.Surname AS PatientSurname,
            p.Name AS PatientName,
            p.Patronymic AS PatientPatronymic,
            pat.CardNumber AS CardNumber,
            p.MobilePhone AS PatientPhone,

            -- Врач
            ps.Surname + ' ' + ps.Name + ISNULL(' ' + ps.Patronymic, '') AS DoctorFullName,
            ps.Surname AS DoctorSurname,
            ps.Name AS DoctorName,
            ps.Patronymic AS DoctorPatronymic,
            pn.NameProfession AS Speciality,

            -- Филиал и кабинет
            COALESCE(oc_order.Name, oc_armchair.Name, 'Не указан') AS Filial,
            a.NameArmchair AS Armchair,

            -- Агрегированные услуги (через STRING_AGG)
            (
                SELECT STRING_AGG(si.Name, ', ') WITHIN GROUP (ORDER BY si.Name)
                FROM OrderServiceRelation osr_agg
                INNER JOIN ServiceItemPrices sip_agg ON osr_agg.ID_ServicePrices = sip_agg.ID
                INNER JOIN ServiceItems si ON sip_agg.ID_ServiceItems = si.ID
                WHERE osr_agg.ID_Orders = o.ID
            ) AS Services,

            -- Общая сумма заказа
            (
                SELECT ISNULL(SUM(osr_agg.CountService * sip_agg.Price - ISNULL(osr_agg.DiscountSum, 0)), 0)
                FROM OrderServiceRelation osr_agg
                INNER JOIN ServiceItemPrices sip_agg ON osr_agg.ID_ServicePrices = sip_agg.ID
                WHERE osr_agg.ID_Orders = o.ID
            ) AS TotalAmount,

            -- Статус
            CASE
                WHEN r.ReceptionCanceled IS NOT NULL THEN 'Отменен'
                WHEN r.CheckIssued IS NOT NULL THEN 'Завершен (счет выдан)'
                WHEN r.ReceptionEnded IS NOT NULL THEN 'Завершен'
                WHEN r.ReceptionStarted IS NOT NULL THEN 'В процессе'
                WHEN r.PatientAppeared IS NOT NULL THEN 'Пациент пришел'
                ELSE 'Запланирован'
            END AS Status,

            -- Временные метки
            r.PatientAppeared AS PatientAppeared,
            r.ReceptionStarted AS ReceptionStarted,
            r.ReceptionEnded AS ReceptionEnded,
            r.ReceptionCanceled AS ReceptionCanceled,
            r.CheckIssued AS CheckIssued,

            -- Даты заказа
            o.DateTimeOrder AS OrderDate,
            o.DateTimeBillFormed AS BillFormedDate,

            -- Комментарий
            r.Comment AS Comment,

            -- Метки времени для инкрементальной синхронизации
            r.DateTimeAdded AS CreatedAt,
            r.DateTimeChanged AS ChangedAt

        FROM Receptions r
            -- Пациент
            INNER JOIN Patients pat ON r.ID_Patients = pat.ID_Persons
            INNER JOIN Persons p ON pat.ID_Persons = p.ID

            -- Врач
            LEFT JOIN Staffs s ON r.ID_Staffs = s.ID_Persons
            LEFT JOIN Persons ps ON s.ID_Persons = ps.ID
            LEFT JOIN Items i ON s.ID_Persons = i.ID_Staffs
            LEFT JOIN ProfessionNames pn ON i.ID_ProfessionNames = pn.ID

            -- Филиал через кабинет
            LEFT JOIN Armchairs a ON r.ID_Armchairs = a.ID
            LEFT JOIN OwnCompanies oc_armchair ON a.ID_OwnCompanies = oc_armchair.ID

            -- Заказы
            LEFT JOIN Orders o ON r.ID = o.ID_Receptions

            -- Филиал через заказ
            LEFT JOIN OwnCompanies oc_order ON o.ID_OwnCompanies = oc_order.ID

        WHERE
            -- Инкрементальная выборка: записи созданные или измененные после last_sync_time
            (
                r.DateTimeAdded > ?
                OR r.DateTimeChanged > ?
                OR r.PatientAppeared > ?
                OR r.ReceptionStarted > ?
                OR r.ReceptionEnded > ?
                OR r.ReceptionCanceled > ?
            )

        ORDER BY r.PlanStart DESC, r.ID DESC
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
            -- ПЛАН (основная информация)
            tp.ID AS PlanID,
            tp.Name AS PlanName,
            tp.DateTimeCreated AS CreatedAt,
            tp.IsActive AS IsActive,

            -- ПАЦИЕНТ
            p.Surname + ' ' + p.Name + ISNULL(' ' + p.Patronymic, '') AS PatientFullName,
            pat.CardNumber AS CardNumber,

            -- ВРАЧ из плана (исполнитель)
            ps_plan.Surname + ' ' + ps_plan.Name + ISNULL(' ' + ps_plan.Patronymic, '') AS DoctorFullName,
            pn_plan.NameProfession AS DoctorSpeciality,

            -- ЭТАПЫ плана
            tps.ID AS StageID,
            tps.Name AS StageName,
            tps.[Order] AS StageOrder,

            -- ЭЛЕМЕНТЫ плана
            tpe.ID AS ElementID,
            tpe.Name AS ElementName,
            tpe.[Order] AS ElementOrder,

            -- УСЛУГИ
            si.ID AS ServiceID,
            si.Name AS ServiceName,
            sc.Name AS ServiceCategory,
            sf.Name AS ServiceFolder,

            -- ЦЕНЫ и СКИДКИ
            sip.Price AS Price,
            tper.DiscountSum AS DiscountAmount,
            (sip.Price - ISNULL(tper.DiscountSum, 0)) AS TotalAmount,

            -- ЗУБЫ
            tper.TeethLong AS TeethMask,

            -- СТАТУС ВЫПОЛНЕНИЯ (связь с заказами)
            CASE
                WHEN osr.ID IS NOT NULL AND o.DateTimeBillFormed IS NOT NULL THEN 'Выполнено и оплачено'
                WHEN osr.ID IS NOT NULL THEN 'Выполнено'
                ELSE 'Не выполнено'
            END AS Status,

            -- Детали выполнения
            o.ID AS OrderID,
            o.DateTimeOrder AS ExecutionDate,
            r.ID AS ReceptionID,
            r.PlanStart AS ReceptionDate

        FROM TreatmentPlans tp
            -- Пациент
            INNER JOIN Patients pat ON tp.ID_Patients = pat.ID_Persons
            INNER JOIN Persons p ON pat.ID_Persons = p.ID

            -- Врач из плана (исполнитель)
            LEFT JOIN Staffs s_plan ON tp.ID_Staffs = s_plan.ID_Persons
            LEFT JOIN Persons ps_plan ON s_plan.ID_Persons = ps_plan.ID
            LEFT JOIN Items i_plan ON s_plan.ID_Persons = i_plan.ID_Staffs
            LEFT JOIN ProfessionNames pn_plan ON i_plan.ID_ProfessionNames = pn_plan.ID

            -- Элементы плана
            LEFT JOIN TreatmentPlanElementRelations tper ON tp.ID = tper.ID_TreatmentPlans
            LEFT JOIN TreatmentPlanStages tps ON tper.ID_TreatmentPlanStages = tps.ID
            LEFT JOIN TreatmentPlanElements tpe ON tper.ID_TreatmentPlanElements = tpe.ID

            -- Услуги
            LEFT JOIN ServiceItemPrices sip ON tper.ID_ServicePrices = sip.ID
            LEFT JOIN ServiceItems si ON sip.ID_ServiceItems = si.ID
            LEFT JOIN ServiceItemContents sic ON si.ID = sic.ID_ServiceItems
                AND sic.DateTimeTo IS NULL
            LEFT JOIN ServiceFolders sf ON sic.ID_ServiceFoldersParent = sf.ID
            LEFT JOIN ServiceCategories sc ON sf.ID_ServiceCategories = sc.ID

            -- Связь с выполнением (заказы)
            LEFT JOIN OrderServiceRelation osr ON tper.ID = osr.ID_TreatmentPlanElementRelations
            LEFT JOIN Orders o ON osr.ID_Orders = o.ID
            LEFT JOIN Receptions r ON o.ID_Receptions = r.ID

        WHERE
            -- Фильтр по пациенту
            p.Surname = ?
            AND p.Name = ?
            AND (? = '' OR p.Patronymic = ?)

        ORDER BY
            tp.DateTimeCreated DESC,
            tps.[Order],
            tpe.[Order],
            si.Name
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
            -- ПЛАН (основная информация)
            tp.ID AS PlanID,
            tp.Name AS PlanName,
            tp.DateTimeCreated AS CreatedAt,
            tp.IsActive AS IsActive,

            -- ПАЦИЕНТ
            p.Surname + ' ' + p.Name + ISNULL(' ' + p.Patronymic, '') AS PatientFullName,
            pat.CardNumber AS CardNumber,

            -- ВРАЧ из плана (исполнитель)
            ps_plan.Surname + ' ' + ps_plan.Name + ISNULL(' ' + ps_plan.Patronymic, '') AS DoctorFullName,
            pn_plan.NameProfession AS DoctorSpeciality,

            -- ЭТАПЫ плана
            tps.ID AS StageID,
            tps.Name AS StageName,
            tps.[Order] AS StageOrder,

            -- ЭЛЕМЕНТЫ плана
            tpe.ID AS ElementID,
            tpe.Name AS ElementName,
            tpe.[Order] AS ElementOrder,

            -- УСЛУГИ
            si.ID AS ServiceID,
            si.Name AS ServiceName,
            sc.Name AS ServiceCategory,
            sf.Name AS ServiceFolder,

            -- ЦЕНЫ и СКИДКИ
            sip.Price AS Price,
            tper.DiscountSum AS DiscountAmount,
            (sip.Price - ISNULL(tper.DiscountSum, 0)) AS TotalAmount,

            -- ЗУБЫ
            tper.TeethLong AS TeethMask,

            -- СТАТУС ВЫПОЛНЕНИЯ (связь с заказами)
            CASE
                WHEN osr.ID IS NOT NULL AND o.DateTimeBillFormed IS NOT NULL THEN 'Выполнено и оплачено'
                WHEN osr.ID IS NOT NULL THEN 'Выполнено'
                ELSE 'Не выполнено'
            END AS Status,

            -- Детали выполнения
            o.ID AS OrderID,
            o.DateTimeOrder AS ExecutionDate,
            r.ID AS ReceptionID,
            r.PlanStart AS ReceptionDate

        FROM TreatmentPlans tp
            -- Пациент
            INNER JOIN Patients pat ON tp.ID_Patients = pat.ID_Persons
            INNER JOIN Persons p ON pat.ID_Persons = p.ID

            -- Врач из плана (исполнитель)
            LEFT JOIN Staffs s_plan ON tp.ID_Staffs = s_plan.ID_Persons
            LEFT JOIN Persons ps_plan ON s_plan.ID_Persons = ps_plan.ID
            LEFT JOIN Items i_plan ON s_plan.ID_Persons = i_plan.ID_Staffs
            LEFT JOIN ProfessionNames pn_plan ON i_plan.ID_ProfessionNames = pn_plan.ID

            -- Элементы плана
            LEFT JOIN TreatmentPlanElementRelations tper ON tp.ID = tper.ID_TreatmentPlans
            LEFT JOIN TreatmentPlanStages tps ON tper.ID_TreatmentPlanStages = tps.ID
            LEFT JOIN TreatmentPlanElements tpe ON tper.ID_TreatmentPlanElements = tpe.ID

            -- Услуги
            LEFT JOIN ServiceItemPrices sip ON tper.ID_ServicePrices = sip.ID
            LEFT JOIN ServiceItems si ON sip.ID_ServiceItems = si.ID
            LEFT JOIN ServiceItemContents sic ON si.ID = sic.ID_ServiceItems
                AND sic.DateTimeTo IS NULL
            LEFT JOIN ServiceFolders sf ON sic.ID_ServiceFoldersParent = sf.ID
            LEFT JOIN ServiceCategories sc ON sf.ID_ServiceCategories = sc.ID

            -- Связь с выполнением (заказы)
            LEFT JOIN OrderServiceRelation osr ON tper.ID = osr.ID_TreatmentPlanElementRelations
            LEFT JOIN Orders o ON osr.ID_Orders = o.ID
            LEFT JOIN Receptions r ON o.ID_Receptions = r.ID

        WHERE
            tp.ID = ?

        ORDER BY
            tps.[Order],
            tpe.[Order],
            si.Name,
            o.DateTimeOrder
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
        query = "SELECT COUNT(*) FROM TreatmentPlans WHERE ID = ?"

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
            'total_receptions': "SELECT COUNT(*) FROM Receptions",
            'total_patients': "SELECT COUNT(*) FROM Patients",
            'total_treatment_plans': "SELECT COUNT(*) FROM TreatmentPlans",
            'receptions_today': """
                SELECT COUNT(*) FROM Receptions
                WHERE CAST(PlanStart AS DATE) = CAST(GETDATE() AS DATE)
            """,
            'receptions_this_week': """
                SELECT COUNT(*) FROM Receptions
                WHERE PlanStart >= DATEADD(WEEK, DATEDIFF(WEEK, 0, GETDATE()), 0)
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

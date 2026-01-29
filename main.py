"""
Главный модуль интеграции Ident → Bitrix24

Функции:
- Периодическая синхронизация по расписанию
- Обработка очереди неудачных синхронизаций
- Мониторинг и статистика
- Graceful shutdown при Ctrl+C
"""

import sys
import time
import signal
import logging
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

# Добавляем src в PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent))

# Импорты модулей проекта
from src.config.config_manager_v2 import get_config, ConfigValidationError
from src.logger.custom_logger_v2 import get_logger
from src.database.ident_connector_v2 import IdentConnector
from src.bitrix.api_client import Bitrix24Client, Bitrix24Error
from src.transformer.data_transformer import DataTransformer, StageMapper
from src.transformer.treatment_plan_sync_manager import TreatmentPlanSyncManager
from src.queue.queue_manager import PersistentQueue

#  ОПТИМИЗАЦИЯ: Метрики производительности
from src.utils.performance_metrics import Timer, get_metrics

# Глобальный logger (будет инициализирован в main())
logger = None


class SyncOrchestrator:
    """
    Оркестратор синхронизации

    Координирует работу всех компонентов:
    - БД коннектор
    - Трансформер данных
    - API клиент Битрикс24
    - Очередь повторных попыток
    """

    # Константы для безопасности и производительности
    DB_FETCH_BATCH_SIZE = 100      # Размер батча при чтении из БД
    API_BATCH_SIZE = 20            #  BATCH ОПТИМИЗАЦИЯ: Размер батча для API запросов

    def __init__(self, config_path: str = "config.ini"):
        """
        Инициализация оркестратора

        Args:
            config_path: Путь к файлу конфигурации
        """
        logger.info("=" * 80)
        logger.info("Инициализация синхронизации Ident → Bitrix24")
        logger.info("=" * 80)

        # Загружаем конфигурацию
        try:
            self.config = get_config(config_path)
        except ConfigValidationError as e:
            logger.error(f"Ошибка валидации конфигурации:\n{e}")
            raise

        # Получаем настройки
        db_config = self.config.get_database_config()
        b24_config = self.config.get_bitrix24_config()
        sync_config = self.config.get_sync_config()
        queue_config = self.config.get_queue_config()

        self.filial_id = sync_config['filial_id']
        self.batch_size = sync_config['batch_size']
        self.initial_days = sync_config['initial_days']
        self.enable_update_existing = sync_config['enable_update_existing']

        # Инициализация компонентов
        logger.info(f"Филиал: {self.filial_id}")
        logger.info(f"Batch size: {self.batch_size}")

        # 1. Database connector
        logger.info("Инициализация подключения к БД Ident...")
        self.db = IdentConnector(
            server=db_config['server'],
            database=db_config['database'],
            username=db_config['username'],
            password=db_config['password'],
            port=db_config['port'],
            connection_timeout=db_config['connection_timeout'],
            query_timeout=db_config['query_timeout']
        )

        # 2. Bitrix24 client
        logger.info("Инициализация клиента Bitrix24...")
        self.b24 = Bitrix24Client(
            webhook_url=b24_config['webhook_url'],
            request_timeout=b24_config['request_timeout'],
            max_retries=b24_config['max_retries'],
            default_assigned_by_id=b24_config.get('default_assigned_by_id')
        )

        # 3. Data transformer
        logger.info("Инициализация трансформера данных...")
        self.transformer = DataTransformer(filial_id=self.filial_id)

        # 4. Queue manager
        if queue_config['enabled']:
            logger.info("Инициализация очереди повторных попыток...")
            self.queue = PersistentQueue(
                persistence_file=queue_config['persistence_file'],
                max_size=queue_config['max_size'],
                max_retry_attempts=queue_config['max_retry_attempts'],
                retry_interval_minutes=queue_config['retry_interval_minutes']
            )
        else:
            self.queue = None
            logger.warning("Очередь повторных попыток ОТКЛЮЧЕНА")

        # 5. Treatment Plan Sync Manager (оптимизированный)
        logger.info("Инициализация менеджера синхронизации планов лечения...")
        self.treatment_plan_manager = TreatmentPlanSyncManager(
            db_connector=self.db,
            b24_client=self.b24,
            cache_file="treatment_plan_cache.json",
            throttle_minutes=30  # Обновлять не чаще раза в 30 минут
        )

        # Статистика
        self.stats = {
            'total_synced': 0,
            'total_errors': 0,
            'last_sync_time': None,
            'last_sync_records': 0
        }

        # Время последней синхронизации (загружаем из файла)
        self.sync_state_file = Path("sync_state.json")
        self.last_sync_time: Optional[datetime] = self._load_last_sync_time()

        # Флаг остановки
        self.should_stop = False

        logger.info("Инициализация завершена успешно")

    def _load_last_sync_time(self) -> Optional[datetime]:
        """Загружает время последней синхронизации из файла"""
        if not self.sync_state_file.exists():
            logger.info("Файл состояния синхронизации не найден, начинаем с нуля")
            return None

        try:
            with open(self.sync_state_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                last_sync_str = data.get('last_sync_time')
                if last_sync_str:
                    last_sync = datetime.fromisoformat(last_sync_str)
                    logger.info(f"Загружено время последней синхронизации: {last_sync}")
                    return last_sync
        except Exception as e:
            logger.warning(f"Ошибка загрузки состояния синхронизации: {e}")

        return None

    def _save_last_sync_time(self):
        """Сохраняет время последней синхронизации в файл"""
        if not self.last_sync_time:
            return

        try:
            data = {
                'last_sync_time': self.last_sync_time.isoformat(),
                'filial_id': self.filial_id,
                'updated_at': datetime.now().isoformat()
            }

            # Атомарная запись через временный файл
            temp_file = self.sync_state_file.with_suffix('.tmp')
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            temp_file.replace(self.sync_state_file)
            logger.debug(f"Сохранено время последней синхронизации: {self.last_sync_time}")

        except Exception as e:
            logger.error(f"Ошибка сохранения состояния синхронизации: {e}")

    def test_connections(self) -> bool:
        """
        Тестирует все подключения

        Returns:
            True если все подключения работают
        """
        logger.info("\n" + "=" * 80)
        logger.info("Проверка подключений")
        logger.info("=" * 80)

        all_ok = True

        # Тест БД
        try:
            logger.info("1. Тест подключения к БД Ident...")
            self.db.test_connection()
            logger.info("    Подключение к БД OK")
        except Exception as e:
            logger.error(f"   ERROR: Ошибка подключения к БД: {e}")
            all_ok = False

        # Тест Bitrix24
        try:
            logger.info("2. Тест подключения к Bitrix24...")
            self.b24.test_connection()
            logger.info("    Подключение к Bitrix24 OK")
        except Exception as e:
            logger.error(f"   ERROR: Ошибка подключения к Bitrix24: {e}")
            all_ok = False

        if all_ok:
            logger.info("\n Все подключения работают корректно")
        else:
            logger.error("\nERROR: Обнаружены проблемы с подключениями!")

        return all_ok

    @staticmethod
    def _safe_int(value: Any, field_name: str = "ID") -> int:
        """
        Безопасное преобразование в int с валидацией

        Args:
            value: Значение для преобразования
            field_name: Имя поля (для логирования)

        Returns:
            Целое число

        Raises:
            ValueError: Если значение невалидно
        """
        if value is None:
            raise ValueError(f"{field_name} не может быть None")

        try:
            return int(value)
        except (ValueError, TypeError) as e:
            raise ValueError(f"Невалидное значение для {field_name}: {value!r} ({type(value).__name__})")

    def sync_reception_to_bitrix24(self, transformed_data: dict) -> bool:
        """
        Синхронизирует одну запись в Bitrix24

        ЛОГИКА ПОИСКА И ОБНОВЛЕНИЯ:
        1. Ищем сделку по IDENT ID
           - Если найдена и НЕ закрыта → обновляем
           - Если найдена и закрыта (Успешно/Неуспешно) → игнорируем, создаем новую
        2. Ищем контакт по телефону + ФИО → если не найден, создаем
        3. Ищем сделку без IDENT ID для контакта → если найдена, автопривязываем
        4. Если сделки нет → создаем новую

        Args:
            transformed_data: Преобразованные данные

        Returns:
            True если успешно
        """
        unique_id = transformed_data['unique_id']
        contact_data = transformed_data['contact']
        deal_data = transformed_data['deal']

        try:
            phone = contact_data['phone']
            name = contact_data.get('name', '')
            last_name = contact_data.get('last_name', '')
            second_name = contact_data.get('second_name', '')

            # ШАГ 1: Поиск сделки по IDENT ID
            existing_deal = self.b24.find_deal_by_ident_id(unique_id)
            should_create_new = False

            if existing_deal:
                # Сделка с IDENT ID найдена
                deal_id = self._safe_int(existing_deal['ID'], 'DealID')
                current_stage = existing_deal.get('STAGE_ID')

                # Если сделка в финальной стадии - игнорируем её
                if StageMapper.is_stage_final(current_stage):
                    logger.info(
                        f"IGNORE: Сделка {deal_id} с IDENT ID {unique_id} уже закрыта "
                        f"(стадия '{current_stage}'). Игнорируем и создаем новую сделку."
                    )
                    should_create_new = True
                else:
                    # Обновляем существующую открытую сделку
                    if StageMapper.is_stage_protected(current_stage):
                        # Защищенная стадия - не меняем stage
                        logger.info(
                            f"PROTECTED: Сделка {deal_id} в защищенной стадии '{current_stage}'. "
                            f"Обновляем данные без изменения стадии."
                        )
                        deal_data_copy = deal_data.copy()
                        deal_data_copy.pop('stage_id', None)
                        if self.enable_update_existing:
                            self.b24.update_deal(deal_id, deal_data_copy)
                    else:
                        # Обычное обновление
                        if self.enable_update_existing:
                            logger.info(f"Обновляем сделку {deal_id} для {unique_id}")
                            self.b24.update_deal(deal_id, deal_data)
                        else:
                            # Обновляем только стадию
                            logger.info(f"Обновляем стадию сделки {deal_id}")
                            stage_only = {'stage_id': deal_data.get('stage_id')}
                            if stage_only['stage_id']:
                                self.b24.update_deal(deal_id, stage_only)
            else:
                should_create_new = True

            # Если сделка не найдена или закрыта - создаем новую
            if should_create_new:
                # ШАГ 2: Сделка с IDENT ID не найдена - ищем контакт
                contact_id = self._find_or_create_contact(phone, name, last_name, second_name, contact_data)

                # ШАГ 3: Ищем сделку без IDENT ID для этого контакта
                deals_without_ident = self.b24.find_deals_by_contact_without_ident_id(
                    contact_id,
                    exclude_final=True
                )

                if deals_without_ident:
                    # Нашли сделку без IDENT ID - привязываем
                    deal = deals_without_ident[0]  # Берем самую свежую (уже отсортировано)
                    deal_id = self._safe_int(deal['ID'], 'DealID')

                    if len(deals_without_ident) > 1:
                        logger.warning(
                            f"МНОЖЕСТВЕННЫЕ СДЕЛКИ: Найдено {len(deals_without_ident)} открытых сделок "
                            f"без IDENT ID для контакта {contact_id}. "
                            f"Привязываем к самой свежей: {deal_id}. "
                            f"Остальные: {[d['ID'] for d in deals_without_ident[1:]]}"
                        )

                    logger.info(
                        f"АВТОПРИВЯЗКА: Сделка {deal_id} привязана к {unique_id} "
                        f"(дата создания: {deal.get('DATE_CREATE')})"
                    )

                    # Обновляем сделку, добавляя IDENT ID и все данные
                    deal_data['uf_crm_ident_id'] = unique_id
                    self.b24.update_deal(deal_id, deal_data)
                else:
                    # ШАГ 4: Сделки без IDENT ID не найдено - создаем новую
                    logger.info(f"Создаем новую сделку для контакта {contact_id}")
                    deal_id = self.b24.create_deal(deal_data, contact_id)
                    logger.info(f"Создана сделка {deal_id} для {unique_id}")

            # Синхронизируем план лечения (оптимизированно с throttling и кешем)
            card_number = deal_data.get('UF_CRM_1769083581481') or deal_data.get('uf_crm_card_number')
            if card_number and deal_id:
                try:
                    # Используем оптимизированный менеджер (с кешем и throttling)
                    self.treatment_plan_manager.sync_plan_for_deal(deal_id, card_number, force=False)
                except Exception as e:
                    logger.warning(f"Ошибка синхронизации плана лечения для сделки {deal_id}: {e}")
                    # Не прерываем синхронизацию из-за ошибки плана лечения
            elif deal_id and not card_number:
                logger.debug(
                    f"WARNING: CardNumber отсутствует для сделки {deal_id} ({unique_id}), "
                    f"план лечения не синхронизирован"
                )

            return True

        except Bitrix24Error as e:
            logger.error(f"Ошибка API Bitrix24 для {unique_id}: {e}")
            raise
        except Exception as e:
            logger.error(f"Неожиданная ошибка синхронизации {unique_id}: {e}", exc_info=True)
            raise

    def _find_or_create_contact(
        self,
        phone: str,
        name: str,
        last_name: str,
        second_name: str,
        contact_data: dict
    ) -> int:
        """
        Ищет или создает контакт с поддержкой семей (несколько контактов с одним телефоном)

        Args:
            phone: Номер телефона
            name: Имя
            last_name: Фамилия
            second_name: Отчество
            contact_data: Полные данные контакта

        Returns:
            ID контакта
        """
        # Ищем контакт по ТОЧНОМУ совпадению ФИО + телефон
        existing_contact = self.b24.find_contact_by_phone_and_name(
            phone, name, last_name, second_name
        )

        if existing_contact:
            # Найден контакт с точным совпадением ФИО
            contact_id = self._safe_int(existing_contact['ID'], 'ContactID')
            logger.info(f"Найден контакт {contact_id}: {last_name} {name} {second_name or ''}")
            return contact_id

        # ТОЧНОГО совпадения нет - проверяем есть ли другие контакты с этим телефоном (семья)
        contacts_by_phone = self.b24.find_all_contacts_by_phone(phone)

        if contacts_by_phone:
            # Есть контакты с этим телефоном, но с другими ФИО (члены семьи)
            logger.info(
                f"Найдено {len(contacts_by_phone)} контактов с телефоном {phone}. "
                f"Создаем новый контакт для {last_name} {name} {second_name or ''} (член семьи)."
            )
        else:
            # Вообще нет контактов с этим телефоном
            logger.info(f"Создаем первый контакт для телефона {phone}")

        # Создаем новый контакт
        contact_id = self.b24.create_contact(contact_data)
        return contact_id

    def sync_treatment_plan(self, deal_id: int, card_number: str, force: bool = False):
        """
        Синхронизирует план лечения для сделки (оптимизированная версия)

        УСТАРЕЛО: Используйте treatment_plan_manager.sync_plan_for_deal()

        Args:
            deal_id: ID сделки в Bitrix24
            card_number: Номер карты пациента
            force: Принудительное обновление (игнорировать кеш и throttling)
        """
        return self.treatment_plan_manager.sync_plan_for_deal(deal_id, card_number, force)

    def sync_once(self):
        """
         BATCH ОПТИМИЗАЦИЯ: Stream Processing + Batch API запросы
        """
        logger.info("\n" + "=" * 80)
        logger.info(f"Начало синхронизации: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("=" * 80)

        sync_start = time.time()
        synced_count = 0
        error_count = 0
        total_received = 0
        transform_success = 0
        transform_failed = 0

        try:
            logger.info(f"Получение записей из БД (batch_size={self.batch_size}, API batch={self.API_BATCH_SIZE})...")

            # Используем генератор для экономии памяти
            receptions_iter = self.db.get_receptions_iter(
                last_sync_time=self.last_sync_time,
                batch_size=self.batch_size,
                initial_days=self.initial_days,
                fetch_size=self.DB_FETCH_BATCH_SIZE
            )

            #  BATCH: Накапливаем записи в буфер для batch обработки
            batch_buffer = []

            for reception in receptions_iter:
                total_received += 1

                # Трансформируем запись
                with Timer("transform_reception"):
                    try:
                        transformed = self.transformer.transform_single(reception)
                        if not transformed:
                            transform_failed += 1
                            continue

                        transform_success += 1
                        batch_buffer.append(transformed)

                    except Exception as e:
                        transform_failed += 1
                        logger.warning(f"Ошибка трансформации записи #{total_received}: {e}")
                        continue

                # Когда батч заполнен - обрабатываем
                if len(batch_buffer) >= self.API_BATCH_SIZE:
                    with Timer("process_batch"):
                        batch_synced, batch_errors = self._process_batch(batch_buffer)
                        synced_count += batch_synced
                        error_count += batch_errors
                    batch_buffer = []

                # Логируем прогресс каждые 100 записей
                if total_received % 100 == 0:
                    logger.info(f"Обработано: {total_received}, синхронизировано: {synced_count}")

            # Обрабатываем остаток батча
            if batch_buffer:
                with Timer("process_batch"):
                    batch_synced, batch_errors = self._process_batch(batch_buffer)
                    synced_count += batch_synced
                    error_count += batch_errors

            logger.info(f"Всего получено из БД: {total_received} записей")

            if total_received == 0:
                logger.info("Новых записей нет")
                return

            # Обрабатываем очередь повторных попыток
            if self.queue:
                self._process_retry_queue()
                # Периодически чистим старые элементы очереди
                self.queue.cleanup_old_items()

            # Обновляем время последней синхронизации
            self.last_sync_time = datetime.now()
            self._save_last_sync_time()  # Сохраняем в файл

            # Статистика
            sync_duration = time.time() - sync_start

            self.stats['total_synced'] += synced_count
            self.stats['total_errors'] += error_count
            self.stats['last_sync_time'] = self.last_sync_time
            self.stats['last_sync_records'] = total_received

            logger.info("\n" + "=" * 80)
            logger.info("Результаты синхронизации")
            logger.info("=" * 80)
            logger.info(f"Получено из БД:       {total_received}")
            logger.info(f"Трансформировано:     {transform_success}")
            logger.info(f"Ошибок трансформации: {transform_failed}")
            logger.info(f"Синхронизировано:     {synced_count}")
            logger.info(f"Ошибок синхронизации: {error_count}")
            logger.info(f"Время выполнения:     {sync_duration:.2f}с")
            if total_received > 0:
                logger.info(f"Скорость:             {total_received / sync_duration:.1f} записей/сек")
            logger.info("=" * 80)

            #  ОПТИМИЗАЦИЯ: Вывод метрик производительности
            get_metrics().log_summary()

        except Exception as e:
            logger.error(f"Критическая ошибка синхронизации: {e}", exc_info=True)

    def _process_batch(self, batch: List[Dict[str, Any]]) -> tuple[int, int]:
        """
        BATCH ОПТИМИЗАЦИЯ: Обрабатывает батч записей с предварительным поиском

        Ускорение достигается за счет:
        - Batch поиск контактов (1 запрос вместо N)
        - Batch поиск лидов (1 запрос вместо N)
        - Batch поиск сделок (1 запрос вместо N)
        - Затем последовательная обработка каждой записи

        Args:
            batch: Список трансформированных записей

        Returns:
            Кортеж (synced_count, error_count)
        """
        if not batch:
            return 0, 0

        logger.debug(f"Обработка батча из {len(batch)} записей...")

        synced_count = 0
        error_count = 0

        # 1. Собираем телефоны и ident_id для batch поиска
        phones = list(set(t['contact']['phone'] for t in batch))
        ident_ids = [t['unique_id'] for t in batch]

        # 2. Делаем batch поиск (3 запроса вместо N*3)
        logger.debug(f"Batch поиск: {len(phones)} телефонов, {len(ident_ids)} сделок")

        with Timer("batch_find_contacts"):
            contacts_map = self.b24.batch_find_contacts_by_phones(phones)

        with Timer("batch_find_leads"):
            leads_map = self.b24.batch_find_leads_by_phones(phones)

        with Timer("batch_find_deals"):
            deals_map = self.b24.batch_find_deals_by_ident_ids(ident_ids)

        logger.debug(
            f"Batch результаты: контактов {sum(1 for c in contacts_map.values() if c)}/{len(phones)}, "
            f"лидов {sum(1 for l in leads_map.values() if l)}/{len(phones)}, "
            f"сделок {sum(1 for d in deals_map.values() if d)}/{len(ident_ids)}"
        )

        # 3. Обрабатываем каждую запись (используем существующую логику)
        # Batch поиск уже сократил запросы с 3N до 3, остальные операции
        # (создание/обновление) выполняются последовательно
        for transformed in batch:
            unique_id = transformed['unique_id']

            try:
                # Вызываем существующий метод синхронизации
                # Он сам обработает всю сложную логику (финальные стадии, создание/обновление)
                with Timer("sync_to_bitrix24"):
                    success = self.sync_reception_to_bitrix24(transformed)

                if success:
                    synced_count += 1

                    # Удаляем из очереди если был там
                    if self.queue:
                        self.queue.mark_completed(unique_id)

            except Exception as e:
                error_count += 1
                logger.warning(f"Ошибка синхронизации {unique_id}: {e}")

                # Добавляем в очередь повторных попыток
                if self.queue:
                    self.queue.add(unique_id, transformed)

        logger.debug(f"Батч обработан: синхронизировано {synced_count}, ошибок {error_count}")
        return synced_count, error_count

    def _process_retry_queue(self):
        """Обрабатывает очередь повторных попыток"""
        if not self.queue:
            return

        logger.info("\nОбработка очереди повторных попыток...")

        retry_count = 0
        max_retries_per_cycle = 10  # Лимит на один цикл

        while retry_count < max_retries_per_cycle:
            item = self.queue.get_next_for_processing()

            if not item:
                break

            retry_count += 1
            unique_id = item.unique_id

            try:
                logger.info(
                    f"Повторная попытка {item.retry_count + 1}/{self.queue.max_retry_attempts} "
                    f"для {unique_id}"
                )

                success = self.sync_reception_to_bitrix24(item.data)

                if success:
                    self.queue.mark_completed(unique_id)
                    logger.info(f" {unique_id} успешно обработан из очереди")
                else:
                    self.queue.mark_failed(unique_id, "Sync returned False")
                    logger.warning(f"WARNING: {unique_id} не синхронизирован (returned False)")

            except Exception as e:
                error_msg = str(e)
                self.queue.mark_failed(unique_id, error_msg)
                logger.warning(f"ERROR: {unique_id} не обработан: {error_msg}")

        if retry_count > 0:
            logger.info(f"Обработано из очереди: {retry_count}")

        # Статистика очереди
        stats = self.queue.get_statistics()
        logger.info(
            f"Очередь: всего={stats['total']}, pending={stats['pending']}, "
            f"failed={stats['failed']}, completed={stats['completed']}"
        )

    def run_scheduled(self, interval_minutes: int = 2):
        """
        Запускает синхронизацию по расписанию

        Args:
            interval_minutes: Интервал синхронизации (минуты)
        """
        logger.info("=" * 80)
        logger.info(f"Запуск синхронизации по расписанию (каждые {interval_minutes} мин)")
        logger.info("Для остановки нажмите Ctrl+C")
        logger.info("=" * 80)

        interval_seconds = interval_minutes * 60

        while not self.should_stop:
            try:
                self.sync_once()
            except Exception as e:
                logger.error(f"Ошибка во время синхронизации: {e}", exc_info=True)

            if self.should_stop:
                break

            # Ждем до следующей синхронизации
            for _ in range(interval_seconds):
                if self.should_stop:
                    break
                time.sleep(1)

    def cleanup(self):
        """Очистка ресурсов"""
        logger.info("\nЗавершение работы...")

        if self.db:
            self.db.close()
            logger.info("Закрыто подключение к БД")

        if self.queue:
            self.queue.cleanup_old_items()
            logger.info("Очищена очередь от старых элементов")

        if hasattr(self, 'treatment_plan_manager'):
            # Очищаем старые записи из кеша планов лечения
            self.treatment_plan_manager.cleanup_cache(max_age_days=90)

            # Выводим статистику
            tp_stats = self.treatment_plan_manager.get_statistics()
            logger.info(
                f"Статистика планов лечения: "
                f"проверок={tp_stats['total_checks']}, "
                f"обновлено={tp_stats['updated']}, "
                f"из кеша={tp_stats['cache_hits']}, "
                f"throttled={tp_stats['throttled']}, "
                f"ошибок={tp_stats['errors']}"
            )

        logger.info("Очистка завершена")

    def stop(self):
        """Останавливает синхронизацию"""
        logger.info("\nПолучен сигнал остановки...")
        self.should_stop = True


def signal_handler(signum, frame):
    """Обработчик сигналов (Ctrl+C)"""
    global orchestrator
    if orchestrator:
        orchestrator.stop()


# Глобальная переменная для signal handler
orchestrator = None


def main():
    """Точка входа"""
    global orchestrator, logger

    try:
        # Инициализация логгера
        from src.config.config_manager_v2 import ConfigManager

        # Загружаем конфигурацию для логгера
        try:
            temp_config = ConfigManager("config.ini")
            log_config = temp_config.get_logging_config()
        except Exception:
            # Если конфиг не найден - используем дефолтные настройки
            log_config = {
                'level': 'INFO',
                'log_dir': 'logs',
                'rotation_days': 30,
                'mask_personal_data': True
            }

        # Инициализируем логгер
        logger = get_logger(
            name='ident_integration',
            log_dir=log_config['log_dir'],
            level=log_config['level'],
            rotation_days=log_config['rotation_days'],
            mask_personal_data=log_config['mask_personal_data']
        )

        logger.info("=" * 80)
        logger.info("ЗАПУСК ИНТЕГРАЦИИ IDENT → BITRIX24")
        logger.info("=" * 80)

        # Создаем оркестратор
        orchestrator = SyncOrchestrator("config.ini")

        # Настраиваем обработчик сигналов
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        # Тестируем подключения
        if not orchestrator.test_connections():
            logger.error("Проверка подключений не пройдена. Завершение работы.")
            sys.exit(1)

        # Получаем интервал синхронизации
        sync_config = orchestrator.config.get_sync_config()
        interval_minutes = sync_config['interval_minutes']

        # Запускаем по расписанию
        orchestrator.run_scheduled(interval_minutes=interval_minutes)

    except KeyboardInterrupt:
        if logger:
            logger.info("\nПрервано пользователем (Ctrl+C)")
        else:
            print("\nПрервано пользователем (Ctrl+C)")

    except ConfigValidationError as e:
        if logger:
            logger.error(f"\nERROR: Ошибка конфигурации:\n{e}")
        else:
            print(f"\nERROR: Ошибка конфигурации:\n{e}")
        sys.exit(1)

    except Exception as e:
        if logger:
            logger.error(f"\nERROR: Критическая ошибка: {e}", exc_info=True)
        else:
            print(f"\nERROR: Критическая ошибка: {e}")
            import traceback
            traceback.print_exc()
        sys.exit(1)

    finally:
        if orchestrator:
            orchestrator.cleanup()

        if logger:
            logger.info("\n" + "=" * 80)
            logger.info("ИНТЕГРАЦИЯ ОСТАНОВЛЕНА")
            logger.info("=" * 80)


if __name__ == "__main__":
    main()

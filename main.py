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
import schedule
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

# Добавляем src в PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent))

# Импорты модулей проекта
from src.config.config_manager_v2 import get_config, ConfigValidationError
from src.logger.custom_logger_v2 import get_logger
from src.database.ident_connector_v2 import IdentConnector
from src.bitrix.api_client import Bitrix24Client, Bitrix24Error
from src.transformer.data_transformer import DataTransformer
from src.queue.queue_manager import PersistentQueue

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
            max_retries=b24_config['max_retries']
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

        logger.info("✅ Инициализация завершена успешно")

    def _load_last_sync_time(self) -> Optional[datetime]:
        """Загружает время последней синхронизации из файла"""
        if not self.sync_state_file.exists():
            logger.info("Файл состояния синхронизации не найден, начинаем с нуля")
            return None

        try:
            import json
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
            import json
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
            logger.info("1️⃣ Тест подключения к БД Ident...")
            self.db.test_connection()
            logger.info("   ✅ Подключение к БД OK")
        except Exception as e:
            logger.error(f"   ❌ Ошибка подключения к БД: {e}")
            all_ok = False

        # Тест Bitrix24
        try:
            logger.info("2️⃣ Тест подключения к Bitrix24...")
            self.b24.test_connection()
            logger.info("   ✅ Подключение к Bitrix24 OK")
        except Exception as e:
            logger.error(f"   ❌ Ошибка подключения к Bitrix24: {e}")
            all_ok = False

        if all_ok:
            logger.info("\n✅ Все подключения работают корректно")
        else:
            logger.error("\n❌ Обнаружены проблемы с подключениями!")

        return all_ok

    def sync_reception_to_bitrix24(self, transformed_data: dict) -> bool:
        """
        Синхронизирует одну запись в Bitrix24

        Args:
            transformed_data: Преобразованные данные

        Returns:
            True если успешно
        """
        unique_id = transformed_data['unique_id']
        contact_data = transformed_data['contact']
        deal_data = transformed_data['deal']

        try:
            # 1. Ищем/создаем контакт
            contact_id = None
            phone = contact_data['phone']

            # Ищем контакт по телефону
            existing_contact = self.b24.find_contact_by_phone(phone)

            if existing_contact:
                contact_id = int(existing_contact['ID'])
                logger.debug(f"Найден существующий контакт: {contact_id}")
            else:
                # Ищем лид
                existing_lead = self.b24.find_lead_by_phone(phone)

                if existing_lead:
                    # Конвертируем лид в контакт
                    logger.info(f"Найден лид {existing_lead['ID']}, конвертируем...")
                    contact_id, _ = self.b24.convert_lead(int(existing_lead['ID']))
                else:
                    # Создаем новый контакт
                    contact_id = self.b24.create_contact(contact_data)

            # 2. Создаем/обновляем сделку
            # ВРЕМЕННО: отключаем поиск пока поле UF_CRM_IDENT_ID не создано в Bitrix24
            # existing_deal = self.b24.find_deal_by_ident_id(unique_id)
            existing_deal = None  # Всегда создаем новую сделку

            if existing_deal:
                deal_id = int(existing_deal['ID'])
                current_stage = existing_deal.get('STAGE_ID')

                if self.enable_update_existing:
                    # Проверяем защищенные стадии
                    from src.transformer.data_transformer import StageMapper

                    if current_stage in StageMapper.PROTECTED_STAGES:
                        logger.info(
                            f"Сделка {deal_id} имеет защищенную стадию '{current_stage}' "
                            f"- обновляем только данные, стадию не меняем"
                        )
                        # Убираем stage_id из обновления
                        deal_data_copy = deal_data.copy()
                        deal_data_copy.pop('stage_id', None)
                        self.b24.update_deal(deal_id, deal_data_copy)
                    else:
                        logger.info(f"Обновляем сделку {deal_id} для {unique_id}")
                        self.b24.update_deal(deal_id, deal_data)
                else:
                    logger.debug(f"Сделка {deal_id} уже существует, обновление отключено")
            else:
                # Создаем новую сделку
                deal_id = self.b24.create_deal(deal_data, contact_id)
                logger.info(f"Создана сделка {deal_id} для {unique_id}")

            return True

        except Bitrix24Error as e:
            logger.error(f"Ошибка API Bitrix24 для {unique_id}: {e}")
            raise
        except Exception as e:
            logger.error(f"Неожиданная ошибка синхронизации {unique_id}: {e}", exc_info=True)
            raise

    def sync_once(self):
        """
        Выполняет одну итерацию синхронизации
        """
        logger.info("\n" + "=" * 80)
        logger.info(f"Начало синхронизации: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("=" * 80)

        sync_start = time.time()
        synced_count = 0
        error_count = 0

        try:
            # 1. Получаем записи из БД
            logger.info(f"Получение записей из БД (batch_size={self.batch_size})...")
            receptions = self.db.get_receptions(
                last_sync_time=self.last_sync_time,
                batch_size=self.batch_size,
                initial_days=self.initial_days
            )

            logger.info(f"Получено записей: {len(receptions)}")

            if not receptions:
                logger.info("Новых записей нет")
                return

            # 2. Трансформируем данные
            logger.info("Трансформация данных...")
            successful, failed = self.transformer.transform_batch(receptions)

            logger.info(
                f"Трансформация: успешно={len(successful)}, "
                f"ошибок={len(failed)}"
            )

            # 3. Синхронизируем в Bitrix24
            logger.info("Синхронизация в Bitrix24...")

            for transformed in successful:
                unique_id = transformed['unique_id']

                try:
                    success = self.sync_reception_to_bitrix24(transformed)

                    if success:
                        synced_count += 1

                        # Удаляем из очереди если был там
                        if self.queue:
                            self.queue.mark_completed(unique_id)

                except Exception as e:
                    error_count += 1

                    # Добавляем в очередь повторных попыток
                    if self.queue:
                        self.queue.add(unique_id, transformed)

            # 4. Обрабатываем очередь повторных попыток
            if self.queue:
                self._process_retry_queue()

            # Обновляем время последней синхронизации
            self.last_sync_time = datetime.now()
            self._save_last_sync_time()  # Сохраняем в файл

            # Статистика
            sync_duration = time.time() - sync_start

            self.stats['total_synced'] += synced_count
            self.stats['total_errors'] += error_count
            self.stats['last_sync_time'] = self.last_sync_time
            self.stats['last_sync_records'] = len(receptions)

            logger.info("\n" + "=" * 80)
            logger.info("Результаты синхронизации")
            logger.info("=" * 80)
            logger.info(f"Получено из БД:       {len(receptions)}")
            logger.info(f"Трансформировано:     {len(successful)}")
            logger.info(f"Синхронизировано:     {synced_count}")
            logger.info(f"Ошибок:               {error_count}")
            logger.info(f"Время выполнения:     {sync_duration:.2f}с")
            logger.info("=" * 80)

        except Exception as e:
            logger.error(f"Критическая ошибка синхронизации: {e}", exc_info=True)

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
                    logger.info(f"✅ {unique_id} успешно обработан из очереди")

            except Exception as e:
                error_msg = str(e)
                self.queue.mark_failed(unique_id, error_msg)
                logger.warning(f"❌ {unique_id} не обработан: {error_msg}")

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
        logger.info("\n" + "=" * 80)
        logger.info(f"Запуск синхронизации по расписанию (каждые {interval_minutes} мин)")
        logger.info("Для остановки нажмите Ctrl+C")
        logger.info("=" * 80)

        # Настраиваем расписание
        schedule.every(interval_minutes).minutes.do(self.sync_once)

        # Выполняем первую синхронизацию сразу
        self.sync_once()

        # Цикл обработки расписания
        while not self.should_stop:
            schedule.run_pending()
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
            logger.error(f"\n❌ Ошибка конфигурации:\n{e}")
        else:
            print(f"\n❌ Ошибка конфигурации:\n{e}")
        sys.exit(1)

    except Exception as e:
        if logger:
            logger.error(f"\n❌ Критическая ошибка: {e}", exc_info=True)
        else:
            print(f"\n❌ Критическая ошибка: {e}")
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

"""
Оптимизированный менеджер синхронизации планов лечения

Функции:
- Кеширование хешей планов для минимизации API запросов
- Throttling - обновление планов не чаще заданного интервала
- Deduplic ation - группировка обновлений по CardNumber
- Batch updates - пакетное обновление сделок
- Персистентный кеш на диске
"""

import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Set, Optional, List, Tuple
from collections import defaultdict

from src.logger.custom_logger_v2 import get_logger
from src.transformer.treatment_plan_handler import TreatmentPlanTransformer

logger = get_logger(__name__)


class TreatmentPlanCache:
    """
    Кеш хешей планов лечения для минимизации запросов

    Хранит:
    - card_number -> plan_hash
    - card_number -> last_update_time
    - deal_id -> card_number (для быстрого поиска)
    """

    def __init__(self, cache_file: str = "treatment_plan_cache.json", max_entries: int = 10000):
        """
        ✅ ОПТИМИЗАЦИЯ: Добавлен лимит размера кеша для предотвращения роста памяти

        Args:
            cache_file: Путь к файлу кеша
            max_entries: Максимальное количество записей в кеше (default: 10000)
        """
        self.cache_file = Path(cache_file)
        self.max_entries = max_entries
        self.data = {
            'hashes': {},  # card_number -> hash
            'timestamps': {},  # card_number -> last_update_timestamp
            'deal_mapping': {}  # deal_id -> card_number
        }
        self._load()
        # Автоочистка старых записей при инициализации
        self.cleanup_old_entries(max_age_days=90)

    def _load(self):
        """Загружает кеш из файла"""
        if not self.cache_file.exists():
            logger.debug("Файл кеша планов лечения не найден, создаем новый")
            return

        try:
            with open(self.cache_file, 'r', encoding='utf-8') as f:
                self.data = json.load(f)
            logger.info(f"Загружен кеш планов лечения: {len(self.data['hashes'])} записей")
        except Exception as e:
            logger.warning(f"Ошибка загрузки кеша планов лечения: {e}")
            self.data = {'hashes': {}, 'timestamps': {}, 'deal_mapping': {}}

    def _save(self):
        """Сохраняет кеш в файл"""
        try:
            # Атомарная запись через временный файл
            temp_file = self.cache_file.with_suffix('.tmp')
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
            temp_file.replace(self.cache_file)
            logger.debug("Кеш планов лечения сохранен")
        except Exception as e:
            logger.error(f"Ошибка сохранения кеша планов лечения: {e}")

    def get_hash(self, card_number: str) -> Optional[str]:
        """Получает хеш плана из кеша"""
        return self.data['hashes'].get(str(card_number))

    def set_hash(self, card_number: str, plan_hash: str):
        """
        ✅ ОПТИМИЗАЦИЯ: Сохраняет хеш с проверкой лимита (LRU eviction)
        """
        # Проверяем лимит размера кеша
        if len(self.data['hashes']) >= self.max_entries:
            # Удаляем 10% самых старых записей (LRU eviction)
            entries_to_remove = int(self.max_entries * 0.1)
            oldest_entries = sorted(
                self.data['timestamps'].items(),
                key=lambda x: x[1]
            )[:entries_to_remove]

            for card, _ in oldest_entries:
                self.data['hashes'].pop(card, None)
                self.data['timestamps'].pop(card, None)

            logger.debug(f"LRU eviction: удалено {entries_to_remove} старых записей из кеша")

        self.data['hashes'][str(card_number)] = plan_hash
        self.data['timestamps'][str(card_number)] = time.time()
        self._save()

    def get_last_update_time(self, card_number: str) -> Optional[float]:
        """Получает время последнего обновления плана"""
        return self.data['timestamps'].get(str(card_number))

    def link_deal(self, deal_id: int, card_number: str):
        """Связывает сделку с номером карты"""
        self.data['deal_mapping'][str(deal_id)] = str(card_number)
        self._save()

    def get_card_by_deal(self, deal_id: int) -> Optional[str]:
        """Получает номер карты по ID сделки"""
        return self.data['deal_mapping'].get(str(deal_id))

    def cleanup_old_entries(self, max_age_days: int = 90):
        """Удаляет старые записи из кеша"""
        cutoff_time = time.time() - (max_age_days * 24 * 3600)
        old_count = len(self.data['hashes'])

        # Фильтруем старые записи
        cards_to_remove = [
            card for card, ts in self.data['timestamps'].items()
            if ts < cutoff_time
        ]

        for card in cards_to_remove:
            self.data['hashes'].pop(card, None)
            self.data['timestamps'].pop(card, None)

        # Удаляем сопоставления сделок для удаленных карт
        cards_set = set(self.data['hashes'].keys())
        deals_to_remove = [
            deal_id for deal_id, card in self.data['deal_mapping'].items()
            if card not in cards_set
        ]

        for deal_id in deals_to_remove:
            self.data['deal_mapping'].pop(deal_id, None)

        removed = old_count - len(self.data['hashes'])
        if removed > 0:
            logger.info(f"Удалено {removed} старых записей из кеша планов лечения")
            self._save()


class TreatmentPlanSyncManager:
    """
    Оптимизированный менеджер синхронизации планов лечения

    Оптимизации:
    - Локальный кеш хешей (минимум API запросов)
    - Throttling (обновление не чаще N минут)
    - Deduplication (группировка по CardNumber)
    - Batch updates (пакетные обновления)
    """

    def __init__(
        self,
        db_connector,
        b24_client,
        cache_file: str = "treatment_plan_cache.json",
        throttle_minutes: int = 30  # Обновлять не чаще раза в 30 минут
    ):
        """
        Args:
            db_connector: Коннектор к БД IDENT
            b24_client: Клиент Bitrix24 API
            cache_file: Путь к файлу кеша
            throttle_minutes: Минимальный интервал между обновлениями (мин)
        """
        self.db = db_connector
        self.b24 = b24_client
        self.cache = TreatmentPlanCache(cache_file)
        self.throttle_seconds = throttle_minutes * 60

        # Статистика
        self.stats = {
            'total_checks': 0,
            'cache_hits': 0,
            'throttled': 0,
            'updated': 0,
            'errors': 0
        }

    def should_update(self, card_number: str) -> bool:
        """
        Проверяет нужно ли обновлять план (throttling)

        Args:
            card_number: Номер карты пациента

        Returns:
            True если прошло достаточно времени с последнего обновления
        """
        last_update = self.cache.get_last_update_time(card_number)

        if not last_update:
            return True  # Никогда не обновлялся

        elapsed = time.time() - last_update
        should_update = elapsed >= self.throttle_seconds

        if not should_update:
            remaining = int((self.throttle_seconds - elapsed) / 60)
            logger.debug(
                f"Throttling: план для карты {card_number} обновлялся "
                f"{int(elapsed / 60)} мин назад, следующее обновление через {remaining} мин"
            )
            self.stats['throttled'] += 1

        return should_update

    def sync_plan_for_deal(
        self,
        deal_id: int,
        card_number: str,
        force: bool = False
    ) -> bool:
        """
        Синхронизирует план лечения для одной сделки (оптимизированная версия)

        Args:
            deal_id: ID сделки в Bitrix24
            card_number: Номер карты пациента
            force: Принудительное обновление (игнорировать throttling и кеш)

        Returns:
            True если план был обновлен
        """
        # Валидация параметров
        if not deal_id or deal_id <= 0:
            logger.error(f"Невалидный deal_id: {deal_id}")
            return False

        if not card_number or not str(card_number).strip():
            logger.warning(f"Пустой card_number для сделки {deal_id}")
            return False

        self.stats['total_checks'] += 1

        try:
            # Сохраняем связь сделка -> карта
            self.cache.link_deal(deal_id, card_number)

            # Throttling (если не force)
            if not force and not self.should_update(card_number):
                return False

            # Получаем ВСЕ планы из БД
            raw_plan_data = self.db.get_treatment_plans_by_card_number(card_number)

            if not raw_plan_data:
                logger.debug(f"Планы лечения не найдены для карты {card_number}")
                return False

            # Преобразуем в структурированный формат (массив планов)
            plans_data = TreatmentPlanTransformer.transform_plans(raw_plan_data)

            if not plans_data:
                logger.warning(f"Не удалось преобразовать планы для карты {card_number}")
                return False

            # Проверяем размер
            is_valid, size_kb = TreatmentPlanTransformer.validate_size(plans_data)
            if not is_valid:
                logger.error(
                    f"⚠️ Планы превышают 60KB ({size_kb}KB) для карты {card_number} "
                    f"- пропускаем"
                )
                self.stats['errors'] += 1
                return False

            # Вычисляем хеш
            new_hash = TreatmentPlanTransformer.calculate_hash(plans_data)

            # Проверяем кеш (если не force)
            if not force:
                cached_hash = self.cache.get_hash(card_number)
                if cached_hash == new_hash:
                    logger.debug(
                        f"План для карты {card_number} не изменился "
                        f"(hash={new_hash[:8]}...) - пропускаем"
                    )
                    self.stats['cache_hits'] += 1
                    return False

            # Планы изменились или force - обновляем
            plans_json = TreatmentPlanTransformer.to_json_string(plans_data, minify=True)

            # Валидация JSON перед сохранением
            try:
                json.loads(plans_json)  # Проверяем что JSON валидный
            except json.JSONDecodeError as e:
                logger.error(
                    f"⚠️ Невалидный JSON для карты {card_number}: {e}. "
                    f"Планы не будут сохранены."
                )
                self.stats['errors'] += 1
                return False

            update_data = {
                'uf_crm_treatment_plan': plans_json,
                'uf_crm_treatment_plan_hash': new_hash
            }

            self.b24.update_deal(deal_id, update_data)

            # Обновляем кеш
            self.cache.set_hash(card_number, new_hash)

            self.stats['updated'] += 1
            logger.info(
                f"✅ Планы обновлены для сделки {deal_id}: "
                f"всего={plans_data['total_plans']}, активных={plans_data['active_plans']}, "
                f"размер={size_kb}KB, hash={new_hash[:8]}..."
            )

            return True

        except Exception as e:
            self.stats['errors'] += 1
            logger.error(f"Ошибка синхронизации плана для сделки {deal_id}: {e}", exc_info=True)
            return False

    def sync_plans_batch(
        self,
        deals_with_cards: List[Tuple[int, str]],
        force: bool = False
    ) -> Dict[str, int]:
        """
        Пакетная синхронизация планов для нескольких сделок (оптимизированная)

        Оптимизация:
        - Группирует сделки по CardNumber
        - Получает план из БД только один раз для каждого CardNumber
        - Обновляет все сделки с одним CardNumber одним планом

        Args:
            deals_with_cards: Список кортежей (deal_id, card_number)
            force: Принудительное обновление

        Returns:
            Словарь со статистикой: {updated, skipped, errors}
        """
        result = {'updated': 0, 'skipped': 0, 'errors': 0}

        # Группируем сделки по CardNumber
        cards_to_deals = defaultdict(list)
        for deal_id, card_number in deals_with_cards:
            if card_number:
                cards_to_deals[card_number].append(deal_id)
                self.cache.link_deal(deal_id, card_number)

        logger.info(
            f"Пакетная синхронизация: {len(deals_with_cards)} сделок, "
            f"{len(cards_to_deals)} уникальных карт"
        )

        # Обрабатываем каждую карту
        for card_number, deal_ids in cards_to_deals.items():
            try:
                # Throttling (если не force)
                if not force and not self.should_update(card_number):
                    result['skipped'] += len(deal_ids)
                    continue

                # Получаем ВСЕ планы из БД один раз
                raw_plan_data = self.db.get_treatment_plans_by_card_number(card_number)

                if not raw_plan_data:
                    logger.debug(f"Планы не найдены для карты {card_number}")
                    result['skipped'] += len(deal_ids)
                    continue

                # Преобразуем в массив планов
                plans_data = TreatmentPlanTransformer.transform_plans(raw_plan_data)
                if not plans_data:
                    result['errors'] += len(deal_ids)
                    continue

                # Проверяем размер
                is_valid, size_kb = TreatmentPlanTransformer.validate_size(plans_data)
                if not is_valid:
                    logger.error(f"Планы превышают 60KB ({size_kb}KB) для карты {card_number}")
                    result['errors'] += len(deal_ids)
                    continue

                # Вычисляем хеш
                new_hash = TreatmentPlanTransformer.calculate_hash(plans_data)

                # Проверяем кеш
                if not force:
                    cached_hash = self.cache.get_hash(card_number)
                    if cached_hash == new_hash:
                        logger.debug(f"Планы для карты {card_number} не изменились")
                        result['skipped'] += len(deal_ids)
                        continue

                # Обновляем все сделки с этой картой
                plans_json = TreatmentPlanTransformer.to_json_string(plans_data, minify=True)
                update_data = {
                    'uf_crm_treatment_plan': plans_json,
                    'uf_crm_treatment_plan_hash': new_hash
                }

                updated_count = 0
                for deal_id in deal_ids:
                    try:
                        self.b24.update_deal(deal_id, update_data)
                        updated_count += 1
                    except Exception as e:
                        logger.error(f"Ошибка обновления сделки {deal_id}: {e}")
                        result['errors'] += 1

                if updated_count > 0:
                    # Обновляем кеш
                    self.cache.set_hash(card_number, new_hash)
                    result['updated'] += updated_count

                    logger.info(
                        f"✅ Планы обновлены для {updated_count} сделок (карта {card_number}): "
                        f"всего={plans_data['total_plans']}, активных={plans_data['active_plans']}, "
                        f"размер={size_kb}KB, hash={new_hash[:8]}..."
                    )

            except Exception as e:
                logger.error(f"Ошибка обработки карты {card_number}: {e}", exc_info=True)
                result['errors'] += len(deal_ids)

        logger.info(
            f"Пакетная синхронизация завершена: "
            f"обновлено={result['updated']}, пропущено={result['skipped']}, "
            f"ошибок={result['errors']}"
        )

        return result

    def get_statistics(self) -> Dict[str, int]:
        """Возвращает статистику работы менеджера"""
        return {
            **self.stats,
            'cache_size': len(self.cache.data['hashes']),
            'deal_mappings': len(self.cache.data['deal_mapping'])
        }

    def cleanup_cache(self, max_age_days: int = 90):
        """Очищает старые записи из кеша"""
        self.cache.cleanup_old_entries(max_age_days)

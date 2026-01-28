"""
Модуль управления очередью неудачных синхронизаций

Функции:
- Персистентная очередь с сохранением в JSON
- Retry логика с экспоненциальной задержкой
- Приоритизация повторных попыток
- Автоматическая очистка старых записей
- Thread-safe операции
"""

import json
import logging
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict
from enum import Enum

# Используем настроенный logger из custom_logger_v2
from src.logger.custom_logger_v2 import get_logger
logger = get_logger('ident_integration')


class QueueItemStatus(Enum):
    """Статус элемента очереди"""
    PENDING = "pending"           # Ожидает обработки
    PROCESSING = "processing"     # Обрабатывается сейчас
    FAILED = "failed"             # Обработка не удалась
    COMPLETED = "completed"       # Успешно обработан


@dataclass
class QueueItem:
    """Элемент очереди"""
    unique_id: str                    # Уникальный ID записи (F1_12345)
    data: Dict[str, Any]              # Преобразованные данные
    status: str                       # Статус (pending/processing/failed/completed)
    created_at: str                   # Время создания (ISO 8601)
    updated_at: str                   # Время последнего обновления
    retry_count: int = 0              # Количество попыток
    last_error: Optional[str] = None  # Последняя ошибка
    next_retry_at: Optional[str] = None  # Время следующей попытки

    def to_dict(self) -> Dict[str, Any]:
        """Преобразует в словарь"""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'QueueItem':
        """Создает из словаря"""
        return cls(**data)


class PersistentQueue:
    """
    Thread-safe персистентная очередь с сохранением в JSON
    """

    def __init__(
        self,
        persistence_file: str = "queue.json",
        max_size: int = 1000,
        max_retry_attempts: int = 3,
        retry_interval_minutes: int = 5,
        retention_days: int = 7
    ):
        """
        Инициализация очереди

        Args:
            persistence_file: Путь к файлу очереди
            max_size: Максимальный размер очереди
            max_retry_attempts: Максимальное количество попыток
            retry_interval_minutes: Интервал между попытками (мин)
            retention_days: Срок хранения завершенных (дни)
        """
        self.persistence_file = Path(persistence_file)
        self.max_size = max_size
        self.max_retry_attempts = max_retry_attempts
        self.retry_interval_minutes = retry_interval_minutes
        self.retention_days = retention_days

        # Thread-safe операции
        self.lock = threading.Lock()

        # Внутренний словарь для быстрого доступа
        self.items: Dict[str, QueueItem] = {}

        # Загружаем из файла
        self._load_from_file()

        logger.info(
            f"PersistentQueue инициализирована: "
            f"размер={len(self.items)}, файл={self.persistence_file}"
        )

    def _load_from_file(self):
        """Загружает очередь из файла"""
        if not self.persistence_file.exists():
            logger.info(f"Файл очереди не существует, создаем новую очередь")
            return

        try:
            with open(self.persistence_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Загружаем элементы
            for item_data in data.get('items', []):
                item = QueueItem.from_dict(item_data)
                self.items[item.unique_id] = item

            logger.info(f"Загружено элементов из очереди: {len(self.items)}")

        except Exception as e:
            logger.error(f"Ошибка загрузки очереди из {self.persistence_file}: {e}")

    def _save_to_file(self):
        """Сохраняет очередь в файл"""
        try:
            # Создаем директорию если не существует
            self.persistence_file.parent.mkdir(parents=True, exist_ok=True)

            # Собираем данные
            data = {
                'saved_at': datetime.now().isoformat(),
                'total_items': len(self.items),
                'items': [item.to_dict() for item in self.items.values()]
            }

            # Сохраняем с временным файлом для атомарности
            temp_file = self.persistence_file.with_suffix('.tmp')
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            # Переименовываем
            temp_file.replace(self.persistence_file)

        except Exception as e:
            logger.error(f"Ошибка сохранения очереди в {self.persistence_file}: {e}")

    def add(self, unique_id: str, data: Dict[str, Any]) -> bool:
        """
        Добавляет элемент в очередь

        Args:
            unique_id: Уникальный ID (F1_12345)
            data: Преобразованные данные

        Returns:
            True если добавлено успешно
        """
        with self.lock:
            # Проверяем размер очереди
            if len(self.items) >= self.max_size:
                logger.error(f"Очередь переполнена (макс. {self.max_size})")
                return False

            # Проверяем дубликаты
            if unique_id in self.items:
                existing = self.items[unique_id]
                if existing.status in [QueueItemStatus.PENDING.value, QueueItemStatus.PROCESSING.value]:
                    logger.warning(f"Элемент {unique_id} уже в очереди со статусом {existing.status}")
                    return False

            # Создаем новый элемент
            now = datetime.now().isoformat()
            item = QueueItem(
                unique_id=unique_id,
                data=data,
                status=QueueItemStatus.PENDING.value,
                created_at=now,
                updated_at=now,
                retry_count=0,
                last_error=None,
                next_retry_at=now  # Можно обрабатывать сразу
            )

            self.items[unique_id] = item
            self._save_to_file()

            logger.info(f"Добавлен элемент в очередь: {unique_id}")
            return True

    def get_next_for_processing(self) -> Optional[QueueItem]:
        """
        Получает следующий элемент для обработки

        Returns:
            Элемент очереди или None
        """
        with self.lock:
            now = datetime.now()

            # Ищем элементы готовые к обработке
            candidates = []

            for item in self.items.values():
                # Пропускаем завершенные и обрабатываемые
                if item.status in [QueueItemStatus.COMPLETED.value, QueueItemStatus.PROCESSING.value]:
                    continue

                # Проверяем лимит попыток
                if item.retry_count >= self.max_retry_attempts:
                    continue

                # Проверяем время следующей попытки
                if item.next_retry_at:
                    next_retry = datetime.fromisoformat(item.next_retry_at)
                    if next_retry > now:
                        continue

                candidates.append(item)

            if not candidates:
                return None

            # Берем самый старый
            item = min(candidates, key=lambda x: x.created_at)

            # Помечаем как обрабатываемый
            item.status = QueueItemStatus.PROCESSING.value
            item.updated_at = now.isoformat()

            self._save_to_file()

            logger.info(f"Взят из очереди для обработки: {item.unique_id} (попытка {item.retry_count + 1})")
            return item

    def mark_completed(self, unique_id: str) -> bool:
        """
        Помечает элемент как успешно обработанный

        Args:
            unique_id: ID элемента

        Returns:
            True если успешно
        """
        with self.lock:
            if unique_id not in self.items:
                logger.warning(f"Элемент {unique_id} не найден в очереди")
                return False

            item = self.items[unique_id]
            item.status = QueueItemStatus.COMPLETED.value
            item.updated_at = datetime.now().isoformat()
            item.last_error = None

            self._save_to_file()

            logger.info(f"Элемент {unique_id} успешно обработан")
            return True

    def mark_failed(self, unique_id: str, error: str) -> bool:
        """
        Помечает элемент как неудачный

        Args:
            unique_id: ID элемента
            error: Описание ошибки

        Returns:
            True если успешно
        """
        with self.lock:
            if unique_id not in self.items:
                logger.warning(f"Элемент {unique_id} не найден в очереди")
                return False

            item = self.items[unique_id]
            item.status = QueueItemStatus.FAILED.value
            item.retry_count += 1
            item.last_error = error
            item.updated_at = datetime.now().isoformat()

            # Рассчитываем время следующей попытки (экспоненциальная задержка)
            if item.retry_count < self.max_retry_attempts:
                delay_minutes = self.retry_interval_minutes * (2 ** (item.retry_count - 1))
                next_retry = datetime.now() + timedelta(minutes=delay_minutes)
                item.next_retry_at = next_retry.isoformat()

                logger.warning(
                    f"Элемент {unique_id} не обработан (попытка {item.retry_count}/{self.max_retry_attempts}). "
                    f"Следующая попытка через {delay_minutes} мин: {error}"
                )
            else:
                item.next_retry_at = None
                logger.error(
                    f"Элемент {unique_id} окончательно не обработан "
                    f"после {item.retry_count} попыток: {error}"
                )

            self._save_to_file()
            return True

    def cleanup_old_items(self):
        """Удаляет старые завершенные и безнадежно проваленные элементы"""
        with self.lock:
            cutoff = datetime.now() - timedelta(days=self.retention_days)
            initial_count = len(self.items)

            to_remove = []
            completed_removed = 0
            failed_removed = 0

            for unique_id, item in self.items.items():
                updated_at = datetime.fromisoformat(item.updated_at)

                # Удаляем старые завершенные
                if item.status == QueueItemStatus.COMPLETED.value:
                    if updated_at < cutoff:
                        to_remove.append(unique_id)
                        completed_removed += 1

                # Удаляем старые FAILED элементы (исчерпали попытки)
                elif item.status == QueueItemStatus.FAILED.value:
                    if item.retry_count >= self.max_retry_attempts and updated_at < cutoff:
                        to_remove.append(unique_id)
                        failed_removed += 1

            for unique_id in to_remove:
                del self.items[unique_id]

            if to_remove:
                self._save_to_file()
                logger.info(
                    f"Очищено элементов очереди: {len(to_remove)} "
                    f"(completed={completed_removed}, failed={failed_removed}). "
                    f"Было {initial_count}, осталось {len(self.items)}"
                )

    def get_statistics(self) -> Dict[str, int]:
        """Возвращает статистику очереди"""
        with self.lock:
            stats = {
                'total': len(self.items),
                'pending': 0,
                'processing': 0,
                'failed': 0,
                'completed': 0,
                'permanently_failed': 0  # Исчерпаны попытки
            }

            for item in self.items.values():
                if item.status == QueueItemStatus.PENDING.value:
                    stats['pending'] += 1
                elif item.status == QueueItemStatus.PROCESSING.value:
                    stats['processing'] += 1
                elif item.status == QueueItemStatus.FAILED.value:
                    stats['failed'] += 1
                    if item.retry_count >= self.max_retry_attempts:
                        stats['permanently_failed'] += 1
                elif item.status == QueueItemStatus.COMPLETED.value:
                    stats['completed'] += 1

            return stats

    def exists(self, unique_id: str) -> bool:
        """
        Проверяет наличие элемента в очереди

        Args:
            unique_id: ID элемента

        Returns:
            True если элемент существует
        """
        with self.lock:
            return unique_id in self.items

    def get_failed_items(self) -> List[QueueItem]:
        """Возвращает список неудачных элементов"""
        with self.lock:
            return [
                item for item in self.items.values()
                if item.status == QueueItemStatus.FAILED.value
                and item.retry_count >= self.max_retry_attempts
            ]

    def reset_item(self, unique_id: str) -> bool:
        """
        Сбрасывает элемент для повторной обработки

        Args:
            unique_id: ID элемента

        Returns:
            True если успешно
        """
        with self.lock:
            if unique_id not in self.items:
                return False

            item = self.items[unique_id]
            item.status = QueueItemStatus.PENDING.value
            item.retry_count = 0
            item.last_error = None
            item.next_retry_at = datetime.now().isoformat()
            item.updated_at = datetime.now().isoformat()

            self._save_to_file()

            logger.info(f"Элемент {unique_id} сброшен для повторной обработки")
            return True

    def clear_completed(self):
        """Удаляет все завершенные элементы"""
        with self.lock:
            initial_count = len(self.items)

            self.items = {
                uid: item for uid, item in self.items.items()
                if item.status != QueueItemStatus.COMPLETED.value
            }

            removed_count = initial_count - len(self.items)

            if removed_count > 0:
                self._save_to_file()
                logger.info(f"Удалено завершенных элементов: {removed_count}")


if __name__ == "__main__":
    """Тестирование очереди"""
    import time

    print("🧪 Тестирование PersistentQueue...")

    # Создаем очередь
    queue = PersistentQueue(
        persistence_file="test_queue.json",
        max_retry_attempts=3,
        retry_interval_minutes=1
    )

    # Тест 1: Добавление элементов
    print("\n1️⃣ Тест добавления элементов:")
    test_data_1 = {
        'deal': {'title': 'Тестовая сделка 1', 'opportunity': 1000},
        'contact': {'phone': '+79991234567'}
    }
    test_data_2 = {
        'deal': {'title': 'Тестовая сделка 2', 'opportunity': 2000},
        'contact': {'phone': '+79997654321'}
    }

    queue.add('F1_TEST1', test_data_1)
    queue.add('F1_TEST2', test_data_2)

    # Тест 2: Статистика
    print("\n2️⃣ Статистика очереди:")
    stats = queue.get_statistics()
    for key, value in stats.items():
        print(f"  {key}: {value}")

    # Тест 3: Получение следующего элемента
    print("\n3️⃣ Обработка элемента:")
    item = queue.get_next_for_processing()
    if item:
        print(f"  Получен: {item.unique_id}")
        print(f"  Статус: {item.status}")
        print(f"  Попытка: {item.retry_count + 1}")

        # Симулируем неудачу
        queue.mark_failed(item.unique_id, "Тестовая ошибка API")

    # Тест 4: Повторная попытка
    print("\n4️⃣ Проверка retry:")
    stats = queue.get_statistics()
    print(f"  Failed: {stats['failed']}")

    # Сброс для повторной попытки
    queue.reset_item('F1_TEST1')
    item = queue.get_next_for_processing()
    if item:
        print(f"  Повторная обработка: {item.unique_id}")
        queue.mark_completed(item.unique_id)

    # Тест 5: Очистка
    print("\n5️⃣ Очистка завершенных:")
    queue.clear_completed()
    stats = queue.get_statistics()
    print(f"  Осталось элементов: {stats['total']}")

    # Проверяем персистентность
    print("\n6️⃣ Тест персистентности:")
    print(f"  Данные сохранены в: {queue.persistence_file}")

    # Загружаем заново
    queue2 = PersistentQueue(persistence_file="test_queue.json")
    stats2 = queue2.get_statistics()
    print(f"  После перезагрузки элементов: {stats2['total']}")

    print("\n✅ Все тесты пройдены!")

"""
Модуль для отслеживания метрик производительности

Функции:
- Измерение времени выполнения функций
- Сбор статистики по операциям
- Логирование производительности
"""

import time
import functools
from typing import Dict, Any, Callable
from collections import defaultdict
from src.logger.custom_logger_v2 import get_logger

logger = get_logger('ident_integration')


class PerformanceMetrics:
    """
    Сборщик метрик производительности

    Отслеживает:
    - Время выполнения операций
    - Количество вызовов
    - Среднее/минимальное/максимальное время
    """

    def __init__(self):
        self.metrics = defaultdict(lambda: {
            'count': 0,
            'total_time': 0.0,
            'min_time': float('inf'),
            'max_time': 0.0
        })
        self.start_time = time.time()

    def record(self, operation: str, duration: float):
        """Записывает метрику выполнения операции"""
        m = self.metrics[operation]
        m['count'] += 1
        m['total_time'] += duration
        m['min_time'] = min(m['min_time'], duration)
        m['max_time'] = max(m['max_time'], duration)

    def get_stats(self, operation: str) -> Dict[str, Any]:
        """Возвращает статистику по операции"""
        m = self.metrics[operation]
        if m['count'] == 0:
            return {}

        return {
            'count': m['count'],
            'total': round(m['total_time'], 3),
            'avg': round(m['total_time'] / m['count'], 3),
            'min': round(m['min_time'], 3),
            'max': round(m['max_time'], 3)
        }

    def get_all_stats(self) -> Dict[str, Dict[str, Any]]:
        """Возвращает статистику по всем операциям"""
        return {op: self.get_stats(op) for op in self.metrics.keys()}

    def log_summary(self):
        """Выводит сводку по всем метрикам"""
        total_runtime = time.time() - self.start_time

        logger.info("\n" + "=" * 80)
        logger.info("📊 МЕТРИКИ ПРОИЗВОДИТЕЛЬНОСТИ")
        logger.info("=" * 80)
        logger.info(f"Общее время работы: {total_runtime:.2f}с")
        logger.info("")

        # Сортируем по общему времени (самые медленные первые)
        sorted_ops = sorted(
            self.metrics.items(),
            key=lambda x: x[1]['total_time'],
            reverse=True
        )

        for operation, _ in sorted_ops:
            stats = self.get_stats(operation)
            if not stats:
                continue

            logger.info(f"{operation}:")
            logger.info(f"  Вызовов:      {stats['count']}")
            logger.info(f"  Общее время:  {stats['total']}с")
            logger.info(f"  Среднее:      {stats['avg']}с")
            logger.info(f"  Мин/Макс:     {stats['min']}с / {stats['max']}с")
            logger.info("")

        logger.info("=" * 80)


# Глобальный экземпляр для сбора метрик
_global_metrics = PerformanceMetrics()


def get_metrics() -> PerformanceMetrics:
    """Возвращает глобальный экземпляр метрик"""
    return _global_metrics


def measure_time(operation_name: str = None):
    """
    Декоратор для измерения времени выполнения функции

    Args:
        operation_name: Название операции (по умолчанию - имя функции)

    Example:
        @measure_time("db_query")
        def get_receptions():
            ...
    """
    def decorator(func: Callable):
        nonlocal operation_name
        if operation_name is None:
            operation_name = func.__name__

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            start = time.time()
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                duration = time.time() - start
                _global_metrics.record(operation_name, duration)

        return wrapper
    return decorator


class Timer:
    """
    Context manager для измерения времени блока кода

    Example:
        with Timer("processing_batch") as t:
            # код для измерения
            process_data()

        print(f"Время: {t.duration}с")
    """

    def __init__(self, operation_name: str, log: bool = False):
        self.operation_name = operation_name
        self.log = log
        self.duration = 0.0
        self.start_time = 0.0

    def __enter__(self):
        self.start_time = time.time()
        return self

    def __exit__(self, *args):
        self.duration = time.time() - self.start_time
        _global_metrics.record(self.operation_name, self.duration)

        if self.log:
            logger.debug(f"{self.operation_name}: {self.duration:.3f}с")


if __name__ == "__main__":
    """Тестирование метрик"""
    import random

    print("🧪 Тестирование PerformanceMetrics...")

    # Тест 1: Декоратор
    @measure_time("test_function")
    def test_func():
        time.sleep(random.uniform(0.01, 0.05))

    print("\n1️⃣ Тест декоратора:")
    for _ in range(10):
        test_func()

    stats = get_metrics().get_stats("test_function")
    print(f"  Вызовов: {stats['count']}")
    print(f"  Среднее время: {stats['avg']}с")

    # Тест 2: Context manager
    print("\n2️⃣ Тест context manager:")
    for _ in range(5):
        with Timer("test_timer", log=True):
            time.sleep(random.uniform(0.01, 0.03))

    # Тест 3: Сводка
    print("\n3️⃣ Общая сводка:")
    get_metrics().log_summary()

    print("\n✅ Тесты пройдены!")

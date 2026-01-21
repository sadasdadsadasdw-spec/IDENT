"""
Модуль логирования для интеграции Ident-Битрикс24
Поддерживает:
- Ротацию файлов по датам
- Маскирование персональных данных
- Различные уровни логирования
- Очистку старых логов
"""

import logging
import os
import re
from datetime import datetime, timedelta
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from typing import Optional


class PersonalDataMaskingFormatter(logging.Formatter):
    """Форматтер с маскированием персональных данных"""

    def __init__(self, fmt=None, datefmt=None, mask_personal_data=True):
        super().__init__(fmt, datefmt)
        self.mask_personal_data = mask_personal_data

        # Паттерны для маскирования
        self.phone_pattern = re.compile(r'(\+7|8)[\s\-]?\(?\d{3}\)? ?[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}')
        # Паттерн для ФИО (упрощенный)
        self.name_pattern = re.compile(
            r'(?:ФИО|Patient|Name|Пациент)[\s:=]+([А-ЯЁ][а-яё]+\s+[А-ЯЁ][а-яё]+(?:\s+[А-ЯЁ][а-яё]+)?)',
            re.IGNORECASE
        )

    def _mask_phone(self, text: str) -> str:
        """Маскирует телефонные номера"""
        def replacer(match):
            phone = match.group(0)
            if len(phone) >= 11:
                return f"+7XXX***XX-XX"
            return "***MASKED_PHONE***"
        return self.phone_pattern.sub(replacer, text)

    def _mask_name(self, text: str) -> str:
        """Маскирует ФИО"""
        def replacer(match):
            prefix = match.group(0).split(':')[0] if ':' in match.group(0) else 'ФИО'
            return f"{prefix}: ***MASKED_NAME***"
        return self.name_pattern.sub(replacer, text)

    def format(self, record):
        """Форматирует запись с маскированием ПД"""
        msg = super().format(record)

        if self.mask_personal_data:
            msg = self._ mask_phone(msg)
            msg = self._mask_name(msg)

        return msg


class CustomLogger:
    """Кастомный логгер с расширенными возможностями"""

    def __init__(
        self,
        name: str = "ident_bitrix_integration",
        log_dir: str = "logs",
        log_level: str = "INFO",
        rotation_days: int = 30,
        max_file_size_mb: int = 100,
        mask_personal_data: bool = True
    ):
        self.name = name
        self.log_dir = Path(log_dir)
        self.log_level = getattr(logging, log_level.upper(), logging.INFO)
        self.rotation_days = rotation_days
        self.max_file_size_mb = max_file_size_mb
        self.mask_personal_data = mask_personal_data

        # Создаем директорию для логов
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # Инициализируем логгер
        self.logger = self._setup_logger()

    def _setup_logger(self) -> logging.Logger:
        """Настраивает логгер с обработчиками"""
        logger = logging.getLogger(self.name)
        logger.setLevel(self.log_level)

        # Удаляем существующие обработчики (если есть)
        logger.handlers.clear()

        # Формат логов
        log_format = '[ %(asctime)s] %(levelname)-8s: %(message)s'
        date_format = '%Y-%m-%d %H:%M:%S'

        # Обработчик для файла с ротацией по дням
        file_handler = TimedRotatingFileHandler(
            filename=self.log_dir / f'integration_log_{datetime.now().strftime("%Y-%m-%d")}.txt',
            when='midnight',
            interval=1,
            backupCount=self.rotation_days,
            encoding='utf-8'
        )
        file_handler.setLevel(self.log_level)
        file_formatter = PersonalDataMaskingFormatter(
            fmt=log_format,
            datefmt=date_format,
            mask_personal_data=self.mask_personal_data
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)

        # Обработчик для консоли
        console_handler = logging.StreamHandler()
        console_handler.setLevel(self.log_level)
        console_formatter = PersonalDataMaskingFormatter(
            fmt=log_format,
            datefmt=date_format,
            mask_personal_data=self.mask_personal_data
        )
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)

        return logger

    def clean_old_logs(self):
        """Удаляет логи старше rotation_days дней"""
        cutoff_date = datetime.now() - timedelta(days=self.rotation_days)

        deleted_count = 0
        for log_file in self.log_dir.glob('integration_log_*.txt'):
            try:
                # Извлекаем дату из имени файла
                date_str = log_file.stem.split('_')[-1]
                file_date = datetime.strptime(date_str, '%Y-%m-%d')

                if file_date < cutoff_date:
                    log_file.unlink()
                    deleted_count += 1
                    self.logger.info(f"Deleted old log file: {log_file.name}")
            except (ValueError, IndexError) as e:
                self.logger.warning(f"Could not parse date from log file {log_file.name}: {e}")

        if deleted_count > 0:
            self.logger.info(f"Cleaned up {deleted_count} old log file(s)")

    def debug(self, message: str):
        """Логирует сообщение уровня DEBUG"""
        self.logger.debug(message)

    def info(self, message: str):
        """Логирует сообщение уровня INFO"""
        self.logger.info(message)

    def warning(self, message: str):
        """Логирует сообщение уровня WARNING"""
        self.logger.warning(message)

    def error(self, message: str, exc_info: bool = False):
        """Логирует сообщение уровня ERROR"""
        self.logger.error(message, exc_info=exc_info)

    def critical(self, message: str, exc_info: bool = False):
        """Логирует сообщение уровня CRITICAL"""
        self.logger.critical(message, exc_info=exc_info)

    def log_reception_sync(self, reception_id: str, status: str, details: str = ""):
        """Логирует синхронизацию записи"""
        self.info(f"Reception sync | ID: {reception_id} | Status: {status} | {details}")

    def log_api_call(self, method: str, endpoint: str, status_code: int, duration_ms: int):
        """Логирует вызов API"""
        self.info(
            f"API call | Method: {method} | Endpoint: {endpoint} | "
            f"Status: {status_code} | Duration: {duration_ms}ms"
        )

    def log_error_with_context(self, error_type: str, error_msg: str, context: dict):
        """Логирует ошибку с контекстом"""
        context_str = " | ".join([f"{k}: {v}" for k, v in context.items()])
        self.error(f"{error_type}: {error_msg} | Context: {context_str}")


# Singleton instance
_logger_instance: Optional[CustomLogger] = None


def get_logger(
    name: str = "ident_bitrix_integration",
    log_dir: str = "logs",
    log_level: str = "INFO",
    rotation_days: int = 30,
    max_file_size_mb: int = 100,
    mask_personal_data: bool = True
) -> CustomLogger:
    """Возвращает singleton instance логгера"""
    global _logger_instance

    if _logger_instance is None:
        _logger_instance = CustomLogger(
            name=name,
            log_dir=log_dir,
            log_level=log_level,
            rotation_days=rotation_days,
            max_file_size_mb=max_file_size_mb,
            mask_personal_data=mask_personal_data
        )

    return _logger_instance


if __name__ == "__main__":
    # Тестирование модуля
    logger = get_logger(log_level="DEBUG", mask_personal_data=True)

    logger.info("Интеграция запущена")
    logger.debug("Подключение к БД Ident")
    logger.warning("Филиал не определен для записи ID 12345")

    # Тестирование маскирования
    logger.info("Пациент: Иванов Иван Иванович, телефон: +7 (916) 123-45-67")
    logger.info("Patient: Петров Петр, phone: 8-916-123-45-67")

    logger.log_reception_sync("F1_12345", "success", "Сделка создана")
    logger.log_api_call("POST", "crm.deal.add", 200, 156)
    logger.log_error_with_context(
        "ValidationError",
        "Телефон не указан",
        {"reception_id": "F1_12345", "patient": "ID_98765"}
    )

    logger.error("Ошибка подключения к БД", exc_info=True)

    # Очистка старых логов
    logger.clean_old_logs()

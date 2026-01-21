"""
Модуль управления конфигурацией интеграции Ident-Битрикс24
Поддерживает:
- Чтение конфигурации из INI файла
- Шифрование/дешифрование чувствительных данных
- Валидацию параметров
- Генерацию ключа шифрования
"""

import configparser
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
from cryptography.fernet import Fernet


class ConfigManager:
    """Менеджер конфигурации с поддержкой шифрования"""

    # Поля, которые нужно шифровать
    ENCRYPTED_FIELDS = [
        ('Database', 'password'),
        ('Bitrix24', 'token'),
        ('Notifications', 'smtp_password')
    ]

    def __init__(self, config_path: str = "config.ini"):
        self.config_path = Path(config_path)
        self.config = configparser.ConfigParser()

        # Проверяем наличие файла конфигурации
        if not self.config_path.exists():
            raise FileNotFoundError(
                f"Файл конфигурации {self.config_path} не найден. "
                f"Скопируйте config.example.ini в config.ini и заполните параметры."
            )

        # Читаем конфигурацию
        self.config.read(self.config_path, encoding='utf-8')

        # Инициализируем шифрование
        self.cipher = self._init_encryption()

        # Шифруем пароли при первом запуске
        self._encrypt_sensitive_data()

    def _init_encryption(self) -> Fernet:
        """Инициализирует систему шифрования"""
        encryption_key = self.config.get('Security', 'encryption_key', fallback='')

        if not encryption_key:
            # Генерируем новый ключ
            encryption_key = Fernet.generate_key().decode()
            self.config.set('Security', 'encryption_key', encryption_key)
            self._save_config()

        return Fernet(encryption_key.encode())

    def _save_config(self):
        """Сохраняет конфигурацию в файл"""
        with open(self.config_path, 'w', encoding='utf-8') as f:
            self.config.write(f)

    def _is_encrypted(self, value: str) -> bool:
        """Проверяет, зашифрован ли текст"""
        if not value:
            return False
        # Зашифрованные значения начинаются с gAAAAA (base64)
        return value.startswith('gAAAAA')

    def _encrypt_sensitive_data(self):
        """Шифрует чувствительные данные при первом запуске"""
        modified = False

        for section, option in self.ENCRYPTED_FIELDS:
            if self.config.has_option(section, option):
                value = self.config.get(section, option)

                # Шифруем только если еще не зашифровано
                if value and not self._is_encrypted(value):
                    encrypted_value = self.cipher.encrypt(value.encode()).decode()
                    self.config.set(section, option, encrypted_value)
                    modified = True

        if modified:
            self._save_config()

    def _decrypt_value(self, value: str) -> str:
        """Дешифрует значение"""
        if not value or not self._is_encrypted(value):
            return value

        try:
            return self.cipher.decrypt(value.encode()).decode()
        except Exception as e:
            raise ValueError(f"Не удалось дешифровать значение: {e}")

    def get(self, section: str, option: str, fallback: Any = None) -> Any:
        """Получает значение из конфигурации с дешифровкой"""
        value = self.config.get(section, option, fallback=fallback)

        # Дешифруем если это зашифрованное поле
        if (section, option) in self.ENCRYPTED_FIELDS:
            value = self._decrypt_value(value)

        return value

    def getint(self, section: str, option: str, fallback: int = 0) -> int:
        """Получает целое число"""
        return self.config.getint(section, option, fallback=fallback)

    def getfloat(self, section: str, option: str, fallback: float = 0.0) -> float:
        """Получает число с плавающей точкой"""
        return self.config.getfloat(section, option, fallback=fallback)

    def getboolean(self, section: str, option: str, fallback: bool = False) -> bool:
        """Получает булево значение"""
        return self.config.getboolean(section, option, fallback=fallback)

    def getlist(self, section: str, option: str, separator: str = ',', fallback: List = None) -> List[str]:
        """Получает список значений"""
        value = self.config.get(section, option, fallback='')
        if not value:
            return fallback if fallback is not None else []
        return [item.strip() for item in value.split(separator)]

    # Удобные методы для получения конфигурации по секциям

    def get_database_config(self) -> Dict[str, Any]:
        """Возвращает конфигурацию БД"""
        return {
            'server': self.get('Database', 'server'),
            'port': self.getint('Database', 'port', 1433),
            'database': self.get('Database', 'database'),
            'username': self.get('Database', 'username'),
            'password': self.get('Database', 'password'),
            'connection_timeout': self.getint('Database', 'connection_timeout', 10),
            'query_timeout': self.getint('Database', 'query_timeout', 30)
        }

    def get_bitrix24_config(self) -> Dict[str, Any]:
        """Возвращает конфигурацию Битрикс24"""
        retry_delays_str = self.getlist('Bitrix24', 'retry_delays', ',', ['30', '60', '300'])
        retry_delays = [int(d) for d in retry_delays_str]

        return {
            'webhook_url': self.get('Bitrix24', 'webhook_url'),
            'token': self.get('Bitrix24', 'token'),
            'max_retries': self.getint('Bitrix24', 'max_retries', 3),
            'retry_delays': retry_delays,
            'rate_limit': self.getint('Bitrix24', 'rate_limit', 2)
        }

    def get_sync_config(self) -> Dict[str, Any]:
        """Возвращает конфигурацию синхронизации"""
        return {
            'interval_minutes': self.getint('Sync', 'interval_minutes', 2),
            'batch_size': self.getint('Sync', 'batch_size', 50),
            'initial_sync_days': self.getint('Sync', 'initial_sync_days', 7),
            'filial_id': self.getint('Sync', 'filial_id', 1)
        }

    def get_logging_config(self) -> Dict[str, Any]:
        """Возвращает конфигурацию логирования"""
        return {
            'level': self.get('Logging', 'level', 'INFO'),
            'log_dir': self.get('Logging', 'log_dir', 'logs'),
            'log_filename': self.get('Logging', 'log_filename', 'integration_log_{date}.txt'),
            'rotation_days': self.getint('Logging', 'rotation_days', 30),
            'max_file_size_mb': self.getint('Logging', 'max_file_size_mb', 100),
            'mask_personal_data': self.getboolean('Logging', 'mask_personal_data', True)
        }

    def get_queue_config(self) -> Dict[str, Any]:
        """Возвращает конфигурацию очереди"""
        return {
            'queue_db_path': self.get('Queue', 'queue_db_path', 'data/queue.db'),
            'max_queue_size': self.getint('Queue', 'max_queue_size', 1000),
            'process_interval_minutes': self.getint('Queue', 'process_interval_minutes', 5)
        }

    def get_monitoring_config(self) -> Dict[str, Any]:
        """Возвращает конфигурацию мониторинга"""
        return {
            'enabled': self.getboolean('Monitoring', 'enabled', True),
            'host': self.get('Monitoring', 'host', 'localhost'),
            'port': self.getint('Monitoring', 'port', 8080),
            'debug': self.getboolean('Monitoring', 'debug', False)
        }

    def get_notifications_config(self) -> Dict[str, Any]:
        """Возвращает конфигурацию уведомлений"""
        return {
            'admin_email': self.get('Notifications', 'admin_email'),
            'smtp_server': self.get('Notifications', 'smtp_server'),
            'smtp_port': self.getint('Notifications', 'smtp_port', 587),
            'smtp_username': self.get('Notifications', 'smtp_username'),
            'smtp_password': self.get('Notifications', 'smtp_password'),
            'error_threshold_percent': self.getint('Notifications', 'error_threshold_percent', 10),
            'error_threshold_count': self.getint('Notifications', 'error_threshold_count', 5)
        }

    def get_stage_mapping(self) -> Dict[str, str]:
        """Возвращает маппинг стадий воронки"""
        if not self.config.has_section('StageMapping'):
            # Возвращаем значения по умолчанию
            return {
                'consultation_scheduled': 'C1:CONSULTATION_SCHEDULED',
                'consultation_done': 'C1:CONSULTATION_DONE',
                'plan_presentation': 'C1:PLAN_PRESENTATION',
                'waiting_list': 'C1:WAITING_LIST',
                'prepayment_received': 'C1:PREPAYMENT_RECEIVED',
                'treatment': 'C1:TREATMENT',
                'won': 'C1:WON',
                'lose': 'C1:LOSE'
            }

        return dict(self.config.items('StageMapping'))

    def get_performance_config(self) -> Dict[str, Any]:
        """Возвращает конфигурацию производительности"""
        return {
            'max_processing_time': self.getint('Performance', 'max_processing_time', 2),
            'batch_pause': self.getint('Performance', 'batch_pause', 1),
            'db_pool_size': self.getint('Performance', 'db_pool_size', 1)
        }

    def get_security_config(self) -> Dict[str, Any]:
        """Возвращает конфигурацию безопасности"""
        return {
            'min_tls_version': self.get('Security', 'min_tls_version', '1.2'),
            'verify_ssl': self.getboolean('Security', 'verify_ssl', True)
        }

    def get_advanced_config(self) -> Dict[str, Any]:
        """Возвращает расширенную конфигурацию"""
        return {
            'debug_mode': self.getboolean('Advanced', 'debug_mode', False),
            'dry_run': self.getboolean('Advanced', 'dry_run', False),
            'skip_validation': self.getboolean('Advanced', 'skip_validation', False)
        }

    def validate_config(self) -> List[str]:
        """Валидирует конфигурацию и возвращает список ошибок"""
        errors = []

        # Проверяем обязательные параметры БД
        db_config = self.get_database_config()
        if not db_config['server']:
            errors.append("Database.server не указан")
        if not db_config['database']:
            errors.append("Database.database не указан")
        if not db_config['username']:
            errors.append("Database.username не указан")
        if not db_config['password']:
            errors.append("Database.password не указан")

        # Проверяем обязательные параметры Битрикс24
        b24_config = self.get_bitrix24_config()
        if not b24_config['webhook_url']:
            errors.append("Bitrix24.webhook_url не указан")
        if not b24_config['token']:
            errors.append("Bitrix24.token не указан")

        # Проверяем ID филиала
        sync_config = self.get_sync_config()
        if sync_config['filial_id'] < 1 or sync_config['filial_id'] > 10:
            errors.append("Sync.filial_id должен быть от 1 до 10")

        return errors


# Singleton instance
_config_instance: Optional[ConfigManager] = None


def get_config(config_path: str = "config.ini") -> ConfigManager:
    """Возвращает singleton instance конфигурации"""
    global _config_instance

    if _config_instance is None:
        _config_instance = ConfigManager(config_path)

    return _config_instance


if __name__ == "__main__":
    # Тестирование модуля
    try:
        config = get_config("config.example.ini")

        print("=== Database Config ===")
        print(config.get_database_config())

        print("\n=== Bitrix24 Config ===")
        print(config.get_bitrix24_config())

        print("\n=== Sync Config ===")
        print(config.get_sync_config())

        print("\n=== Stage Mapping ===")
        print(config.get_stage_mapping())

        print("\n=== Validation ===")
        errors = config.validate_config()
        if errors:
            print("Ошибки валидации:")
            for error in errors:
                print(f"  - {error}")
        else:
            print("Конфигурация валидна")

    except FileNotFoundError as e:
        print(f"Ошибка: {e}")
    except Exception as e:
        print(f"Неожиданная ошибка: {e}")

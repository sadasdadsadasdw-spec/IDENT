"""
IDENT → Bitrix24 Integration - Service Runner

Wrapper для запуска интеграции с автоматическим перезапуском при сбоях
Используется с Windows Task Scheduler
"""

import sys
import os
import time
import logging
from pathlib import Path
from datetime import datetime

# Добавляем текущую директорию в PYTHONPATH
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

# Настройка логирования
log_dir = current_dir / 'logs'
log_dir.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_dir / 'service_runner.log', encoding='utf-8')
    ]
)

logger = logging.getLogger('ServiceRunner')


def main():
    """
    Главная функция с автоматическим перезапуском при сбоях
    """
    logger.info("=" * 80)
    logger.info("IDENT -> Bitrix24 Integration Service Runner Starting")
    logger.info("=" * 80)
    logger.info(f"Working Directory: {os.getcwd()}")
    logger.info(f"Python Version: {sys.version}")
    logger.info(f"Python Path: {sys.executable}")
    logger.info(f"Start Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 80)

    restart_count = 0
    max_quick_restarts = 5  # Максимум 5 быстрых перезапусков подряд
    quick_restart_window = 60  # "Быстрый" = в течение 60 секунд
    last_start_time = time.time()

    while True:
        try:
            # Проверяем не слишком ли часто перезапускаемся
            current_time = time.time()
            time_since_last_start = current_time - last_start_time

            if time_since_last_start < quick_restart_window:
                restart_count += 1
                if restart_count >= max_quick_restarts:
                    logger.error(
                        f"ERROR: Слишком много быстрых перезапусков ({restart_count} за {quick_restart_window} сек)"
                    )
                    logger.error("Останавливаем службу для предотвращения бесконечного цикла")
                    logger.error("Проверьте логи и исправьте проблему, затем запустите службу вручную")
                    sys.exit(1)
            else:
                # Прошло достаточно времени, сбрасываем счетчик
                restart_count = 0

            last_start_time = current_time

            # Импортируем и запускаем основной модуль
            logger.info("[INFO] Importing main module...")

            try:
                from main import main as run_integration
                logger.info("[OK] Main module imported successfully")
            except ImportError as e:
                logger.error(f"ERROR: Failed to import main module: {e}")
                logger.error("Убедитесь что файл main.py существует и все зависимости установлены")
                sys.exit(1)

            logger.info("[START]  Starting integration loop...")
            logger.info("")

            # Запускаем интеграцию
            run_integration()

            # Если дошли сюда, значит интеграция завершилась штатно
            logger.info("")
            logger.info("[OK] Integration completed normally")
            break

        except KeyboardInterrupt:
            logger.info("")
            logger.info("[STOP] Service stopped by user (Ctrl+C)")
            sys.exit(0)

        except Exception as e:
            logger.error("")
            logger.error("=" * 80)
            logger.error(f"ERROR: FATAL ERROR: {e}")
            logger.error("=" * 80)
            logger.exception("Full traceback:")
            logger.error("=" * 80)

            # Определяем нужно ли перезапускаться
            restart_delay = 60

            logger.warning(f"[RESTART] Service will restart in {restart_delay} seconds...")
            logger.warning(f"   (Restart #{restart_count + 1})")
            logger.warning("")

            time.sleep(restart_delay)

            logger.info("[RESTART] Restarting integration...")
            logger.info("")
            # Цикл продолжится и попробует перезапустить

    logger.info("=" * 80)
    logger.info("[END] Service Runner shutting down")
    logger.info("=" * 80)


if __name__ == "__main__":
    main()

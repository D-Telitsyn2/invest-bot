import logging
import os
from datetime import datetime

def setup_logging():
    """Настройка системы логирования"""

    # Создаем директорию для логов если её нет
    if not os.path.exists('logs'):
        os.makedirs('logs')

    # Формат логов
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    date_format = '%Y-%m-%d %H:%M:%S'

    # Конфигурация для файла
    file_handler = logging.FileHandler(
        f'logs/bot_{datetime.now().strftime("%Y%m%d")}.log',
        encoding='utf-8'
    )
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(logging.Formatter(log_format, date_format))

    # Конфигурация для консоли
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter(log_format, date_format))

    # Настройка корневого логгера
    logging.basicConfig(
        level=logging.INFO,
        handlers=[file_handler, console_handler],
        format=log_format,
        datefmt=date_format
    )

    # Отключаем избыточные логи от библиотек
    logging.getLogger('aiogram.event').setLevel(logging.WARNING)
    logging.getLogger('aiogram.middlewares').setLevel(logging.WARNING)
    logging.getLogger('openai').setLevel(logging.WARNING)
    logging.getLogger('httpx').setLevel(logging.WARNING)

    logger = logging.getLogger(__name__)
    logger.info("Система логирования настроена")

if __name__ == "__main__":
    setup_logging()

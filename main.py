import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand
from dotenv import load_dotenv
import os

from handlers import register_handlers
from database import init_db, create_user
from scheduler import scheduler_service
from config import setup_logging

# Загружаем переменные окружения
load_dotenv()

# Настройка логирования
setup_logging()
logger = logging.getLogger(__name__)

# Инициализация бота
bot = Bot(token=os.getenv('TELEGRAM_BOT_TOKEN'))
dp = Dispatcher()

async def set_bot_commands():
    """Установка команд бота в меню"""
    commands = [
        BotCommand(command="start", description="🚀 Запустить бота"),
        BotCommand(command="portfolio", description="💼 Показать портфель"),
        BotCommand(command="target", description="🎯 Целевые цены"),
        BotCommand(command="ideas", description="💡 Получить инвестиционные идеи"),
        BotCommand(command="history", description="📊 История операций"),
        BotCommand(command="finances", description="💰 Финансовая статистика"),
        BotCommand(command="settings", description="⚙️ Настройки"),
        BotCommand(command="help", description="❓ Помощь")
    ]
    await bot.set_my_commands(commands)

async def main():
    logger.info("Запуск бота...")

    logger.info("Инициализация базы данных...")
    await init_db()
    logger.info("База данных успешно инициализирована.")

    logger.info("Регистрация обработчиков...")
    register_handlers(dp)
    logger.info("Обработчики успешно зарегистрированы.")

    logger.info("Установка команд бота...")
    await set_bot_commands()
    logger.info("Команды бота успешно установлены.")

    logger.info("Запуск планировщика...")
    scheduler_service.bot = bot
    await scheduler_service.start()
    logger.info("Планировщик успешно запущен.")

    logger.info("Бот готов к работе. Запуск опроса...")

    # Запуск polling
    try:
        await dp.start_polling(bot)
    finally:
        logger.info("Остановка бота...")
        await scheduler_service.stop()
        await bot.session.close()
        logger.info("Бот остановлен. Сессия и планировщик завершены.")

if __name__ == "__main__":
    asyncio.run(main())

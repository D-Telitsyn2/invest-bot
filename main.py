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
        BotCommand(command="ideas", description="💡 Получить инвестиционные идеи"),
        BotCommand(command="confirm", description="✅ Подтвердить сделку"),
        BotCommand(command="history", description="📊 История операций"),
        BotCommand(command="help", description="❓ Помощь")
    ]
    await bot.set_my_commands(commands)

async def main():
    """Основная функция запуска бота"""
    try:
        # Инициализация базы данных
        await init_db()

        # Регистрация обработчиков
        register_handlers(dp)

        # Установка команд бота
        await set_bot_commands()

        # Запуск планировщика задач
        scheduler_service.bot = bot
        await scheduler_service.start()

        logger.info("Бот запущен")

        # Запуск polling
        await dp.start_polling(bot)

    except Exception as e:
        logger.error(f"Ошибка при запуске бота: {e}")
    finally:
        # Остановка планировщика
        await scheduler_service.stop()
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())

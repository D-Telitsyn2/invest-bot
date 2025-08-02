#!/usr/bin/env python3
"""
Проверка валидности Telegram Bot Token
"""

import asyncio
from aiogram import Bot
from dotenv import load_dotenv
import os

async def test_telegram_bot():
    load_dotenv()

    token = os.getenv('TELEGRAM_BOT_TOKEN')
    if not token:
        print("❌ Токен не найден")
        return

    print(f"🔑 Тестирование токена: {token[:10]}...")

    bot = Bot(token=token)

    try:
        # Получаем информацию о боте
        me = await bot.get_me()
        print(f"✅ Бот активен!")
        print(f"   Имя: {me.first_name}")
        print(f"   Username: @{me.username}")
        print(f"   ID: {me.id}")
        print(f"   Может получать сообщения: {me.can_join_groups}")

        # Проверяем webhook
        webhook_info = await bot.get_webhook_info()
        print(f"📡 Webhook URL: {webhook_info.url or 'Не установлен (polling режим)'}")

        return True

    except Exception as e:
        print(f"❌ Ошибка проверки бота: {e}")
        return False
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(test_telegram_bot())

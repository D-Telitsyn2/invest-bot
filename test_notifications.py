#!/usr/bin/env python3
"""
Скрипт для тестирования системы уведомлений
"""
import asyncio
import os
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

async def test_notifications():
    """Тестирует систему уведомлений"""
    print("=== ТЕСТ СИСТЕМЫ УВЕДОМЛЕНИЙ ===")

    try:
        # Инициализируем базу данных
        from database import init_db, get_users_with_notification_type, get_user_settings
        await init_db()
        print("✅ База данных инициализирована")

        # Проверяем пользователей с включенной ежедневной сводкой
        users = await get_users_with_notification_type('daily_market_analysis')
        print(f"📊 Найдено {len(users)} пользователей с включенной ежедневной сводкой")

        if users:
            for user in users:
                print(f"\n👤 Пользователь: {user['user_id']} (@{user.get('username', 'no_username')})")
                settings = await get_user_settings(user['user_id'])
                print(f"   Настройки: {settings}")

                # Проверяем, активен ли пользователь для уведомлений
                if settings and settings.get('notifications', True):
                    print(f"   ✅ Пользователь получит уведомления")
                else:
                    print(f"   ❌ Пользователь НЕ получит уведомления (отключены)")
        else:
            print("❌ НЕТ пользователей с включенной ежедневной сводкой!")

        # Проверяем всех пользователей в системе
        from database import get_pool
        pool = await get_pool()
        async with pool.acquire() as connection:
            all_users = await connection.fetch("SELECT COUNT(*) as cnt FROM users")
            all_settings = await connection.fetch("SELECT COUNT(*) as cnt FROM user_settings")
            print(f"\n📈 Всего пользователей в системе: {all_users[0]['cnt']}")
            print(f"📈 Всего записей настроек: {all_settings[0]['cnt']}")

            # Показываем все настройки
            settings_rows = await connection.fetch("""
                SELECT u.telegram_id, u.username, s.notifications, s.daily_market_analysis,
                       s.weekly_portfolio_report, s.target_price_alerts, s.price_updates
                FROM users u
                LEFT JOIN user_settings s ON u.telegram_id = s.user_id
                ORDER BY u.telegram_id
            """)

            print(f"\n📋 Все пользователи и их настройки:")
            for row in settings_rows:
                print(f"   {row['telegram_id']} (@{row['username'] or 'no_username'}): "
                      f"notifications={row['notifications']}, "
                      f"daily={row['daily_market_analysis']}, "
                      f"weekly={row['weekly_portfolio_report']}")

        # Тест планировщика
        print(f"\n🕒 Тест планировщика...")
        from scheduler import scheduler_service

        # Имитируем запуск бота
        class MockBot:
            async def send_message(self, chat_id, text, parse_mode=None):
                print(f"📨 ОТПРАВКА СООБЩЕНИЯ пользователю {chat_id}:")
                print(f"   {text[:100]}...")

        scheduler_service.bot = MockBot()

        # Запускаем тест ежедневного анализа
        print(f"\n🚀 Запуск ежедневного анализа...")
        await scheduler_service.daily_market_analysis()
        print(f"✅ Ежедневный анализ завершен")

    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_notifications())

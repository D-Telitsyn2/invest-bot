#!/usr/bin/env python3
"""
Простой тест подключения к базе данных
"""
import asyncio
import os
from dotenv import load_dotenv

async def test_db_connection():
    """Простой тест подключения к БД"""
    print("=== ТЕСТ ПОДКЛЮЧЕНИЯ К БД ===")

    # Загружаем переменные окружения
    load_dotenv()

    db_url = os.getenv('DATABASE_URL')
    if not db_url:
        print("❌ DATABASE_URL не найден в переменных окружения")
        return

    print(f"✅ DATABASE_URL найден: {db_url[:50]}...")

    try:
        import asyncpg
        print("✅ asyncpg импортирован")

        # Пробуем подключиться к базе
        conn = await asyncpg.connect(db_url)
        print("✅ Подключение к БД успешно")

        # Проверяем таблицы
        tables = await conn.fetch("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
        print(f"📊 Найдено таблиц: {len(tables)}")
        for table in tables:
            print(f"   - {table['table_name']}")

        # Проверяем пользователей
        if any(t['table_name'] == 'users' for t in tables):
            users_count = await conn.fetchval("SELECT COUNT(*) FROM users")
            print(f"👥 Пользователей в БД: {users_count}")

        if any(t['table_name'] == 'user_settings' for t in tables):
            settings_count = await conn.fetchval("SELECT COUNT(*) FROM user_settings")
            print(f"⚙️ Записей настроек: {settings_count}")

            # Показываем настройки пользователей
            if settings_count > 0:
                settings = await conn.fetch("""
                    SELECT u.telegram_id, u.username, s.notifications, s.daily_market_analysis
                    FROM users u
                    JOIN user_settings s ON u.telegram_id = s.user_id
                """)
                print(f"\n📋 Настройки пользователей:")
                for row in settings:
                    print(f"   {row['telegram_id']} (@{row['username'] or 'no_username'}): "
                          f"notifications={row['notifications']}, daily={row['daily_market_analysis']}")

        await conn.close()
        print("✅ Соединение закрыто")

    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_db_connection())

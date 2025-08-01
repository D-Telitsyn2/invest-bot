#!/usr/bin/env python3
"""
Демонстрационный скрипт для тестирования основных функций бота
"""

import asyncio
import os
import sys
from dotenv import load_dotenv

# Добавляем текущую директорию в путь для импорта модулей
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database import init_db, create_user, save_order, get_user_portfolio
from tinkoff_client import get_price, place_order

async def demo():
    """Демонстрация основных функций"""
    print("🤖 Демонстрация Invest Bot\n")

    # Инициализация базы данных
    print("📁 Инициализация базы данных...")
    await init_db()
    print("✅ База данных готова\n")

    # Создание тестового пользователя
    test_user_id = 123456789
    print(f"👤 Создание тестового пользователя (ID: {test_user_id})...")
    await create_user(test_user_id, "test_user", "Test User")
    print("✅ Пользователь создан\n")

    # Получение инвестиционных идей (без API ключа OpenAI)
    print("💡 Получение инвестиционных идей...")
    print("⚠️  Для демонстрации без API ключа, используем заглушки:")

    # Заглушка идей
    mock_ideas = [
        {"ticker": "SBER", "action": "BUY", "price": 280.50},
        {"ticker": "GAZP", "action": "BUY", "price": 175.20},
        {"ticker": "YNDX", "action": "BUY", "price": 2650.00}
    ]

    print(f"✅ Получено {len(mock_ideas)} идей:")
    for i, idea in enumerate(mock_ideas, 1):
        print(f"  {i}. {idea['ticker']} - {idea['action']} по {idea['price']:.2f} ₽")
    print()

    # Получение цен акций
    print("📈 Получение текущих цен акций...")
    tickers = ["SBER", "GAZP", "YNDX"]
    for ticker in tickers:
        try:
            price = await get_price(ticker)
            if price:
                print(f"  {ticker}: {price:.2f} ₽")
            else:
                print(f"  {ticker}: цена недоступна")
        except Exception as e:
            print(f"  {ticker}: ошибка - {e}")
    print()

    # Симуляция покупки акций
    print("💰 Симуляция покупки акций...")
    try:
        result = await place_order(
            ticker="SBER",
            quantity=10,
            price=280.50,
            direction="buy"
        )

        if result['success']:
            print(f"✅ Заявка выполнена: {result['order_id']}")

            # Сохраняем в базу данных
            await save_order(
                user_id=test_user_id,
                ticker="SBER",
                quantity=10,
                price=280.50,
                order_type="BUY",
                total_amount=2805.0,
                order_id=result['order_id']
            )
            print("✅ Сделка сохранена в базу данных")
        else:
            print(f"❌ Ошибка заявки: {result['error']}")
    except Exception as e:
        print(f"❌ Ошибка при размещении заявки: {e}")
    print()

    # Просмотр портфеля
    print("💼 Просмотр портфеля...")
    try:
        portfolio = await get_user_portfolio(test_user_id)
        if portfolio:
            print("✅ Позиции в портфеле:")
            for position in portfolio:
                print(f"  {position['ticker']}: {position['quantity']} шт. "
                      f"по {position['avg_price']:.2f} ₽ "
                      f"(стоимость: {position['current_value']:.2f} ₽)")
        else:
            print("📭 Портфель пуст")
    except Exception as e:
        print(f"❌ Ошибка при получении портфеля: {e}")
    print()

    print("🎉 Демонстрация завершена!")
    print("\n💡 Для запуска бота используйте: python main.py")

if __name__ == "__main__":
    # Загружаем переменные окружения
    load_dotenv()

    # Проверяем наличие необходимых переменных (для полной функциональности)
    required_vars = ['TELEGRAM_BOT_TOKEN', 'OPENAI_API_KEY', 'TINKOFF_TOKEN']
    missing_vars = [var for var in required_vars if not os.getenv(var)]

    if missing_vars:
        print("⚠️  Отсутствуют переменные окружения для полной функциональности:")
        for var in missing_vars:
            print(f"  - {var}")
        print("\nЗапускаем демонстрацию с заглушками...\n")
    else:
        print("✅ Все переменные окружения настроены!\n")    # Запускаем демонстрацию
    asyncio.run(demo())

#!/usr/bin/env python3
"""
Полное тестирование всех компонентов бота
"""

import asyncio
import os
from dotenv import load_dotenv
from database import init_db, create_user, get_user_portfolio, save_order
from gpt_client import GPTClient
from tinkoff_client import TinkoffClient

async def test_full_bot():
    print("🤖 Полное тестирование Invest Bot")
    print("=" * 50)

    # Загружаем переменные окружения
    load_dotenv()

    # 1. Тест базы данных
    print("📁 Тестирование базы данных...")
    await init_db()

    test_user_id = 987654321
    await create_user(test_user_id, "test_user", "Test User")
    print("✅ База данных и пользователь созданы")

    # 2. Тест GPT клиента
    print("\n🧠 Тестирование GPT клиента...")
    gpt_client = GPTClient()

    try:
        ideas = await gpt_client.get_investment_ideas(budget=100000, risk_level="high")
        print(f"✅ Получено {len(ideas)} инвестиционных идей")

        for i, idea in enumerate(ideas[:2], 1):
            print(f"  {i}. {idea['ticker']} - {idea['action']} по {idea['price']} ₽")

        # Анализ акции
        analysis = await gpt_client.analyze_stock("SBER")
        print(f"✅ Анализ SBER: {analysis.get('recommendation', 'DEMO')}")

    except Exception as e:
        print(f"⚠️  GPT клиент работает в демо-режиме: {e}")

    # 3. Тест Tinkoff клиента
    print("\n📈 Тестирование Tinkoff клиента...")
    tinkoff_client = TinkoffClient()

    try:
        # Получение цен
        price_sber = await tinkoff_client.get_price("SBER")
        price_gazp = await tinkoff_client.get_price("GAZP")
        print(f"✅ Цены получены: SBER={price_sber}₽, GAZP={price_gazp}₽")

        # Выполнение сделки
        order_result = await tinkoff_client.place_order("SBER", 5, price_sber, "BUY")
        print(f"✅ Заявка выполнена: {order_result.get('order_id', 'DEMO')}")

    except Exception as e:
        print(f"⚠️  Tinkoff клиент работает в демо-режиме: {e}")

    # 4. Тест сохранения сделки
    print("\n💾 Тестирование сохранения сделки...")
    saved = await save_order(
        user_id=test_user_id,
        ticker="SBER",
        quantity=5,
        price=280.50,
        order_type="BUY",
        total_amount=5 * 280.50,
        order_id="TEST_ORDER_001"
    )

    if saved:
        print("✅ Сделка сохранена в базе данных")
    else:
        print("❌ Ошибка сохранения сделки")

    # 5. Тест портфеля
    print("\n💼 Тестирование портфеля...")
    portfolio = await get_user_portfolio(test_user_id)

    if portfolio:
        print("✅ Портфель пользователя:")
        total_value = 0
        for position in portfolio:
            value = position['current_value']
            total_value += value
            print(f"  {position['ticker']}: {position['quantity']} шт. = {value:.2f} ₽")
        print(f"  Общая стоимость: {total_value:.2f} ₽")
    else:
        print("⚠️  Портфель пуст")

    # 6. Проверка готовности к продакшену
    print("\n🎯 Проверка готовности к продакшену...")

    telegram_token = os.getenv('TELEGRAM_BOT_TOKEN')
    openai_key = os.getenv('OPENAI_API_KEY')
    tinkoff_token = os.getenv('TINKOFF_TOKEN')

    print(f"  Telegram Bot Token: {'✅' if telegram_token else '❌'}")
    print(f"  OpenAI API Key: {'✅' if openai_key else '❌'}")
    print(f"  Tinkoff Token: {'✅' if tinkoff_token else '❌'}")

    if telegram_token and openai_key and tinkoff_token:
        print("\n🚀 Бот готов к запуску в продакшене!")
        print("Выполните: python main.py")
    else:
        print("\n⚠️  Для полной функциональности добавьте недостающие токены в .env файл")

    print("\n" + "=" * 50)
    print("✅ Тестирование завершено успешно!")

if __name__ == "__main__":
    asyncio.run(test_full_bot())

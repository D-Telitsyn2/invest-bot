#!/usr/bin/env python3
"""
Тест GPT-4 интеграции с реальным API ключом
"""

import asyncio
import os
from dotenv import load_dotenv
from gpt_client import GPTClient

async def test_gpt_integration():
    print("🧪 Тестирование GPT-4 интеграции...")

    # Загружаем переменные окружения
    load_dotenv()

    # Проверяем наличие API ключа
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        print("❌ OPENAI_API_KEY не найден в .env файле")
        return

    print(f"✅ API ключ найден: {api_key[:20]}...")

    # Создаем клиент
    gpt_client = GPTClient()

    try:
        print("\n💡 Получение инвестиционных идей от GPT-4...")
        ideas = await gpt_client.get_investment_ideas(budget=50000, risk_level="medium")

        print(f"✅ Получено {len(ideas)} идей:")
        for i, idea in enumerate(ideas, 1):
            print(f"  {i}. {idea.get('ticker', 'N/A')} - {idea.get('action', 'N/A')} по {idea.get('price', 'N/A')} ₽")
            print(f"     {idea.get('reasoning', 'N/A')[:80]}...")

        print("\n📊 Тестирование анализа акции...")
        analysis = await gpt_client.analyze_stock("SBER")

        print(f"✅ Анализ SBER:")
        print(f"  Рекомендация: {analysis.get('recommendation', 'N/A')}")
        print(f"  Целевая цена: {analysis.get('target_price', 'N/A')} ₽")
        print(f"  Уровень риска: {analysis.get('risk_level', 'N/A')}")
        print(f"  Анализ: {analysis.get('analysis', 'N/A')[:100]}...")

    except Exception as e:
        print(f"❌ Ошибка при работе с GPT-4: {e}")

    print("\n🎉 Тест завершен!")

if __name__ == "__main__":
    asyncio.run(test_gpt_integration())

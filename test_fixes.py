#!/usr/bin/env python3
"""
Тест исправлений для проверки что все работает правильно
"""
import asyncio
import logging
from gpt_client import XAIClient

logging.basicConfig(level=logging.INFO)

async def test_ideas_format():
    """Тест формата возвращаемых идей"""
    print("🧪 Тестируем исправления...")

    xai_client = XAIClient()
    try:
        ideas = await xai_client.get_investment_ideas(budget=50000, risk_level="medium")

        if not ideas:
            print("❌ Нет идей от xAI")
            return

        print(f"✅ Получено {len(ideas)} идей")

        for i, idea in enumerate(ideas[:3], 1):
            print(f"\n--- Идея {i} ---")
            print(f"Тикер: {idea.get('ticker', 'N/A')}")
            print(f"Цена: {idea.get('price', 'N/A')} ₽")
            print(f"Целевая цена: {idea.get('target_price', 'N/A')} ₽")
            print(f"Действие: {idea.get('action', 'N/A')}")
            print(f"Обоснование: {idea.get('reasoning', 'N/A')[:100]}...")

            # Проверяем что все основные поля присутствуют
            required_fields = ['ticker', 'price', 'target_price', 'action', 'reasoning']
            missing = [field for field in required_fields if not idea.get(field)]

            if missing:
                print(f"⚠️ Отсутствуют поля: {missing}")
            else:
                print("✅ Все поля присутствуют")

    except Exception as e:
        print(f"❌ Ошибка: {e}")

if __name__ == "__main__":
    asyncio.run(test_ideas_format())

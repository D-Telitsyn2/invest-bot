#!/usr/bin/env python3
"""
Тест новых возможностей Grok-4 с техническими данными
"""

import asyncio
import json
from gpt_client import XAIClient

async def test_grok4_technical_analysis():
    """Тестируем новый формат ответа с техническими данными"""

    print("🔬 Тестируем Grok-4 с техническими данными...")

    client = XAIClient()
    print(f"📋 Доступные модели: {client.models}")
    print(f"🎯 Первая модель (приоритетная): {client.models[0]}")

    # Тестируем получение идей
    try:
        ideas = await client.get_investment_ideas(budget=50000, risk_level="medium")

        if ideas:
            print(f"\n✅ Получено {len(ideas)} идей")

            # Проверяем первую идею на наличие новых полей
            first_idea = ideas[0]
            print(f"\n📊 Пример идеи ({first_idea.get('ticker', 'N/A')}):")

            fields_to_check = [
                'current_price', 'target_price', 'support_level',
                'resistance_level', 'trend', 'reasoning'
            ]

            for field in fields_to_check:
                value = first_idea.get(field, 'НЕТ')
                print(f"  {field}: {value}")

            # Проверяем что Grok-4 дает более детальные данные
            has_technical = any(first_idea.get(field) for field in ['support_level', 'resistance_level', 'trend'])

            if has_technical:
                print("\n🎯 ✅ Технические данные успешно получены от Grok-4!")
            else:
                print("\n⚠️ Технические данные не найдены, возможно старая модель")

        else:
            print("❌ Идеи не получены")

    except Exception as e:
        print(f"❌ Ошибка: {e}")

if __name__ == "__main__":
    asyncio.run(test_grok4_technical_analysis())

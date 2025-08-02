#!/usr/bin/env python3
"""
Тест xAI API для инвестиционного бота
"""

import asyncio
import os
import sys
from dotenv import load_dotenv

# Добавляем текущую директорию в путь
sys.path.append('/root/invest-bot')

load_dotenv()

async def test_xai():
    """Тестирование xAI API"""

    print("🤖 Тестирование xAI Grok API...")
    print("=" * 50)

    # Проверяем API ключ
    api_key = os.getenv('XAI_API_KEY')
    if not api_key or api_key == 'your_xai_api_key_here':
        print("❌ xAI API ключ не настроен!")
        print("📋 Добавьте ключ в .env файл")
        return

    print(f"✅ API ключ найден: {api_key[:10]}...")

    try:
        from gpt_client import XAIClient

        client = XAIClient()
        print("✅ XAIClient создан успешно")

        # Тест получения инвестиционных идей
        print("\n💡 Запрашиваем инвестиционные идеи от Grok...")
        ideas = await client.get_investment_ideas(budget=50000, risk_level="medium")

        if ideas:
            print(f"✅ Получено {len(ideas)} идей от xAI Grok!")
            print("\n📊 Результаты:")
            print("-" * 40)

            for i, idea in enumerate(ideas, 1):
                ticker = idea.get('ticker', 'N/A')
                action = idea.get('action', 'N/A')
                price = idea.get('price', 0)
                target = idea.get('target_price', 0)
                reasoning = idea.get('reasoning', 'N/A')[:60] + "..."

                print(f"{i}. {ticker} - {action}")
                print(f"   💰 {price} ₽ → 🎯 {target} ₽")
                print(f"   📝 {reasoning}")
                print()

            print("🎉 xAI Grok API работает отлично!")
            print("� Используем ваш оплаченный аккаунт ($5)")

        else:
            print("❌ Не удалось получить идеи")
            print("💡 Возможно, превышен лимит или API недоступен")

    except ImportError as e:
        print(f"❌ Ошибка импорта: {e}")
        print("🔧 Установите зависимости: pip install -r requirements.txt")
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        print("🔍 Проверьте API ключ и интернет-соединение")

async def test_analysis():
    """Тестирование анализа акций"""
    print("\n🔍 Тестирование анализа акций...")

    try:
        from gpt_client import XAIClient

        client = XAIClient()
        result = await client.analyze_stock("SBER")

        if result and 'error' not in result:
            print("✅ Анализ акций работает!")
            print(f"📊 {result.get('ticker')}: {result.get('recommendation')}")
            print(f"🎯 Цель: {result.get('target_price')} ₽")
        else:
            print(f"❌ Ошибка анализа: {result.get('error', 'Unknown')}")

    except Exception as e:
        print(f"❌ Ошибка анализа: {e}")

if __name__ == "__main__":
    print("🚀 Запуск тестов xAI Grok API...")
    asyncio.run(test_xai())
    asyncio.run(test_analysis())
    print("\n✅ Тестирование завершено!")
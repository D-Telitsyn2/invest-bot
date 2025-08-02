#!/usr/bin/env python3
"""
Финальная проверка готовности бота к работе
"""

import os
import sys
from pathlib import Path

def check_files():
    """Проверка наличия всех необходимых файлов"""
    required_files = [
        'main.py', 'handlers.py', 'gpt_client.py',
        'database.py', 'scheduler.py', 'config.py', 'requirements.txt',
        '.env', 'README.md'
    ]

    missing_files = []
    for file in required_files:
        if not Path(file).exists():
            missing_files.append(file)

    return missing_files

def check_env():
    """Проверка переменных окружения"""
    from dotenv import load_dotenv
    load_dotenv()

    required_vars = ['OPENAI_API_KEY']
    optional_vars = ['TELEGRAM_BOT_TOKEN']

    env_status = {}
    for var in required_vars + optional_vars:
        value = os.getenv(var)
        env_status[var] = {
            'present': bool(value),
            'required': var in required_vars
        }

    return env_status

def main():
    print("🔍 Финальная проверка Invest Bot")
    print("=" * 40)

    # Проверка файлов
    missing_files = check_files()
    if missing_files:
        print(f"❌ Отсутствуют файлы: {', '.join(missing_files)}")
        return False
    else:
        print("✅ Все необходимые файлы присутствуют")

    # Проверка переменных окружения
    env_status = check_env()
    print("\n🔑 Статус переменных окружения:")

    all_required_present = True
    for var, status in env_status.items():
        icon = "✅" if status['present'] else ("❌" if status['required'] else "⚠️")
        req_text = "(обязательно)" if status['required'] else "(опционально)"
        print(f"  {icon} {var} {req_text}")

        if status['required'] and not status['present']:
            all_required_present = False

    # Итоговый статус
    print("\n" + "=" * 40)
    if all_required_present:
        print("🎉 Бот готов к работе!")
        print("\n📋 Следующие шаги:")
        print("1. Для тестирования: python demo.py")
        print("2. Для полного теста: python test_full.py")
        if env_status['TELEGRAM_BOT_TOKEN']['present']:
            print("3. Для запуска бота: python main.py")
        else:
            print("3. Добавьте TELEGRAM_BOT_TOKEN для запуска бота")

        return True
    else:
        print("❌ Необходимо настроить обязательные переменные окружения")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

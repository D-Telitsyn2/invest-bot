#!/usr/bin/env python3
"""
Тест логики определения Railway
"""
import os

print("🔍 Проверка переменных окружения Railway")
print("=" * 50)

# Проверяем все возможные переменные Railway
env_vars = [
    'RAILWAY_ENVIRONMENT',
    'PORT', 
    'RAILWAY_STATIC_URL',
    'RAILWAY_PROJECT_NAME',
    'RAILWAY_PROJECT_ID',
    'RAILWAY_PUBLIC_DOMAIN',
    'RAILWAY_PRIVATE_DOMAIN'
]

print("\n📊 Переменные окружения:")
for var in env_vars:
    value = os.getenv(var)
    status = "✅ Установлена" if value else "❌ Не установлена"
    print(f"  {var}: {value or 'None'} ({status})")

# Логика определения Railway как в коде
is_railway = (
    os.getenv('RAILWAY_ENVIRONMENT') == 'true' or
    os.getenv('PORT') is not None
)

print(f"\n🎯 Результат определения среды:")
if is_railway:
    print("  🚂 Railway среда определена")
    print(f"  📁 Путь к БД: /app/data/invest_bot.db")
else:
    print("  🖥️ Локальная среда")
    print(f"  📁 Путь к БД: invest_bot.db")

print(f"\n💡 Рекомендации:")
if not is_railway:
    print("  1. В Railway добавьте переменную: RAILWAY_ENVIRONMENT = true")
    print("  2. Или убедитесь что Railway устанавливает PORT автоматически")
    print("  3. Сделайте redeploy после изменений")
else:
    print("  ✅ Среда определена корректно!")

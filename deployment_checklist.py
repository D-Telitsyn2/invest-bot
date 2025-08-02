#!/usr/bin/env python3
"""
Чек-лист проверки после деплоя на Railway
"""

print("🚀 Чек-лист проверки после деплоя на Railway")
print("=" * 50)

print("\n📋 ЧТО НУЖНО ПРОВЕРИТЬ:")

print("\n1. 🌐 Railway Dashboard:")
print("   • Откройте https://railway.app/dashboard")
print("   • Найдите ваш проект invest-bot")
print("   • Проверьте статус деплоя (должен быть зеленый)")

print("\n2. 📊 Логи деплоя:")
print("   • Railway Dashboard → Deployments → View Logs")
print("   • Ищите строку: '🚂 Railway: используется постоянное хранилище'")
print("   • Если видите '🖥️ Локально' - volume не активирован!")

print("\n3. 💾 Volume проверка:")
print("   • Railway Dashboard → Settings → Volumes")
print("   • Должен быть volume:")
print("     - Name: 'database'")
print("     - Mount Path: '/app/data'")
print("     - Status: Active")

print("\n4. 🔧 Environment Variables:")
print("   • Railway Dashboard → Variables")
print("   • Должна быть переменная:")
print("     - RAILWAY_ENVIRONMENT = true")

print("\n5. 🤖 Тестирование бота:")
print("   • Откройте бота в Telegram")
print("   • Отправьте /start")
print("   • Перейдите в /settings")
print("   • Измените уровень риска на 'high'")
print("   • Измените макс. сумму на 50000")
print("   • Проверьте настройки уведомлений")

print("\n6. 🔄 Тест сохранения:")
print("   • Сделайте redeploy в Railway (если нужно)")
print("   • Снова проверьте настройки в боте")
print("   • Настройки должны сохраниться!")

print("\n" + "=" * 50)
print("🎯 ПРИЗНАКИ УСПЕШНОГО ДЕПЛОЯ:")
print("✅ В логах: '🚂 Railway: используется постоянное хранилище'")
print("✅ Volume 'database' создан и активен")
print("✅ Настройки сохраняются после redeploy")
print("✅ Все типы уведомлений работают")

print("\n❌ ПРИЗНАКИ ПРОБЛЕМ:")
print("🚨 В логах: '🖥️ Локально: используется invest_bot.db'")
print("🚨 Volume не создан или неактивен")
print("🚨 Настройки сбрасываются после redeploy")

print("\n🔧 ЕСЛИ ЕСТЬ ПРОБЛЕМЫ:")
print("1. Создайте volume вручную в Railway Dashboard")
print("2. Добавьте переменную RAILWAY_ENVIRONMENT = true")
print("3. Сделайте redeploy")
print("4. Проверьте логи снова")

print("\n📞 НУЖНА ПОМОЩЬ?")
print("Покажите логи из Railway Dashboard, особенно строки:")
print("• При запуске бота (определение среды)")
print("• При инициализации базы данных")
print("• При изменении настроек пользователя")

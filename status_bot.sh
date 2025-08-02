#!/bin/bash
# Проверка статуса Invest Bot

echo "🔍 Статус Invest Bot"
echo "===================="

# Проверяем screen сессию
if screen -list | grep -q "invest-bot"; then
    echo "✅ Бот работает в screen сессии"
    echo "📋 Информация о сессии:"
    screen -list | grep invest-bot

    echo ""
    echo "🔧 Управление:"
    echo "   screen -r invest-bot    # Подключиться к боту"
    echo "   ./stop_bot.sh          # Остановить бота"
else
    echo "❌ Бот не запущен"
    echo ""
    echo "🚀 Для запуска:"
    echo "   ./start_bot.sh"
fi

echo ""
echo "📊 Процессы Python:"
ps aux | grep python | grep -v grep

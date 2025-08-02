#!/bin/bash
# Остановка Invest Bot

echo "🛑 Остановка Invest Bot..."

# Останавливаем screen сессию
screen -S invest-bot -X quit 2>/dev/null

if [ $? -eq 0 ]; then
    echo "✅ Бот остановлен"
else
    echo "⚠️  Сессия 'invest-bot' не найдена"
fi

# Показываем оставшиеся сессии
echo "📋 Активные screen сессии:"
screen -ls

#!/bin/bash
# Автозапуск Invest Bot в screen сессии

# Переходим в директорию проекта
cd /root/invest-bot

# Останавливаем существующую сессию если есть
screen -S invest-bot -X quit 2>/dev/null

# Запускаем бота в новой screen сессии
screen -dmS invest-bot python3 main.py

echo "🤖 Invest Bot запущен в screen сессии 'invest-bot'"
echo "📋 Управление:"
echo "   screen -r invest-bot  # Подключиться к сессии"
echo "   screen -ls            # Список всех сессий"
echo "   Ctrl+A, D             # Отключиться от сессии (бот продолжит работать)"
echo "   screen -S invest-bot -X quit  # Остановить бота"

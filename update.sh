#!/bin/bash

# 🔄 Скрипт обновления бота
# Использование: ./update.sh

set -e

echo "🔄 Обновляем бота..."

# Останавливаем бота
echo "⏹️ Останавливаем бота..."
sudo systemctl stop invest-bot

# Подтягиваем изменения из Git
echo "📥 Загружаем обновления..."
git pull origin main

# Обновляем зависимости
echo "📚 Обновляем зависимости..."
source venv/bin/activate
pip install -r requirements.txt --upgrade

# Запускаем бота
echo "▶️ Запускаем бота..."
sudo systemctl start invest-bot

# Проверяем статус
echo "📊 Проверяем статус..."
sleep 3
sudo systemctl status invest-bot --no-pager

echo "✅ Обновление завершено!"

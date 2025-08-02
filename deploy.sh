#!/bin/bash

# 🚀 Скрипт автоматического деплоя бота на VPS
# Использование: ./deploy.sh

set -e

echo "🚀 Начинаем деплой инвестиционного бота..."

# Проверяем что мы в правильной директории
if [ ! -f "main.py" ]; then
    echo "❌ Ошибка: main.py не найден. Запустите скрипт из корня проекта."
    exit 1
fi

# Обновляем систему
echo "📦 Обновляем систему..."
sudo apt update && sudo apt upgrade -y

# Устанавливаем зависимости
echo "🔧 Устанавливаем зависимости..."
sudo apt install python3 python3-pip python3-venv git systemd -y

# Создаем виртуальное окружение если его нет
if [ ! -d "venv" ]; then
    echo "🐍 Создаем виртуальное окружение..."
    python3 -m venv venv
fi

# Активируем окружение и устанавливаем пакеты
echo "📚 Устанавливаем Python пакеты..."
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# Проверяем .env файл
if [ ! -f ".env" ]; then
    echo "⚠️  Создайте .env файл с токенами:"
    echo "TELEGRAM_BOT_TOKEN=your_token"
    echo "XAI_API_KEY=your_xai_key"
    echo ""
    echo "Создать сейчас? (y/n)"
    read -r create_env
    if [[ $create_env =~ ^[Yy]$ ]]; then
        echo "TELEGRAM_BOT_TOKEN=" > .env
        echo "XAI_API_KEY=" >> .env
        echo "✅ Файл .env создан. Отредактируйте его и запустите скрипт снова."
        exit 0
    fi
fi

# Копируем systemd сервис
echo "⚙️ Настраиваем systemd сервис..."
sudo cp invest-bot.service /etc/systemd/system/
sudo systemctl daemon-reload

# Останавливаем старую версию если запущена
sudo systemctl stop invest-bot 2>/dev/null || true

# Включаем автозапуск и запускаем
echo "🎯 Запускаем бота..."
sudo systemctl enable invest-bot
sudo systemctl start invest-bot

# Проверяем статус
echo "📊 Проверяем статус..."
sleep 3
sudo systemctl status invest-bot --no-pager

echo ""
echo "✅ Деплой завершен!"
echo ""
echo "📋 Полезные команды:"
echo "sudo systemctl status invest-bot    # Статус бота"
echo "sudo systemctl restart invest-bot   # Перезапуск"
echo "sudo systemctl stop invest-bot      # Остановка"
echo "sudo journalctl -u invest-bot -f    # Логи в реальном времени"
echo ""
echo "🎉 Ваш бот работает 24/7!"

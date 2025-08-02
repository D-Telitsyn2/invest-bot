#!/bin/bash
# Автозапуск бота при старте системы

# Ждем 30 секунд после загрузки системы
sleep 30

# Переходим в директорию бота
cd /root/invest-bot

# Запускаем бота
./start_bot.sh

# Логируем запуск
echo "$(date): Invest Bot автоматически запущен" >> /root/invest-bot/autostart.log

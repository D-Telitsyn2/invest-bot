# 🌐 Гайд по хостингу Telegram бота

## 🎯 Вариант 1: VPS/VDS (Рекомендуется)

### 1. Покупка VPS
Выберите провайдера:
- **Timeweb** (российский) - от 190₽/мес
- **Beget** (российский) - от 199₽/мес  
- **DigitalOcean** - от $4/мес
- **Contabo** - от €3.99/мес

### 2. Подключение к серверу
```bash
ssh root@YOUR_SERVER_IP
```

### 3. Установка зависимостей
```bash
# Обновляем систему
apt update && apt upgrade -y

# Устанавливаем Python 3.11+
apt install python3 python3-pip python3-venv git -y

# Устанавливаем systemd для автозапуска
apt install systemd -y
```

### 4. Клонирование проекта
```bash
# Клонируем репозиторий
git clone https://github.com/YOUR_USERNAME/invest-bot.git
cd invest-bot

# Создаем виртуальное окружение
python3 -m venv venv
source venv/bin/activate

# Устанавливаем зависимости
pip install -r requirements.txt
```

### 5. Настройка переменных окружения
```bash
# Создаем .env файл
nano .env
```

Добавляем:
```env
TELEGRAM_BOT_TOKEN=YOUR_BOT_TOKEN
XAI_API_KEY=YOUR_XAI_API_KEY
```

### 6. Создание systemd сервиса
```bash
nano /etc/systemd/system/invest-bot.service
```

Содержимое файла:
```ini
[Unit]
Description=Investment Telegram Bot
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/invest-bot
Environment=PATH=/root/invest-bot/venv/bin
ExecStart=/root/invest-bot/venv/bin/python main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### 7. Запуск сервиса
```bash
# Перезагружаем systemd
systemctl daemon-reload

# Включаем автозапуск
systemctl enable invest-bot

# Запускаем бота
systemctl start invest-bot

# Проверяем статус
systemctl status invest-bot
```

### 8. Проверка логов
```bash
# Смотрим логи
journalctl -u invest-bot -f

# Или файловые логи
tail -f /root/invest-bot/logs/bot_$(date +%Y%m%d).log
```

---

## 🎯 Вариант 2: Heroku (Простой)

### 1. Установка Heroku CLI
```bash
curl https://cli-assets.heroku.com/install.sh | sh
```

### 2. Создание Heroku приложения
```bash
heroku login
heroku create your-invest-bot
```

### 3. Создание Procfile
```bash
echo "worker: python main.py" > Procfile
```

### 4. Настройка переменных
```bash
heroku config:set TELEGRAM_BOT_TOKEN=your_token
heroku config:set XAI_API_KEY=your_xai_key
```

### 5. Деплой
```bash
git add .
git commit -m "Deploy to Heroku"
git push heroku main
```

### 6. Масштабирование
```bash
heroku ps:scale worker=1
```

---

## 🎯 Вариант 3: Railway (Современный)

### 1. Создание аккаунта
- Идем на [railway.app](https://railway.app)
- Подключаем GitHub

### 2. Создание проекта
- New Project → Deploy from GitHub repo
- Выбираем репозиторий с ботом

### 3. Настройка переменных
В настройках проекта добавляем:
- `TELEGRAM_BOT_TOKEN`
- `XAI_API_KEY`

### 4. Настройка запуска
Создаем `railway.toml`:
```toml
[build]
builder = "nixpacks"

[deploy]
startCommand = "python main.py"
```

---

## 📊 Сравнение вариантов

| Критерий | VPS | Heroku | Railway |
|----------|-----|---------|---------|
| Цена | 190₽/мес | $7/мес | $5/мес |
| Простота | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| Контроль | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ |
| Надежность | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ |

## 🎯 Рекомендация

**Для начинающих:** Railway или Heroku
**Для опытных:** VPS (больше контроля и дешевле)

---

## 🔧 Дополнительные настройки

### Мониторинг
```bash
# Установка htop для мониторинга
apt install htop

# Просмотр процессов
htop
```

### Автообновление
```bash
# Создаем скрипт обновления
nano /root/update_bot.sh
```

Содержимое:
```bash
#!/bin/bash
cd /root/invest-bot
git pull origin main
systemctl restart invest-bot
```

### Backup базы данных
```bash
# Создаем backup скрипт
nano /root/backup_db.sh
```

Содержимое:
```bash
#!/bin/bash
cp /root/invest-bot/invest_bot.db /root/backups/invest_bot_$(date +%Y%m%d).db
```

---

## 🚨 Важные моменты

1. **Безопасность:**
   - Меняйте пароль root
   - Настройте firewall
   - Используйте SSH ключи

2. **Мониторинг:**
   - Проверяйте логи регулярно
   - Настройте уведомления об ошибках

3. **Backup:**
   - Регулярно бэкапьте базу данных
   - Сохраняйте конфигурационные файлы

4. **Обновления:**
   - Регулярно обновляйте систему
   - Следите за обновлениями зависимостей

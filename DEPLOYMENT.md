# 🤖 Управление Invest Bot

## 🚀 Быстрый запуск

### Запуск бота в фоне
```bash
./start_bot.sh
```

### Остановка бота
```bash
./stop_bot.sh
```

### Проверка статуса
```bash
./status_bot.sh
```

## 📋 Управление через Screen

### Подключиться к работающему боту
```bash
screen -r invest-bot
```

### Отключиться от сессии (бот продолжит работать)
Нажмите: `Ctrl+A`, затем `D`

### Список всех screen сессий
```bash
screen -ls
```

## 🔄 Автозапуск при перезагрузке

### Добавить в crontab
```bash
crontab -e
```

Добавьте строку:
```
@reboot /root/invest-bot/autostart.sh
```

### Или добавить в ~/.bashrc для автозапуска при входе
```bash
echo "/root/invest-bot/autostart.sh &" >> ~/.bashrc
```

## 📊 Мониторинг

### Просмотр логов бота
```bash
screen -r invest-bot
# или
tail -f autostart.log
```

### Проверка процессов
```bash
ps aux | grep python
```

### Проверка портов (если нужно)
```bash
netstat -tlnp | grep python
```

## 🛠️ Устранение неполадок

### Если бот не отвечает
1. Проверьте статус: `./status_bot.sh`
2. Перезапустите: `./stop_bot.sh && ./start_bot.sh`
3. Проверьте логи: `screen -r invest-bot`

### Если screen сессия потерялась
```bash
screen -ls  # найти номер сессии
screen -r [номер]  # подключиться к сессии
```

### Очистка зависших процессов
```bash
pkill -f "python3.*main.py"
screen -wipe  # очистить мертвые сессии
```

## ⚙️ Настройки производительности

### Ограничение использования памяти
Добавьте в `main.py` перед запуском:
```python
import resource
resource.setrlimit(resource.RLIMIT_AS, (512*1024*1024, 512*1024*1024))  # 512MB
```

### Логирование в файл
Измените в `config.py`:
```python
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()
    ]
)
```

import asyncio
import logging
import aiosqlite
from typing import List, Dict, Optional
from datetime import datetime
import os

logger = logging.getLogger(__name__)

# Определяем путь к базе данных на основе среды
# Railway всегда устанавливает переменную PORT, используем её для определения
is_railway = (
    os.getenv('RAILWAY_ENVIRONMENT') == 'true' or  # Из railway.toml
    os.getenv('PORT') is not None                  # Railway всегда устанавливает PORT
)

if is_railway:
    # Railway с постоянным хранилищем
    DATABASE_PATH = "/app/data/invest_bot.db"
    os.makedirs("/app/data", exist_ok=True)
    logger.info("🚂 Railway: используется постоянное хранилище")
    logger.info(f"🚂 Railway PORT: {os.getenv('PORT', 'Unknown')}")
else:
    # Локальная разработка
    DATABASE_PATH = "invest_bot.db"
    logger.info("🖥️ Локально: используется invest_bot.db")

async def init_db():
    """Инициализация базы данных"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        # Таблица пользователей
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                telegram_id INTEGER UNIQUE NOT NULL,
                username TEXT,
                first_name TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Таблица позиций портфеля
        await db.execute("""
            CREATE TABLE IF NOT EXISTS positions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                ticker TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                avg_price REAL NOT NULL,
                current_price REAL,
                target_price REAL DEFAULT 0,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (telegram_id),
                UNIQUE(user_id, ticker)
            )
        """)

        # Добавляем поле target_price если его нет (миграция)
        try:
            await db.execute("ALTER TABLE positions ADD COLUMN target_price REAL DEFAULT 0")
        except Exception:
            pass  # Поле уже существует

        # Таблица заявок/ордеров
        await db.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                order_id TEXT UNIQUE NOT NULL,
                ticker TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                price REAL NOT NULL,
                order_type TEXT NOT NULL, -- 'BUY' или 'SELL'
                status TEXT DEFAULT 'pending', -- 'pending', 'filled', 'cancelled'
                total_amount REAL NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                executed_at TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (telegram_id)
            )
        """)

        # Таблица истории операций
        await db.execute("""
            CREATE TABLE IF NOT EXISTS history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                operation_type TEXT NOT NULL, -- 'buy', 'sell', 'dividend'
                ticker TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                price REAL NOT NULL,
                total_amount REAL NOT NULL,
                commission REAL DEFAULT 0,
                profit_loss REAL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (telegram_id)
            )
        """)

        # Таблица настроек пользователей
        await db.execute("""
            CREATE TABLE IF NOT EXISTS user_settings (
                user_id INTEGER PRIMARY KEY,
                risk_level TEXT DEFAULT 'medium',
                max_investment_amount REAL DEFAULT 10000,
                auto_invest BOOLEAN DEFAULT FALSE,
                notifications BOOLEAN DEFAULT TRUE,
                daily_market_analysis BOOLEAN DEFAULT TRUE,
                weekly_portfolio_report BOOLEAN DEFAULT TRUE,
                target_price_alerts BOOLEAN DEFAULT TRUE,
                price_updates BOOLEAN DEFAULT FALSE,
                FOREIGN KEY (user_id) REFERENCES users (telegram_id)
            )
        """)

        # Добавляем новые поля уведомлений если их нет (миграция)
        try:
            await db.execute("ALTER TABLE user_settings ADD COLUMN daily_market_analysis BOOLEAN DEFAULT TRUE")
        except Exception:
            pass
        try:
            await db.execute("ALTER TABLE user_settings ADD COLUMN weekly_portfolio_report BOOLEAN DEFAULT TRUE")
        except Exception:
            pass
        try:
            await db.execute("ALTER TABLE user_settings ADD COLUMN target_price_alerts BOOLEAN DEFAULT TRUE")
        except Exception:
            pass
        try:
            await db.execute("ALTER TABLE user_settings ADD COLUMN price_updates BOOLEAN DEFAULT FALSE")
        except Exception:
            pass

        await db.commit()
        logger.info("База данных инициализирована")

async def create_user(telegram_id: int, username: Optional[str] = None, first_name: Optional[str] = None):
    """Создание нового пользователя"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        try:
            await db.execute("""
                INSERT OR IGNORE INTO users (telegram_id, username, first_name)
                VALUES (?, ?, ?)
            """, (telegram_id, username, first_name))

            # Создаем настройки по умолчанию
            await db.execute("""
                INSERT OR IGNORE INTO user_settings (user_id)
                VALUES (?)
            """, (telegram_id,))

            await db.commit()

        except Exception as e:
            logger.error(f"Ошибка при создании пользователя {telegram_id}: {e}")

async def update_user_activity(telegram_id: int):
    """Обновление времени последней активности пользователя"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("""
            UPDATE users SET last_activity = CURRENT_TIMESTAMP
            WHERE telegram_id = ?
        """, (telegram_id,))
        await db.commit()

async def get_user_portfolio(user_id: int) -> List[Dict]:
    """Получение портфеля пользователя"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("""
            SELECT ticker, quantity, avg_price, current_price, last_updated
            FROM positions
            WHERE user_id = ? AND quantity > 0
            ORDER BY ticker
        """, (user_id,))

        rows = await cursor.fetchall()

        portfolio = []
        for row in rows:
            current_price = row['current_price'] or row['avg_price']
            current_value = row['quantity'] * current_price

            portfolio.append({
                'ticker': row['ticker'],
                'quantity': row['quantity'],
                'avg_price': row['avg_price'],
                'current_price': current_price,
                'current_value': current_value,
                'profit_loss': current_value - (row['quantity'] * row['avg_price']),
                'last_updated': row['last_updated']
            })

        return portfolio

async def save_order(user_id: int, ticker: str, quantity: int, price: float,
                    order_type: str, total_amount: float, order_id: Optional[str] = None) -> bool:
    """Сохранение заявки в базу данных"""
    if not order_id:
        order_id = f"ORD_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{ticker}"

    async with aiosqlite.connect(DATABASE_PATH) as db:
        try:
            await db.execute("""
                INSERT INTO orders (user_id, order_id, ticker, quantity, price, order_type, total_amount, status, executed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'filled', CURRENT_TIMESTAMP)
            """, (user_id, order_id, ticker, quantity, price, order_type, total_amount))

            # Обновляем позицию в портфеле
            if order_type.upper() == 'BUY':
                await _update_position_buy(db, user_id, ticker, quantity, price)
            elif order_type.upper() == 'SELL':
                await _update_position_sell(db, user_id, ticker, quantity, price)

            # Добавляем в историю
            await db.execute("""
                INSERT INTO history (user_id, operation_type, ticker, quantity, price, total_amount)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (user_id, order_type.lower(), ticker, quantity, price, total_amount))

            await db.commit()
            return True

        except Exception as e:
            logger.error(f"Ошибка при сохранении заявки: {e}")
            await db.rollback()
            return False

async def _update_position_buy(db, user_id: int, ticker: str, quantity: int, price: float):
    """Обновление позиции при покупке"""
    # Получаем текущую позицию
    cursor = await db.execute("""
        SELECT quantity, avg_price FROM positions
        WHERE user_id = ? AND ticker = ?
    """, (user_id, ticker))

    row = await cursor.fetchone()

    if row:
        # Обновляем существующую позицию
        old_quantity = row[0]
        old_avg_price = row[1]

        new_quantity = old_quantity + quantity
        new_avg_price = ((old_quantity * old_avg_price) + (quantity * price)) / new_quantity

        await db.execute("""
            UPDATE positions
            SET quantity = ?, avg_price = ?, current_price = ?, last_updated = CURRENT_TIMESTAMP
            WHERE user_id = ? AND ticker = ?
        """, (new_quantity, new_avg_price, price, user_id, ticker))
    else:
        # Создаем новую позицию
        await db.execute("""
            INSERT INTO positions (user_id, ticker, quantity, avg_price, current_price)
            VALUES (?, ?, ?, ?, ?)
        """, (user_id, ticker, quantity, price, price))

async def _update_position_sell(db, user_id: int, ticker: str, quantity: int, price: float):
    """Обновление позиции при продаже"""
    cursor = await db.execute("""
        SELECT quantity FROM positions
        WHERE user_id = ? AND ticker = ?
    """, (user_id, ticker))

    row = await cursor.fetchone()

    if row:
        old_quantity = row[0]
        new_quantity = max(0, old_quantity - quantity)

        if new_quantity > 0:
            await db.execute("""
                UPDATE positions
                SET quantity = ?, current_price = ?, last_updated = CURRENT_TIMESTAMP
                WHERE user_id = ? AND ticker = ?
            """, (new_quantity, price, user_id, ticker))
        else:
            # Удаляем позицию если количество стало 0
            await db.execute("""
                DELETE FROM positions
                WHERE user_id = ? AND ticker = ?
            """, (user_id, ticker))

async def get_order_history(user_id: int, limit: int = 50) -> List[Dict]:
    """Получение истории заявок пользователя"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("""
            SELECT order_id, ticker, quantity, price, order_type, total_amount, status, created_at, executed_at
            FROM orders
            WHERE user_id = ?
            ORDER BY created_at DESC
            LIMIT ?
        """, (user_id, limit))

        rows = await cursor.fetchall()

        history = []
        for row in rows:
            history.append({
                'order_id': row['order_id'],
                'ticker': row['ticker'],
                'quantity': row['quantity'],
                'price': row['price'],
                'order_type': row['order_type'],
                'total_amount': row['total_amount'],
                'status': row['status'],
                'date': row['executed_at'] or row['created_at']
            })

        return history

async def get_user_settings(user_id: int) -> Dict:
    """Получение настроек пользователя"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("""
            SELECT risk_level, max_investment_amount, auto_invest, notifications,
                   daily_market_analysis, weekly_portfolio_report, target_price_alerts, price_updates
            FROM user_settings
            WHERE user_id = ?
        """, (user_id,))

        row = await cursor.fetchone()

        if row:
            return {
                'risk_level': row['risk_level'],
                'max_investment_amount': row['max_investment_amount'],
                'auto_invest': row['auto_invest'],
                'notifications': row['notifications'],
                'daily_market_analysis': row['daily_market_analysis'],
                'weekly_portfolio_report': row['weekly_portfolio_report'],
                'target_price_alerts': row['target_price_alerts'],
                'price_updates': row['price_updates']
            }
        else:
            # Возвращаем настройки по умолчанию
            return {
                'risk_level': 'medium',
                'max_investment_amount': 10000,
                'auto_invest': False,
                'notifications': True,
                'daily_market_analysis': True,
                'weekly_portfolio_report': True,
                'target_price_alerts': True,
                'price_updates': False
            }

async def update_user_settings(user_id: int, **settings):
    """Обновление настроек пользователя"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        # Сначала убедимся, что запись пользователя существует
        cursor = await db.execute("SELECT 1 FROM user_settings WHERE user_id = ?", (user_id,))
        user_exists = await cursor.fetchone()
        
        if not user_exists:
            # Создаем запись с настройками по умолчанию
            await db.execute("""
                INSERT INTO user_settings (user_id)
                VALUES (?)
            """, (user_id,))
            await db.commit()
        
        # Формируем запрос динамически
        set_clauses = []
        values = []

        for key, value in settings.items():
            if key in ['risk_level', 'max_investment_amount', 'auto_invest', 'notifications',
                      'daily_market_analysis', 'weekly_portfolio_report', 'target_price_alerts', 'price_updates']:
                set_clauses.append(f"{key} = ?")
                values.append(value)

        if set_clauses:
            query = f"""
                UPDATE user_settings
                SET {', '.join(set_clauses)}
                WHERE user_id = ?
            """
            values.append(user_id)

            await db.execute(query, values)
            await db.commit()
            logger.info(f"Настройки пользователя {user_id} обновлены: {settings}")

async def get_portfolio_statistics(user_id: int) -> Dict:
    """Получение статистики портфеля"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row

        # Общая стоимость портфеля
        cursor = await db.execute("""
            SELECT
                SUM(quantity * current_price) as total_value,
                SUM(quantity * avg_price) as total_cost,
                COUNT(*) as positions_count
            FROM positions
            WHERE user_id = ? AND quantity > 0
        """, (user_id,))

        portfolio_stats = await cursor.fetchone()

        # Статистика операций
        cursor = await db.execute("""
            SELECT
                COUNT(*) as total_operations,
                SUM(CASE WHEN operation_type = 'buy' THEN total_amount ELSE 0 END) as total_invested,
                SUM(CASE WHEN operation_type = 'sell' THEN total_amount ELSE 0 END) as total_sold
            FROM history
            WHERE user_id = ?
        """, (user_id,))

        operations_stats = await cursor.fetchone()

        total_value = portfolio_stats['total_value'] or 0
        total_cost = portfolio_stats['total_cost'] or 0
        profit_loss = total_value - total_cost

        return {
            'total_value': total_value,
            'total_cost': total_cost,
            'profit_loss': profit_loss,
            'profit_loss_percent': (profit_loss / total_cost * 100) if total_cost > 0 else 0,
            'positions_count': portfolio_stats['positions_count'] or 0,
            'total_operations': operations_stats['total_operations'] or 0,
            'total_invested': operations_stats['total_invested'] or 0,
            'total_sold': operations_stats['total_sold'] or 0
        }

async def update_prices_in_portfolio(price_updates: Dict[str, float]):
    """Обновление цен в портфеле"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        for ticker, price in price_updates.items():
            await db.execute("""
                UPDATE positions
                SET current_price = ?, last_updated = CURRENT_TIMESTAMP
                WHERE ticker = ?
            """, (price, ticker))

        await db.commit()
        logger.info(f"Обновлены цены для {len(price_updates)} инструментов")

async def get_users_with_notification_type(notification_type: str) -> list:
    """Получение пользователей с включенным конкретным типом уведомлений"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row

        # Проверяем общие уведомления И конкретный тип
        cursor = await db.execute(f"""
            SELECT user_id, risk_level, max_investment_amount
            FROM user_settings
            WHERE notifications = 1 AND {notification_type} = 1
        """)

        users = await cursor.fetchall()
        return [dict(user) for user in users]

async def get_all_users_with_notifications() -> list:
    """Получение всех пользователей с включенными уведомлениями (для обратной совместимости)"""
    return await get_users_with_notification_type('daily_market_analysis')

async def get_user_portfolio_for_notifications(user_id: int) -> list:
    """Получение портфеля пользователя для уведомлений"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row

        cursor = await db.execute("""
            SELECT ticker, quantity, avg_price, current_price,
                   (current_price - avg_price) * quantity as unrealized_pnl,
                   ((current_price - avg_price) / avg_price) * 100 as return_pct
            FROM positions
            WHERE user_id = ? AND quantity > 0
            ORDER BY ticker
        """, (user_id,))

        positions = await cursor.fetchall()
        return [dict(position) for position in positions]

async def check_target_prices_achieved(user_id: int) -> list:
    """Проверка достижения целевых цен"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row

        # Получаем позиции, где текущая цена достигла или превысила целевую
        cursor = await db.execute("""
            SELECT ticker, quantity, avg_price, current_price, target_price,
                   (current_price - avg_price) * quantity as unrealized_pnl,
                   ((current_price - avg_price) / avg_price) * 100 as return_pct
            FROM positions
            WHERE user_id = ? AND quantity > 0 AND target_price > 0
            AND current_price >= target_price
        """, (user_id,))

        positions = await cursor.fetchall()
        return [dict(position) for position in positions]

async def set_target_price(user_id: int, ticker: str, target_price: float):
    """Установка целевой цены для позиции"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("""
            UPDATE positions
            SET target_price = ?, updated_at = CURRENT_TIMESTAMP
            WHERE user_id = ? AND ticker = ?
        """, (target_price, user_id, ticker))

        await db.commit()

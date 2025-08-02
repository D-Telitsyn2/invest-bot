import logging
import asyncpg
import os
from typing import List, Dict, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

# Получаем URL базы данных из переменных окружения
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    logger.critical("Переменная окружения DATABASE_URL не установлена!")
    raise ValueError("Переменная окружения DATABASE_URL должна быть установлена.")

# Глобальный пул соединений
_pool: Optional[asyncpg.Pool] = None

async def get_pool() -> asyncpg.Pool:
    """Инициализирует и возвращает пул соединений с базой данных."""
    global _pool
    if _pool is None:
        try:
            _pool = await asyncpg.create_pool(DATABASE_URL)
            logger.info("Пул соединений с PostgreSQL успешно создан.")
        except Exception as e:
            logger.error(f"Не удалось создать пул соединений с PostgreSQL: {e}")
            raise
    return _pool

async def close_pool():
    """Закрытие пула соединений."""
    global _pool
    if _pool:
        await _pool.close()
        _pool = None
        logger.info("Пул соединений с PostgreSQL закрыт.")

async def init_db():
    """Инициализация базы данных и создание таблиц, если они не существуют."""
    pool = await get_pool()
    async with pool.acquire() as connection:
        async with connection.transaction():
            # Таблица пользователей
            await connection.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    telegram_id BIGINT UNIQUE NOT NULL,
                    username TEXT,
                    first_name TEXT,
                    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                    last_activity TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Таблица позиций портфеля
            await connection.execute("""
                CREATE TABLE IF NOT EXISTS positions (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL,
                    ticker TEXT NOT NULL,
                    quantity INTEGER NOT NULL,
                    avg_price REAL NOT NULL,
                    current_price REAL,
                    target_price REAL DEFAULT 0,
                    last_updated TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (telegram_id) ON DELETE CASCADE,
                    UNIQUE(user_id, ticker)
                )
            """)
            await connection.execute("ALTER TABLE positions ADD COLUMN IF NOT EXISTS target_price REAL DEFAULT 0")

            # Таблица заявок/ордеров
            await connection.execute("""
                CREATE TABLE IF NOT EXISTS orders (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL,
                    order_id TEXT UNIQUE NOT NULL,
                    ticker TEXT NOT NULL,
                    quantity INTEGER NOT NULL,
                    price REAL NOT NULL,
                    order_type TEXT NOT NULL,
                    status TEXT DEFAULT 'pending',
                    total_amount REAL NOT NULL,
                    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                    executed_at TIMESTAMPTZ,
                    FOREIGN KEY (user_id) REFERENCES users (telegram_id) ON DELETE CASCADE
                )
            """)

            # Таблица истории операций
            await connection.execute("""
                CREATE TABLE IF NOT EXISTS history (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL,
                    operation_type TEXT NOT NULL,
                    ticker TEXT NOT NULL,
                    quantity INTEGER NOT NULL,
                    price REAL NOT NULL,
                    total_amount REAL NOT NULL,
                    commission REAL DEFAULT 0,
                    profit_loss REAL DEFAULT 0,
                    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (telegram_id) ON DELETE CASCADE
                )
            """)

            # Таблица настроек пользователей
            await connection.execute("""
                CREATE TABLE IF NOT EXISTS user_settings (
                    user_id BIGINT PRIMARY KEY,
                    risk_level TEXT DEFAULT 'medium',
                    max_investment_amount REAL DEFAULT 10000,
                    auto_invest BOOLEAN DEFAULT FALSE,
                    notifications BOOLEAN DEFAULT TRUE,
                    daily_market_analysis BOOLEAN DEFAULT TRUE,
                    weekly_portfolio_report BOOLEAN DEFAULT TRUE,
                    target_price_alerts BOOLEAN DEFAULT TRUE,
                    price_updates BOOLEAN DEFAULT FALSE,
                    FOREIGN KEY (user_id) REFERENCES users (telegram_id) ON DELETE CASCADE
                )
            """)
            await connection.execute("ALTER TABLE user_settings ADD COLUMN IF NOT EXISTS daily_market_analysis BOOLEAN DEFAULT TRUE")
            await connection.execute("ALTER TABLE user_settings ADD COLUMN IF NOT EXISTS weekly_portfolio_report BOOLEAN DEFAULT TRUE")
            await connection.execute("ALTER TABLE user_settings ADD COLUMN IF NOT EXISTS target_price_alerts BOOLEAN DEFAULT TRUE")
            await connection.execute("ALTER TABLE user_settings ADD COLUMN IF NOT EXISTS price_updates BOOLEAN DEFAULT FALSE")

        logger.info("База данных успешно инициализирована.")

async def create_user(telegram_id: int, username: Optional[str] = None, first_name: Optional[str] = None):
    """Создание нового пользователя или обновление существующего."""
    pool = await get_pool()
    async with pool.acquire() as connection:
        try:
            await connection.execute("""
                INSERT INTO users (telegram_id, username, first_name)
                VALUES ($1, $2, $3)
                ON CONFLICT (telegram_id) DO UPDATE SET
                    username = EXCLUDED.username,
                    first_name = EXCLUDED.first_name,
                    last_activity = CURRENT_TIMESTAMP
            """, telegram_id, username, first_name)
            await connection.execute("""
                INSERT INTO user_settings (user_id) VALUES ($1) ON CONFLICT (user_id) DO NOTHING
            """, telegram_id)
        except Exception as e:
            logger.error(f"Ошибка при создании/обновлении пользователя {telegram_id}: {e}")

async def update_user_activity(telegram_id: int):
    """Обновление времени последней активности пользователя."""
    pool = await get_pool()
    async with pool.acquire() as connection:
        await connection.execute("UPDATE users SET last_activity = CURRENT_TIMESTAMP WHERE telegram_id = $1", telegram_id)

async def get_user_portfolio(user_id: int) -> List[Dict]:
    """Получение портфеля пользователя."""
    pool = await get_pool()
    async with pool.acquire() as connection:
        rows = await connection.fetch(
            "SELECT * FROM positions WHERE user_id = $1 AND quantity > 0 ORDER BY ticker", user_id
        )
        portfolio = []
        for row in rows:
            r = dict(row)
            current_price = r.get('current_price') or r['avg_price']
            current_value = r['quantity'] * current_price
            r['current_price'] = current_price
            r['current_value'] = current_value
            r['profit_loss'] = current_value - (r['quantity'] * r['avg_price'])
            portfolio.append(r)
        return portfolio

async def save_order(user_id: int, ticker: str, quantity: int, price: float, order_type: str, total_amount: float, order_id: Optional[str] = None) -> bool:
    """Сохранение заявки в базу данных."""
    if not order_id:
        order_id = f"ORD_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{ticker}"
    pool = await get_pool()
    async with pool.acquire() as connection:
        async with connection.transaction():
            try:
                await connection.execute(
                    """
                    INSERT INTO orders (user_id, order_id, ticker, quantity, price, order_type, total_amount, status, executed_at)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, 'filled', CURRENT_TIMESTAMP)
                    """,
                    user_id, order_id, ticker, quantity, price, order_type, total_amount
                )

                # Обновляем позицию в портфеле
                if order_type.upper() == 'BUY':
                    await _update_position_buy(connection, user_id, ticker, quantity, price)
                elif order_type.upper() == 'SELL':
                    await _update_position_sell(connection, user_id, ticker, quantity, price)

                # Добавляем в историю с расчетом P&L
                profit_loss = 0
                if order_type.upper() == 'SELL':
                    # Для продажи рассчитываем прибыль/убыток
                    position = await connection.fetchrow(
                        "SELECT avg_price FROM positions WHERE user_id = $1 AND ticker = $2",
                        user_id, ticker
                    )
                    if position:
                        profit_loss = (price - position['avg_price']) * quantity

                await connection.execute("""
                    INSERT INTO history (user_id, operation_type, ticker, quantity, price, total_amount, profit_loss)
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                """, user_id, order_type.lower(), ticker, quantity, price, total_amount, profit_loss)

                return True
            except asyncpg.UniqueViolationError:
                logger.warning(f"Попытка вставить дублирующуюся заявку с order_id: {order_id}")
                return False
            except Exception as e:
                logger.error(f"Ошибка при сохранении заявки {order_id}: {e}")
                return False

async def _update_position_buy(connection, user_id: int, ticker: str, quantity: int, price: float):
    """Обновление позиции при покупке (в рамках транзакции)."""
    pos = await connection.fetchrow("SELECT quantity, avg_price FROM positions WHERE user_id = $1 AND ticker = $2", user_id, ticker)
    if pos:
        new_quantity = pos['quantity'] + quantity
        new_avg_price = ((pos['avg_price'] * pos['quantity']) + (price * quantity)) / new_quantity
        await connection.execute("UPDATE positions SET quantity = $1, avg_price = $2, current_price = $3, last_updated = CURRENT_TIMESTAMP WHERE user_id = $4 AND ticker = $5", new_quantity, new_avg_price, price, user_id, ticker)
    else:
        await connection.execute("INSERT INTO positions (user_id, ticker, quantity, avg_price, current_price) VALUES ($1, $2, $3, $4, $5)", user_id, ticker, quantity, price, price)

async def _update_position_sell(connection, user_id: int, ticker: str, quantity: int, price: float):
    """Обновление позиции при продаже (в рамках транзакции)."""
    pos = await connection.fetchrow("SELECT quantity FROM positions WHERE user_id = $1 AND ticker = $2", user_id, ticker)
    if pos:
        new_quantity = max(0, pos['quantity'] - quantity)
        if new_quantity > 0:
            await connection.execute("UPDATE positions SET quantity = $1, current_price = $2, last_updated = CURRENT_TIMESTAMP WHERE user_id = $3 AND ticker = $4", new_quantity, price, user_id, ticker)
        else:
            await connection.execute("DELETE FROM positions WHERE user_id = $1 AND ticker = $2", user_id, ticker)

async def add_position(user_id: int, ticker: str, quantity: int, purchase_price: float):
    """Добавление или обновление позиции в портфеле."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            await _update_position_buy(conn, user_id, ticker, quantity, purchase_price)

async def get_position(user_id: int, ticker: str) -> Optional[Dict]:
    """Получение информации о конкретной позиции."""
    pool = await get_pool()
    async with pool.acquire() as connection:
        row = await connection.fetchrow("SELECT * FROM positions WHERE user_id = $1 AND ticker = $2", user_id, ticker)
        return dict(row) if row else None

async def update_position_price(ticker: str, new_price: float):
    """Обновление текущей цены для всех позиций с указанным тикером."""
    pool = await get_pool()
    async with pool.acquire() as connection:
        await connection.execute("UPDATE positions SET current_price = $1, last_updated = CURRENT_TIMESTAMP WHERE ticker = $2", new_price, ticker)

async def get_all_user_settings() -> List[Dict]:
    """Получение настроек всех пользователей."""
    pool = await get_pool()
    async with pool.acquire() as connection:
        rows = await connection.fetch("SELECT * FROM user_settings")
        return [dict(row) for row in rows]

async def get_user_settings(user_id: int) -> Optional[Dict]:
    """Получение настроек конкретного пользователя."""
    pool = await get_pool()
    async with pool.acquire() as connection:
        row = await connection.fetchrow("SELECT * FROM user_settings WHERE user_id = $1", user_id)
        if row:
            return dict(row)
        # Возвращаем настройки по умолчанию, если пользователь не найден в настройках
        return {
            'risk_level': 'medium', 'max_investment_amount': 10000, 'auto_invest': False,
            'notifications': True, 'daily_market_analysis': True, 'weekly_portfolio_report': True,
            'target_price_alerts': True, 'price_updates': False
        }


async def update_user_settings(user_id: int, **kwargs):
    """Обновление настроек пользователя."""
    pool = await get_pool()
    async with pool.acquire() as connection:
        set_clause = ", ".join([f"{key} = ${i+2}" for i, key in enumerate(kwargs.keys())])
        await connection.execute(f"UPDATE user_settings SET {set_clause} WHERE user_id = $1", user_id, *kwargs.values())

async def get_all_tickers() -> List[str]:
    """Получение списка всех уникальных тикеров из портфелей."""
    pool = await get_pool()
    async with pool.acquire() as connection:
        rows = await connection.fetch("SELECT DISTINCT ticker FROM positions WHERE quantity > 0")
        return [row['ticker'] for row in rows]

async def get_order_history(user_id: int, limit: int = 50) -> List[Dict]:
    """Получение истории заявок пользователя."""
    pool = await get_pool()
    async with pool.acquire() as connection:
        rows = await connection.fetch("SELECT * FROM orders WHERE user_id = $1 ORDER BY created_at DESC LIMIT $2", user_id, limit)
        return [dict(row) for row in rows]

async def update_target_price(user_id: int, ticker: str, target_price: float):
    """Установка или обновление целевой цены для позиции."""
    pool = await get_pool()
    async with pool.acquire() as connection:
        await connection.execute(
            "UPDATE positions SET target_price = $1 WHERE user_id = $2 AND ticker = $3",
            target_price, user_id, ticker
        )

async def get_positions_for_alerts() -> List[Dict]:
    """Получение позиций, для которых установлены целевые цены."""
    pool = await get_pool()
    async with pool.acquire() as connection:
        rows = await connection.fetch("""
            SELECT p.user_id, p.ticker, p.current_price, p.target_price
            FROM positions p
            JOIN user_settings s ON p.user_id = s.user_id
            WHERE p.target_price > 0 AND s.target_price_alerts = TRUE
        """)
        return [dict(row) for row in rows]

async def update_prices_in_portfolio(prices: Dict[str, float]):
    """
    Обновляет текущие цены для нескольких тикеров в портфелях пользователей.
    :param prices: Словарь, где ключ - тикер, значение - новая цена.
    """
    if not prices:
        return

    pool = await get_pool()
    async with pool.acquire() as connection:
        async with connection.transaction():
            try:
                for ticker, price in prices.items():
                    await connection.execute(
                        "UPDATE positions SET current_price = $1, last_updated = CURRENT_TIMESTAMP WHERE ticker = $2",
                        price, ticker
                    )
                logger.info(f"Обновлены цены в портфелях для {len(prices)} тикеров.")
            except Exception as e:
                logger.error(f"Ошибка при массовом обновлении цен в портфелях: {e}")

async def get_portfolio_statistics(user_id: int) -> Dict[str, float]:
    """Вычисляет и возвращает статистику по портфелю пользователя."""
    pool = await get_pool()
    async with pool.acquire() as connection:
        stats = await connection.fetchrow("""
            SELECT
                COALESCE(SUM(quantity * avg_price), 0) as total_cost,
                COALESCE(SUM(quantity * COALESCE(current_price, avg_price)), 0) as total_value
            FROM positions
            WHERE user_id = $1 AND quantity > 0
        """, user_id)
        return dict(stats) if stats else {'total_cost': 0, 'total_value': 0}

async def get_user_trading_stats(user_id: int) -> Dict:
    """Получает детальную статистику торговли пользователя"""
    pool = await get_pool()
    async with pool.acquire() as connection:
        # Общая статистика покупок и продаж
        trading_stats = await connection.fetchrow("""
            SELECT
                COUNT(CASE WHEN operation_type = 'buy' THEN 1 END) as total_buys,
                COUNT(CASE WHEN operation_type = 'sell' THEN 1 END) as total_sells,
                COALESCE(SUM(CASE WHEN operation_type = 'buy' THEN total_amount ELSE 0 END), 0) as total_bought,
                COALESCE(SUM(CASE WHEN operation_type = 'sell' THEN total_amount ELSE 0 END), 0) as total_sold,
                COALESCE(SUM(profit_loss), 0) as realized_pnl,
                COALESCE(SUM(commission), 0) as total_commission
            FROM history
            WHERE user_id = $1
        """, user_id)

        # Статистика по портфелю
        portfolio_stats = await connection.fetchrow("""
            SELECT
                COALESCE(SUM(quantity * avg_price), 0) as portfolio_cost,
                COALESCE(SUM(quantity * COALESCE(current_price, avg_price)), 0) as portfolio_value,
                COUNT(*) as positions_count
            FROM positions
            WHERE user_id = $1 AND quantity > 0
        """, user_id)

        # Топ прибыльных позиций
        top_positions = await connection.fetch("""
            SELECT
                ticker,
                quantity,
                avg_price,
                COALESCE(current_price, avg_price) as current_price,
                (COALESCE(current_price, avg_price) - avg_price) * quantity as unrealized_pnl,
                CASE
                    WHEN avg_price > 0 THEN ((COALESCE(current_price, avg_price) - avg_price) / avg_price) * 100
                    ELSE 0
                END as return_pct
            FROM positions
            WHERE user_id = $1 AND quantity > 0
            ORDER BY unrealized_pnl DESC
            LIMIT 5
        """, user_id)

        # История прибыльных сделок
        profitable_trades = await connection.fetch("""
            SELECT ticker, profit_loss, created_at
            FROM history
            WHERE user_id = $1 AND operation_type = 'sell' AND profit_loss > 0
            ORDER BY profit_loss DESC
            LIMIT 5
        """, user_id)

        result = {
            'trading': dict(trading_stats) if trading_stats else {},
            'portfolio': dict(portfolio_stats) if portfolio_stats else {},
            'top_positions': [dict(row) for row in top_positions],
            'profitable_trades': [dict(row) for row in profitable_trades]
        }

        # Вычисляем дополнительные метрики
        if result['portfolio']['portfolio_cost'] > 0:
            unrealized_pnl = result['portfolio']['portfolio_value'] - result['portfolio']['portfolio_cost']
            result['portfolio']['unrealized_pnl'] = unrealized_pnl
            result['portfolio']['unrealized_return_pct'] = (unrealized_pnl / result['portfolio']['portfolio_cost']) * 100

        # Общий P&L (реализованный + нереализованный)
        total_pnl = result['trading'].get('realized_pnl', 0) + result['portfolio'].get('unrealized_pnl', 0)
        result['total_pnl'] = total_pnl

        return result

async def get_users_with_notification_type(notification_type: str) -> List[Dict]:
    """
    Получает список пользователей, у которых включен определенный тип уведомлений.
    """
    pool = await get_pool()
    async with pool.acquire() as connection:
        # Используем pg_get_expr для получения значения по умолчанию, если колонка не существует
        query = f"""
            SELECT s.user_id, u.username, u.first_name, s.risk_level, s.max_investment_amount
            FROM user_settings s
            JOIN users u ON s.user_id = u.telegram_id
            WHERE s.{notification_type} = TRUE
        """
        try:
            rows = await connection.fetch(query)
            logger.info(f"Найдено {len(rows)} пользователей с включенным {notification_type}")
            result = [dict(row) for row in rows]
            for user in result:
                logger.info(f"Пользователь: {user['user_id']} ({user.get('username', 'no_username')})")
            return result
        except asyncpg.exceptions.UndefinedColumnError:
            logger.warning(f"Колонка {notification_type} не найдена в user_settings. Возвращен пустой список.")
            return []

async def get_user_portfolio_for_notifications(user_id: int) -> List[Dict]:
    """
    Получение портфеля пользователя для отправки уведомлений.
    Включает расчет нереализованной прибыли и процента доходности.
    """
    pool = await get_pool()
    async with pool.acquire() as connection:
        rows = await connection.fetch("""
            SELECT
                ticker,
                quantity,
                avg_price,
                COALESCE(current_price, avg_price) as current_price,
                (COALESCE(current_price, avg_price) - avg_price) * quantity as unrealized_pnl,
                CASE
                    WHEN avg_price > 0 THEN ((COALESCE(current_price, avg_price) - avg_price) / avg_price) * 100
                    ELSE 0
                END as return_pct
            FROM positions
            WHERE user_id = $1 AND quantity > 0
        """, user_id)
        return [dict(row) for row in rows]

async def check_target_prices_achieved(user_id: int) -> List[Dict]:
    """
    Проверяет, достигнуты ли целевые цены для позиций пользователя.
    Возвращает список позиций, где цена достигла или превысила целевую.
    """
    pool = await get_pool()
    async with pool.acquire() as connection:
        rows = await connection.fetch("""
            SELECT
                p.ticker,
                p.target_price,
                p.current_price,
                (p.current_price - p.avg_price) * p.quantity as unrealized_pnl,
                CASE
                    WHEN p.avg_price > 0 THEN ((p.current_price - p.avg_price) / p.avg_price) * 100
                    ELSE 0
                END as return_pct
            FROM positions p
            WHERE p.user_id = $1
              AND p.target_price > 0
              AND p.current_price >= p.target_price
        """, user_id)
        return [dict(row) for row in rows]

#!/usr/bin/env python3
"""
Модуль для получения реальных данных о российских акциях
Теперь используется только для получения цен с MOEX, без хардкода списков компаний
"""

import aiohttp
import asyncio
import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

class RealMarketData:
    """Класс для получения реальных данных о рынке"""

    def __init__(self):
        self.session = None

        # Убираем статический список - теперь AI будет составлять список сам
        # Оставляем только базовые сектора для справки
        self.sectors_info = {
            "Банки": "Крупнейшие российские банки",
            "Энергетика": "Нефтегазовые компании",
            "IT": "Технологические компании",
            "Металлургия": "Металлургические холдинги",
            "Телеком": "Телекоммуникационные операторы",
            "Ритейл": "Торговые сети",
            "Авиация": "Авиакомпании",
            "Логистика": "Транспортные компании"
        }

    async def get_session(self):
        """Получение HTTP сессии"""
        if not self.session:
            self.session = aiohttp.ClientSession()
        return self.session

    async def close_session(self):
        """Закрытие HTTP сессии"""
        if self.session:
            await self.session.close()
            self.session = None

    async def get_moex_price(self, ticker: str) -> Optional[float]:
        """Получение актуальной цены с MOEX API"""
        try:
            session = await self.get_session()
            # Используем marketdata эндпоинт для получения актуальных торговых данных
            url = f"https://iss.moex.com/iss/engines/stock/markets/shares/boards/TQBR/securities/{ticker}.json?iss.meta=off&iss.only=marketdata,securities&marketdata.columns=SECID,LAST,OPEN,HIGH,LOW,CLOSEPRICE,UPDATETIME,TRADINGSTATUS&securities.columns=SECID,PREVPRICE,PREVDATE"

            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()

                    # Пытаемся получить текущую цену из marketdata
                    marketdata = data.get('marketdata', {}).get('data', [])
                    if marketdata and len(marketdata) > 0:
                        row = marketdata[0]
                        # row[1] = LAST (последняя цена)
                        if len(row) > 1 and row[1] is not None:
                            price = float(row[1])
                            update_time = row[6] if len(row) > 6 else "неизвестно"
                            trading_status = row[7] if len(row) > 7 else "неизвестно"
                            logger.info(f"✅ Получена цена {ticker}: {price} ₽ (обновлено: {update_time}, статус: {trading_status})")
                            return price

                        # Если LAST нет, берем CLOSEPRICE (цена закрытия)
                        elif len(row) > 5 and row[5] is not None:
                            price = float(row[5])
                            logger.info(f"⚠️ Получена цена закрытия {ticker}: {price} ₽")
                            return price

                    # Если marketdata не дал результат, берем из securities (цена предыдущего дня)
                    securities_data = data.get('securities', {}).get('data', [])
                    if securities_data and len(securities_data) > 0:
                        row = securities_data[0]
                        if len(row) > 1 and row[1] is not None:
                            price = float(row[1])
                            prev_date = row[2] if len(row) > 2 else "неизвестно"
                            logger.info(f"📊 Получена цена предыдущего дня {ticker}: {price} ₽ (дата: {prev_date})")
                            return price
                else:
                    logger.warning(f"Ошибка MOEX API {response.status} для {ticker}")

        except Exception as e:
            logger.warning(f"Ошибка получения цены {ticker} с MOEX: {e}")

        return None

    async def get_multiple_moex_prices(self, tickers: list) -> Dict[str, float]:
        """Получение цен для нескольких тикеров одновременно"""
        try:
            prices = {}

            # Получаем цены параллельно
            tasks = [self.get_moex_price(ticker) for ticker in tickers]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for ticker, result in zip(tickers, results):
                if isinstance(result, float):
                    prices[ticker] = result
                else:
                    logger.warning(f"Не удалось получить цену для {ticker}")

            return prices

        except Exception as e:
            logger.error(f"Ошибка при получении множественных цен: {e}")
            return {}

    async def get_moex_price_with_info(self, ticker: str) -> Dict:
        """Получение цены с дополнительной информацией о времени и статусе торгов"""
        try:
            session = await self.get_session()
            url = f"https://iss.moex.com/iss/engines/stock/markets/shares/boards/TQBR/securities/{ticker}.json?iss.meta=off&iss.only=marketdata,securities&marketdata.columns=SECID,LAST,OPEN,HIGH,LOW,CLOSEPRICE,UPDATETIME,TRADINGSTATUS&securities.columns=SECID,PREVPRICE,PREVDATE"

            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    result = {"ticker": ticker, "price": None, "status": "unknown", "update_time": None, "is_current": False}

                    # Проверяем marketdata
                    marketdata = data.get('marketdata', {}).get('data', [])
                    if marketdata and len(marketdata) > 0:
                        row = marketdata[0]
                        if len(row) > 1 and row[1] is not None:
                            result["price"] = float(row[1])
                            result["update_time"] = row[6] if len(row) > 6 else None
                            result["trading_status"] = row[7] if len(row) > 7 else None
                            result["is_current"] = True
                            result["status"] = "live"
                            return result
                        elif len(row) > 5 and row[5] is not None:
                            result["price"] = float(row[5])
                            result["status"] = "close_price"
                            return result

                    # Fallback к securities
                    securities_data = data.get('securities', {}).get('data', [])
                    if securities_data and len(securities_data) > 0:
                        row = securities_data[0]
                        if len(row) > 1 and row[1] is not None:
                            result["price"] = float(row[1])
                            result["update_time"] = row[2] if len(row) > 2 else None
                            result["status"] = "prev_day"
                            return result

                    return result
                else:
                    return {"ticker": ticker, "price": None, "status": "api_error", "update_time": None, "is_current": False}

        except Exception as e:
            logger.warning(f"Ошибка получения информации о цене {ticker}: {e}")
            return {"ticker": ticker, "price": None, "status": "error", "update_time": None, "is_current": False}

    def get_sectors_info(self) -> dict:
        """Получение информации о секторах для AI"""
        return self.sectors_info

    def is_trading_hours(self) -> bool:
        """Проверка, идут ли сейчас торги на MOEX"""
        from datetime import datetime, time

        try:
            # Используем UTC+3 (московское время)
            now = datetime.now()
            current_time = now.time()
            weekday = now.weekday()  # 0 = понедельник, 6 = воскресенье

            if weekday >= 5:  # выходные
                return False

            # Основные торги 10:00-18:40 (по московскому времени)
            if time(10, 0) <= current_time <= time(18, 40):
                return True

            # Вечерние торги 19:05-23:50
            if time(19, 5) <= current_time <= time(23, 50):
                return True

            return False

        except Exception as e:
            logger.warning(f"Ошибка проверки времени торгов: {e}")
            return False

# Глобальный экземпляр
market_data = RealMarketData()

async def get_diverse_investment_ideas(count: int = 5) -> List[Dict]:
    """
    Получение инвестиционных идей полностью через AI без хардкода
    AI сам выбирает компании и составляет анализ
    """
    try:
        # Больше не используем статический список - все делает AI
        # Эта функция теперь просто возвращает пустой список
        # Весь анализ перенесен в gpt_client.py
        logger.info("get_diverse_investment_ideas больше не используется - анализ полностью через AI")
        return []

    except Exception as e:
        logger.error(f"Ошибка в get_diverse_investment_ideas: {e}")
        return []

if __name__ == "__main__":
    async def test():
        print("🔍 Тест работы с MOEX API:")
        # Тестируем получение цены для известной акции
        real_price = await market_data.get_moex_price("SBER")
        if real_price:
            print(f"✅ Цена SBER с MOEX: {real_price} ₽")
        else:
            print("❌ Не удалось получить цену SBER")

        await market_data.close_session()

    asyncio.run(test())

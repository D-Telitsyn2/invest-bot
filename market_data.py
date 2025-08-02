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
            # Используем более надежный эндпоинт для получения цен
            url = f"https://iss.moex.com/iss/engines/stock/markets/shares/boards/TQBR/securities/{ticker}.json?iss.meta=off&iss.only=securities&securities.columns=SECID,LAST,PREVPRICE,CHANGE,CHANGEPRCNT"

            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    securities_data = data.get('securities', {}).get('data', [])
                    if securities_data and len(securities_data) > 0:
                        row = securities_data[0]
                        # row[1] = LAST (последняя цена)
                        if len(row) > 1 and row[1] is not None:
                            price = float(row[1])
                            logger.info(f"✅ Получена актуальная цена {ticker}: {price} ₽")
                            return price
                        # Если LAST нет, берем PREVPRICE
                        elif len(row) > 2 and row[2] is not None:
                            price = float(row[2])
                            logger.info(f"⚠️ Получена цена закрытия {ticker}: {price} ₽")
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

    async def get_realistic_price(self, ticker: str) -> Optional[float]:
        """Получение реалистичной цены только с MOEX API"""
        # Пытаемся получить реальную цену
        real_price = await self.get_moex_price(ticker)
        if real_price:
            return real_price

        # Если не получилось, возвращаем None
        # AI будет использовать свои актуальные данные
        return None

    def get_sectors_info(self) -> dict:
        """Получение информации о секторах для AI"""
        return self.sectors_info

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

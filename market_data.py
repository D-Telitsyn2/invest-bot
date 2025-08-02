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
        """Получение цены с MOEX API"""
        try:
            session = await self.get_session()
            url = f"https://iss.moex.com/iss/engines/stock/markets/shares/securities/{ticker}.json"

            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    # Парсим ответ MOEX
                    securities = data.get('securities', {}).get('data', [])
                    if securities:
                        # Ищем текущую цену
                        for row in securities:
                            if len(row) > 3 and row[3] is not None:  # LAST цена
                                return float(row[3])

        except Exception as e:
            logger.warning(f"Ошибка получения цены {ticker} с MOEX: {e}")

        return None

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

import asyncio
import json
import logging
from typing import List, Dict
import openai
import os
from dotenv import load_dotenv
from market_data import get_diverse_investment_ideas, market_data

load_dotenv()

logger = logging.getLogger(__name__)

class GPTClient:
    def __init__(self):
        self.api_key = os.getenv('OPENAI_API_KEY')
        if not self.api_key:
            logger.warning("OpenAI API ключ не найден - используется демо режим")
            self.client = None
        else:
            self.client = openai.AsyncOpenAI(
                api_key=self.api_key
            )

    async def get_investment_ideas(self, budget: float = 10000, risk_level: str = "medium") -> List[Dict]:
        """
        Получение инвестиционных идей от GPT-4

        Args:
            budget: Бюджет для инвестирования
            risk_level: Уровень риска (low, medium, high)

        Returns:
            List[Dict]: Список инвестиционных идей
        """
        try:
            # Если нет API ключа, используем улучшенные данные
            if not self.client:
                logger.info("Используются улучшенные данные для инвестиционных идей")
                return await self._get_fallback_ideas()

            prompt = f"""
Ты - опытный инвестиционный аналитик. Проанализируй текущую ситуацию на российском фондовом рынке и предложи 3-5 инвестиционных идей.

Параметры:
- Бюджет: {budget} рублей
- Уровень риска: {risk_level}
- Рынок: Российские акции (MOEX)

Для каждой идеи укажи:
1. Тикер акции
2. Рекомендуемое действие (BUY/SELL)
3. Текущую примерную цену
4. Целевую цену
5. Краткое обоснование (1-2 предложения)

Формат ответа должен быть JSON массивом:
[
  {{
    "ticker": "SBER",
    "action": "BUY",
    "price": 280.50,
    "target_price": 320.00,
    "reasoning": "Сбербанк показывает стабильный рост прибыли на фоне высоких процентных ставок"
  }}
]

Учитывай только ликвидные российские акции, торгующиеся на MOEX.
"""

            response = await self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "Ты опытный инвестиционный аналитик российского рынка."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=1500,
                temperature=0.7
            )

            content = response.choices[0].message.content.strip()

            # Парсим JSON ответ
            start_idx = content.find('[')
            end_idx = content.rfind(']') + 1

            if start_idx != -1 and end_idx != -1:
                json_str = content[start_idx:end_idx]
                ideas = json.loads(json_str)
                return ideas
            else:
                logger.error("GPT не вернул корректный JSON")
                return await self._get_fallback_ideas()

        except Exception as e:
            logger.error(f"Ошибка при получении идей от GPT: {e}")
            return await self._get_fallback_ideas()

    async def _get_fallback_ideas(self) -> List[Dict]:
        """Улучшенные резервные инвестиционные идеи с реальными данными"""
        try:
            # Получаем разнообразные идеи с реальными ценами
            return await get_diverse_investment_ideas(count=4)
        except Exception as e:
            logger.error(f"Ошибка получения улучшенных идей: {e}")
            # В крайнем случае возвращаем базовые идеи
            return [
                {
                    "ticker": "SBER",
                    "action": "BUY",
                    "price": 280.50,
                    "target_price": 320.00,
                    "reasoning": "Крупнейший банк России с стабильными показателями"
                }
            ]

    async def analyze_stock(self, ticker: str) -> Dict:
        """
        Анализ конкретной акции

        Args:
            ticker: Тикер акции

        Returns:
            Dict: Анализ акции
        """
        try:
            # Если нет API ключа, используем заглушки
            if not self.client:
                logger.info(f"Используются демо-данные для анализа {ticker}")
                return {
                    "ticker": ticker,
                    "recommendation": "HOLD",
                    "target_price": 300.0,
                    "risk_level": "medium",
                    "analysis": f"Демо-анализ для {ticker}. Компания показывает стабильные результаты.",
                    "pros": ["Стабильная выручка", "Хорошие дивиденды"],
                    "cons": ["Высокая волатильность", "Зависимость от макроэкономики"]
                }

            prompt = f"""
Проанализируй акцию {ticker} на российском рынке.

Предоставь анализ в формате JSON:
{{
  "ticker": "{ticker}",
  "recommendation": "BUY/HOLD/SELL",
  "target_price": 0.0,
  "risk_level": "low/medium/high",
  "analysis": "Подробный анализ компании и перспектив",
  "pros": ["плюс 1", "плюс 2"],
  "cons": ["минус 1", "минус 2"]
}}
"""

            response = await self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "Ты опытный аналитик российского фондового рынка."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=1000,
                temperature=0.5
            )

            content = response.choices[0].message.content.strip()

            start_idx = content.find('{')
            end_idx = content.rfind('}') + 1

            if start_idx != -1 and end_idx != -1:
                json_str = content[start_idx:end_idx]
                analysis = json.loads(json_str)
                return analysis
            else:
                return {"error": "Не удалось получить анализ"}

        except Exception as e:
            logger.error(f"Ошибка при анализе акции {ticker}: {e}")
            return {"error": f"Ошибка анализа: {str(e)}"}

# Глобальный экземпляр клиента
gpt_client = GPTClient()

async def get_investment_ideas(budget: float = 10000, risk_level: str = "medium") -> List[Dict]:
    """Обертка для получения инвестиционных идей"""
    return await gpt_client.get_investment_ideas(budget, risk_level)

async def analyze_stock(ticker: str) -> Dict:
    """Обертка для анализа акции"""
    return await gpt_client.analyze_stock(ticker)

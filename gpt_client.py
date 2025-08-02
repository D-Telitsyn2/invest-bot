import asyncio
import json
import logging
from typing import List, Dict
import aiohttp
import os
from dotenv import load_dotenv
from market_data import get_diverse_investment_ideas, market_data, RealMarketData

load_dotenv()

logger = logging.getLogger(__name__)

class XAIClient:
    def __init__(self):
        self.api_key = os.getenv('XAI_API_KEY')
        self.base_url = "https://api.x.ai/v1/chat/completions"
        # Попробуем разные модели xAI в порядке приоритета
        self.models = ["grok-2-1212", "grok-2", "grok-1", "grok-beta"]
        if not self.api_key:
            logger.warning("xAI API ключ не найден - используется демо режим")
        else:
            logger.info("xAI (Grok) клиент инициализирован")

    async def _make_request(self, messages: list, max_tokens: int = 1500, temperature: float = 0.7) -> dict:
        """Делает запрос к xAI API с автоматическим переключением моделей"""

        for model in self.models:
            try:
                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                }

                payload = {
                    "model": model,
                    "messages": messages,
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                    "stream": False
                }

                async with aiohttp.ClientSession() as session:
                    async with session.post(self.base_url, headers=headers, json=payload) as response:
                        if response.status == 200:
                            data = await response.json()
                            logger.info(f"✅ Успешный запрос с моделью {model}")
                            return data
                        elif response.status == 404:
                            logger.warning(f"❌ Модель {model} недоступна, пробуем следующую...")
                            continue
                        else:
                            error_text = await response.text()
                            logger.error(f"xAI API error {response.status} с моделью {model}: {error_text}")
                            continue

            except Exception as e:
                logger.error(f"Ошибка с моделью {model}: {e}")
                continue

        # Если все модели не работают
        raise Exception("Все модели xAI недоступны")

    async def get_investment_ideas(self, budget: float = 10000, risk_level: str = "medium") -> List[Dict]:
        """
        Получение инвестиционных идей от xAI Grok

        Args:
            budget: Бюджет для инвестирования
            risk_level: Уровень риска (low, medium, high)

        Returns:
            List[Dict]: Список инвестиционных идей
        """
        try:
            # Если нет API ключа, используем улучшенные данные
            if not self.api_key:
                logger.info("Используются улучшенные данные для инвестиционных идей")
                return await self._get_fallback_ideas()

            prompt = f"""
Ты - опытный инвестиционный аналитик российского рынка. Проанализируй текущую ситуацию на MOEX и предложи 3-5 конкретных инвестиционных идей.

Параметры:
- Бюджет: {budget} рублей
- Уровень риска: {risk_level}
- Рынок: Российские акции (MOEX)

Для каждой идеи укажи:
1. Тикер акции (ТОЛЬКО реальные российские тикеры)
2. Рекомендуемое действие (BUY/SELL/HOLD)
3. Текущую примерную цену
4. Целевую цену
5. Краткое обоснование (1-2 предложения)

ВАЖНО: Используй только реальные российские тикеры: SBER, GAZP, LUKOIL, YNDX, VTB, NVTK, TCSG, GMKN, NLMK, MTSS, MAIL, OZON, FIVE, MGNT, AFLT, FESH, ROSN, MAGN, CHMF, RTKM и другие ликвидные акции MOEX.

Формат ответа - строго JSON массив:
[
  {{
    "ticker": "SBER",
    "action": "BUY",
    "price": 280.50,
    "target_price": 320.00,
    "reasoning": "Сбербанк показывает стабильный рост прибыли на фоне высоких процентных ставок"
  }}
]
"""

            messages = [
                {"role": "system", "content": "Ты профессиональный инвестиционный аналитик российского рынка с 15+ лет опыта. Знаешь все о MOEX и российских компаниях."},
                {"role": "user", "content": prompt}
            ]

            data = await self._make_request(messages, max_tokens=1500, temperature=0.7)
            content = data['choices'][0]['message']['content'].strip()

            # Парсим JSON ответ
            start_idx = content.find('[')
            end_idx = content.rfind(']') + 1

            if start_idx != -1 and end_idx != -1:
                json_str = content[start_idx:end_idx]
                ideas = json.loads(json_str)
                logger.info(f"✅ xAI Grok вернул {len(ideas)} инвестиционных идей")
                return ideas
            else:
                logger.error("xAI не вернул корректный JSON")
                return await self._get_fallback_ideas()

        except json.JSONDecodeError as e:
            logger.error(f"Ошибка парсинга JSON от xAI: {e}")
            return await self._get_fallback_ideas()
        except Exception as e:
            logger.error(f"Ошибка при получении идей от xAI: {e}")
            return await self._get_fallback_ideas()

    async def _get_fallback_ideas(self) -> List[Dict]:
        """Улучшенные резервные инвестиционные идеи с реальными данными"""
        try:
            # Получаем разнообразные идеи с реальными ценами
            return await get_diverse_investment_ideas(count=4)
        except Exception as e:
            logger.error(f"Ошибка получения улучшенных идей: {e}")
            # В крайнем случае используем минимальный fallback с реальными тикерами
            logger.warning("Используется минимальный fallback с реальными данными")

            # Получаем реальные цены хотя бы для базовых акций
            try:
                market = RealMarketData()
                fallback_stocks = ["SBER", "GAZP", "YNDX"]
                ideas = []

                for ticker in fallback_stocks:
                    price = await market.get_realistic_price(ticker)
                    stock_info = market.russian_stocks.get(ticker, {})

                    ideas.append({
                        "ticker": ticker,
                        "action": "HOLD",
                        "price": price,
                        "target_price": price * 1.15,  # +15% цель
                        "reasoning": f"{stock_info.get('name', ticker)} - стабильная российская компания с хорошими перспективами"
                    })

                await market.close_session()
                return ideas

            except Exception as fallback_error:
                logger.error(f"Критическая ошибка fallback: {fallback_error}")
                # Самый крайний случай - возвращаем пустой список
                return []

    async def analyze_stock(self, ticker: str) -> Dict:
        """
        Анализ конкретной акции через xAI Grok

        Args:
            ticker: Тикер акции

        Returns:
            Dict: Анализ акции
        """
        try:
            # Если нет API ключа, используем заглушки
            if not self.api_key:
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
Проанализируй акцию {ticker} на российском рынке MOEX. Дай профессиональный инвестиционный анализ.

Предоставь анализ в формате JSON:
{{
  "ticker": "{ticker}",
  "recommendation": "BUY/HOLD/SELL",
  "target_price": 0.0,
  "risk_level": "low/medium/high",
  "analysis": "Подробный анализ компании, её финансового состояния и перспектив",
  "pros": ["плюс 1", "плюс 2", "плюс 3"],
  "cons": ["минус 1", "минус 2"]
}}

Учитывай:
- Текущую макроэкономическую ситуацию в России
- Финансовые показатели компании
- Отраслевые тренды и перспективы
- Геополитические факторы
- Технический анализ
"""

            messages = [
                {"role": "system", "content": "Ты топовый инвестиционный аналитик российского фондового рынка с экспертизой в MOEX и российских компаниях."},
                {"role": "user", "content": prompt}
            ]

            data = await self._make_request(messages, max_tokens=1200, temperature=0.5)
            content = data['choices'][0]['message']['content'].strip()

            start_idx = content.find('{')
            end_idx = content.rfind('}') + 1

            if start_idx != -1 and end_idx != -1:
                json_str = content[start_idx:end_idx]
                analysis = json.loads(json_str)
                logger.info(f"✅ xAI Grok проанализировал {ticker}")
                return analysis
            else:
                return {"error": "Не удалось получить анализ"}

        except Exception as e:
            logger.error(f"Ошибка при анализе акции {ticker}: {e}")
            return {"error": f"Ошибка анализа: {str(e)}"}

# Глобальный экземпляр клиента
xai_client = XAIClient()

async def get_investment_ideas(budget: float = 10000, risk_level: str = "medium") -> List[Dict]:
    """Обертка для получения инвестиционных идей"""
    return await xai_client.get_investment_ideas(budget, risk_level)

async def analyze_stock(ticker: str) -> Dict:
    """Обертка для анализа акции"""
    return await xai_client.analyze_stock(ticker)

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
        self.models = [
            "grok-4-0709",
            "grok-3-mini-fast",
            "grok-3-mini",
            "grok-3-fast",
            "grok-3",
            "grok-2-vision-1212",
            "grok-2-image-1212",
            "grok-2-1212"
        ]
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
        Получение инвестиционных идей с реальными ценами MOEX

        Args:
            budget: Бюджет для инвестирования
            risk_level: Уровень риска (low, medium, high)

        Returns:
            List[Dict]: Список инвестиционных идей или пустой список если ошибка
        """
        if not self.api_key:
            logger.error("xAI API ключ не настроен")
            return []

        try:
            # Создаем детальное описание стратегии на основе уровня риска
            risk_strategies = {
                'low': {
                    'description': 'Консервативная стратегия',
                    'focus': 'дивидендные аристократы, государственные и крупные частные банки, нефтегазовый сектор с стабильными дивидендами',
                    'target_return': '5-15% годовых',
                    'examples': 'SBER, LKOH, GAZP, TATN'
                },
                'medium': {
                    'description': 'Сбалансированная стратегия',
                    'focus': 'микс из надежных "голубых фишек" и растущих компаний второго эшелона',
                    'target_return': '15-30% годовых',
                    'examples': 'SBER, YNDX, NLMK, ROSN, MGNT'
                },
                'high': {
                    'description': 'Агрессивная стратегия',
                    'focus': 'высокотехнологичные компании, второй эшелон с высоким потенциалом роста, волатильные активы',
                    'target_return': '30-100%+ годовых',
                    'examples': 'OZON, HEADHUNTER, AFLT, QIWI, растущие IT и биотех'
                }
            }

            strategy = risk_strategies.get(risk_level, risk_strategies['medium'])

            # Сначала получаем идеи от AI
            prompt = f"""
Ты - ведущий инвестиционный аналитик российского рынка. Проанализируй MOEX и подбери 8-12 разнообразных инвестиционных идей.

СТРАТЕГИЯ: {strategy['description']}
ФОКУС: {strategy['focus']}
ЦЕЛЕВАЯ ДОХОДНОСТЬ: {strategy['target_return']}

ПАРАМЕТРЫ:
- Бюджет: {budget:,.0f} рублей
- Уровень риска: {risk_level.upper()}
- Рынок: Российские акции (MOEX)

ВАЖНО: Подбери РАЗНООБРАЗНЫЕ компании из разных секторов для диверсификации.

ТРЕБОВАНИЯ ПО РИСКУ:
{f"- Выбирай ТОЛЬКО надежные дивидендные компании с долгой историей" if risk_level == 'low' else ""}
{f"- Микс из стабильных лидеров (70%) и перспективных компаний (30%)" if risk_level == 'medium' else ""}
{f"- Акцент на высокий потенциал роста, допустима повышенная волатильность" if risk_level == 'high' else ""}

ОТВЕТ ТОЛЬКО В JSON ФОРМАТЕ:
[
  {{
    "ticker": "SBER",
    "action": "BUY",
    "target_price": 320.0,
    "target_timeframe": "3-6 месяцев",
    "reasoning": "Краткое обоснование с учетом уровня риска {risk_level}"
  }}
]
"""

            messages = [
                {"role": "system", "content": "Ты инвестиционный аналитик российского рынка. Отвечай ТОЛЬКО чистым JSON массивом без дополнительного текста. Анализируй реальные компании MOEX и ОБЯЗАТЕЛЬНО указывай реалистичные целевые цены на основе фундментального и технического анализа."},
                {"role": "user", "content": prompt}
            ]

            data = await self._make_request(messages, max_tokens=1200, temperature=0.3)
            content = data['choices'][0]['message']['content'].strip()

            # Парсим JSON ответ
            start_idx = content.find('[')
            end_idx = content.rfind(']') + 1

            if start_idx != -1 and end_idx != -1:
                json_str = content[start_idx:end_idx]
                ideas = json.loads(json_str)

                # Получаем реальные цены с MOEX
                from market_data import market_data
                tickers = [idea['ticker'] for idea in ideas]
                real_prices = await market_data.get_multiple_moex_prices(tickers)

                # Добавляем реальные цены к идеям
                for idea in ideas:
                    ticker = idea['ticker']
                    if ticker in real_prices:
                        idea['price'] = real_prices[ticker]
                        logger.info(f"✅ Добавлена реальная цена для {ticker}: {real_prices[ticker]} ₽")
                    else:
                        # Если не удалось получить цену, используем примерную
                        idea['price'] = idea.get('target_price', 100.0) * 0.9
                        logger.warning(f"⚠️ Используется примерная цена для {ticker}")

                logger.info(f"✅ xAI Grok вернул {len(ideas)} инвестиционных идей с реальными ценами")
                return ideas
            else:
                logger.error("xAI не вернул корректный JSON")
                return []

        except json.JSONDecodeError as e:
            logger.error(f"Ошибка парсинга JSON от xAI: {e}")
            return []
        except Exception as e:
            logger.error(f"Ошибка при получении идей от xAI: {e}")
            return []

    async def analyze_stock(self, ticker: str) -> Dict:
        """
        Анализ конкретной акции

        Args:
            ticker: Тикер акции

        Returns:
            Dict: Анализ акции или ошибка
        """
        if not self.api_key:
            logger.error("xAI API ключ не настроен")
            return {"error": "API ключ не настроен"}

        try:
            prompt = f"""
Проанализируй акцию {ticker} на российском рынке MOEX. Дай профессиональный инвестиционный анализ.

Предоставь анализ в формате JSON:
{{
  "ticker": "{ticker}",
  "recommendation": "BUY/HOLD/SELL",
  "target_price": 0.0,
  "risk_level": "low/medium/high",
  "analysis": "Подробный анализ компании",
  "pros": ["плюс 1", "плюс 2"],
  "cons": ["минус 1", "минус 2"]
}}
"""

            messages = [
                {"role": "system", "content": "Ты топовый инвестиционный аналитик российского фондового рынка."},
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

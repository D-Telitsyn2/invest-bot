import asyncio
import logging
from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from gpt_client import XAIClient
from database import get_user_portfolio, save_order, get_order_history, create_user, update_user_activity, get_user_settings, update_user_settings, get_user_trading_stats

logger = logging.getLogger(__name__)

# Состояния FSM
class InvestmentStates(StatesGroup):
    waiting_for_confirmation = State()
    waiting_for_amount = State()
    waiting_for_risk_level = State()
    waiting_for_max_amount = State()
    waiting_for_custom_price = State()  # Новое состояние для ввода пользовательской цены
    waiting_for_target_ticker = State()  # Ожидание тикера для установки целевой цены
    waiting_for_target_price = State()   # Ожидание целевой цены

router = Router()

@router.message(CommandStart())
async def cmd_start(message: Message):
    """Обработчик команды /start"""
    logger.info(f"Получена команда /start от пользователя {message.from_user.id} (@{message.from_user.username})")

    # Создаем пользователя в базе данных
    await create_user(
        telegram_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.first_name
    )
    await update_user_activity(message.from_user.id)

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="💼 Портфель", callback_data="portfolio"),
            InlineKeyboardButton(text="💡 Идеи", callback_data="get_ideas")
        ],
        [
            InlineKeyboardButton(text="📈 Анализ акций", callback_data="analyze_menu"),
            InlineKeyboardButton(text="📊 История", callback_data="history")
        ],
        [
            InlineKeyboardButton(text="💰 Финансы", callback_data="finances"),
            InlineKeyboardButton(text="⚙️ Настройки", callback_data="settings")
        ],
        [
            InlineKeyboardButton(text="❓ Помощь", callback_data="help")
        ]
    ])

    welcome_text = """
🤖 *Добро пожаловать в Invest Bot!*

Интеллектуальный помощник для инвестиций на российском рынке с AI-анализом

*Что я умею:*
• 🧠 **AI-рекомендации** — персональные инвестиционные идеи от xAI Grok
• 📊 **Анализ MOEX** — детальное исследование любых акций по тикеру
• 💼 **Управление портфелем** — отслеживание позиций и доходности
• 🎯 **Целевые цены** — алерты при достижении ваших целей
• 📈 **История операций** — полная статистика торговли
• 🔔 **Умные уведомления** — ежедневные сводки и отчеты

*Безопасность:*
✅ Двойное подтверждение всех операций
✅ Sandbox-режим для тестирования
✅ Никаких автоматических транзакций

Выберите действие из меню ниже:
    """

    await message.answer(welcome_text, reply_markup=keyboard, parse_mode="Markdown")

@router.message(Command("portfolio"))
async def cmd_portfolio(message: Message):
    """Показать портфель пользователя с актуальными ценами"""
    try:
        await message.answer("📊 Получаю актуальные данные портфеля...")

        portfolio = await get_user_portfolio(message.from_user.id)

        if not portfolio:
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="💡 Получить идеи", callback_data="get_ideas")]
            ])
            await message.answer("💼 Ваш портфель пуст\n\nНачните инвестировать!", reply_markup=keyboard)
            return

        # Получаем актуальные цены для всех тикеров в портфеле
        from market_data import market_data
        tickers = [pos['ticker'] for pos in portfolio]
        current_prices = await market_data.get_multiple_moex_prices(tickers)

        portfolio_text = "💼 *Ваш портфель:*\n\n"
        total_value = 0
        total_invested = 0

        for position in portfolio:
            ticker = position['ticker']
            quantity = position['quantity']
            avg_price = position['avg_price']

            # Используем актуальную цену с биржи
            current_price = current_prices.get(ticker, position.get('current_price', avg_price))
            current_value = quantity * current_price
            invested_value = quantity * avg_price
            profit_loss = current_value - invested_value
            profit_percent = (profit_loss / invested_value * 100) if invested_value > 0 else 0

            profit_emoji = "📈" if profit_loss >= 0 else "📉"
            profit_sign = "+" if profit_loss >= 0 else ""

            portfolio_text += f"📈 `{ticker}`: {quantity} шт.\n"
            portfolio_text += f"💰 Средняя цена: {avg_price:.2f} ₽\n"
            portfolio_text += f"💵 Текущая цена: {current_price:.2f} ₽\n"

            # Добавляем информацию о целевой цене
            target_price = position.get('target_price', 0)
            if target_price > 0:
                target_profit = ((target_price - avg_price) / avg_price) * 100
                portfolio_text += f"🎯 Целевая цена: {target_price:.2f} ₽ (+{target_profit:.1f}%)\n"

            portfolio_text += f"💎 Стоимость: {current_value:.2f} ₽\n"
            portfolio_text += f"{profit_emoji} P&L: {profit_sign}{profit_loss:.2f} ₽ ({profit_sign}{profit_percent:.1f}%)\n\n"

            total_value += current_value
            total_invested += invested_value

        total_profit = total_value - total_invested
        total_profit_percent = (total_profit / total_invested * 100) if total_invested > 0 else 0
        total_emoji = "📈" if total_profit >= 0 else "📉"
        total_sign = "+" if total_profit >= 0 else ""

        portfolio_text += f"💎 *Общая стоимость: {total_value:.2f} ₽*\n"
        portfolio_text += f"💰 Инвестировано: {total_invested:.2f} ₽\n"
        portfolio_text += f"{total_emoji} *Общий P&L: {total_sign}{total_profit:.2f} ₽ ({total_sign}{total_profit_percent:.1f}%)*"

        # Добавляем кнопки управления портфелем
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="🎯 Целевые цены", callback_data="target_prices"),
                InlineKeyboardButton(text="💡 Новые идеи", callback_data="get_ideas")
            ],
            [
                InlineKeyboardButton(text="🗑️ Продать акции", callback_data="sell_stock")
            ]
        ])

        await message.answer(portfolio_text, reply_markup=keyboard, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Ошибка при получении портфеля: {e}")
        await message.answer("❌ Ошибка при получении данных портфеля")

@router.message(Command("target"))
async def cmd_target_price(message: Message, state: FSMContext):
    """Установка целевых цен для позиций в портфеле"""
    try:
        user_id = message.from_user.id

        # Получаем портфель пользователя
        portfolio = await get_user_portfolio(user_id)

        if not portfolio:
            await message.answer("💼 Ваш портфель пуст. Сначала добавьте позиции через /ideas")
            return

        # Показываем текущие позиции и целевые цены
        target_text = "🎯 *Управление целевыми ценами*\n\n"
        target_text += "Ваши позиции:\n\n"

        for i, pos in enumerate(portfolio, 1):
            ticker = pos['ticker']
            current_price = pos.get('current_price', pos['avg_price'])
            target_price = pos.get('target_price', 0)

            target_text += f"{i}. `{ticker}`\n"
            target_text += f"   💰 Текущая: {current_price:.2f} ₽\n"

            if target_price > 0:
                target_text += f"   🎯 Целевая: {target_price:.2f} ₽\n"
                profit_percent = ((target_price - pos['avg_price']) / pos['avg_price']) * 100
                target_text += f"   📊 Потенциал: +{profit_percent:.1f}%\n"
            else:
                target_text += f"   🎯 Целевая: не установлена\n"
            target_text += "\n"

        target_text += "Отправьте команду в формате:\n"
        target_text += "`/target ТИКЕР цена`\n\n"
        target_text += "Например: `/target SBER 350.5`"

        await message.answer(target_text, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Ошибка при показе целевых цен: {e}")
        await message.answer("❌ Ошибка при получении данных")

@router.message(Command("ideas"))
async def cmd_ideas(message: Message, state: FSMContext):
    """Получить инвестиционные идеи"""
    await message.answer("🤖 Анализирую рынок...")

    try:
        # Получаем настройки пользователя
        settings = await get_user_settings(message.from_user.id)

        # Если настройки не найдены, используем значения по умолчанию
        if not settings:
            logger.warning(f"Настройки не найдены для пользователя {message.from_user.id}, используем значения по умолчанию")
            settings = {
                'max_investment_amount': 10000,
                'risk_level': 'medium'
            }

        # Получаем идеи с учетом настроек
        xai_client = XAIClient()
        ideas = await xai_client.get_investment_ideas(
            budget=settings['max_investment_amount'],
            risk_level=settings['risk_level']
        )

        if not ideas:
            await message.answer("❌ Не удалось получить рекомендации")
            return

        # Сохраняем идеи в состоянии для последующего выбора
        await state.update_data(investment_ideas=ideas)

        # Формируем сообщение с идеями
        ideas_text = "🎯 *Инвестиционные идеи:*\n\n"
        keyboard_buttons = []

        for i, idea in enumerate(ideas[:7], 1):  # Показываем максимум 7 идей для быстрого ответа
            ticker = idea.get('ticker', 'N/A')
            price = idea.get('price', 0)
            target_price = idea.get('target_price', 0)
            action = idea.get('action', 'BUY')
            reasoning = idea.get('reasoning', 'Нет описания')

            # Рассчитываем потенциальную доходность
            potential_return = 0
            if price > 0 and target_price > 0:
                potential_return = ((target_price - price) / price) * 100

            ideas_text += f"*{i}.* `{ticker}`\n"
            ideas_text += f"💰 Цена: {price:.2f} ₽\n"
            ideas_text += f"📈 Прогноз: {target_price:.2f} ₽ (+{potential_return:.1f}%)\n"
            ideas_text += f"💡 {reasoning}\n\n"

            # Добавляем кнопки для покупки (по 2 в ряду)
            row_index = (i - 1) // 2  # Определяем номер ряда (0, 1, 2, 3, 4)

            # Создаем новый ряд если нужно
            while len(keyboard_buttons) <= row_index:
                keyboard_buttons.append([])

            # Добавляем кнопку в соответствующий ряд
            keyboard_buttons[row_index].append(
                InlineKeyboardButton(text=f"💳 {ticker}", callback_data=f"select_idea_{i-1}")
            )

        # Добавляем кнопку обновления идей и возврата в меню
        keyboard_buttons.append([
            InlineKeyboardButton(text="🔄 Обновить идеи", callback_data="get_ideas")
        ])
        keyboard_buttons.append([
            InlineKeyboardButton(text="🔙 Назад в меню", callback_data="back_to_menu")
        ])

        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
        await message.answer(ideas_text, reply_markup=keyboard, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Ошибка при получении инвестиционных идей: {e}")
        await message.answer("❌ Ошибка при получении инвестиционных идей")

@router.message(Command("analyze"))
async def cmd_analyze_stock(message: Message):
    """Анализ конкретной акции по тикеру"""
    # Извлекаем тикер из команды
    command_parts = message.text.split()

    if len(command_parts) < 2:
        await message.answer(
            "📈 *Анализ акций*\n\n"
            "Для анализа акции введите команду:\n"
            "`/analyze ТИКЕР`\n\n"
            "*Примеры:*\n"
            "• `/analyze SBER` - анализ Сбербанка\n"
            "• `/analyze YNDX` - анализ Яндекса\n"
            "• `/analyze GAZP` - анализ Газпрома\n\n"
            "💡 Можно анализировать любые акции с MOEX",
            parse_mode="Markdown"
        )
        return

    ticker = command_parts[1].upper().strip()

    # Валидация тикера
    if not ticker.isalpha() or len(ticker) > 10:
        await message.answer("❌ Некорректный тикер. Используйте только буквы (например: SBER, YNDX)")
        return

    await message.answer(f"🔍 Анализирую акцию {ticker}...")

    try:
        # Импортируем функцию анализа
        from gpt_client import analyze_stock

        # Получаем анализ от GPT
        analysis = await analyze_stock(ticker)

        # Проверяем на ошибки
        if "error" in analysis:
            if "не найден" in analysis["error"].lower() or "не существует" in analysis["error"].lower():
                await message.answer(
                    f"❌ *Акция {ticker} не найдена на MOEX*\n\n"
                    "Проверьте правильность тикера или попробуйте другую акцию.\n\n"
                    "💡 Популярные тикеры: SBER, GAZP, LKOH, YNDX, OZON",
                    parse_mode="Markdown"
                )
            else:
                await message.answer(f"❌ Ошибка анализа: {analysis['error']}")
            return

        # Дополнительная валидация данных анализа
        current_price = analysis.get("current_price")
        target_price = analysis.get("target_price")

        # Проверяем корректность цен
        if target_price and current_price:
            # Если целевая цена слишком далека от текущей (более чем в 5 раз), корректируем
            if target_price > current_price * 5 or target_price < current_price * 0.2:
                logger.warning(f"Некорректная целевая цена {target_price} для {ticker} при текущей {current_price}, корректируем")
                recommendation = analysis.get('recommendation', 'HOLD')
                if recommendation == 'BUY':
                    target_price = current_price * 1.20  # +20%
                elif recommendation == 'SELL':
                    target_price = current_price * 0.85  # -15%
                else:  # HOLD
                    target_price = current_price * 1.05  # +5%
                analysis['target_price'] = round(target_price, 2)

        # Формируем ответ с анализом
        recommendation_emoji = {
            "BUY": "🟢 ПОКУПАТЬ",
            "HOLD": "🟡 ДЕРЖАТЬ",
            "SELL": "🔴 ПРОДАВАТЬ"
        }.get(analysis.get("recommendation", "HOLD"), "🟡 ДЕРЖАТЬ")

        risk_emoji = {
            "low": "🟢 Низкий",
            "medium": "🟡 Средний",
            "high": "🔴 Высокий"
        }.get(analysis.get("risk_level", "medium"), "🟡 Средний")

        # Получаем текущую цену (либо из анализа, либо отдельно с MOEX)
        current_price = analysis.get("current_price")
        if not current_price:
            from market_data import market_data
            current_prices = await market_data.get_multiple_moex_prices([ticker])
            current_price = current_prices.get(ticker)

        analysis_text = f"📊 *Анализ акции {ticker}*\n\n"

        if current_price:
            analysis_text += f"💰 *Текущая цена:* {current_price:.2f} ₽\n"

        if analysis.get("target_price"):
            analysis_text += f"🎯 *Целевая цена:* {analysis['target_price']:.2f} ₽\n"

            if current_price and analysis.get("target_price"):
                potential = ((analysis['target_price'] - current_price) / current_price) * 100
                potential_emoji = "📈" if potential > 0 else "📉"
                analysis_text += f"{potential_emoji} *Потенциал:* {potential:+.1f}%\n"

        analysis_text += f"\n{recommendation_emoji}\n"
        analysis_text += f"⚠️ *Риск:* {risk_emoji}\n\n"

        if analysis.get("analysis"):
            analysis_text += f"📝 *Анализ:*\n{analysis['analysis']}\n\n"

        if analysis.get("pros"):
            analysis_text += "✅ *Плюсы:*\n"
            for pro in analysis['pros']:
                analysis_text += f"• {pro}\n"
            analysis_text += "\n"

        if analysis.get("cons"):
            analysis_text += "❌ *Минусы:*\n"
            for con in analysis['cons']:
                analysis_text += f"• {con}\n"

        # Создаем кнопки для дальнейших действий
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="💡 Получить идеи", callback_data="get_ideas"),
                InlineKeyboardButton(text="💼 Портфель", callback_data="portfolio")
            ]
        ])

        await message.answer(analysis_text, reply_markup=keyboard, parse_mode="Markdown")

        logger.info(f"✅ Анализ акции {ticker} предоставлен пользователю {message.from_user.id}")

    except Exception as e:
        logger.error(f"Ошибка при анализе акции {ticker}: {e}")
        await message.answer(
            f"❌ Не удалось проанализировать акцию {ticker}\n\n"
            "Возможные причины:\n"
            "• Акция не торгуется на MOEX\n"
            "• Временные проблемы с сервисом\n\n"
            "Попробуйте позже или выберите другую акцию."
        )

@router.callback_query(F.data == "notification_settings")
async def show_notification_settings(callback: CallbackQuery):
    """Показать детальные настройки уведомлений"""
    try:
        settings = await get_user_settings(callback.from_user.id)

        # Безопасная проверка настроек
        if not settings:
            settings = {
                'notifications': True,
                'daily_market_analysis': True,
                'weekly_portfolio_report': True,
                'target_price_alerts': True,
                'price_updates': False
            }

        settings_text = f"""
🔔 *Настройки уведомлений*

📊 *Общие уведомления:* {'✅' if settings.get('notifications', True) else '❌'}

*Детальные настройки:*
🌅 *Ежедневная сводка* (9:00): {'✅' if settings.get('daily_market_analysis', True) else '❌'}
📊 *Еженедельный отчет* (вс 20:00): {'✅' if settings.get('weekly_portfolio_report', True) else '❌'}
🎯 *Целевые цены* (каждые 30 мин, пн-пт 10-18): {'✅' if settings.get('target_price_alerts', True) else '❌'}
⏰ *Обновления цен* (каждые 5 мин, пн-пт 10-18): {'✅' if settings.get('price_updates', False) else '❌'}
        """

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📊 Общие уведомления",
                    callback_data="toggle_notifications"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🌅 Ежедневная сводка",
                    callback_data="toggle_daily_analysis"
                ),
                InlineKeyboardButton(
                    text="📊 Еженедельный отчет",
                    callback_data="toggle_weekly_report"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🎯 Целевые цены",
                    callback_data="toggle_target_alerts"
                ),
                InlineKeyboardButton(
                    text="⏰ Обновления цен",
                    callback_data="toggle_price_updates"
                )
            ],
            [
                InlineKeyboardButton(text="🔙 Назад к настройкам", callback_data="settings")
            ]
        ])

        await callback.message.edit_text(settings_text, reply_markup=keyboard, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Ошибка при показе настроек уведомлений: {e}")
        await callback.message.answer("❌ Ошибка при получении настроек")

    await callback.answer()

@router.callback_query(F.data == "toggle_daily_analysis")
async def toggle_daily_analysis(callback: CallbackQuery):
    """Переключение ежедневного анализа"""
    try:
        settings = await get_user_settings(callback.from_user.id)
        if not settings:
            settings = {'daily_market_analysis': True}

        new_value = not settings.get('daily_market_analysis', True)

        await update_user_settings(callback.from_user.id, daily_market_analysis=new_value)
        logger.info(f"Пользователь {callback.from_user.id}: ежедневный анализ -> {new_value}")

        # Возвращаемся к настройкам уведомлений без дополнительного сообщения
        await show_notification_settings(callback)

    except Exception as e:
        logger.error(f"Ошибка toggle_daily_analysis: {e}")
        await callback.answer("❌ Ошибка при изменении настройки")

@router.callback_query(F.data == "toggle_weekly_report")
async def toggle_weekly_report(callback: CallbackQuery):
    """Переключение еженедельного отчета"""
    try:
        settings = await get_user_settings(callback.from_user.id)
        if not settings:
            settings = {'weekly_portfolio_report': True}

        new_value = not settings.get('weekly_portfolio_report', True)

        await update_user_settings(callback.from_user.id, weekly_portfolio_report=new_value)
        logger.info(f"Пользователь {callback.from_user.id}: еженедельный отчет -> {new_value}")

        # Возвращаемся к настройкам уведомлений без дополнительного сообщения
        await show_notification_settings(callback)

    except Exception as e:
        logger.error(f"Ошибка toggle_weekly_report: {e}")
        await callback.answer("❌ Ошибка при изменении настройки")

@router.callback_query(F.data == "toggle_target_alerts")
async def toggle_target_alerts(callback: CallbackQuery):
    """Переключение уведомлений о целевых ценах"""
    try:
        settings = await get_user_settings(callback.from_user.id)
        if not settings:
            settings = {'target_price_alerts': True}
        new_value = not settings.get('target_price_alerts', True)

        await update_user_settings(callback.from_user.id, target_price_alerts=new_value)
        logger.info(f"Пользователь {callback.from_user.id}: целевые цены -> {new_value}")

        # Возвращаемся к настройкам уведомлений без дополнительного сообщения
        await show_notification_settings(callback)

    except Exception as e:
        logger.error(f"Ошибка toggle_target_alerts: {e}")
        await callback.answer("❌ Ошибка при изменении настройки")

@router.callback_query(F.data == "toggle_price_updates")
async def toggle_price_updates(callback: CallbackQuery):
    """Переключение обновлений цен"""
    try:
        settings = await get_user_settings(callback.from_user.id)
        if not settings:
            settings = {'price_updates': False}

        new_value = not settings.get('price_updates', False)

        await update_user_settings(callback.from_user.id, price_updates=new_value)
        logger.info(f"Пользователь {callback.from_user.id}: обновления цен -> {new_value}")

        # Возвращаемся к настройкам уведомлений без дополнительного сообщения
        await show_notification_settings(callback)

    except Exception as e:
        logger.error(f"Ошибка toggle_price_updates: {e}")
        await callback.answer("❌ Ошибка при изменении настройки")

@router.message(F.text.regexp(r'^/target\s+([A-Z]{3,5})\s+(\d+\.?\d*)$'))
async def set_target_price(message: Message):
    """Установка целевой цены для конкретного тикера"""
    try:
        # Извлекаем тикер и цену из сообщения
        import re
        match = re.match(r'^/target\s+([A-Z]{3,5})\s+(\d+\.?\d*)$', message.text)
        if not match:
            await message.answer("❌ Неверный формат. Используйте: `/target ТИКЕР цена`\nНапример: `/target SBER 350.5`", parse_mode="Markdown")
            return

        ticker = match.group(1).upper()
        target_price = float(match.group(2))
        user_id = message.from_user.id

        # Проверяем, есть ли такая позиция в портфеле
        portfolio = await get_user_portfolio(user_id)
        position = next((p for p in portfolio if p['ticker'] == ticker), None)

        if not position:
            await message.answer(f"❌ Позиция `{ticker}` не найдена в вашем портфеле.\nСначала добавьте её через /ideas", parse_mode="Markdown")
            return

        # Устанавливаем целевую цену
        from database import update_target_price
        await update_target_price(user_id, ticker, target_price)

        # Рассчитываем потенциальную прибыль
        avg_price = position['avg_price']
        current_price = position.get('current_price', avg_price)
        quantity = position['quantity']

        profit_from_avg = ((target_price - avg_price) / avg_price) * 100
        profit_from_current = ((target_price - current_price) / current_price) * 100

        profit_amount = (target_price - avg_price) * quantity

        success_text = f"✅ *Целевая цена установлена!*\n\n"
        success_text += f"📊 `{ticker}`\n"
        success_text += f"💰 Ваша цена: {avg_price:.2f} ₽\n"
        success_text += f"💵 Текущая: {current_price:.2f} ₽\n"
        success_text += f"🎯 Целевая: {target_price:.2f} ₽\n\n"
        success_text += f"📈 Потенциал от покупки: +{profit_from_avg:.1f}%\n"
        success_text += f"📊 От текущей цены: {profit_from_current:+.1f}%\n"
        success_text += f"💎 Потенциальная прибыль: {profit_amount:+,.0f} ₽\n\n"
        success_text += f"🔔 Вы получите уведомление, когда цена достигнет {target_price:.2f} ₽"

        await message.answer(success_text, parse_mode="Markdown")

        logger.info(f"Пользователь {user_id} установил целевую цену {target_price} для {ticker}")

    except ValueError:
        await message.answer("❌ Неверный формат цены. Используйте числа, например: 350.5")
    except Exception as e:
        logger.error(f"Ошибка при установке целевой цены: {e}")
        await message.answer("❌ Ошибка при установке целевой цены")

def register_handlers(dp):
    """Регистрация всех обработчиков"""
    dp.include_router(router)

@router.callback_query(F.data.startswith("select_idea_"))
async def process_idea_selection(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора инвестиционной идеи"""
    idea_index = int(callback.data.split("_")[-1])

    data = await state.get_data()
    ideas = data.get("investment_ideas", [])

    if idea_index < len(ideas):
        selected_idea = ideas[idea_index]

        confirmation_text = f"""
💡 *Выбранная идея:*

📈 Тикер: *{selected_idea['ticker']}*
📊 Действие: *{selected_idea['action']}*
💰 Текущая цена: *{selected_idea['price']:.2f} ₽*
🎯 Целевая цена: *{selected_idea['target_price']:.2f} ₽*

📝 Обоснование:
{selected_idea['reasoning']}

Выберите способ указания цены:
        """

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="📊 Авто цена", callback_data="use_auto_price"),
                InlineKeyboardButton(text="✏️ Своя цена", callback_data="use_custom_price")
            ],
            [
                InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_trade")
            ]
        ])

        await callback.message.answer(confirmation_text, reply_markup=keyboard, parse_mode="Markdown")
        await state.update_data(selected_idea=selected_idea)

    await callback.answer()

@router.callback_query(F.data == "use_auto_price")
async def use_auto_price(callback: CallbackQuery, state: FSMContext):
    """Использование автоматической цены"""
    await callback.answer()
    await callback.message.answer("💰 Укажите сумму для инвестирования (в рублях):")
    await state.set_state(InvestmentStates.waiting_for_amount)

@router.callback_query(F.data == "use_custom_price")
async def use_custom_price(callback: CallbackQuery, state: FSMContext):
    """Использование пользовательской цены"""
    await callback.answer()
    await callback.message.answer("✏️ Введите желаемую цену за одну акцию (в рублях):")
    await state.set_state(InvestmentStates.waiting_for_custom_price)

@router.message(InvestmentStates.waiting_for_custom_price)
async def process_custom_price(message: Message, state: FSMContext):
    """Обработка пользовательской цены для покупки и продажи"""
    try:
        data = await state.get_data()
        logger.info(f"process_custom_price - Полученные данные состояния: {data}")

        custom_price = float(message.text.replace(",", "."))

        if custom_price <= 0:
            await message.answer("❌ Цена должна быть больше 0")
            return

        # Проверяем, это цена для покупки или продажи
        if 'custom_sell_ticker' in data:
            logger.info("process_custom_price - Обрабатываем как ПРОДАЖУ")
            # Это продажа
            ticker = data.get("custom_sell_ticker")
            sell_quantity = data.get("sell_quantity")
            avg_price = data.get("avg_price")

            logger.info(f"process_custom_price - ticker: {ticker}, sell_quantity: {sell_quantity}, avg_price: {avg_price}")

            if not all([ticker, sell_quantity]):
                logger.error(f"process_custom_price - Неполные данные: ticker={ticker}, sell_quantity={sell_quantity}")
                await message.answer("❌ Ошибка: неполные данные для продажи")
                await state.clear()
                return

            total_amount = sell_quantity * custom_price
            profit_loss = (custom_price - avg_price) * sell_quantity

            confirmation_text = f"""
✅ *Подтверждение продажи:*

📉 Продать: `{ticker}`
🔢 Количество: *{sell_quantity} шт.*
💰 Цена продажи: *{custom_price:.2f} ₽*
💎 Получите: *{total_amount:.2f} ₽*
📈 P&L: *{profit_loss:+.2f} ₽*

Подтвердить продажу?
            """

            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text="✅ Продать", callback_data=f"final_sell_{ticker}"),
                    InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_sell")
                ]
            ])

            await message.answer(confirmation_text, reply_markup=keyboard, parse_mode="Markdown")
            await state.update_data(sell_price=custom_price, total_amount=total_amount)

        else:
            logger.info("process_custom_price - Обрабатываем как ПОКУПКУ")
            # Это покупка (существующий код)
            selected_idea = data.get("selected_idea")
            logger.info(f"process_custom_price - selected_idea: {selected_idea}")

            if not selected_idea:
                logger.error("process_custom_price - selected_idea отсутствует, показываем ошибку")
                await message.answer("❌ Идея не найдена. Начните заново с /ideas")
                await state.clear()
                return

            # Обновляем цену в идее
            selected_idea['price'] = custom_price
            await state.update_data(selected_idea=selected_idea)

            await message.answer(f"✅ Цена установлена: {custom_price:.2f} ₽\n\n💰 Теперь укажите сумму для инвестирования (в рублях):")
            await state.set_state(InvestmentStates.waiting_for_amount)

    except ValueError:
        await message.answer("❌ Некорректная цена. Введите число (например: 250.50)")

@router.message(InvestmentStates.waiting_for_amount)
async def process_investment_amount(message: Message, state: FSMContext):
    """Обработка суммы инвестирования"""
    try:
        amount = float(message.text.replace(",", "."))

        if amount <= 0:
            await message.answer("❌ Сумма должна быть больше 0")
            return

        data = await state.get_data()
        selected_idea = data.get("selected_idea")

        if not selected_idea:
            await message.answer("❌ Идея не найдена. Начните заново с /ideas")
            await state.clear()
            return

        # Рассчитываем количество акций
        quantity = int(amount / selected_idea['price'])
        total_cost = quantity * selected_idea['price']

        if quantity == 0:
            await message.answer("❌ Недостаточно средств для покупки хотя бы одной акции")
            return

        confirmation_text = f"""
✅ *Подтверждение сделки:*

📈 Тикер: *{selected_idea['ticker']}*
📊 Операция: *{selected_idea['action']}*
🔢 Количество: *{quantity} шт.*
💰 Цена за акцию: *{selected_idea['price']:.2f} ₽*
💎 Общая стоимость: *{total_cost:.2f} ₽*

Подтвердить сделку?
        """

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Подтвердить", callback_data="confirm_trade"),
                InlineKeyboardButton(text="❌ Отменить", callback_data="cancel_trade")
            ]
        ])

        await message.answer(confirmation_text, reply_markup=keyboard, parse_mode="Markdown")
        await state.update_data(quantity=quantity, total_cost=total_cost)
        await state.set_state(InvestmentStates.waiting_for_confirmation)

    except ValueError:
        await message.answer("❌ Некорректная сумма. Введите число (например: 5000 или 5000.50)")

@router.callback_query(F.data == "confirm_trade")
async def confirm_trade(callback: CallbackQuery, state: FSMContext):
    """Подтверждение и выполнение сделки"""
    try:
        data = await state.get_data()
        selected_idea = data.get("selected_idea")
        quantity = data.get("quantity")
        total_cost = data.get("total_cost")

        if not all([selected_idea, quantity, total_cost]):
            await callback.message.answer("❌ Ошибка: неполные данные сделки")
            await state.clear()
            return

        # Сохраняем сделку в базу данных
        success = await save_order(
            user_id=callback.from_user.id,
            ticker=selected_idea['ticker'],
            quantity=quantity,
            price=selected_idea['price'],
            order_type=selected_idea['action'],
            total_amount=total_cost
        )

        if success:
            await callback.message.edit_text(
                f"✅ *Сделка выполнена!*\n\n"
                f"📈 Тикер: `{selected_idea['ticker']}`\n"
                f"📊 Операция: *{selected_idea['action']}*\n"
                f"🔢 Количество: *{quantity} шт.*\n"
                f"💰 Цена: *{selected_idea['price']:.2f} ₽*\n"
                f"💎 Сумма: *{total_cost:.2f} ₽*\n\n"
                f"Сделка добавлена в ваш портфель!",
                reply_markup=None,
                parse_mode="Markdown"
            )
        else:
            await callback.message.edit_text(
                "❌ Ошибка при сохранении сделки в базу данных",
                reply_markup=None
            )

        await state.clear()

    except Exception as e:
        logger.error(f"Ошибка при выполнении операции: {e}")
        await callback.message.answer("❌ Произошла ошибка при выполнении операции")
        await state.clear()

    await callback.answer()

@router.callback_query(F.data == "sell_stock")
async def sell_stock_selection(callback: CallbackQuery, state: FSMContext):
    """Выбор акции для продажи"""
    try:
        portfolio = await get_user_portfolio(callback.from_user.id)

        if not portfolio:
            await callback.message.answer("💼 Ваш портфель пуст")
            await callback.answer()
            return

        # Создаем клавиатуру с акциями для продажи
        keyboard_buttons = []
        for position in portfolio:
            ticker = position['ticker']
            quantity = position['quantity']
            button_text = f"📉 {ticker} ({quantity} шт.)"
            keyboard_buttons.append([InlineKeyboardButton(
                text=button_text,
                callback_data=f"sell_{ticker}"
            )])

        keyboard_buttons.append([InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_sell")])
        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

        await callback.message.answer(
            "🗑️ *Выберите акцию для продажи:*",
            reply_markup=keyboard,
            parse_mode="Markdown"
        )

    except Exception as e:
        logger.error(f"Ошибка при выборе акций для продажи: {e}")
        await callback.message.answer("❌ Ошибка при получении данных портфеля")

    await callback.answer()

@router.callback_query(F.data.startswith("sell_auto_"))
async def confirm_sell_auto_price(callback: CallbackQuery, state: FSMContext):
    """Продажа по текущей цене"""
    ticker = callback.data.replace("sell_auto_", "")

    try:
        data = await state.get_data()
        current_price = data.get("current_price")
        sell_quantity = data.get("sell_quantity")
        avg_price = data.get("avg_price")

        if not all([current_price, sell_quantity]):
            await callback.message.answer("❌ Ошибка: неполные данные для продажи")
            await state.clear()
            return

        total_amount = sell_quantity * current_price
        profit_loss = (current_price - avg_price) * sell_quantity

        confirmation_text = f"""
✅ *Подтверждение продажи:*

📉 Продать: `{ticker}`
🔢 Количество: *{sell_quantity} шт.*
💰 Цена продажи: *{current_price:.2f} ₽*
💎 Получите: *{total_amount:.2f} ₽*
📈 P&L: *{profit_loss:+.2f} ₽*

Подтвердить продажу?
        """

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Продать", callback_data=f"final_sell_{ticker}"),
                InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_sell")
            ]
        ])

        await callback.message.answer(confirmation_text, reply_markup=keyboard, parse_mode="Markdown")
        await state.update_data(sell_price=current_price, total_amount=total_amount)

    except Exception as e:
        logger.error(f"Ошибка при подтверждении продажи {ticker}: {e}")
        await callback.message.answer("❌ Ошибка при обработке продажи")

    await callback.answer()

@router.callback_query(F.data.startswith("sell_custom_"))
async def sell_custom_price(callback: CallbackQuery, state: FSMContext):
    """Продажа по пользовательской цене"""
    ticker = callback.data.replace("sell_custom_", "")

    await callback.answer()
    await callback.message.answer(f"✏️ Введите желаемую цену продажи для {ticker} (в рублях):")

    # Получаем существующие данные и добавляем к ним custom_sell_ticker
    data = await state.get_data()
    logger.info(f"sell_custom_price - Данные ДО добавления custom_sell_ticker: {data}")
    data['custom_sell_ticker'] = ticker
    await state.update_data(**data)

    # Проверяем, что данные сохранились
    updated_data = await state.get_data()
    logger.info(f"sell_custom_price - Данные ПОСЛЕ добавления custom_sell_ticker: {updated_data}")

    await state.set_state(InvestmentStates.waiting_for_custom_price)

@router.callback_query(F.data.startswith("final_sell_"))
async def final_sell_confirmation(callback: CallbackQuery, state: FSMContext):
    """Финальное подтверждение продажи"""
    ticker = callback.data.replace("final_sell_", "")

    try:
        data = await state.get_data()
        sell_price = data.get("sell_price")
        sell_quantity = data.get("sell_quantity")
        total_amount = data.get("total_amount")

        if not all([sell_price, sell_quantity, total_amount]):
            await callback.message.answer("❌ Ошибка: неполные данные для продажи")
            await state.clear()
            return

        # Выполняем продажу (сохраняем в базу)
        success = await save_order(
            user_id=callback.from_user.id,
            ticker=ticker,
            quantity=sell_quantity,
            price=sell_price,
            order_type="SELL",
            total_amount=total_amount
        )

        if success:
            await callback.message.edit_text(
                f"✅ *Продажа выполнена!*\n\n"
                f"📉 Продано: `{ticker}`\n"
                f"🔢 Количество: *{sell_quantity} шт.*\n"
                f"💰 Цена: *{sell_price:.2f} ₽*\n"
                f"💎 Получено: *{total_amount:.2f} ₽*",
                reply_markup=None,
                parse_mode="Markdown"
            )
        else:
            await callback.message.edit_text(
                "❌ Ошибка при выполнении продажи",
                reply_markup=None
            )

        await state.clear()

    except Exception as e:
        logger.error(f"Ошибка при финальном подтверждении продажи {ticker}: {e}")
        await callback.message.answer("❌ Ошибка при выполнении продажи")
        await state.clear()

    await callback.answer()


@router.callback_query(F.data == "cancel_sell")
async def cancel_sell(callback: CallbackQuery, state: FSMContext):
    """Отмена продажи"""
    await callback.message.answer("❌ Продажа отменена")
    await state.clear()
    await callback.answer()

@router.callback_query(F.data.startswith("sell_"))
async def process_sell_stock(callback: CallbackQuery, state: FSMContext):
    """Обработка продажи конкретной акции"""
    if callback.data == "sell_stock":
        await sell_stock_selection(callback, state)
        return

    # Проверяем, что это не callback для auto, custom или final продажи
    if (callback.data.startswith("sell_auto_") or
        callback.data.startswith("sell_custom_") or
        callback.data.startswith("final_sell_")):
        return  # Эти callback обрабатываются другими функциями

    ticker = callback.data.replace("sell_", "")

    try:
        # Получаем информацию о позиции
        portfolio = await get_user_portfolio(callback.from_user.id)
        position = next((p for p in portfolio if p['ticker'] == ticker), None)

        if not position:
            await callback.message.answer(f"❌ Акция {ticker} не найдена в портфеле")
            await callback.answer()
            return

        # Получаем текущую цену
        from market_data import market_data
        current_price = await market_data.get_moex_price(ticker)
        if not current_price:
            current_price = position.get('current_price', position['avg_price'])

        quantity = position['quantity']
        avg_price = position['avg_price']
        current_value = quantity * current_price
        invested_value = quantity * avg_price
        profit_loss = current_value - invested_value

        confirmation_text = f"""
🗑️ *Продажа акций {ticker}*

📊 В портфеле: *{quantity} шт.*
💰 Средняя цена покупки: *{avg_price:.2f} ₽*
💱 Текущая цена: *{current_price:.2f} ₽*
💎 Стоимость позиции: *{current_value:.2f} ₽*
📈 P&L: *{profit_loss:+.2f} ₽*

Выберите способ указания цены:
        """

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="📊 По текущей цене", callback_data=f"sell_auto_{ticker}"),
                InlineKeyboardButton(text="✏️ Своя цена", callback_data=f"sell_custom_{ticker}")
            ],
            [
                InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_sell")
            ]
        ])

        await callback.message.answer(confirmation_text, reply_markup=keyboard, parse_mode="Markdown")
        await state.update_data(sell_ticker=ticker, current_price=current_price, sell_quantity=quantity, avg_price=avg_price)

    except Exception as e:
        logger.error(f"Ошибка при обработке продажи {ticker}: {e}")
        await callback.message.answer("❌ Ошибка при обработке продажи")

    await callback.answer()

@router.callback_query(F.data == "cancel_trade")
async def cancel_trade(callback: CallbackQuery, state: FSMContext):
    """Отмена сделки"""
    await callback.message.answer("❌ Сделка отменена")
    await state.clear()
    await callback.answer()

@router.message(Command("history"))
async def cmd_history(message: Message):
    """Показать историю операций"""
    try:
        history = await get_order_history(message.from_user.id)

        if not history:
            await message.answer("📊 История операций пуста")
            return

        # Заголовок и начало таблицы
        header = "📊 <b>История операций:</b>\n<pre>"
        table = "Дата  | Время | Тип  | Тикер | Кол-во |  Цена \n"
        table += "────────────────────────────────────────\n"

        for order in history[-15:]:  # Последние 15 операций
            # Форматируем дату и время
            created_at = order.get('created_at')
            if created_at:
                if isinstance(created_at, str):
                    try:
                        from datetime import datetime
                        dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                        date_str = dt.strftime('%d.%m')
                        time_str = dt.strftime('%H:%M')
                    except:
                        date_str = created_at.split('T')[0][-5:]
                        time_str = created_at.split('T')[1][:5] if 'T' in created_at else '     '
                else:
                    date_str = created_at.strftime('%d.%m')
                    time_str = created_at.strftime('%H:%M')
            else:
                date_str = "  .  "
                time_str = "  :  "

            # Тип операции
            operation_type = order.get('operation_type', '').upper()
            if operation_type == 'BUY':
                op_type = "BUY"
            elif operation_type == 'SELL':
                op_type = "SELL"
            else:
                op_type = "   "

            ticker = order.get('ticker', '')[:5].ljust(5)
            quantity = f"{order.get('quantity', 0):>6}"
            price = f"{order.get('price', 0):>6.1f}"

            table += f"{date_str:<5} | {time_str:<5} | {op_type:<4} | {ticker:<5} | {quantity} | {price}\n"

        table += "</pre>\n\n💡 <i>Легенда:</i> BUY = Покупка, SELL = Продажа"

        await message.answer(header + table, parse_mode="HTML")

    except Exception as e:
        logger.error(f"Ошибка при получении истории: {e}")
        await message.answer("❌ Ошибка при получении истории операций")


@router.message(Command("settings"))
async def cmd_settings(message: Message):
    """Показать настройки (команда)"""
    try:
        settings = await get_user_settings(message.from_user.id)

        # Безопасная проверка настроек
        if not settings:
            settings = {
                'risk_level': 'medium',
                'max_investment_amount': 10000,
                'notifications': True
            }

        risk_levels = {
            'low': '🟢 Низкий',
            'medium': '🟡 Средний',
            'high': '🔴 Высокий'
        }

        settings_text = f"""
⚙️ *Ваши настройки:*

🎯 *Уровень риска:* {risk_levels.get(settings.get('risk_level', 'medium'), settings.get('risk_level', 'medium'))}
💰 *Макс. сумма инвестирования:* {settings.get('max_investment_amount', 10000):,.0f} ₽
🔔 *Уведомления:* {'✅ Включены' if settings.get('notifications', True) else '❌ Отключены'}

Выберите что изменить:
        """

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="🎯 Уровень риска", callback_data="set_risk"),
                InlineKeyboardButton(text="💰 Макс. сумма", callback_data="set_max_amount")
            ],
            [
                InlineKeyboardButton(text="🔔 Общие уведомления", callback_data="toggle_notifications"),
                InlineKeyboardButton(text="🔧 Настройки уведомлений", callback_data="notification_settings")
            ],
            [
                InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_menu")
            ]
        ])

        await message.answer(settings_text, reply_markup=keyboard, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Ошибка при показе настроек: {e}")
        await message.answer("❌ Ошибка при получении настроек")

@router.callback_query(F.data == "portfolio")
async def show_portfolio_callback(callback: CallbackQuery):
    """Показать портфель через callback"""
    # Исправлено: передаем user_id напрямую
    try:
        await callback.answer("📊 Получаю актуальные данные портфеля...")
        portfolio = await get_user_portfolio(callback.from_user.id)
        if not portfolio:
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="💡 Получить идеи", callback_data="get_ideas")],
                [InlineKeyboardButton(text="🔙 Назад в меню", callback_data="back_to_menu")]
            ])
            await callback.message.edit_text("💼 Ваш портфель пуст\n\nНачните инвестировать!", reply_markup=keyboard)
            return
        from market_data import market_data
        tickers = [pos['ticker'] for pos in portfolio]
        current_prices = await market_data.get_multiple_moex_prices(tickers)
        portfolio_text = "💼 *Ваш портфель:*\n\n"
        total_value = 0
        total_invested = 0
        for position in portfolio:
            ticker = position['ticker']
            quantity = position['quantity']
            avg_price = position['avg_price']
            current_price = current_prices.get(ticker, position.get('current_price', avg_price))
            current_value = quantity * current_price
            invested_value = quantity * avg_price
            profit_loss = current_value - invested_value
            profit_percent = (profit_loss / invested_value * 100) if invested_value > 0 else 0
            profit_emoji = "📈" if profit_loss >= 0 else "📉"
            profit_sign = "+" if profit_loss >= 0 else ""
            portfolio_text += f"📈 `{ticker}`: {quantity} шт.\n"
            portfolio_text += f"💰 Средняя цена: {avg_price:.2f} ₽\n"
            portfolio_text += f"💵 Текущая цена: {current_price:.2f} ₽\n"
            portfolio_text += f"💎 Стоимость: {current_value:.2f} ₽\n"
            portfolio_text += f"{profit_emoji} P&L: {profit_sign}{profit_loss:.2f} ₽ ({profit_sign}{profit_percent:.1f}%)\n\n"
            total_value += current_value
            total_invested += invested_value
        if total_invested > 0:
            total_profit = total_value - total_invested
            total_percent = (total_profit / total_invested * 100)
            total_emoji = "📈" if total_profit >= 0 else "📉"
            total_sign = "+" if total_profit >= 0 else ""
            portfolio_text += f"\n{total_emoji} *Общий P&L:* {total_sign}{total_profit:.2f} ₽ ({total_sign}{total_percent:.1f}%)"
        # Добавляем кнопки управления портфелем и возврата в меню
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="🗑️ Продать акции", callback_data="sell_stock"),
                InlineKeyboardButton(text="💡 Новые идеи", callback_data="get_ideas")
            ],
            [
                InlineKeyboardButton(text="🔙 Назад в меню", callback_data="back_to_menu")
            ]
        ])

        await callback.message.edit_text(portfolio_text, parse_mode="Markdown", reply_markup=keyboard)
    except Exception as e:
        logger.error(f"Ошибка при получении портфеля через callback: {e}")
        await callback.message.edit_text("❌ Ошибка при получении портфеля")

@router.callback_query(F.data == "target_prices")
async def show_target_prices(callback: CallbackQuery):
    """Показать и управлять целевыми ценами"""
    try:
        await callback.answer("🎯 Загружаю целевые цены...")

        user_id = callback.from_user.id
        portfolio = await get_user_portfolio(user_id)

        if not portfolio:
            await callback.message.answer("💼 Ваш портфель пуст. Сначала добавьте позиции через /ideas")
            return

        # Показываем текущие позиции и целевые цены
        target_text = "🎯 *Управление целевыми ценами*\n\n"

        for i, pos in enumerate(portfolio, 1):
            ticker = pos['ticker']
            current_price = pos.get('current_price', pos['avg_price'])
            target_price = pos.get('target_price', 0)
            avg_price = pos['avg_price']

            target_text += f"{i}. `{ticker}`\n"
            target_text += f"   💰 Ваша цена: {avg_price:.2f} ₽\n"
            target_text += f"   💵 Текущая: {current_price:.2f} ₽\n"

            if target_price > 0:
                target_text += f"   🎯 Целевая: {target_price:.2f} ₽\n"
                profit_percent = ((target_price - avg_price) / avg_price) * 100
                profit_from_current = ((target_price - current_price) / current_price) * 100
                target_text += f"   📊 Потенциал: +{profit_percent:.1f}%"
                if profit_from_current != profit_percent:
                    target_text += f" (от текущей: {profit_from_current:+.1f}%)"
                target_text += "\n"
            else:
                target_text += f"   🎯 Целевая: не установлена\n"
            target_text += "\n"

        target_text += "Для установки целевой цены используйте:\n"
        target_text += "`/target ТИКЕР цена`\n\n"
        target_text += "Например: `/target SBER 350.5`"

        await callback.message.answer(target_text, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Ошибка при показе целевых цен: {e}")
        await callback.message.answer("❌ Ошибка при получении данных")

@router.callback_query(F.data == "get_ideas")
async def get_ideas_callback(callback: CallbackQuery, state: FSMContext):
    """Получить идеи через callback"""
    await callback.answer("🤖 Анализирую рынок...")

    try:
        # Получаем настройки пользователя
        settings = await get_user_settings(callback.from_user.id)

        # Если настройки не найдены, используем значения по умолчанию
        if not settings:
            logger.warning(f"Настройки не найдены для пользователя {callback.from_user.id}, используем значения по умолчанию")
            settings = {
                'max_investment_amount': 10000,
                'risk_level': 'medium'
            }

        # Получаем идеи с учетом настроек
        xai_client = XAIClient()
        ideas = await xai_client.get_investment_ideas(
            budget=settings['max_investment_amount'],
            risk_level=settings['risk_level']
        )

        if not ideas:
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад в меню", callback_data="back_to_menu")]
            ])
            await callback.message.edit_text("❌ Не удалось получить рекомендации", reply_markup=keyboard)
            return

        # Сохраняем идеи в состоянии для последующего выбора
        await state.update_data(investment_ideas=ideas)

        # Формируем сообщение с идеями
        ideas_text = "🎯 *Инвестиционные идеи:*\n\n"
        keyboard_buttons = []

        for i, idea in enumerate(ideas[:7], 1):  # Показываем максимум 7 идей для быстрого ответа
            ticker = idea.get('ticker', 'N/A')
            price = idea.get('price', 0)
            target_price = idea.get('target_price', 0)
            action = idea.get('action', 'BUY')
            reasoning = idea.get('reasoning', 'Нет описания')

            # Рассчитываем потенциальную доходность
            potential_return = 0
            if price > 0 and target_price > 0:
                potential_return = ((target_price - price) / price) * 100

            ideas_text += f"*{i}.* `{ticker}`\n"
            ideas_text += f"💰 Цена: {price:.2f} ₽\n"
            ideas_text += f"📈 Прогноз: {target_price:.2f} ₽ (+{potential_return:.1f}%)\n"
            ideas_text += f"💡 {reasoning}\n\n"

            # Добавляем кнопки для покупки (по 2 в ряду)
            row_index = (i - 1) // 2  # Определяем номер ряда (0, 1, 2, 3, 4)

            # Создаем новый ряд если нужно
            while len(keyboard_buttons) <= row_index:
                keyboard_buttons.append([])

            # Добавляем кнопку в соответствующий ряд
            keyboard_buttons[row_index].append(
                InlineKeyboardButton(text=f"💳 {ticker}", callback_data=f"select_idea_{i-1}")
            )

        # Добавляем кнопку обновления идей и возврата в меню
        keyboard_buttons.append([
            InlineKeyboardButton(text="🔄 Обновить идеи", callback_data="get_ideas")
        ])
        keyboard_buttons.append([
            InlineKeyboardButton(text="🔙 Назад в меню", callback_data="back_to_menu")
        ])

        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
        await callback.message.edit_text(ideas_text, reply_markup=keyboard, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Ошибка при получении инвестиционных идей: {e}")
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад в меню", callback_data="back_to_menu")]
        ])
        await callback.message.edit_text("❌ Ошибка при получении инвестиционных идей", reply_markup=keyboard)

@router.callback_query(F.data == "finances")
async def show_finances_callback(callback: CallbackQuery):
    """Показать финансовую статистику"""
    try:
        await callback.answer("💰 Загружаю финансовую статистику...")

        stats = await get_user_trading_stats(callback.from_user.id)

        if not stats:
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад в меню", callback_data="back_to_menu")]
            ])
            await callback.message.edit_text("💰 Финансовая статистика пуста", reply_markup=keyboard)
            return

        # Формируем сообщение со статистикой
        message = "💰 *Финансовая статистика*\n\n"

        # Общие торговые данные
        trading = stats.get('trading', {})
        message += "📊 *Торговая активность:*\n"
        message += f"🛒 Покупок: {trading.get('total_buys', 0)}\n"
        message += f"💸 Продаж: {trading.get('total_sells', 0)}\n"
        message += f"💰 Куплено на: {trading.get('total_bought', 0):,.0f} ₽\n"
        message += f"💎 Продано на: {trading.get('total_sold', 0):,.0f} ₽\n"
        message += f"✅ Реализованная прибыль: {trading.get('realized_pnl', 0):+,.0f} ₽\n\n"

        # Статистика портфеля
        portfolio = stats.get('portfolio', {})
        message += "💼 *Текущий портфель:*\n"
        message += f"🔢 Позиций: {portfolio.get('positions_count', 0)}\n"
        message += f"💰 Вложено: {portfolio.get('portfolio_cost', 0):,.0f} ₽\n"
        message += f"💎 Стоимость: {portfolio.get('portfolio_value', 0):,.0f} ₽\n"
        message += f"📈 Нереализованная прибыль: {portfolio.get('unrealized_pnl', 0):+,.0f} ₽ ({portfolio.get('unrealized_return_pct', 0):+.1f}%)\n\n"

        # Общий P&L
        total_pnl = stats.get('total_pnl', 0)
        pnl_emoji = "📈" if total_pnl >= 0 else "📉"
        message += f"{pnl_emoji} *Общий P&L: {total_pnl:+,.0f} ₽*\n\n"

        # Топ позиции
        top_positions = stats.get('top_positions', [])
        if top_positions:
            message += "🏆 *Топ позиции по прибыли:*\n"
            for i, pos in enumerate(top_positions[:3], 1):
                pnl_emoji = "📈" if pos['unrealized_pnl'] >= 0 else "📉"
                message += f"{i}. {pos['ticker']}: {pnl_emoji} {pos['unrealized_pnl']:+,.0f} ₽ ({pos['return_pct']:+.1f}%)\n"

        # Прибыльные сделки
        profitable_trades = stats.get('profitable_trades', [])
        if profitable_trades:
            message += "\n💎 *Лучшие сделки:*\n"
            for i, trade in enumerate(profitable_trades[:3], 1):
                date_str = trade['created_at'].strftime('%d.%m.%Y') if trade.get('created_at') else 'N/A'
                message += f"{i}. {trade['ticker']}: +{trade['profit_loss']:,.0f} ₽ ({date_str})\n"

        # Добавляем кнопку возврата в меню
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад в меню", callback_data="back_to_menu")]
        ])

        await callback.message.edit_text(message, parse_mode="Markdown", reply_markup=keyboard)

    except Exception as e:
        logger.error(f"Ошибка при показе финансовой статистики: {e}")
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад в меню", callback_data="back_to_menu")]
        ])
        await callback.message.edit_text("❌ Ошибка при получении финансовой статистики", reply_markup=keyboard)

@router.message(Command("finances"))
async def cmd_finances(message: Message):
    """Показать финансовую статистику (команда)"""
    try:
        stats = await get_user_trading_stats(message.from_user.id)

        if not stats:
            await message.answer("💰 Финансовая статистика пуста")
            return

        # Повторяем ту же логику форматирования
        finance_message = "💰 *Финансовая статистика*\n\n"

        trading = stats.get('trading', {})
        finance_message += "📊 *Торговая активность:*\n"
        finance_message += f"🛒 Покупок: {trading.get('total_buys', 0)}\n"
        finance_message += f"💸 Продаж: {trading.get('total_sells', 0)}\n"
        finance_message += f"💰 Куплено на: {trading.get('total_bought', 0):,.0f} ₽\n"
        finance_message += f"💎 Продано на: {trading.get('total_sold', 0):,.0f} ₽\n"
        finance_message += f"✅ Реализованная прибыль: {trading.get('realized_pnl', 0):+,.0f} ₽\n\n"

        portfolio = stats.get('portfolio', {})
        finance_message += "💼 *Текущий портфель:*\n"
        finance_message += f"🔢 Позиций: {portfolio.get('positions_count', 0)}\n"
        finance_message += f"💰 Вложено: {portfolio.get('portfolio_cost', 0):,.0f} ₽\n"
        finance_message += f"💎 Стоимость: {portfolio.get('portfolio_value', 0):,.0f} ₽\n"
        finance_message += f"📈 Нереализованная прибыль: {portfolio.get('unrealized_pnl', 0):+,.0f} ₽ ({portfolio.get('unrealized_return_pct', 0):+.1f}%)\n\n"

        total_pnl = stats.get('total_pnl', 0)
        pnl_emoji = "📈" if total_pnl >= 0 else "📉"
        finance_message += f"{pnl_emoji} *Общий P&L: {total_pnl:+,.0f} ₽*"

        await message.answer(finance_message, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Ошибка при показе финансовой статистики: {e}")
        await message.answer("❌ Ошибка при получении финансовой статистики")

@router.callback_query(F.data == "history")
async def show_history_callback(callback: CallbackQuery):
    """Показать историю через callback"""
    await callback.answer("📊 Загружаю историю...")
    try:
        history = await get_order_history(callback.from_user.id)
        if not history:
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад в меню", callback_data="back_to_menu")]
            ])
            await callback.message.edit_text("📊 История операций пуста", reply_markup=keyboard)
            return

        # Заголовок и начало таблицы
        header = "📊 <b>История операций:</b>\n<pre>"
        table = "Дата  | Время | Тип  | Тикер | Кол-во |  Цена \n"
        table += "────────────────────────────────────────\n"

        for order in history[-15:]:
            created_at = order.get('created_at')
            if created_at:
                if isinstance(created_at, str):
                    try:
                        from datetime import datetime
                        dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                        date_str = dt.strftime('%d.%m')
                        time_str = dt.strftime('%H:%M')
                    except:
                        date_str = created_at.split('T')[0][-5:]
                        time_str = created_at.split('T')[1][:5] if 'T' in created_at else '     '
                else:
                    date_str = created_at.strftime('%d.%m')
                    time_str = created_at.strftime('%H:%M')
            else:
                date_str = "  .  "
                time_str = "  :  "

            operation_type = order.get('operation_type', '').upper()
            if operation_type == 'BUY':
                op_type = "BUY"
            elif operation_type == 'SELL':
                op_type = "SELL"
            else:
                op_type = "   "

            ticker = order.get('ticker', '')[:5].ljust(5)
            quantity = f"{order.get('quantity', 0):>6}"
            price = f"{order.get('price', 0):>6.1f}"

            table += f"{date_str:<5} | {time_str:<5} | {op_type:<4} | {ticker:<5} | {quantity} | {price}\n"

        table += "</pre>\n\n💡 <i>Легенда:</i> BUY = Покупка, SELL = Продажа"

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад в меню", callback_data="back_to_menu")]
        ])

        await callback.message.edit_text(header + table, parse_mode="HTML", reply_markup=keyboard)

    except Exception as e:
        logger.error(f"Ошибка при получении истории через callback: {e}")
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад в меню", callback_data="back_to_menu")]
        ])
        await callback.message.edit_text("❌ Ошибка при получении истории операций", reply_markup=keyboard)

@router.message(Command("help"))
async def cmd_help(message: Message):
    """Показать помощь (команда)"""
    help_text = """
❓ <b>Полное руководство Invest Bot</b>

🤖 <b>Основные команды:</b>
• /start - Главное меню и быстрый доступ ко всем функциям
• /portfolio - Показать текущий портфель с актуальными ценами и P&L
• /ideas - Получить персональные инвестиционные идеи от AI
• /analyze ТИКЕР - Детальный анализ акции (например: /analyze SBER)
• /target ТИКЕР ЦЕНА - Установить целевую цену (например: /target SBER 350)
• /history - История всех операций и торговая статистика
• /finances - Финансовая сводка и показатели доходности
• /settings - Настройки профиля, риска и уведомлений
• /help - Показать это руководство

📊 <b>Возможности бота:</b>

<b>🧠 AI-Анализ и Рекомендации:</b>
• Персональные инвестиционные идеи на основе вашего профиля риска
• Профессиональный анализ любых акций MOEX с обоснованием
• Оценка потенциальной доходности и рисков каждой позиции
• Машинное обучение для улучшения качества рекомендаций

<b>💼 Управление Портфелем:</b>
• Отслеживание всех позиций с актуальными ценами MOEX
• Автоматический расчет прибыли/убытков и общей доходности
• Установка целевых цен с уведомлениями о достижении
• Детальная история операций и торговая статистика

<b>🔔 Система Уведомлений:</b>
• 🌅 Ежедневная сводка рынка (9:00 МСК)
• 📊 Еженедельный отчет портфеля (воскресенье 20:00)
• 🎯 Алерты при достижении целевых цен (пн-пт 10:00-18:00)
• ⏰ Опциональные обновления цен в течение торгового дня

<b>⚙️ Персонализация:</b>
• Настройка уровня риска (консервативный/умеренный/агрессивный)
• Персональный бюджет для инвестиций
• Гибкие настройки уведомлений под ваши предпочтения
• Sandbox-режим для безопасного тестирования стратегий

🚀 <b>Как начать работу:</b>
1. Настройте профиль через "⚙️ Настройки"
2. Укажите ваш инвестиционный бюджет и уровень риска
3. Запросите AI-рекомендации через "💡 Идеи"
4. Изучите предложенные активы с детальным обоснованием
5. Настройте уведомления для отслеживания ваших целей

🔒 <b>Безопасность и надежность:</b>
• Все операции требуют двойного подтверждения
• Sandbox-режим для тестирования без рисков
• Защищенное API и локальное хранение данных
• Никаких автоматических транзакций без вашего согласия

📈 <b>Источники данных:</b>
• Актуальные цены с MOEX в реальном времени
• AI-анализ на базе xAI Grok для максимальной точности
• Учет макроэкономических факторов и новостей рынка
• Машинное обучение для персональных рекомендаций

❓ <b>Нужна помощь?</b>
Используйте /start для главного меню или обратитесь к @d_telitsyn
    """

    # Создаем кнопку возврата в меню
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Главное меню", callback_data="back_to_menu")]
    ])

    await message.answer(help_text, parse_mode="HTML", reply_markup=keyboard)

@router.callback_query(F.data == "help")
async def show_help_callback(callback: CallbackQuery):
    """Показать помощь"""
    help_text = """
❓ <b>Полное руководство Invest Bot</b>

🤖 <b>Основные команды:</b>
• /start - Главное меню и быстрый доступ ко всем функциям
• /portfolio - Показать текущий портфель с актуальными ценами и P&L
• /ideas - Получить персональные инвестиционные идеи от AI
• /analyze ТИКЕР - Детальный анализ акции (например: /analyze SBER)
• /target ТИКЕР ЦЕНА - Установить целевую цену (например: /target SBER 350)
• /history - История всех операций и торговая статистика
• /finances - Финансовая сводка и показатели доходности
• /settings - Настройки профиля, риска и уведомлений

📊 <b>Возможности бота:</b>

<b>🧠 AI-Анализ и Рекомендации:</b>
• Персональные инвестиционные идеи на основе вашего профиля риска
• Профессиональный анализ любых акций MOEX с обоснованием
• Оценка потенциальной доходности и рисков каждой позиции
• Машинное обучение для улучшения качества рекомендаций

<b>💼 Управление Портфелем:</b>
• Отслеживание всех позиций с актуальными ценами MOEX
• Автоматический расчет прибыли/убытков и общей доходности
• Установка целевых цен с уведомлениями о достижении
• Детальная история операций и торговая статистика

<b>🔔 Система Уведомлений:</b>
• 🌅 Ежедневная сводка рынка (9:00 МСК)
• 📊 Еженедельный отчет портфеля (воскресенье 20:00)
• 🎯 Алерты при достижении целевых цен (пн-пт 10:00-18:00)
• ⏰ Опциональные обновления цен в течение торгового дня

<b>⚙️ Персонализация:</b>
• Настройка уровня риска (консервативный/умеренный/агрессивный)
• Персональный бюджет для инвестиций
• Гибкие настройки уведомлений под ваши предпочтения
• Sandbox-режим для безопасного тестирования стратегий

🚀 <b>Как начать работу:</b>
1. Настройте профиль через "⚙️ Настройки"
2. Укажите ваш инвестиционный бюджет и уровень риска
3. Запросите AI-рекомендации через "💡 Идеи"
4. Изучите предложенные активы с детальным обоснованием
5. Настройте уведомления для отслеживания ваших целей

🔒 <b>Безопасность и надежность:</b>
• Все операции требуют двойного подтверждения
• Sandbox-режим для тестирования без рисков
• Защищенное API и локальное хранение данных
• Никаких автоматических транзакций без вашего согласия

📈 <b>Источники данных:</b>
• Актуальные цены с MOEX в реальном времени
• AI-анализ на базе xAI Grok для максимальной точности
• Учет макроэкономических факторов и новостей рынка
• Машинное обучение для персональных рекомендаций

❓ <b>Нужна помощь?</b>
Используйте /start для главного меню или обратитесь к @d_telitsyn
    """

    # Создаем кнопку возврата в меню
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад в меню", callback_data="back_to_menu")]
    ])

    await callback.message.edit_text(help_text, parse_mode="HTML", reply_markup=keyboard)
    await callback.answer()

@router.callback_query(F.data == "settings")
async def show_settings(callback: CallbackQuery):
    """Показать настройки пользователя"""
    try:
        settings = await get_user_settings(callback.from_user.id)

        # Безопасная проверка настроек
        if not settings:
            settings = {
                'risk_level': 'medium',
                'max_investment_amount': 10000,
                'notifications': True
            }

        risk_levels = {
            'low': '🟢 Низкий',
            'medium': '🟡 Средний',
            'high': '🔴 Высокий'
        }

        settings_text = f"""
⚙️ *Ваши настройки:*

🎯 *Уровень риска:* {risk_levels.get(settings.get('risk_level', 'medium'), settings.get('risk_level', 'medium'))}
💰 *Макс. сумма инвестирования:* {settings.get('max_investment_amount', 10000):,.0f} ₽
🔔 *Уведомления:* {'✅ Включены' if settings.get('notifications', True) else '❌ Отключены'}

Выберите что изменить:
        """

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="🎯 Уровень риска", callback_data="set_risk"),
                InlineKeyboardButton(text="💰 Макс. сумма", callback_data="set_max_amount")
            ],
            [
                InlineKeyboardButton(text="🔔 Общие уведомления", callback_data="toggle_notifications"),
                InlineKeyboardButton(text="🔧 Настройки уведомлений", callback_data="notification_settings")
            ],
            [
                InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_menu")
            ]
        ])

        await callback.message.edit_text(settings_text, reply_markup=keyboard, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Ошибка при показе настроек: {e}")
        await callback.message.edit_text("❌ Ошибка при получении настроек")

    await callback.answer()

@router.callback_query(F.data == "set_risk")
async def set_risk_level(callback: CallbackQuery, state: FSMContext):
    """Настройка уровня риска"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🟢 Низкий", callback_data="risk_low"),
            InlineKeyboardButton(text="🟡 Средний", callback_data="risk_medium")
        ],
        [
            InlineKeyboardButton(text="🔴 Высокий", callback_data="risk_high"),
            InlineKeyboardButton(text="❌ Отмена", callback_data="settings")
        ]
    ])

    await callback.message.answer(
        "🎯 *Выберите уровень риска:*\n\n"
        "🟢 *Низкий* - консервативные инвестиции\n"
        "🟡 *Средний* - сбалансированный портфель\n"
        "🔴 *Высокий* - агрессивные инвестиции",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )
    await callback.answer()

@router.callback_query(F.data.startswith("risk_"))
async def update_risk_level(callback: CallbackQuery):
    """Обновление уровня риска"""
    risk_level = callback.data.replace("risk_", "")

    await update_user_settings(callback.from_user.id, risk_level=risk_level)

    risk_names = {'low': 'Низкий', 'medium': 'Средний', 'high': 'Высокий'}
    await callback.message.answer(
        f"✅ Уровень риска изменен на: *{risk_names[risk_level]}*",
        parse_mode="Markdown"
    )

    # Возвращаемся к настройкам
    await show_settings(callback)

@router.callback_query(F.data == "set_max_amount")
async def set_max_amount(callback: CallbackQuery, state: FSMContext):
    """Настройка максимальной суммы"""
    await callback.message.answer(
        "💰 *Введите максимальную сумму для одной инвестиции (в рублях):*\n\n"
        "Например: 50000",
        parse_mode="Markdown"
    )
    await state.set_state(InvestmentStates.waiting_for_max_amount)
    await callback.answer()

@router.message(InvestmentStates.waiting_for_max_amount)
async def process_max_amount(message: Message, state: FSMContext):
    """Обработка максимальной суммы"""
    try:
        amount = float(message.text.replace(",", ".").replace(" ", ""))

        if amount <= 0:
            await message.answer("❌ Сумма должна быть больше 0")
            return

        if amount > 10000000:  # 10 млн лимит
            await message.answer("❌ Слишком большая сумма (максимум 10,000,000 ₽)")
            return

        await update_user_settings(message.from_user.id, max_investment_amount=amount)

        await message.answer(f"✅ Максимальная сумма инвестирования установлена: *{amount:,.0f} ₽*", parse_mode="Markdown")
        await state.clear()

    except ValueError:
        await message.answer("❌ Некорректная сумма. Введите число (например: 50000)")

@router.callback_query(F.data == "toggle_notifications")
async def toggle_notifications(callback: CallbackQuery):
    """Переключение уведомлений"""
    try:
        settings = await get_user_settings(callback.from_user.id)
        if not settings:
            settings = {'notifications': True}

        new_notifications = not settings.get('notifications', True)

        await update_user_settings(callback.from_user.id, notifications=new_notifications)
        logger.info(f"Пользователь {callback.from_user.id}: общие уведомления -> {new_notifications}")

        # Если переключаем в окне уведомлений, возвращаемся туда
        if "уведомлений" in callback.message.text:
            await show_notification_settings(callback)
        else:
            # Иначе возвращаемся к основным настройкам
            await show_settings(callback)

    except Exception as e:
        logger.error(f"Ошибка toggle_notifications: {e}")
        await callback.answer("❌ Ошибка при изменении настройки")

@router.message(Command("test_notifications"))
async def test_notifications(message: Message):
    """Тестирование системы уведомлений"""
    user_id = message.from_user.id
    settings = await get_user_settings(user_id)

    if not settings:
        settings = {
            'notifications': True,
            'max_investment_amount': 10000,
            'risk_level': 'medium'
        }

    if not settings.get('notifications', True):
        await message.answer("❌ У вас отключены уведомления. Включите их в /settings")
        return

    # Симуляция ежедневного анализа
    await message.answer("🧪 *Тест уведомлений запущен...*", parse_mode="Markdown")

    # Получаем рекомендации
    xai_client = XAIClient()
    ideas = await xai_client.get_investment_ideas(
        budget=settings.get('max_investment_amount', 10000),
        risk_level=settings.get('risk_level', 'medium')
    )

    if ideas:
        # Формируем тестовое уведомление
        test_message = "🌅 *ТЕСТ: Ежедневная сводка рынка*\n\n"
        test_message += f"📈 *Свежие инвестиционные идеи для вас:*\n\n"

        for i, idea in enumerate(ideas[:3], 1):
            current_price = idea.get('current_price', 0)
            target_price = idea.get('target_price', 0)
            potential_return = ((target_price - current_price) / current_price * 100) if current_price > 0 else 0

            test_message += f"*{i}.* `{idea['ticker']}`\n"
            test_message += f"💰 Цена: {current_price:.2f} ₽ → 🎯 {target_price:.2f} ₽\n"
            test_message += f"📊 Потенциал: +{potential_return:.1f}%\n"
            test_message += f"📝 {idea['reasoning'][:100]}...\n\n"

        test_message += "_Это тестовое уведомление. Настоящие будут приходить в 9:00 ежедневно._"

        await message.answer(test_message, parse_mode="Markdown")
    else:
        await message.answer("❌ Не удалось получить рекомендации для теста")

@router.message(Command("force_daily"))
async def force_daily_analysis(message: Message):
    """Принудительный запуск ежедневного анализа для отладки"""
    try:
        await message.answer("🔧 Принудительный запуск ежедневного анализа...")

        # Импортируем планировщик
        from scheduler import scheduler_service

        # Запускаем ежедневный анализ принудительно
        await scheduler_service.daily_market_analysis()

        await message.answer("✅ Ежедневный анализ выполнен! Проверьте логи для деталей.")

    except Exception as e:
        logger.error(f"Ошибка при принудительном запуске анализа: {e}")
        await message.answer(f"❌ Ошибка: {e}")

@router.message(Command("force_weekly"))
async def force_weekly_report(message: Message):
    """Принудительный запуск еженедельного отчета для отладки"""
    try:
        await message.answer("🔧 Принудительный запуск еженедельного отчета...")

        from scheduler import scheduler_service
        await scheduler_service.weekly_portfolio_report()

        await message.answer("✅ Еженедельный отчет выполнен!")

    except Exception as e:
        logger.error(f"Ошибка при принудительном запуске еженедельного отчета: {e}")
        await message.answer(f"❌ Ошибка: {e}")

@router.message(Command("force_targets"))
async def force_target_check(message: Message):
    """Принудительная проверка целевых цен для отладки"""
    try:
        await message.answer("🔧 Принудительная проверка целевых цен...")

        from scheduler import scheduler_service
        await scheduler_service.check_target_prices()

        await message.answer("✅ Проверка целевых цен выполнена!")

    except Exception as e:
        logger.error(f"Ошибка при принудительной проверке целевых цен: {e}")
        await message.answer(f"❌ Ошибка: {e}")

@router.message(Command("force_prices"))
async def force_price_update(message: Message):
    """Принудительное обновление цен для отладки"""
    try:
        await message.answer("🔧 Принудительное обновление цен...")

        from scheduler import scheduler_service
        await scheduler_service.update_market_prices()

        await message.answer("✅ Обновление цен выполнено!")

    except Exception as e:
        logger.error(f"Ошибка при принудительном обновлении цен: {e}")
        await message.answer(f"❌ Ошибка: {e}")

@router.message(Command("debug_test"))
async def debug_test_simple(message: Message):
    """Простая версия отладки без сложного форматирования"""
    try:
        user_id = message.from_user.id

        # Проверяем настройки пользователя
        settings = await get_user_settings(user_id)

        text = f"🔍 Отладка уведомлений для пользователя {user_id}\n\n"

        # Проверяем текущее время
        import datetime
        from pytz import UTC
        now = datetime.datetime.now(UTC)
        is_workday = now.weekday() < 5  # 0-4 это пн-пт
        is_workhour = 10 <= now.hour <= 18
        is_worktime = is_workday and is_workhour

        text += f"🕒 Текущее время: {now.strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
        text += f"📅 Рабочий день: {'✅' if is_workday else '❌'} ({now.strftime('%A')})\n"
        text += f"⏰ Рабочие часы: {'✅' if is_workhour else '❌'} (10-18 UTC)\n"
        text += f"💼 Рабочее время: {'✅ Уведомления работают' if is_worktime else '❌ Уведомления остановлены'}\n\n"

        if settings:
            text += "✅ Настройки найдены:\n"
            text += f"• notifications: {settings.get('notifications', 'не задано')}\n"
            text += f"• daily_market_analysis: {settings.get('daily_market_analysis', 'не задано')}\n"
            text += f"• weekly_portfolio_report: {settings.get('weekly_portfolio_report', 'не задано')}\n"
            text += f"• target_price_alerts: {settings.get('target_price_alerts', 'не задано')}\n"
            text += f"• price_updates: {settings.get('price_updates', 'не задано')}\n\n"
        else:
            text += "❌ Настройки НЕ найдены в БД\n\n"

        # Проверяем планировщик
        from scheduler import scheduler_service
        if scheduler_service.is_running:
            text += "⏰ Планировщик: ✅ Запущен\n"
            jobs = scheduler_service.list_jobs()
            text += f"⏰ Активных задач: {len(jobs)}\n"
        else:
            text += "⏰ Планировщик: ❌ Остановлен\n"

        text += "\n🔧 Команды для тестирования:\n"
        text += "• /force_daily - Ежедневная сводка\n"
        text += "• /force_weekly - Еженедельный отчет\n"
        text += "• /force_targets - Целевые цены\n"
        text += "• /force_prices - Обновление цен\n\n"
        text += "ℹ️ *Обратите внимание:*\n"
        text += "Обновления цен и целевые цены работают только в рабочее время (пн-пт 10-18 UTC)"

        await message.answer(text)

    except Exception as e:
        logger.error(f"Ошибка простой отладки уведомлений: {e}")
        await message.answer(f"❌ Ошибка: {str(e)[:100]}...")

@router.message(Command("debug_notifications"))
async def debug_notifications(message: Message):
    """Отладка настроек уведомлений"""
    try:
        user_id = message.from_user.id

        # Проверяем настройки пользователя
        settings = await get_user_settings(user_id)

        debug_info = f"🔍 *Отладка уведомлений для пользователя {user_id}*\n\n"

        if settings:
            debug_info += "✅ *Настройки найдены:*\n"
            debug_info += f"• notifications: {settings.get('notifications', 'не задано')}\n"
            debug_info += f"• daily_market_analysis: {settings.get('daily_market_analysis', 'не задано')}\n"
            debug_info += f"• weekly_portfolio_report: {settings.get('weekly_portfolio_report', 'не задано')}\n"
            debug_info += f"• target_price_alerts: {settings.get('target_price_alerts', 'не задано')}\n"
            debug_info += f"• price_updates: {settings.get('price_updates', 'не задано')}\n\n"
        else:
            debug_info += "❌ *Настройки НЕ найдены в БД*\n\n"

        # Проверяем, есть ли пользователь в списках для разных типов уведомлений
        from database import get_users_with_notification_type
        notification_types = [
            ('daily_market_analysis', '🌅 Ежедневная сводка'),
            ('weekly_portfolio_report', '📊 Еженедельный отчет'),
            ('target_price_alerts', '🎯 Целевые цены'),
            ('price_updates', '⏰ Обновления цен')
        ]

        for notification_type, description in notification_types:
            try:
                users = await get_users_with_notification_type(notification_type)
                user_in_list = any(u['user_id'] == user_id for u in users)
                debug_info += f"{description}: {'✅ Да' if user_in_list else '❌ Нет'} ({len(users)} всего)\\n"
            except Exception as e:
                # Экранируем ошибку для безопасного отображения
                error_msg = str(e).replace('*', '\\*').replace('_', '\\_').replace('[', '\\[').replace(']', '\\]')
                debug_info += f"{description}: ❌ Ошибка проверки - {error_msg}\\n"

        debug_info += "\n"

        # Проверяем планировщик
        from scheduler import scheduler_service
        if scheduler_service.is_running:
            debug_info += "⏰ *Планировщик:* ✅ Запущен\n"
            jobs = scheduler_service.list_jobs()
            debug_info += f"⏰ *Активных задач:* {len(jobs)}\n"
            for job in jobs:
                # Безопасно форматируем время следующего запуска
                next_run = str(job['next_run']) if job['next_run'] else 'не запланировано'
                # Экранируем специальные символы для Markdown
                job_name = str(job['name']).replace('*', '\\*').replace('_', '\\_').replace('[', '\\[').replace(']', '\\]')
                next_run = next_run.replace('*', '\\*').replace('_', '\\_').replace('[', '\\[').replace(']', '\\]')
                debug_info += f"  • {job_name} (следующий запуск: {next_run})\n"
        else:
            debug_info += "⏰ *Планировщик:* ❌ Остановлен\n"

        debug_info += "\\n🔧 *Команды для тестирования:*\\n"
        debug_info += "• `/force_daily` - Ежедневная сводка\\n"
        debug_info += "• `/force_weekly` - Еженедельный отчет\\n"
        debug_info += "• `/force_targets` - Целевые цены\\n"
        debug_info += "• `/force_prices` - Обновление цен"

        try:
            await message.answer(debug_info, parse_mode="Markdown")
        except Exception as markdown_error:
            # Если Markdown не работает, отправляем без форматирования
            logger.warning(f"Ошибка Markdown в debug_notifications: {markdown_error}")
            # Убираем все markdown символы для простого текста
            plain_text = debug_info.replace('*', '').replace('_', '').replace('`', '').replace('\\n', '\n').replace('\\[', '[').replace('\\]', ']')
            await message.answer(plain_text)

    except Exception as e:
        logger.error(f"Ошибка отладки уведомлений: {e}")
        await message.answer(f"❌ Ошибка: {e}")

@router.callback_query(F.data == "analyze_menu")
async def show_analyze_menu(callback: CallbackQuery):
    """Показать меню анализа акций"""
    analyze_text = """
📈 *Анализ акций*

Для анализа любой акции с MOEX используйте команду:
`/analyze ТИКЕР`

*Примеры:*
• `/analyze SBER` - анализ Сбербанка
• `/analyze YNDX` - анализ Яндекса
• `/analyze GAZP` - анализ Газпрома
• `/analyze OZON` - анализ Озона
• `/analyze LKOH` - анализ ЛУКОЙЛа

*Что включает анализ:*
✅ Текущая цена акции
✅ Рекомендация (покупать/держать/продавать)
✅ Целевая цена и потенциал роста
✅ Оценка рисков
✅ Плюсы и минусы компании
✅ Профессиональный анализ от AI

💡 Можно анализировать любые тикеры, торгующиеся на MOEX
    """

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="💡 Идеи от AI", callback_data="get_ideas"),
            InlineKeyboardButton(text="💼 Портфель", callback_data="portfolio")
        ],
        [
            InlineKeyboardButton(text="🔙 Главное меню", callback_data="back_to_menu")
        ]
    ])

    await callback.message.edit_text(analyze_text, reply_markup=keyboard, parse_mode="Markdown")

@router.callback_query(F.data == "back_to_menu")
async def back_to_menu(callback: CallbackQuery):
    """Возврат в главное меню"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="💼 Портфель", callback_data="portfolio"),
            InlineKeyboardButton(text="💡 Идеи", callback_data="get_ideas")
        ],
        [
            InlineKeyboardButton(text="📈 Анализ акций", callback_data="analyze_menu"),
            InlineKeyboardButton(text="📊 История", callback_data="history")
        ],
        [
            InlineKeyboardButton(text="💰 Финансы", callback_data="finances"),
            InlineKeyboardButton(text="⚙️ Настройки", callback_data="settings")
        ],
        [
            InlineKeyboardButton(text="❓ Помощь", callback_data="help")
        ]
    ])

    welcome_text = """
🤖 *Добро пожаловать в Invest Bot!*

Я помогу вам:
• 💡 Получать персональные инвестиционные идеи от AI
• 📈 Анализировать любые акции MOEX по тикеру
• 💼 Управлять инвестиционным портфелем
• 📊 Отслеживать историю операций и доходность
• 🔔 Получать уведомления о рынке

Выберите действие из меню ниже:
    """

    await callback.message.edit_text(welcome_text, parse_mode="Markdown", reply_markup=keyboard)
    await callback.answer()

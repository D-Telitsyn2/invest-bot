import asyncio
import logging
from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from gpt_client import XAIClient
from database import get_user_portfolio, save_order, get_order_history, create_user, update_user_activity, get_user_settings, update_user_settings

logger = logging.getLogger(__name__)

# Состояния FSM
class InvestmentStates(StatesGroup):
    waiting_for_confirmation = State()
    waiting_for_amount = State()
    waiting_for_risk_level = State()
    waiting_for_max_amount = State()

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
            InlineKeyboardButton(text="📊 История", callback_data="history"),
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
• 💼 Управлять инвестиционным портфелем
• 📊 Отслеживать историю операций и доходность
• 🔔 Получать уведомления о рынке

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

            portfolio_text += f"📈 *{ticker}*: {quantity} шт.\n"
            portfolio_text += f"💰 Средняя цена: {avg_price:.2f} ₽\n"
            portfolio_text += f"� Текущая цена: {current_price:.2f} ₽\n"
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
                InlineKeyboardButton(text="🗑️ Продать акции", callback_data="sell_stock"),
                InlineKeyboardButton(text="💡 Новые идеи", callback_data="get_ideas")
            ]
        ])

        await message.answer(portfolio_text, reply_markup=keyboard, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Ошибка при получении портфеля: {e}")
        await message.answer("❌ Ошибка при получении данных портфеля")

@router.message(Command("ideas"))
async def cmd_ideas(message: Message, state: FSMContext):
    """Получить инвестиционные идеи"""
    await message.answer("🤖 Анализирую рынок с помощью xAI Grok...")

    try:
        # Получаем настройки пользователя
        settings = await get_user_settings(message.from_user.id)

        # Получаем идеи от xAI Grok с учетом настроек
        xai_client = XAIClient()
        ideas = await xai_client.get_investment_ideas(
            budget=settings['max_investment_amount'],
            risk_level=settings['risk_level']
        )

        if not ideas:
            await message.answer("❌ Не удалось получить рекомендации для теста")
            return

        # Сохраняем идеи в состоянии для последующего выбора
        await state.update_data(investment_ideas=ideas)

        # Формируем сообщение с идеями
        ideas_text = "🎯 *Инвестиционные идеи от xAI Grok:*\n\n"
        keyboard_buttons = []

        for i, idea in enumerate(ideas[:5], 1):  # Показываем максимум 5 идей
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
            ideas_text += f" {reasoning}\n\n"            # Добавляем кнопку для покупки этой идеи
            if i <= 2:  # Первый ряд - первые 2 идеи
                if len(keyboard_buttons) == 0:
                    keyboard_buttons.append([])
                keyboard_buttons[0].append(
                    InlineKeyboardButton(text=f"💳 Купить {ticker}", callback_data=f"select_idea_{i-1}")
                )
            elif i <= 4:  # Второй ряд - следующие 2 идеи
                if len(keyboard_buttons) == 1:
                    keyboard_buttons.append([])
                keyboard_buttons[1].append(
                    InlineKeyboardButton(text=f"💳 Купить {ticker}", callback_data=f"select_idea_{i-1}")
                )
            else:  # Третий ряд - последняя идея
                if len(keyboard_buttons) == 2:
                    keyboard_buttons.append([])
                keyboard_buttons[2].append(
                    InlineKeyboardButton(text=f"💳 Купить {ticker}", callback_data=f"select_idea_{i-1}")
                )

        # Добавляем кнопку обновления идей
        keyboard_buttons.append([
            InlineKeyboardButton(text="🔄 Обновить идеи", callback_data="get_ideas")
        ])

        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
        await message.answer(ideas_text, reply_markup=keyboard, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Ошибка при получении инвестиционных идей: {e}")
        await message.answer("❌ Ошибка при получении инвестиционных идей")

@router.callback_query(F.data == "notification_settings")
async def show_notification_settings(callback: CallbackQuery):
    """Показать детальные настройки уведомлений"""
    try:
        settings = await get_user_settings(callback.from_user.id)

        settings_text = f"""
🔔 *Настройки уведомлений*

📊 *Общие уведомления:* {'✅' if settings['notifications'] else '❌'}

*Детальные настройки:*
🌅 *Ежедневная сводка* (9:00): {'✅' if settings.get('daily_market_analysis', True) else '❌'}
📊 *Еженедельный отчет* (вс 20:00): {'✅' if settings.get('weekly_portfolio_report', True) else '❌'}
🎯 *Целевые цены* (каждые 30 мин): {'✅' if settings.get('target_price_alerts', True) else '❌'}
⏰ *Обновления цен* (каждые 5 мин): {'✅' if settings.get('price_updates', False) else '❌'}
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
        new_value = not settings.get('daily_market_analysis', True)

        await update_user_settings(callback.from_user.id, daily_market_analysis=new_value)
        logger.info(f"Пользователь {callback.from_user.id}: ежедневный анализ -> {new_value}")

        # Возвращаемся к настройкам уведомлений
        await show_notification_settings(callback)

    except Exception as e:
        logger.error(f"Ошибка toggle_daily_analysis: {e}")
        await callback.answer("❌ Ошибка при изменении настройки")

@router.callback_query(F.data == "toggle_weekly_report")
async def toggle_weekly_report(callback: CallbackQuery):
    """Переключение еженедельного отчета"""
    try:
        settings = await get_user_settings(callback.from_user.id)
        new_value = not settings.get('weekly_portfolio_report', True)

        await update_user_settings(callback.from_user.id, weekly_portfolio_report=new_value)
        logger.info(f"Пользователь {callback.from_user.id}: еженедельный отчет -> {new_value}")

        # Возвращаемся к настройкам уведомлений
        await show_notification_settings(callback)

    except Exception as e:
        logger.error(f"Ошибка toggle_weekly_report: {e}")
        await callback.answer("❌ Ошибка при изменении настройки")

@router.callback_query(F.data == "toggle_target_alerts")
async def toggle_target_alerts(callback: CallbackQuery):
    """Переключение уведомлений о целевых ценах"""
    try:
        settings = await get_user_settings(callback.from_user.id)
        new_value = not settings.get('target_price_alerts', True)

        await update_user_settings(callback.from_user.id, target_price_alerts=new_value)
        logger.info(f"Пользователь {callback.from_user.id}: целевые цены -> {new_value}")

        # Возвращаемся к настройкам уведомлений
        await show_notification_settings(callback)

    except Exception as e:
        logger.error(f"Ошибка toggle_target_alerts: {e}")
        await callback.answer("❌ Ошибка при изменении настройки")

@router.callback_query(F.data == "toggle_price_updates")
async def toggle_price_updates(callback: CallbackQuery):
    """Переключение обновлений цен"""
    try:
        settings = await get_user_settings(callback.from_user.id)
        new_value = not settings.get('price_updates', False)

        await update_user_settings(callback.from_user.id, price_updates=new_value)
        logger.info(f"Пользователь {callback.from_user.id}: обновления цен -> {new_value}")

        # Возвращаемся к настройкам уведомлений
        await show_notification_settings(callback)

    except Exception as e:
        logger.error(f"Ошибка toggle_price_updates: {e}")
        await callback.answer("❌ Ошибка при изменении настройки")

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

Укажите сумму для инвестирования (в рублях):
        """

        await callback.message.answer(confirmation_text, parse_mode="Markdown")
        await state.update_data(selected_idea=selected_idea)
        await state.set_state(InvestmentStates.waiting_for_amount)

    await callback.answer()

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
                f"📈 Тикер: *{selected_idea['ticker']}*\n"
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

@router.callback_query(F.data.startswith("sell_"))
async def process_sell_stock(callback: CallbackQuery, state: FSMContext):
    """Обработка продажи конкретной акции"""
    if callback.data == "sell_stock":
        await sell_stock_selection(callback, state)
        return

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

Продать все акции по текущей цене?
        """

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Продать все", callback_data=f"confirm_sell_{ticker}"),
                InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_sell")
            ]
        ])

        await callback.message.answer(confirmation_text, reply_markup=keyboard, parse_mode="Markdown")
        await state.update_data(sell_ticker=ticker, sell_price=current_price, sell_quantity=quantity)

    except Exception as e:
        logger.error(f"Ошибка при обработке продажи {ticker}: {e}")
        await callback.message.answer("❌ Ошибка при обработке продажи")

    await callback.answer()

@router.callback_query(F.data.startswith("confirm_sell_"))
async def confirm_sell_stock(callback: CallbackQuery, state: FSMContext):
    """Подтверждение продажи акции"""
    ticker = callback.data.replace("confirm_sell_", "")

    try:
        data = await state.get_data()
        sell_price = data.get("sell_price")
        sell_quantity = data.get("sell_quantity")

        if not all([sell_price, sell_quantity]):
            await callback.message.answer("❌ Ошибка: неполные данные для продажи")
            await state.clear()
            return

        total_amount = sell_quantity * sell_price

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
                f"📉 Продано: *{ticker}*\n"
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
        logger.error(f"Ошибка при подтверждении продажи {ticker}: {e}")
        await callback.message.answer("❌ Ошибка при выполнении продажи")
        await state.clear()

    await callback.answer()

@router.callback_query(F.data == "cancel_sell")
async def cancel_sell(callback: CallbackQuery, state: FSMContext):
    """Отмена продажи"""
    await callback.message.answer("❌ Продажа отменена")
    await state.clear()
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

        history_text = "📊 *История операций:*\n\n"

        for order in history[-10:]:  # Последние 10 операций
            history_text += f"📅 {order['date']}\n"
            history_text += f"📈 {order['ticker']}: {order['quantity']} шт.\n"
            history_text += f"💰 Цена: {order['price']:.2f} ₽\n"
            history_text += f"📊 Операция: {order['order_type']}\n"
            history_text += f"💎 Сумма: {order['total_amount']:.2f} ₽\n\n"

        await message.answer(history_text, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Ошибка при получении истории: {e}")
        await message.answer("❌ Ошибка при получении истории операций")

@router.message(Command("settings"))
async def cmd_settings(message: Message):
    """Показать настройки (команда)"""
    try:
        settings = await get_user_settings(message.from_user.id)

        risk_levels = {
            'low': '🟢 Низкий',
            'medium': '🟡 Средний',
            'high': '🔴 Высокий'
        }

        settings_text = f"""
⚙️ *Ваши настройки:*

🎯 *Уровень риска:* {risk_levels.get(settings['risk_level'], settings['risk_level'])}
💰 *Макс. сумма инвестирования:* {settings['max_investment_amount']:,.0f} ₽
🔔 *Уведомления:* {'✅ Включены' if settings['notifications'] else '❌ Отключены'}

Выберите что изменить:
        """

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="🎯 Уровень риска", callback_data="set_risk"),
                InlineKeyboardButton(text="💰 Макс. сумма", callback_data="set_max_amount")
            ],
            [
                InlineKeyboardButton(text="🔔 Уведомления", callback_data="toggle_notifications"),
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
    await cmd_portfolio(callback.message)
    await callback.answer()

@router.callback_query(F.data == "get_ideas")
async def get_ideas_callback(callback: CallbackQuery, state: FSMContext):
    """Получить идеи через callback"""
    await cmd_ideas(callback.message, state)
    await callback.answer()

@router.callback_query(F.data == "history")
async def show_history_callback(callback: CallbackQuery):
    """Показать историю через callback"""
    await cmd_history(callback.message)
    await callback.answer()

@router.message(Command("help"))
async def cmd_help(message: Message):
    """Показать помощь (команда)"""
    help_text = """
❓ *Полное руководство по боту:*

🤖 *Основные команды:*
• /start - Главное меню и быстрый доступ ко всем функциям
• /portfolio - Показать текущий портфель и его стоимость
• /ideas - Получить персональные инвестиционные идеи от AI
• /history - История всех ваших операций
• /settings - Настройки профиля и уведомлений
• /help - Показать это руководство

📊 *Функции бота:*

*1. Инвестиционные идеи (AI-powered):*
• Персональные рекомендации на основе ваших настроек
• Анализ рисков и потенциальной доходности
• Актуальные цены и целевые уровни
• Обоснование каждой рекомендации

*2. Управление портфелем:*
• Просмотр всех ваших активов
• Текущая стоимость позиций
• Прибыль/убыток по каждой позиции
• Общая доходность портфеля

*3. Уведомления:*
• 🌅 Ежедневная сводка рынка (9:00)
• 📊 Еженедельный отчет портфеля (вс 20:00)
• 🎯 Уведомления о достижении целевых цен
• ⏰ Регулярные обновления цен (опционально)

*4. Настройки профиля:*
• Максимальная сумма для инвестиций
• Уровень риска (консервативный/умеренный/агрессивный)
• Гибкие настройки уведомлений
• Персонализация рекомендаций

💡 *Как начать работу:*
1. Настройте профиль через "⚙️ Настройки"
2. Укажите бюджет и уровень риска
3. Запросите идеи через "💡 Идеи"
4. Изучите рекомендации и выберите подходящие
5. Настройте уведомления для отслеживания

🔒 *Безопасность:*
• Все операции проходят через защищенное API
• Двойное подтверждение для сделок
• Sandbox-режим для тестирования
• Никаких автоматических транзакций без вашего согласия

📈 *Аналитика:*
• Интеграция с xAI Grok для анализа рынка
• Реальные данные с биржи
• Машинное обучение для персональных рекомендаций
• Учет макроэкономических факторов

❓ *Нужна помощь?*
Используйте /start для возврата в главное меню или обратитесь к разработчику.
    """

    # Создаем кнопку возврата в меню
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Главное меню", callback_data="back_to_menu")]
    ])

    await message.answer(help_text, parse_mode="Markdown", reply_markup=keyboard)

@router.callback_query(F.data == "help")
async def show_help_callback(callback: CallbackQuery):
    """Показать помощь"""
    help_text = """
❓ *Полное руководство по боту:*

🤖 *Основные команды:*
• /start - Главное меню и быстрый доступ ко всем функциям
• /portfolio - Показать текущий портфель и его стоимость
• /ideas - Получить персональные инвестиционные идеи от AI
• /history - История всех ваших операций
• /settings - Настройки профиля и уведомлений

📊 *Функции бота:*

*1. Инвестиционные идеи (AI-powered):*
• Персональные рекомендации на основе ваших настроек
• Анализ рисков и потенциальной доходности
• Актуальные цены и целевые уровни
• Обоснование каждой рекомендации

*2. Управление портфелем:*
• Просмотр всех ваших активов
• Текущая стоимость позиций
• Прибыль/убыток по каждой позиции
• Общая доходность портфеля

*3. Уведомления:*
• 🌅 Ежедневная сводка рынка (9:00)
• 📊 Еженедельный отчет портфеля (вс 20:00)
• 🎯 Уведомления о достижении целевых цен
• ⏰ Регулярные обновления цен (опционально)

*4. Настройки профиля:*
• Максимальная сумма для инвестиций
• Уровень риска (консервативный/умеренный/агрессивный)
• Гибкие настройки уведомлений
• Персонализация рекомендаций

💡 *Как начать работу:*
1. Настройте профиль через "⚙️ Настройки"
2. Укажите бюджет и уровень риска
3. Запросите идеи через "💡 Идеи"
4. Изучите рекомендации и выберите подходящие
5. Настройте уведомления для отслеживания

🔒 *Безопасность:*
• Все операции проходят через защищенное API
• Двойное подтверждение для сделок
• Sandbox-режим для тестирования
• Никаких автоматических транзакций без вашего согласия

📈 *Аналитика:*
• Интеграция с xAI Grok для анализа рынка
• Реальные данные с биржи
• Машинное обучение для персональных рекомендаций
• Учет макроэкономических факторов

❓ *Нужна помощь?*
Используйте /start для возврата в главное меню или обратитесь к разработчику.
    """

    # Создаем кнопку возврата в меню
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад в меню", callback_data="back_to_menu")]
    ])

    await callback.message.edit_text(help_text, parse_mode="Markdown", reply_markup=keyboard)
    await callback.answer()

@router.callback_query(F.data == "settings")
async def show_settings(callback: CallbackQuery):
    """Показать настройки пользователя"""
    try:
        settings = await get_user_settings(callback.from_user.id)

        risk_levels = {
            'low': '🟢 Низкий',
            'medium': '🟡 Средний',
            'high': '🔴 Высокий'
        }

        settings_text = f"""
⚙️ *Ваши настройки:*

🎯 *Уровень риска:* {risk_levels.get(settings['risk_level'], settings['risk_level'])}
💰 *Макс. сумма инвестирования:* {settings['max_investment_amount']:,.0f} ₽
🔔 *Уведомления:* {'✅ Включены' if settings['notifications'] else '❌ Отключены'}

Выберите что изменить:
        """

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="🎯 Уровень риска", callback_data="set_risk"),
                InlineKeyboardButton(text="💰 Макс. сумма", callback_data="set_max_amount")
            ],
            [
                InlineKeyboardButton(text="🔔 Уведомления", callback_data="toggle_notifications"),
                InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_menu")
            ]
        ])

        await callback.message.answer(settings_text, reply_markup=keyboard, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Ошибка при показе настроек: {e}")
        await callback.message.answer("❌ Ошибка при получении настроек")

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
        new_notifications = not settings['notifications']

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

    if not settings['notifications']:
        await message.answer("❌ У вас отключены уведомления. Включите их в /settings")
        return

    # Симуляция ежедневного анализа
    await message.answer("🧪 *Тест уведомлений запущен...*", parse_mode="Markdown")

    # Получаем рекомендации
    xai_client = XAIClient()
    ideas = await xai_client.get_investment_ideas(
        budget=settings['max_investment_amount'],
        risk_level=settings['risk_level']
    )

    if ideas:
        # Формируем тестовое уведомление
        test_message = "🌅 *ТЕСТ: Ежедневная сводка рынка*\n\n"
        test_message += f"📈 *Свежие инвестиционные идеи для вас:*\n\n"

        for i, idea in enumerate(ideas[:3], 1):
            current_price = idea.get('current_price', 0)
            target_price = idea.get('target_price', 0)
            potential_return = ((target_price - current_price) / current_price * 100) if current_price > 0 else 0

            test_message += f"*{i}. {idea['ticker']}*\n"
            test_message += f"💰 Цена: {current_price:.2f} ₽ → 🎯 {target_price:.2f} ₽\n"
            test_message += f"📊 Потенциал: +{potential_return:.1f}%\n"
            test_message += f"📝 {idea['reasoning'][:100]}...\n\n"

        test_message += "_Это тестовое уведомление. Настоящие будут приходить в 9:00 ежедневно._"

        await message.answer(test_message, parse_mode="Markdown")
    else:
        await message.answer("❌ Не удалось получить рекомендации для теста")

@router.callback_query(F.data == "back_to_menu")
async def back_to_menu(callback: CallbackQuery):
    """Возврат в главное меню"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="💼 Портфель", callback_data="portfolio"),
            InlineKeyboardButton(text="💡 Идеи", callback_data="get_ideas")
        ],
        [
            InlineKeyboardButton(text="📊 История", callback_data="history"),
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
• 💼 Управлять инвестиционным портфелем
• 📊 Отслеживать историю операций и доходность
• 🔔 Получать уведомления о рынке

Выберите действие из меню ниже:
    """

    await callback.message.edit_text(welcome_text, parse_mode="Markdown", reply_markup=keyboard)
    await callback.answer()

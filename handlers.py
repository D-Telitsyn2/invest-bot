import asyncio
import logging
from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from gpt_client import XAIClient
from database import get_user_portfolio, save_order, get_order_history, create_user, update_user_activity

logger = logging.getLogger(__name__)

# Состояния FSM
class InvestmentStates(StatesGroup):
    waiting_for_confirmation = State()
    waiting_for_amount = State()

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
            InlineKeyboardButton(text="❓ Помощь", callback_data="help")
        ]
    ])

    welcome_text = """
🤖 *Добро пожаловать в Invest Bot!*

Я помогу вам:
• 💡 Получать инвестиционные идеи от AI
• 💼 Управлять портфелем
• 📈 Получать инвестиционные рекомендации от ИИ
• 📊 Отслеживать историю операций

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
        # Получаем идеи от xAI Grok
        xai_client = XAIClient()
        ideas = await xai_client.get_investment_ideas(budget=10000)

        if not ideas:
            await message.answer("❌ Не удалось получить идеи. Попробуйте позже.")
            return

        ideas_text = "🚀 *Инвестиционные идеи от xAI Grok:*\n\n"

        for i, idea in enumerate(ideas[:5], 1):  # Показываем первые 5 идей
            current_price = idea.get('price', 0)
            target_price = idea.get('target_price', 0)
            timeframe = idea.get('target_timeframe', 'средний срок')

            # Рассчитываем потенциальную доходность
            if current_price > 0 and target_price > 0:
                potential_return = ((target_price - current_price) / current_price) * 100
                return_emoji = "📈" if potential_return > 0 else "📉"
                return_text = f"{return_emoji} Потенциал: {potential_return:+.1f}%"
            else:
                return_text = "⚠️ Цели нет"

            ideas_text += f"*{i}. {idea['ticker']}*\n"
            ideas_text += f"📊 Рекомендация: {idea['action']}\n"
            ideas_text += f"💰 Текущая цена: {current_price:.2f} ₽\n"
            ideas_text += f"🎯 Целевая цена: {target_price:.2f} ₽ ({timeframe})\n"
            ideas_text += f"{return_text}\n"
            ideas_text += f"📝 {idea['reasoning']}\n\n"

        # Клавиатура для выбора идеи
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"📈 {idea['ticker']}", callback_data=f"select_idea_{i}")]
            for i, idea in enumerate(ideas[:15])
        ])

        await message.answer(ideas_text, reply_markup=keyboard, parse_mode="Markdown")
        await state.update_data(investment_ideas=ideas)

    except Exception as e:
        logger.error(f"Ошибка при получении идей: {e}")
        await message.answer("❌ Ошибка при получении инвестиционных идей")

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

@router.callback_query(F.data == "help")
async def show_help_callback(callback: CallbackQuery):
    """Показать помощь"""
    help_text = """
❓ *Помощь по боту:*

🤖 *Основные команды:*
• /start - Главное меню
• /portfolio - Показать портфель
• /ideas - Получить инвестиционные идеи
• /history - История операций

💡 *Как использовать:*
1. Запросите инвестиционные идеи
2. Выберите понравившуюся идею
3. Укажите сумму для инвестирования
4. Подтвердите сделку

⚠️ *Важно:*
Все сделки требуют ручного подтверждения.
Бот работает в sandbox режиме для безопасности.
    """

    await callback.message.answer(help_text, parse_mode="Markdown")
    await callback.answer()

def register_handlers(dp):
    """Регистрация всех обработчиков"""
    dp.include_router(router)

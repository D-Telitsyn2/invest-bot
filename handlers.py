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
    """Показать портфель пользователя"""
    try:
        portfolio = await get_user_portfolio(message.from_user.id)

        if not portfolio:
            await message.answer("💼 Ваш портфель пуст")
            return

        portfolio_text = "💼 *Ваш портфель:*\n\n"
        total_value = 0

        for position in portfolio:
            portfolio_text += f"📈 {position['ticker']}: {position['quantity']} шт.\n"
            portfolio_text += f"💰 Средняя цена: {position['avg_price']:.2f} ₽\n"
            portfolio_text += f"📊 Текущая стоимость: {position['current_value']:.2f} ₽\n\n"
            total_value += position['current_value']

        portfolio_text += f"💎 *Общая стоимость: {total_value:.2f} ₽*"

        await message.answer(portfolio_text, parse_mode="Markdown")

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

        for i, idea in enumerate(ideas[:5], 1):  # Показываем первые 15 идей
            ideas_text += f"*{i}. {idea['ticker']}*\n"
            ideas_text += f"📊 Рекомендация: {idea['action']}\n"
            ideas_text += f"💰 Цена: {idea['price']:.2f} ₽\n"
            ideas_text += f"🎯 Цель: {idea['target_price']:.2f} ₽\n"
            ideas_text += f"📝 Обоснование: {idea['reasoning']}\n\n"

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

        # Симуляция выполнения сделки (торговля отключена)
        await callback.message.edit_text(
            "❌ Торговля через бота временно недоступна.\n"
            "Используйте полученные рекомендации для торговли в вашем брокерском приложении.",
            reply_markup=None
        )

    except Exception as e:
        logger.error(f"Ошибка при выполнении операции: {e}")
        await callback.message.answer("❌ Произошла ошибка при выполнении операции")
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

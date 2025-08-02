# Функции для настроек уведомлений

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
    settings = await get_user_settings(callback.from_user.id)
    new_value = not settings.get('daily_market_analysis', True)

    await update_user_settings(callback.from_user.id, daily_market_analysis=new_value)

    status = "включен" if new_value else "отключен"
    await callback.message.answer(f"✅ Ежедневный анализ рынка {status}")

    # Возвращаемся к настройкам уведомлений
    await show_notification_settings(callback)

@router.callback_query(F.data == "toggle_weekly_report")
async def toggle_weekly_report(callback: CallbackQuery):
    """Переключение еженедельного отчета"""
    settings = await get_user_settings(callback.from_user.id)
    new_value = not settings.get('weekly_portfolio_report', True)

    await update_user_settings(callback.from_user.id, weekly_portfolio_report=new_value)

    status = "включен" if new_value else "отключен"
    await callback.message.answer(f"✅ Еженедельный отчет {status}")

    # Возвращаемся к настройкам уведомлений
    await show_notification_settings(callback)

@router.callback_query(F.data == "toggle_target_alerts")
async def toggle_target_alerts(callback: CallbackQuery):
    """Переключение уведомлений о целевых ценах"""
    settings = await get_user_settings(callback.from_user.id)
    new_value = not settings.get('target_price_alerts', True)

    await update_user_settings(callback.from_user.id, target_price_alerts=new_value)

    status = "включены" if new_value else "отключены"
    await callback.message.answer(f"✅ Уведомления о целевых ценах {status}")

    # Возвращаемся к настройкам уведомлений
    await show_notification_settings(callback)

@router.callback_query(F.data == "toggle_price_updates")
async def toggle_price_updates(callback: CallbackQuery):
    """Переключение обновлений цен"""
    settings = await get_user_settings(callback.from_user.id)
    new_value = not settings.get('price_updates', False)

    await update_user_settings(callback.from_user.id, price_updates=new_value)

    status = "включены" if new_value else "отключены"
    await callback.message.answer(f"✅ Обновления цен {status}")

    # Возвращаемся к настройкам уведомлений
    await show_notification_settings(callback)

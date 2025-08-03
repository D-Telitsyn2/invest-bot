#!/usr/bin/env python3
"""
Патч для обновления отображения технических данных в handlers.py
"""

def patch_ideas_display():
    """Создает новую функцию отображения идей с техническими данными"""

    new_display_code = '''
    # Формируем детальное сообщение с техническими данными
    for i, idea in enumerate(ideas[:7], 1):
        ticker = idea.get('ticker', 'N/A')
        price = idea.get('price', 0)
        target_price = idea.get('target_price', 0)
        action = idea.get('action', 'BUY')
        reasoning = idea.get('reasoning', 'Нет описания')

        # Новые технические данные от Grok-4
        support_level = idea.get('support_level', 0)
        resistance_level = idea.get('resistance_level', 0)
        trend = idea.get('trend', '')
        current_price = idea.get('current_price', price)

        # Рассчитываем потенциальную доходность
        potential_return = 0
        if price > 0 and target_price > 0:
            potential_return = ((target_price - price) / price) * 100

        ideas_text += f"*{i}.* `{ticker}`\\n"
        ideas_text += f"💰 Текущая цена: {current_price:.2f} ₽\\n"
        ideas_text += f"🎯 Целевая цена: {target_price:.2f} ₽ (+{potential_return:.1f}%)\\n"

        # Добавляем технические уровни если они есть
        if support_level > 0:
            ideas_text += f"🟢 Поддержка: {support_level:.2f} ₽\\n"
        if resistance_level > 0:
            ideas_text += f"🔴 Сопротивление: {resistance_level:.2f} ₽\\n"
        if trend and trend.strip():
            ideas_text += f"📊 Тренд: {trend}\\n"

        ideas_text += f"💡 {reasoning}\\n\\n"
    '''

    print("📝 Новый код отображения для handlers.py:")
    print(new_display_code)

    return new_display_code

if __name__ == "__main__":
    patch_ideas_display()

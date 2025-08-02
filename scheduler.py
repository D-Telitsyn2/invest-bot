import asyncio
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime
from typing import Dict, Optional

from database import (
    update_prices_in_portfolio, get_portfolio_statistics,
    get_users_with_notification_type, get_user_portfolio_for_notifications,
    check_target_prices_achieved
)
from gpt_client import get_investment_ideas
from market_data import RealMarketData

logger = logging.getLogger(__name__)

class SchedulerService:
    def __init__(self, bot=None):
        self.scheduler = AsyncIOScheduler()
        self.bot = bot
        self.is_running = False

    async def start(self):
        """Запуск планировщика"""
        if not self.is_running:
            # Обновление цен каждые 5 минут в рабочее время
            self.scheduler.add_job(
                self.update_market_prices,
                CronTrigger(
                    minute="*/5",
                    hour="10-18",
                    day_of_week="mon-fri"
                ),
                id="update_prices",
                name="Обновление цен акций"
            )

            # Ежедневный анализ рынка в 9:00
            self.scheduler.add_job(
                self.daily_market_analysis,
                CronTrigger(hour=9, minute=0),
                id="daily_analysis",
                name="Ежедневный анализ рынка"
            )

            # Еженедельный отчет по воскресеньям в 20:00
            self.scheduler.add_job(
                self.weekly_portfolio_report,
                CronTrigger(day_of_week="sun", hour=20, minute=0),
                id="weekly_report",
                name="Еженедельный отчет"
            )

            # Проверка целевых цен каждые 30 минут в рабочее время
            self.scheduler.add_job(
                self.check_target_prices,
                CronTrigger(
                    minute="*/30",
                    hour="10-18",
                    day_of_week="mon-fri"
                ),
                id="check_targets",
                name="Проверка целевых цен"
            )

            self.scheduler.start()
            self.is_running = True
            logger.info("Планировщик задач запущен")

    async def stop(self):
        """Остановка планировщика"""
        if self.is_running:
            self.scheduler.shutdown()
            self.is_running = False
            logger.info("Планировщик задач остановлен")

    async def update_market_prices(self):
        """Обновление цен акций в рабочее время"""
        try:
            logger.info("⏰ Обновление цен акций...")

            # Получаем всех пользователей с портфелями (для обновления цен)
            users = await get_users_with_notification_type('price_updates')
            if not users:
                return

            # Собираем уникальные тикеры из всех портфелей
            unique_tickers = set()
            for user in users:
                portfolio = await get_user_portfolio_for_notifications(user['user_id'])
                for position in portfolio:
                    unique_tickers.add(position['ticker'])

            if not unique_tickers:
                return

            # Получаем актуальные цены
            market_data = RealMarketData()
            try:
                prices = await market_data.get_multiple_moex_prices(list(unique_tickers))
                if prices:
                    await update_prices_in_portfolio(prices)
                    logger.info(f"Обновлены цены для {len(prices)} акций")
            finally:
                await market_data.close_session()

        except Exception as e:
            logger.error(f"Ошибка при обновлении цен: {e}")

    async def daily_market_analysis(self):
        """Ежедневный анализ рынка"""
        try:
            logger.info("📊 Ежедневный анализ рынка...")

            # Получаем пользователей с включенными ежедневными уведомлениями
            users = await get_users_with_notification_type('daily_market_analysis')

            for user in users:
                try:
                    # Получаем персональные рекомендации
                    ideas = await get_investment_ideas(
                        budget=user['max_investment_amount'],
                        risk_level=user['risk_level']
                    )

                    if ideas and self.bot:
                        # Формируем сообщение
                        message = "🌅 *Доброе утро! Ежедневная сводка рынка*\n\n"
                        message += f"📈 *Свежие инвестиционные идеи для вас:*\n\n"

                        for i, idea in enumerate(ideas[:3], 1):  # Топ-3 для уведомлений
                            current_price = idea.get('price', 0)  # Исправлено: используем 'price' вместо 'current_price'
                            target_price = idea.get('target_price', 0)
                            potential_return = ((target_price - current_price) / current_price * 100) if current_price > 0 else 0

                            message += f"*{i}. {idea['ticker']}*\n"
                            message += f"💰 Цена: {current_price:.2f} ₽ → 🎯 {target_price:.2f} ₽\n"
                            message += f"📊 Потенциал: +{potential_return:.1f}%\n"
                            message += f"📝 {idea['reasoning'][:100]}...\n\n"

                        message += "_Полный анализ доступен в боте: /ideas_"

                        await self.bot.send_message(
                            chat_id=user['user_id'],
                            text=message,
                            parse_mode="Markdown"
                        )

                        # Небольшая пауза между отправками
                        await asyncio.sleep(0.1)

                except Exception as e:
                    logger.error(f"Ошибка при отправке ежедневного анализа пользователю {user['user_id']}: {e}")

        except Exception as e:
            logger.error(f"Ошибка при ежедневном анализе: {e}")

    async def weekly_portfolio_report(self):
        """Еженедельный отчет по портфелям"""
        try:
            logger.info("📊 Генерация еженедельных отчетов...")

            # Получаем пользователей с включенными еженедельными отчетами
            users = await get_users_with_notification_type('weekly_portfolio_report')

            for user in users:
                try:
                    # Получаем портфель пользователя
                    portfolio = await get_user_portfolio_for_notifications(user['user_id'])

                    if not portfolio:
                        continue

                    # Получаем общую статистику
                    stats = await get_portfolio_statistics(user['user_id'])

                    # Формируем отчет
                    message = "📅 *Еженедельный отчет по портфелю*\n\n"

                    # Общая статистика
                    total_value = stats.get('total_value', 0)
                    total_cost = stats.get('total_cost', 0)
                    total_pnl = total_value - total_cost
                    total_return = (total_pnl / total_cost * 100) if total_cost > 0 else 0

                    message += f"💼 *Общая статистика:*\n"
                    message += f"💰 Стоимость: {total_value:,.0f} ₽\n"
                    message += f"💸 Вложено: {total_cost:,.0f} ₽\n"
                    message += f"📈 P&L: {total_pnl:+,.0f} ₽ ({total_return:+.1f}%)\n\n"

                    # Топ позиции
                    message += "🏆 *Топ позиции:*\n"
                    sorted_positions = sorted(portfolio, key=lambda x: x['return_pct'], reverse=True)

                    for i, pos in enumerate(sorted_positions[:5], 1):
                        message += f"{i}. *{pos['ticker']}*: {pos['return_pct']:+.1f}% "
                        message += f"({pos['unrealized_pnl']:+,.0f} ₽)\n"

                    message += f"\n_Полная статистика в боте: /portfolio_"

                    if self.bot:
                        await self.bot.send_message(
                            chat_id=user['user_id'],
                            text=message,
                            parse_mode="Markdown"
                        )

                        # Небольшая пауза между отправками
                        await asyncio.sleep(0.1)

                except Exception as e:
                    logger.error(f"Ошибка при отправке еженедельного отчета пользователю {user['user_id']}: {e}")

        except Exception as e:
            logger.error(f"Ошибка при генерации еженедельных отчетов: {e}")

    async def check_target_prices(self):
        """Проверка достижения целевых цен"""
        try:
            logger.info("🎯 Проверка целевых цен...")

            # Получаем пользователей с включенными уведомлениями о целевых ценах
            users = await get_users_with_notification_type('target_price_alerts')

            for user in users:
                try:
                    # Проверяем достижение целевых цен
                    achieved_targets = await check_target_prices_achieved(user['user_id'])

                    if not achieved_targets:
                        continue

                    # Формируем уведомление
                    message = "🎯 *Целевые цены достигнуты!*\n\n"

                    for target in achieved_targets:
                        message += f"*{target['ticker']}*\n"
                        message += f"🎯 Целевая цена: {target['target_price']:.2f} ₽\n"
                        message += f"💰 Текущая цена: {target['current_price']:.2f} ₽\n"
                        message += f"📈 Ваша прибыль: {target['unrealized_pnl']:+,.0f} ₽ ({target['return_pct']:+.1f}%)\n\n"

                    message += "_Рассмотрите возможность фиксации прибыли! 💰_"

                    if self.bot:
                        await self.bot.send_message(
                            chat_id=user['user_id'],
                            text=message,
                            parse_mode="Markdown"
                        )

                        # Небольшая пауза между отправками
                        await asyncio.sleep(0.1)

                except Exception as e:
                    logger.error(f"Ошибка при проверке целевых цен для пользователя {user['user_id']}: {e}")

        except Exception as e:
            logger.error(f"Ошибка при проверке целевых цен: {e}")

    def add_custom_job(self, func, trigger, job_id: str, name: Optional[str] = None):
        """Добавление пользовательской задачи"""
        try:
            self.scheduler.add_job(
                func=func,
                trigger=trigger,
                id=job_id,
                name=name or job_id,
                replace_existing=True
            )
            logger.info(f"Добавлена задача: {name or job_id}")
        except Exception as e:
            logger.error(f"Ошибка при добавлении задачи {job_id}: {e}")

    def remove_job(self, job_id: str):
        """Удаление задачи"""
        try:
            self.scheduler.remove_job(job_id)
            logger.info(f"Удалена задача: {job_id}")
        except Exception as e:
            logger.error(f"Ошибка при удалении задачи {job_id}: {e}")

    def list_jobs(self):
        """Список всех задач"""
        jobs = self.scheduler.get_jobs()
        return [{"id": job.id, "name": job.name, "next_run": job.next_run_time} for job in jobs]

# Глобальный экземпляр планировщика
scheduler_service = SchedulerService()

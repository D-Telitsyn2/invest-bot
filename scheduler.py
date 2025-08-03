import asyncio
import logging
import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime
from typing import Dict, Optional

from database import (
    update_prices_in_portfolio, get_portfolio_statistics,
    get_users_with_notification_type, get_user_portfolio_for_notifications,
    check_target_prices_achieved, get_user_settings
)
from gpt_client import get_investment_ideas
from market_data import RealMarketData

logger = logging.getLogger(__name__)

def is_user_work_time(user_timezone: str) -> bool:
    """
    Проверяет, находится ли пользователь в рабочем времени (пн-пт 10-18) по его таймзоне
    """
    try:
        tz = pytz.timezone(user_timezone)
        user_time = datetime.now(tz)

        # Проверяем день недели (0-6, где 0 = понедельник, 6 = воскресенье)
        is_weekday = user_time.weekday() < 5  # пн-пт

        # Проверяем время (10-18)
        is_work_hour = 10 <= user_time.hour < 18

        return is_weekday and is_work_hour
    except Exception as e:
        logger.error(f"Ошибка проверки рабочего времени для таймзоны {user_timezone}: {e}")
        return False

class SchedulerService:
    def __init__(self, bot=None):
        self.scheduler = AsyncIOScheduler()
        self.bot = bot
        self.is_running = False

    async def start(self):
        """Запуск планировщика"""
        if not self.is_running:
            # Проверяем подключение к БД перед запуском
            try:
                from database import get_pool
                pool = await get_pool()
                async with pool.acquire() as connection:
                    await connection.fetchval("SELECT 1")
                logger.info("✅ Подключение к базе данных успешно")
            except Exception as e:
                logger.error(f"❌ Ошибка подключения к БД: {e}")
                logger.error("Планировщик запущен, но уведомления могут не работать")

            # Обновление цен каждые 5 минут (проверяем рабочее время внутри метода)
            self.scheduler.add_job(
                self.update_market_prices_with_timezone,
                CronTrigger(minute="*/5"),  # Каждые 5 минут, проверяем таймзону внутри
                id="update_prices",
                name="Обновление цен акций (с учетом таймзон)"
            )

            # Ежедневный анализ рынка - проверяем каждый час
            self.scheduler.add_job(
                self.daily_market_analysis_with_timezone,
                CronTrigger(minute=0),  # Каждый час в 0 минут
                id="daily_analysis",
                name="Ежедневный анализ рынка (с учетом таймзон)"
            )

            # Еженедельный отчет - проверяем каждый час в воскресенье
            self.scheduler.add_job(
                self.weekly_portfolio_report_with_timezone,
                CronTrigger(day_of_week="sun", minute=0),  # Каждый час в воскресенье
                id="weekly_report",
                name="Еженедельный отчет (с учетом таймзон)"
            )

            # Проверка целевых цен каждые 30 минут (проверяем рабочее время внутри метода)
            self.scheduler.add_job(
                self.check_target_prices_with_timezone,
                CronTrigger(minute="*/30"),  # Каждые 30 минут, проверяем таймзону внутри
                id="check_targets",
                name="Проверка целевых цен (с учетом таймзон)"
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

    async def update_market_prices_with_timezone(self):
        """Обновление цен акций с учетом таймзоны пользователей"""
        try:
            logger.info("⏰ Проверка обновления цен с учетом таймзон...")

            # Получаем всех пользователей с включенными уведомлениями об обновлении цен
            users = await get_users_with_notification_type('price_updates')
            if not users:
                logger.debug("Нет пользователей с включенными обновлениями цен")
                return

            # Фильтруем пользователей по рабочему времени и общим настройкам
            active_users = []
            for user in users:
                try:
                    user_settings = await get_user_settings(user['user_id'])
                    if user_settings and user_settings.get('notifications', True):
                        user_timezone = user.get('timezone', 'Europe/Moscow')
                        if is_user_work_time(user_timezone):
                            active_users.append(user)
                            logger.info(f"Пользователь {user['user_id']} в рабочем времени ({user_timezone})")
                except Exception as e:
                    logger.error(f"Ошибка проверки пользователя {user['user_id']}: {e}")

            if not active_users:
                logger.debug("Нет пользователей в рабочем времени для обновления цен")
                return

            logger.info(f"Найдено {len(active_users)} пользователей в рабочем времени")

            # Собираем уникальные тикеры из всех портфелей активных пользователей
            unique_tickers = set()
            user_portfolios = {}

            for user in active_users:
                portfolio = await get_user_portfolio_for_notifications(user['user_id'])
                if portfolio:
                    user_portfolios[user['user_id']] = portfolio
                    for position in portfolio:
                        unique_tickers.add(position['ticker'])

            if not unique_tickers:
                logger.info("Нет тикеров для обновления цен")
                return

            # Получаем актуальные цены
            market_data = RealMarketData()
            try:
                prices = await market_data.get_multiple_moex_prices(list(unique_tickers))
                if prices:
                    # Обновляем цены в базе данных
                    await update_prices_in_portfolio(prices)
                    logger.info(f"Обновлены цены для {len(prices)} акций для {len(active_users)} пользователей")

                    # Отправляем уведомления пользователям о значительных изменениях цен
                    await self._send_price_update_notifications(active_users, user_portfolios, prices)

            except Exception as e:
                logger.error(f"❌ Ошибка получения цен с рынка: {e}")

        except Exception as e:
            logger.error(f"❌ Ошибка при обновлении цен с учетом таймзон: {e}")

    async def update_market_prices(self):
        """Обновление цен акций в рабочее время"""
        try:
            logger.info("⏰ Обновление цен акций...")

            # Получаем всех пользователей с включенными уведомлениями об обновлении цен
            users = await get_users_with_notification_type('price_updates')
            if not users:
                logger.info("Нет пользователей с включенными обновлениями цен")
                return

            # Фильтруем пользователей с включенными общими уведомлениями
            active_users = []
            for user in users:
                try:
                    user_settings = await get_user_settings(user['user_id'])
                    if user_settings and user_settings.get('notifications', True):
                        active_users.append(user)
                except Exception as e:
                    logger.error(f"Ошибка получения настроек пользователя {user['user_id']}: {e}")

            if not active_users:
                logger.info("Нет активных пользователей для обновления цен")
                return

            # Собираем уникальные тикеры из всех портфелей активных пользователей
            unique_tickers = set()
            user_portfolios = {}

            for user in active_users:
                portfolio = await get_user_portfolio_for_notifications(user['user_id'])
                if portfolio:
                    user_portfolios[user['user_id']] = portfolio
                    for position in portfolio:
                        unique_tickers.add(position['ticker'])

            if not unique_tickers:
                logger.info("Нет тикеров для обновления цен")
                return

            # Получаем актуальные цены
            market_data = RealMarketData()
            try:
                prices = await market_data.get_multiple_moex_prices(list(unique_tickers))
                if prices:
                    # Обновляем цены в базе данных
                    await update_prices_in_portfolio(prices)
                    logger.info(f"Обновлены цены для {len(prices)} акций")

                    # Отправляем уведомления пользователям о значительных изменениях цен
                    await self._send_price_update_notifications(active_users, user_portfolios, prices)

            finally:
                await market_data.close_session()

        except Exception as e:
            logger.error(f"Ошибка при обновлении цен: {e}")

    async def _send_price_update_notifications(self, users, user_portfolios, new_prices):
        """Отправляет уведомления о значительных изменениях цен"""
        if not self.bot:
            return

        for user in users:
            try:
                portfolio = user_portfolios.get(user['user_id'], [])
                if not portfolio:
                    continue

                significant_changes = []

                for position in portfolio:
                    ticker = position['ticker']
                    old_price = position.get('current_price', position['avg_price'])
                    new_price = new_prices.get(ticker)

                    if new_price and old_price:
                        change_percent = ((new_price - old_price) / old_price) * 100

                        # Уведомляем о изменениях больше 3%
                        if abs(change_percent) >= 3:
                            significant_changes.append({
                                'ticker': ticker,
                                'old_price': old_price,
                                'new_price': new_price,
                                'change_percent': change_percent,
                                'quantity': position['quantity']
                            })

                if significant_changes:
                    message = "📈 *Значительные изменения цен в вашем портфеле:*\n\n"

                    for change in significant_changes:
                        emoji = "📈" if change['change_percent'] > 0 else "📉"
                        message += f"{emoji} `{change['ticker']}`\n"
                        message += f"💰 {change['old_price']:.2f} ₽ → {change['new_price']:.2f} ₽\n"
                        message += f"📊 Изменение: {change['change_percent']:+.1f}%\n"

                        position_change = (change['new_price'] - change['old_price']) * change['quantity']
                        message += f"💼 Ваша позиция: {position_change:+,.0f} ₽\n\n"

                    await self.bot.send_message(
                        chat_id=user['user_id'],
                        text=message,
                        parse_mode="Markdown"
                    )

                    # Небольшая пауза между отправками
                    await asyncio.sleep(0.1)

            except Exception as e:
                logger.error(f"Ошибка при отправке уведомления об изменении цен пользователю {user['user_id']}: {e}")

    async def daily_market_analysis(self):
        """Ежедневный анализ рынка"""
        try:
            logger.info("📊 Ежедневный анализ рынка...")

            # Проверяем, есть ли у нас бот для отправки сообщений
            if not self.bot:
                logger.error("❌ Бот не инициализирован для отправки уведомлений")
                return

            # Получаем пользователей с включенными ежедневными уведомлениями
            try:
                users = await get_users_with_notification_type('daily_market_analysis')
                logger.info(f"Найдено {len(users)} пользователей с включенной ежедневной сводкой")
            except Exception as e:
                logger.error(f"❌ Ошибка получения пользователей из БД: {e}")
                return

            # Фильтруем пользователей с включенными общими уведомлениями
            active_users = []
            for user in users:
                try:
                    user_settings = await get_user_settings(user['user_id'])
                    logger.info(f"Пользователь {user['user_id']}: настройки = {user_settings}")
                    if user_settings and user_settings.get('notifications', True):
                        active_users.append(user)
                        logger.info(f"Пользователь {user['user_id']} добавлен в активные")
                    else:
                        logger.info(f"Пользователь {user['user_id']} пропущен (notifications = False)")
                except Exception as e:
                    logger.error(f"❌ Ошибка получения настроек пользователя {user['user_id']}: {e}")

            logger.info(f"Активных пользователей для отправки: {len(active_users)}")

            if not active_users:
                logger.info("⚠️ Нет активных пользователей для отправки ежедневной сводки")
                return

            for user in active_users:
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

                            message += f"*{i}.* `{idea['ticker']}`\n"
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

            # Проверяем, есть ли у нас бот для отправки сообщений
            if not self.bot:
                logger.error("❌ Бот не инициализирован для отправки еженедельных отчетов")
                return

            # Получаем пользователей с включенными еженедельными отчетами
            try:
                users = await get_users_with_notification_type('weekly_portfolio_report')
                logger.info(f"Найдено {len(users)} пользователей с включенными еженедельными отчетами")
            except Exception as e:
                logger.error(f"❌ Ошибка получения пользователей для еженедельных отчетов: {e}")
                return

            # Фильтруем пользователей с включенными общими уведомлениями
            active_users = []
            for user in users:
                try:
                    user_settings = await get_user_settings(user['user_id'])
                    if user_settings and user_settings.get('notifications', True):
                        active_users.append(user)
                except Exception as e:
                    logger.error(f"❌ Ошибка получения настроек пользователя {user['user_id']}: {e}")

            logger.info(f"Активных пользователей для еженедельных отчетов: {len(active_users)}")

            if not active_users:
                logger.info("⚠️ Нет активных пользователей для отправки еженедельных отчетов")
                return

            for user in active_users:
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
                        message += f"{i}. `{pos['ticker']}`: {pos['return_pct']:+.1f}% "
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

            # Проверяем, есть ли у нас бот для отправки сообщений
            if not self.bot:
                logger.error("❌ Бот не инициализирован для отправки уведомлений о целевых ценах")
                return

            # Получаем пользователей с включенными уведомлениями о целевых ценах
            try:
                users = await get_users_with_notification_type('target_price_alerts')
                logger.info(f"Найдено {len(users)} пользователей с включенными уведомлениями о целевых ценах")
            except Exception as e:
                logger.error(f"❌ Ошибка получения пользователей для целевых цен: {e}")
                return

            # Фильтруем пользователей с включенными общими уведомлениями
            active_users = []
            for user in users:
                try:
                    user_settings = await get_user_settings(user['user_id'])
                    if user_settings and user_settings.get('notifications', True):
                        active_users.append(user)
                except Exception as e:
                    logger.error(f"❌ Ошибка получения настроек пользователя {user['user_id']}: {e}")

            logger.info(f"Активных пользователей для проверки целевых цен: {len(active_users)}")

            if not active_users:
                logger.info("⚠️ Нет активных пользователей для проверки целевых цен")
                return

            for user in active_users:
                try:
                    # Проверяем достижение целевых цен
                    achieved_targets = await check_target_prices_achieved(user['user_id'])

                    if not achieved_targets:
                        continue

                    # Формируем уведомление
                    message = "🎯 *Целевые цены достигнуты!*\n\n"

                    for target in achieved_targets:
                        message += f"`{target['ticker']}`\n"
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

    async def check_target_prices_with_timezone(self):
        """Проверка достижения целевых цен с учетом таймзоны пользователей"""
        try:
            logger.info("🎯 Проверка целевых цен с учетом таймзон...")

            # Проверяем, есть ли у нас бот для отправки сообщений
            if not self.bot:
                logger.error("❌ Бот не инициализирован для отправки уведомлений о целевых ценах")
                return

            # Получаем пользователей с включенными уведомлениями о целевых ценах
            try:
                users = await get_users_with_notification_type('target_price_alerts')
                logger.info(f"Найдено {len(users)} пользователей с включенными уведомлениями о целевых ценах")
            except Exception as e:
                logger.error(f"❌ Ошибка получения пользователей для целевых цен: {e}")
                return

            # Фильтруем пользователей по рабочему времени и общим настройкам
            active_users = []
            for user in users:
                try:
                    user_settings = await get_user_settings(user['user_id'])
                    if user_settings and user_settings.get('notifications', True):
                        user_timezone = user.get('timezone', 'Europe/Moscow')
                        if is_user_work_time(user_timezone):
                            active_users.append(user)
                            logger.info(f"Пользователь {user['user_id']} в рабочем времени ({user_timezone})")
                except Exception as e:
                    logger.error(f"❌ Ошибка проверки пользователя {user['user_id']}: {e}")

            if not active_users:
                logger.debug("⚠️ Нет пользователей в рабочем времени для проверки целевых цен")
                return

            logger.info(f"Активных пользователей в рабочем времени: {len(active_users)}")

            for user in active_users:
                try:
                    # Проверяем достижение целевых цен
                    achieved_targets = await check_target_prices_achieved(user['user_id'])

                    if not achieved_targets:
                        continue

                    # Формируем уведомление
                    message = "🎯 *Целевые цены достигнуты!*\n\n"

                    for target in achieved_targets:
                        message += f"`{target['ticker']}`\n"
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
                        logger.info(f"✅ Отправлено уведомление о {len(achieved_targets)} целевых ценах пользователю {user['user_id']}")

                except Exception as e:
                    logger.error(f"❌ Ошибка при проверке целевых цен для пользователя {user['user_id']}: {e}")

        except Exception as e:
            logger.error(f"❌ Ошибка при проверке целевых цен с учетом таймзон: {e}")

    def list_jobs(self):
        """Список всех задач"""
        jobs = self.scheduler.get_jobs()
        return [{"id": job.id, "name": job.name, "next_run": job.next_run_time} for job in jobs]

    async def daily_market_analysis_with_timezone(self):
        """Ежедневный анализ рынка с учетом таймзон пользователей (9:00 по местному времени)"""
        try:
            current_utc = datetime.now(pytz.UTC)
            logger.info(f"📊 Проверка времени для ежедневного анализа. UTC: {current_utc.strftime('%H:%M')}")

            # Получаем пользователей с включенными ежедневными уведомлениями
            try:
                users = await get_users_with_notification_type('daily_market_analysis')
                logger.info(f"Найдено {len(users)} пользователей с включенной ежедневной сводкой")
            except Exception as e:
                logger.error(f"❌ Ошибка получения пользователей из БД: {e}")
                return

            if not self.bot or not users:
                return

            # Проверяем для каждого пользователя, не 9:00 ли по их времени
            for user in users:
                try:
                    user_timezone = user.get('timezone', 'Europe/Moscow')
                    tz = pytz.timezone(user_timezone)
                    user_time = current_utc.astimezone(tz)

                    # Проверяем, что сейчас 9:00 по времени пользователя
                    if user_time.hour == 9 and user_time.minute == 0:
                        await self._send_daily_analysis_to_user(user)

                except Exception as e:
                    logger.error(f"❌ Ошибка обработки пользователя {user.get('user_id')}: {e}")

        except Exception as e:
            logger.error(f"❌ Ошибка в daily_market_analysis_with_timezone: {e}")

    async def weekly_portfolio_report_with_timezone(self):
        """Еженедельный отчет портфеля с учетом таймзон пользователей (20:00 воскресенье по местному времени)"""
        try:
            current_utc = datetime.now(pytz.UTC)
            logger.info(f"📊 Проверка времени для еженедельного отчета. UTC: {current_utc.strftime('%H:%M')}")

            # Получаем пользователей с включенными еженедельными отчетами
            try:
                users = await get_users_with_notification_type('weekly_portfolio_report')
                logger.info(f"Найдено {len(users)} пользователей с включенным еженедельным отчетом")
            except Exception as e:
                logger.error(f"❌ Ошибка получения пользователей из БД: {e}")
                return

            if not self.bot or not users:
                return

            # Проверяем для каждого пользователя, не 20:00 воскресенья ли по их времени
            for user in users:
                try:
                    user_timezone = user.get('timezone', 'Europe/Moscow')
                    tz = pytz.timezone(user_timezone)
                    user_time = current_utc.astimezone(tz)

                    # Проверяем, что сейчас воскресенье 20:00 по времени пользователя
                    if user_time.weekday() == 6 and user_time.hour == 20 and user_time.minute == 0:  # 6 = воскресенье
                        await self._send_weekly_report_to_user(user)

                except Exception as e:
                    logger.error(f"❌ Ошибка обработки пользователя {user.get('user_id')}: {e}")

        except Exception as e:
            logger.error(f"❌ Ошибка в weekly_portfolio_report_with_timezone: {e}")

    async def _send_daily_analysis_to_user(self, user):
        """Отправка ежедневного анализа конкретному пользователю"""
        try:
            # Проверяем настройки пользователя
            user_settings = await get_user_settings(user['user_id'])
            if not user_settings or not user_settings.get('notifications', True):
                return

            # Получаем персональные рекомендации
            ideas = await get_investment_ideas(
                budget=user['max_investment_amount'],
                risk_level=user['risk_level']
            )

            if ideas and self.bot:
                # Формируем сообщение
                message = "🌅 *Доброе утро! Ежедневная сводка рынка*\n\n"
                message += "📈 *Топ идеи на сегодня:*\n\n"

                for i, idea in enumerate(ideas[:3], 1):
                    message += f"{i}. `{idea['ticker']}` - {idea['action']}\n"
                    message += f"   💰 Цена: {idea['price']:.2f} ₽\n"
                    message += f"   🎯 Цель: {idea['target_price']:.2f} ₽\n"
                    message += f"   📝 {idea['reasoning'][:100]}...\n\n"

                message += "💡 Получить полный анализ: /ideas"

                await self.bot.send_message(
                    chat_id=user['user_id'],
                    text=message,
                    parse_mode="Markdown"
                )
                logger.info(f"✅ Ежедневная сводка отправлена пользователю {user['user_id']}")

        except Exception as e:
            logger.error(f"❌ Ошибка отправки ежедневной сводки пользователю {user['user_id']}: {e}")

    async def _send_weekly_report_to_user(self, user):
        """Отправка еженедельного отчета конкретному пользователю"""
        try:
            # Проверяем настройки пользователя
            user_settings = await get_user_settings(user['user_id'])
            if not user_settings or not user_settings.get('notifications', True):
                return

            # Получаем портфель пользователя для отчета
            portfolio = await get_user_portfolio_for_notifications(user['user_id'])

            if portfolio and self.bot:
                # Формируем еженедельный отчет
                message = "📊 *Еженедельный отчет портфеля*\n\n"

                total_value = 0
                total_cost = 0
                best_position = None
                worst_position = None

                for position in portfolio:
                    current_value = position['quantity'] * position['current_price']
                    invested_value = position['quantity'] * position['avg_price']

                    total_value += current_value
                    total_cost += invested_value

                    # Определяем лучшую и худшую позицию
                    if not best_position or position['return_pct'] > best_position['return_pct']:
                        best_position = position
                    if not worst_position or position['return_pct'] < worst_position['return_pct']:
                        worst_position = position

                # Общая статистика
                total_pnl = total_value - total_cost
                total_pnl_pct = (total_pnl / total_cost * 100) if total_cost > 0 else 0

                message += f"💰 *Общая стоимость:* {total_value:.2f} ₽\n"
                message += f"📈 *P&L:* {total_pnl:+.2f} ₽ ({total_pnl_pct:+.1f}%)\n\n"

                if best_position:
                    message += f"🏆 *Лучшая позиция:* `{best_position['ticker']}`\n"
                    message += f"   📊 Доходность: +{best_position['return_pct']:.1f}%\n\n"

                if worst_position and worst_position != best_position:
                    message += f"📉 *Требует внимания:* `{worst_position['ticker']}`\n"
                    message += f"   📊 Доходность: {worst_position['return_pct']:+.1f}%\n\n"

                message += "💡 Подробный анализ: /portfolio"

                await self.bot.send_message(
                    chat_id=user['user_id'],
                    text=message,
                    parse_mode="Markdown"
                )
                logger.info(f"✅ Еженедельный отчет отправлен пользователю {user['user_id']}")

        except Exception as e:
            logger.error(f"❌ Ошибка отправки еженедельного отчета пользователю {user['user_id']}: {e}")

# Глобальный экземпляр планировщика
scheduler_service = SchedulerService()

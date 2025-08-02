import asyncio
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime
from typing import Dict, Optional

from database import update_prices_in_portfolio, get_portfolio_statistics
from gpt_client import get_investment_ideas

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
            logger.info("⏰ Задача обновления цен запущена")
            # Примечание: Обновление цен временно отключено
            # В будущем здесь будет интеграция с биржевыми API

        except Exception as e:
            logger.error(f"Ошибка при обновлении цен: {e}")

    async def daily_market_analysis(self):
        """Ежедневный анализ рынка"""
        try:
            logger.info("Запущен ежедневный анализ рынка")

            # Получаем свежие инвестиционные идеи
            ideas = await get_investment_ideas(budget=50000)

            if ideas and self.bot:
                # Здесь можно отправить уведомления активным пользователям
                # О новых возможностях на рынке
                pass

        except Exception as e:
            logger.error(f"Ошибка при ежедневном анализе: {e}")

    async def weekly_portfolio_report(self):
        """Еженедельный отчет по портфелям"""
        try:
            logger.info("Генерация еженедельных отчетов")

            # Здесь можно реализовать отправку еженедельных отчетов
            # всем пользователям с их статистикой портфеля

        except Exception as e:
            logger.error(f"Ошибка при генерации еженедельных отчетов: {e}")

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

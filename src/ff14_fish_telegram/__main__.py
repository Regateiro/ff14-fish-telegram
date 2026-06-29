import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from telegram.ext import ApplicationBuilder

from ff14_fish_telegram.bot.handlers import BOT_DATA_KEY, get_handlers
from ff14_fish_telegram.bot.reminders import check_reminders
from ff14_fish_telegram.config import (
    FETCH_INTERVAL_HOURS,
    TELEGRAM_TOKEN,
)
from ff14_fish_telegram.data.fetcher import load_fish_data
from ff14_fish_telegram.db.database import cleanup_old_reminders, init_db

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


async def refresh_fish_data(application) -> None:
    logger.info("Refreshing fish data from tracker site...")
    try:
        data = await load_fish_data()
        application.bot_data[BOT_DATA_KEY] = data
        logger.info(f"Fish data refreshed: {len(data.fish)} fish loaded.")
    except Exception as e:
        logger.error(f"Failed to refresh fish data: {e}")


async def reminder_job(application) -> None:
    try:
        await check_reminders(application)
    except Exception as e:
        logger.error(f"Reminder check failed: {e}")


async def post_init(application) -> None:
    init_db()
    await refresh_fish_data(application)

    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        refresh_fish_data,
        "interval",
        hours=FETCH_INTERVAL_HOURS,
        args=[application],
        id="refresh_fish_data",
    )
    scheduler.add_job(
        reminder_job,
        "interval",
        minutes=1,
        args=[application],
        id="check_reminders",
    )
    scheduler.add_job(
        cleanup_old_reminders,
        "interval",
        days=1,
        id="cleanup_reminders",
    )
    scheduler.start()
    application.bot_data["scheduler"] = scheduler


async def post_stop(application) -> None:
    scheduler = application.bot_data.get("scheduler")
    if scheduler:
        scheduler.shutdown(wait=False)


def main() -> None:
    app = (
        ApplicationBuilder().token(TELEGRAM_TOKEN).post_init(post_init).post_stop(post_stop).build()
    )

    for handler in get_handlers():
        app.add_handler(handler)

    app.run_polling(allowed_updates=["messages"])


if __name__ == "__main__":
    main()

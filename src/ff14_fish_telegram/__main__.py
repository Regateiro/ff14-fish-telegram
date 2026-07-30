"""Application entry point: initializes the bot, database, scheduler, and starts polling.

This module wires together all layers of the application:
  - config.py          → provides TELEGRAM_TOKEN and FETCH_INTERVAL_HOURS
  - data/fetcher.py    → provides load_fish_data() for FishData ingestion
  - db/database.py     → provides init_db() and cleanup_old_reminders()
  - bot/handlers.py    → provides get_handlers() and BOT_DATA_KEY
  - bot/reminders.py   → provides check_reminders() for proactive alerts

The main() function is the console entry point defined in pyproject.toml.
"""

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from telegram.ext import Application, ApplicationBuilder

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


async def refresh_fish_data(application: Application) -> None:
    """Fetch the latest fish/weather data from the tracker repo and store it in bot_data.

    This is called:
      - Once at startup (from post_init)
      - Recurring every FETCH_INTERVAL_HOURS (scheduled job)

    The fetched FishData is stored in application.bot_data[BOT_DATA_KEY]
    and is subsequently read by bot/handlers.py and bot/reminders.py
    via context.bot_data.
    """
    logger.info("Refreshing fish data from tracker repo...")
    try:
        data = await load_fish_data()
        application.bot_data[BOT_DATA_KEY] = data
        logger.info(f"Fish data refreshed: {len(data.fish)} fish loaded.")
    except Exception as e:
        logger.error(f"Failed to refresh fish data: {e}")


async def reminder_job(application: Application) -> None:
    """Wrapper around check_reminders that logs failures without crashing the scheduler.

    APScheduler would stop the job if the coroutine raised an unhandled
    exception. This wrapper ensures the bot keeps running even if one
    reminder cycle encounters an error.
    """
    try:
        await check_reminders(application)
    except Exception as e:
        logger.error(f"Reminder check failed: {e}")


async def post_init(application: Application) -> None:
    """Run once after the bot starts: initialize DB, load fish data, and start background jobs.

    This callback is wired via ApplicationBuilder.post_init(). It:
      1. Creates SQLite tables via init_db()
       2. Loads fish data from the remote tracker repo
      3. Sets up three APScheduler recurring jobs:
         - Fish data refresh every FETCH_INTERVAL_HOURS
         - Reminder check every minute
         - Old reminder cleanup every day
    """
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


async def post_stop(application: Application) -> None:
    """Shut down the APScheduler when the bot stops.

    Ensures background jobs are properly cancelled to avoid dangling
    asyncio tasks on shutdown.
    """
    scheduler = application.bot_data.get("scheduler")
    if scheduler:
        scheduler.shutdown(wait=False)


def main() -> None:
    """Build the Telegram application, register handlers, and start long-polling.

    This is the console entry point (pyproject.toml:
    ff14-fish-telegram = ff14_fish_telegram.__main__:main).

    Steps:
      1. Build the Application with the bot token
      2. Attach post_init and post_stop lifecycle callbacks
      3. Register all command and callback handlers from handlers.py
      4. Start polling for Telegram updates (messages + callback queries)
    """
    app = (
        ApplicationBuilder().token(TELEGRAM_TOKEN).post_init(post_init).post_stop(post_stop).build()
    )

    for handler in get_handlers():
        app.add_handler(handler)

    app.run_polling(allowed_updates=["message", "callback_query"])


if __name__ == "__main__":
    main()

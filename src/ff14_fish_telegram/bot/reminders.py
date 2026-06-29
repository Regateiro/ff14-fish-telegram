from datetime import datetime, timezone

from telegram import Bot
from telegram.ext import Application

from ff14_fish_telegram.data.availability import get_next_window
from ff14_fish_telegram.data.models import Fish, FishData
from ff14_fish_telegram.db.database import (
    get_all_user_ids,
    get_caught_fish_ids,
    mark_reminder_sent,
    reminder_sent,
)


def _lead_time_seconds(fish: Fish) -> int:
    if fish.has_intuition_or_predator:
        return 30 * 60
    return 10 * 60


async def check_reminders(application: Application) -> None:
    fish_data: FishData | None = application.bot_data.get("fish_data")
    if fish_data is None:
        return

    now = datetime.now(timezone.utc)

    for user_id in get_all_user_ids():
        caught_ids = get_caught_fish_ids(user_id)
        for fish in fish_data.fish.values():
            if fish.id in caught_ids or fish.always_available:
                continue

            window = get_next_window(fish, fish_data, from_time=now)
            if not window:
                continue

            lead = _lead_time_seconds(fish)
            remaining = (window.start_earth - now).total_seconds()
            if 0 < remaining <= lead:
                ws_key = int(window.start_eorzea)
                if not reminder_sent(user_id, fish.id, ws_key):
                    spot = fish_data.fishing_spots.get(fish.location_id)
                    zone_name = fish_data.zones.get(spot.zone_id, "") if spot else ""
                    msg = (
                        f"🎣 *{fish.name_en}* will be available soon!\n"
                        f"Time: ET {fish.start_hour:.1f} - {fish.end_hour:.1f}\n"
                        f"Location: {zone_name}\n"
                        f"Starts in ~{remaining // 60:.0f} minutes."
                    )
                    try:
                        await Bot(application.bot.token).send_message(
                            chat_id=user_id,
                            text=msg,
                            parse_mode="Markdown",
                        )
                    except Exception:
                        pass
                    mark_reminder_sent(user_id, fish.id, ws_key)

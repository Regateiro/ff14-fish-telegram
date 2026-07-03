"""Telegram command handlers for the fishing bot (/start, /caught, /uncaught, /day).

This module implements the user-facing Telegram interface. Each handler:
  1. Receives a telegram.Update from the PTB framework
  2. Retrieves the shared FishData from context.bot_data (populated by __main__.py)
  3. Uses db/database.py for persistence (caught/uncaught state)
  4. Uses data/availability.py for window computation (/day command)
  5. Sends formatted replies back to the user

Handlers are registered with the Application in __main__.py via get_handlers().
"""

from datetime import datetime, timezone

from telegram import Update
from telegram.ext import CallbackQueryHandler, CommandHandler, ContextTypes

from ff14_fish_telegram.data.availability import (
    CatchableWindow,
    compute_catchable_windows,
    get_zone_name_for_spot,
)
from ff14_fish_telegram.data.models import Fish, FishData
from ff14_fish_telegram.db.database import (
    get_caught_fish_ids,
    is_caught,
    mark_caught,
    mark_caught_many,
    mark_uncaught,
    mark_uncaught_many,
)

# Key used to store/retrieve FishData in Application.bot_data.
# Must match the key used in __main__.py's refresh_fish_data().
BOT_DATA_KEY = "fish_data"

_HELP_TEXT = (
    "FFXIV Flying Fish Bot\n\n"
    "Commands:\n"
    "  /start - Show this help message\n"
    "  /caught [name|all] - List caught fish, or mark a fish as caught\n"
    "  /uncaught [name|all] - List uncaught fish, or mark a fish as uncaught\n"
    "  /day - List uncaught fish available in the next 24 hours\n\n"
    "Reminders are automatically sent when a fish window is approaching."
)


def _sanitize(name: str) -> str:
    """Lowercase and strip whitespace from a fish name for case-insensitive matching.

    Used by /caught and /uncaught to match user input against fish names
    regardless of capitalization or accidental whitespace.
    """
    return name.strip().lower()


def _get_fish_data(context: ContextTypes.DEFAULT_TYPE) -> FishData | None:
    """Retrieve the shared FishData from bot_data, or None if not yet loaded.

    FishData is populated by __main__.py's post_init callback and
    refreshed on a schedule. If data is not yet loaded (e.g. first
    startup), handlers show a friendly error message.
    """
    return context.bot_data.get(BOT_DATA_KEY)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start: send the help message listing available commands."""
    await update.message.reply_text(_HELP_TEXT)


async def caught(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /caught [name|all]: list caught fish or mark one/all as caught.

    Behavior depends on arguments:
      - No arguments: display a paginated list of caught fish names
      - "all": mark every fish in FishData as caught via batch insert
      - <name>: case-insensitive substring match, mark the single match
    """
    user_id = update.effective_user.id
    fish_data = _get_fish_data(context)
    if fish_data is None:
        await update.message.reply_text("Fish data not loaded yet. Try again shortly.")
        return

    args = context.args
    if not args:
        caught_ids = get_caught_fish_ids(user_id)
        if not caught_ids:
            await update.message.reply_text("You haven't caught any fish yet.")
            return
        names = sorted(f.name_en for f in fish_data.fish.values() if f.id in caught_ids)
        if not names:
            await update.message.reply_text("No named fish found in caught list.")
            return
        lines = "\n".join(f"  • {n}" for n in names[:50])
        extra = f"\n...and {len(names) - 50} more" if len(names) > 50 else ""
        await update.message.reply_text(f"Caught fish ({len(names)}):\n{lines}{extra}")
        return

    query = " ".join(args).strip()
    if _sanitize(query) == "all":
        all_ids = list(fish_data.fish.keys())
        mark_caught_many(user_id, all_ids)
        await update.message.reply_text(f"Marked all {len(all_ids)} fish as caught.")
        return

    matches = []
    for f in fish_data.fish.values():
        if _sanitize(query) in _sanitize(f.name_en):
            matches.append(f)

    if not matches:
        await update.message.reply_text(f"No fish found matching '{query}'.")
        return

    if len(matches) > 1:
        names = "\n".join(f"  • {f.name_en}" for f in matches[:10])
        extra = f" ...and {len(matches) - 10} more" if len(matches) > 10 else ""
        await update.message.reply_text(
            f"Multiple fish match '{query}':\n{names}{extra}\n\nPlease be more specific."
        )
        return

    fish = matches[0]
    mark_caught(user_id, fish.id)
    await update.message.reply_text(f"Marked '{fish.name_en}' as caught.")


async def uncaught(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /uncaught [name|all]: list uncaught fish or mark one/all as uncaught.

    Mirror of /caught: shows uncaught fish, or removes fish from the
    user's caught list.
    """
    user_id = update.effective_user.id
    fish_data = _get_fish_data(context)
    if fish_data is None:
        await update.message.reply_text("Fish data not loaded yet. Try again shortly.")
        return

    args = context.args
    if not args:
        caught_ids = get_caught_fish_ids(user_id)
        names = sorted(f.name_en for f in fish_data.fish.values() if f.id not in caught_ids)
        if not names:
            await update.message.reply_text("You've caught every fish!")
            return
        lines = "\n".join(f"  • {n}" for n in names[:50])
        extra = f"\n...and {len(names) - 50} more" if len(names) > 50 else ""
        await update.message.reply_text(f"Uncaught fish ({len(names)}):\n{lines}{extra}")
        return

    query = " ".join(args).strip()
    if _sanitize(query) == "all":
        all_ids = list(fish_data.fish.keys())
        mark_uncaught_many(user_id, all_ids)
        await update.message.reply_text(f"Marked all {len(all_ids)} fish as uncaught.")
        return

    matches = []
    for f in fish_data.fish.values():
        if _sanitize(query) in _sanitize(f.name_en):
            matches.append(f)

    if not matches:
        await update.message.reply_text(f"No fish found matching '{query}'.")
        return

    if len(matches) > 1:
        names = "\n".join(f"  • {f.name_en}" for f in matches[:10])
        extra = f" ...and {len(matches) - 10} more" if len(matches) > 10 else ""
        await update.message.reply_text(
            f"Multiple fish match '{query}':\n{names}{extra}\n\nPlease be more specific."
        )
        return

    fish = matches[0]
    mark_uncaught(user_id, fish.id)
    await update.message.reply_text(f"Marked '{fish.name_en}' as uncaught.")


async def day(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /day: show uncaught fish available in the next 24 hours with time/weather info.

    Iterates all fish in FishData, filters to uncaught fish only,
    computes their next catchable window via data/availability.py, and
    displays those starting within the next 24 hours sorted by time.

    Each entry shows:
      - Fish name
      - Window start time (UTC)
      - Eorzea time range
      - Zone name
      - Weather requirements (if any)
    """
    user_id = update.effective_user.id
    fish_data = _get_fish_data(context)
    if fish_data is None:
        await update.message.reply_text("Fish data not loaded yet. Try again shortly.")
        return

    caught_ids = get_caught_fish_ids(user_id)
    now = datetime.now(timezone.utc)
    end = datetime.fromtimestamp(now.timestamp() + 86400, tz=timezone.utc)

    upcoming: list[tuple[str, CatchableWindow, Fish]] = []
    for fish in fish_data.fish.values():
        if fish.id in caught_ids:
            continue
        windows = compute_catchable_windows(fish, fish_data, from_time=now, max_windows=1)
        if windows and windows[0].start_earth < end:
            upcoming.append((fish.name_en, windows[0], fish))

    if not upcoming:
        await update.message.reply_text("No uncaught fish available in the next 24 hours.")
        return

    upcoming.sort(key=lambda x: x[1].start_earth)

    await update.message.reply_text(
        f"Uncaught fish available in the next 24h ({len(upcoming)}):"
    )

    for name, window, fish in upcoming:
        start_local = window.start_earth.strftime("%H:%M UTC")
        start_hour = int(window.start_eorzea / 3600) % 24
        end_hour = int(window.end_eorzea / 3600) % 24

        zone_name = get_zone_name_for_spot(fish.location_id, fish_data)

        weather_parts = []
        if fish.weather_set:
            weather_names = [fish_data.weather_types.get(w, str(w)) for w in fish.weather_set]
            weather_parts.append("Weather: " + ", ".join(weather_names))
        if fish.previous_weather_set:
            prev_names = [
                fish_data.weather_types.get(w, str(w))
                for w in fish.previous_weather_set
            ]
            weather_parts.append("Prev: " + ", ".join(prev_names))
        weather_str = f" [{', '.join(weather_parts)}]" if weather_parts else ""

        et_range = f"ET {start_hour:02d}:00-{end_hour:02d}:00"
        msg = (
            f"🎣 *{name}*\n"
            f"⏰ {start_local} ({et_range})\n"
            f"📍 {zone_name}{weather_str}"
        )
        await update.message.reply_text(msg)


async def caught_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle inline button presses to mark a fish as caught from a reminder notification.

    This is the callback for the "Mark caught ✅" inline button sent by
    bot/reminders.py. It:
      1. Extracts the fish_id from the callback data ("caught:<id>")
      2. Validates the fish exists in FishData
      3. Checks it hasn't already been marked caught
      4. Persists via mark_caught and updates the message text
    """
    query = update.callback_query
    await query.answer()

    try:
        fish_id = int(query.data.split(":", 1)[1])
    except (IndexError, ValueError):
        await query.edit_message_text("Invalid callback data.")
        return

    user_id = query.from_user.id
    fish_data = _get_fish_data(context)
    if fish_data is None:
        await query.edit_message_text("Fish data not loaded yet. Try again shortly.")
        return

    fish = fish_data.fish.get(fish_id)
    if fish is None:
        await query.edit_message_text("Fish not found in data.")
        return

    if is_caught(user_id, fish_id):
        await query.edit_message_text(f"'{fish.name_en}' was already marked as caught.")
        return

    mark_caught(user_id, fish_id)
    await query.edit_message_text(f"Marked '{fish.name_en}' as caught! ✅")


def get_handlers() -> list:
    """Return all handlers to register with the Telegram application.

    Called by __main__.py during bot setup. Registers:
      - Four command handlers (/start, /caught, /uncaught, /day)
      - One callback query handler for inline button interaction
    """
    return [
        CommandHandler("start", start),
        CommandHandler("caught", caught),
        CommandHandler("uncaught", uncaught),
        CommandHandler("day", day),
        CallbackQueryHandler(caught_callback, pattern=r"^caught:\d+$"),
    ]

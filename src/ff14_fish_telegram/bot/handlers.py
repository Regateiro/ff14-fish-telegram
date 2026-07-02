"""Telegram command handlers for the fishing bot (/start, /caught, /uncaught, /day)."""

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
    """Lowercase and strip whitespace from a fish name for case-insensitive matching."""
    return name.strip().lower()


def _get_fish_data(context: ContextTypes.DEFAULT_TYPE) -> FishData | None:
    """Retrieve the shared FishData from bot_data, or None if not yet loaded."""
    return context.bot_data.get(BOT_DATA_KEY)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start: send the help message listing available commands."""
    await update.message.reply_text(_HELP_TEXT)


async def caught(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /caught [name|all]: list caught fish or mark one/all as caught."""
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
        names = sorted(fish_data.fish[fid].name_en for fid in caught_ids if fid in fish_data.fish)
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
    """Handle /uncaught [name|all]: list uncaught fish or mark one/all as uncaught."""
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
    """Handle /day: show uncaught fish available in the next 24 hours with time/weather info."""
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

    lines = []
    for name, window, fish in upcoming[:50]:
        start_local = window.start_earth.strftime("%H:%M UTC")
        start_hour = int(window.start_eorzea / 3600) % 24
        end_hour = int(window.end_eorzea / 3600) % 24

        zone_name = get_zone_name_for_spot(fish.location_id, fish_data)

        weather_parts = []
        if fish.weather_set:
            weather_names = [fish_data.weather_types.get(w, str(w)) for w in fish.weather_set]
            weather_parts.append("Weather: " + ", ".join(weather_names))
        if fish.previous_weather_set:
            prev_names = [fish_data.weather_types.get(w, str(w)) for w in fish.previous_weather_set]
            weather_parts.append("Prev: " + ", ".join(prev_names))
        weather_str = f" [{', '.join(weather_parts)}]" if weather_parts else ""

        et_range = f"ET {start_hour:02d}:00-{end_hour:02d}:00"
        lines.append(f"  • {name} @ {start_local} ({et_range}) {zone_name}{weather_str}")

    extra = f"\n...and {len(upcoming) - 50} more" if len(upcoming) > 50 else ""
    await update.message.reply_text(
        "Uncaught fish available in the next 24h:\n" + "\n".join(lines) + extra
    )


async def caught_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle inline button presses to mark a fish as caught from a reminder notification."""
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
    """Return all handlers to register with the Telegram application."""
    return [
        CommandHandler("start", start),
        CommandHandler("caught", caught),
        CommandHandler("uncaught", uncaught),
        CommandHandler("day", day),
        CallbackQueryHandler(caught_callback, pattern=r"^caught:\d+$"),
    ]

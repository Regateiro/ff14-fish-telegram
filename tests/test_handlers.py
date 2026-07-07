"""Tests for Telegram command handlers (_sanitize, /start, /caught, /uncaught, /day, callback)."""

import pytest
from telegram import Update
from telegram.ext import ContextTypes

from ff14_fish_telegram.bot.handlers import _HELP_TEXT, BOT_DATA_KEY, _sanitize, get_handlers
from ff14_fish_telegram.data.models import Fish, FishData, FishingSpot, Item


def _make_fish_data():
    """Return a minimal FishData with one fish."""
    return FishData(
        fish={
            4898: Fish(
                id=4898,
                name_en="Merlthor Goby",
                start_hour=0,
                end_hour=24,
                patch=2.0,
                big_fish=False,
                collectable=None,
                weather_set=[],
                previous_weather_set=[],
                location_id=52,
                best_catch_path=[2596],
                predators=[],
                intuition_length=None,
                fish_eyes=True,
                folklore=None,
                snagging=None,
                lure=None,
                hookset="Precision",
                tug="light",
                gig=None,
                data_missing=None,
                aquarium=None,
            ),
        },
        fishing_spots={
            52: FishingSpot(
                id=52,
                name_en="Moraby Bay",
                territory_id=134,
                placename_id=52,
                zone_id=31,
                region_id=22,
            ),
        },
        items={2596: Item(id=2596, name_en="Spoon Worm")},
        weather_rates={},
        weather_types={1: "Clear Skies"},
        regions={22: "La Noscea"},
        zones={31: "Lower La Noscea"},
    )


class TestSanitize:
    """Tests for the _sanitize helper (lowercase + strip)."""

    def test_lowercase(self):
        assert _sanitize("Merlthor Goby") == "merlthor goby"

    def test_strip(self):
        assert _sanitize("  Fish  ") == "fish"

    def test_empty(self):
        assert _sanitize("") == ""


class TestStartHandler:
    """Tests for the /start command handler."""

    @pytest.mark.asyncio
    async def test_start(self, mocker):
        update = mocker.Mock(spec=Update)
        update.effective_user.id = 1001
        update.message.reply_text = mocker.AsyncMock()
        context = mocker.Mock(spec=ContextTypes.DEFAULT_TYPE)

        from ff14_fish_telegram.bot.handlers import start

        await start(update, context)
        update.message.reply_text.assert_awaited_once_with(_HELP_TEXT)


class TestCaughtHandler:
    """Tests for the /caught command handler."""

    @pytest.mark.asyncio
    async def test_no_args_no_fish_data(self, mocker):
        update = mocker.Mock(spec=Update)
        update.effective_user.id = 1001
        update.message.reply_text = mocker.AsyncMock()
        context = mocker.Mock(spec=ContextTypes.DEFAULT_TYPE)
        context.args = []
        context.bot_data = {}

        from ff14_fish_telegram.bot.handlers import caught

        await caught(update, context)
        update.message.reply_text.assert_awaited_once_with(
            "Fish data not loaded yet. Try again shortly."
        )

    @pytest.mark.asyncio
    async def test_no_args_caught_fish_without_names(self, mocker):
        from ff14_fish_telegram.db.database import mark_caught

        mark_caught(1001, 99999)
        update = mocker.Mock(spec=Update)
        update.effective_user.id = 1001
        update.message.reply_text = mocker.AsyncMock()
        context = mocker.Mock(spec=ContextTypes.DEFAULT_TYPE)
        context.args = []
        context.bot_data = {BOT_DATA_KEY: _make_fish_data()}

        from ff14_fish_telegram.bot.handlers import caught

        await caught(update, context)
        update.message.reply_text.assert_awaited_once_with(
            "No named fish found in caught list.",
        )

    @pytest.mark.asyncio
    async def test_no_args_empty(self, mocker):
        update = mocker.Mock(spec=Update)
        update.effective_user.id = 1001
        update.message.reply_text = mocker.AsyncMock()
        context = mocker.Mock(spec=ContextTypes.DEFAULT_TYPE)
        context.args = []
        context.bot_data = {BOT_DATA_KEY: _make_fish_data()}

        from ff14_fish_telegram.bot.handlers import caught

        await caught(update, context)
        update.message.reply_text.assert_awaited_once_with("You haven't caught any fish yet.")

    @pytest.mark.asyncio
    async def test_no_args_with_caught_fish(self, mocker):
        from ff14_fish_telegram.db.database import mark_caught

        mark_caught(1001, 4898)
        update = mocker.Mock(spec=Update)
        update.effective_user.id = 1001
        update.message.reply_text = mocker.AsyncMock()
        context = mocker.Mock(spec=ContextTypes.DEFAULT_TYPE)
        context.args = []
        context.bot_data = {BOT_DATA_KEY: _make_fish_data()}

        from ff14_fish_telegram.bot.handlers import caught

        await caught(update, context)
        msg = update.message.reply_text.call_args[0][0]
        assert "Merlthor Goby" in msg
        assert "Caught fish" in msg

    @pytest.mark.asyncio
    async def test_no_fish_data(self, mocker):
        update = mocker.Mock(spec=Update)
        update.effective_user.id = 1001
        update.message.reply_text = mocker.AsyncMock()
        context = mocker.Mock(spec=ContextTypes.DEFAULT_TYPE)
        context.args = ["fish"]
        context.bot_data = {}

        from ff14_fish_telegram.bot.handlers import caught

        await caught(update, context)
        update.message.reply_text.assert_awaited_once_with(
            "Fish data not loaded yet. Try again shortly."
        )

    @pytest.mark.asyncio
    async def test_no_match(self, mocker):
        update = mocker.Mock(spec=Update)
        update.effective_user.id = 1001
        update.message.reply_text = mocker.AsyncMock()
        context = mocker.Mock(spec=ContextTypes.DEFAULT_TYPE)
        context.args = ["nonexistent"]
        context.bot_data = {BOT_DATA_KEY: _make_fish_data()}

        from ff14_fish_telegram.bot.handlers import caught

        await caught(update, context)
        update.message.reply_text.assert_awaited_once_with("No fish found matching 'nonexistent'.")

    @pytest.mark.asyncio
    async def test_match_single_fish(self, mocker):
        update = mocker.Mock(spec=Update)
        update.effective_user.id = 1001
        update.message.reply_text = mocker.AsyncMock()
        context = mocker.Mock(spec=ContextTypes.DEFAULT_TYPE)
        context.args = ["Merlthor"]
        context.bot_data = {BOT_DATA_KEY: _make_fish_data()}

        from ff14_fish_telegram.bot.handlers import caught

        await caught(update, context)
        update.message.reply_text.assert_awaited_once_with("Marked 'Merlthor Goby' as caught.")

        from ff14_fish_telegram.db.database import is_caught

        assert is_caught(1001, 4898) is True

    @pytest.mark.asyncio
    async def test_match_all(self, mocker):
        update = mocker.Mock(spec=Update)
        update.effective_user.id = 1001
        update.message.reply_text = mocker.AsyncMock()
        context = mocker.Mock(spec=ContextTypes.DEFAULT_TYPE)
        context.args = ["all"]
        context.bot_data = {BOT_DATA_KEY: _make_fish_data()}

        from ff14_fish_telegram.bot.handlers import caught

        await caught(update, context)
        update.message.reply_text.assert_awaited_once_with("Marked all 1 fish as caught.")

        from ff14_fish_telegram.db.database import is_caught

        assert is_caught(1001, 4898) is True

    @pytest.mark.asyncio
    async def test_multiple_matches(self, mocker):
        fd = _make_fish_data()
        fd.fish[4911] = Fish(
            id=4911,
            name_en="Merlthor Clam",
            start_hour=0,
            end_hour=24,
            patch=2.0,
            big_fish=False,
            collectable=None,
            weather_set=[],
            previous_weather_set=[],
            location_id=52,
            best_catch_path=[],
            predators=[],
            intuition_length=None,
            fish_eyes=False,
            folklore=None,
            snagging=None,
            lure=None,
            hookset=None,
            tug=None,
            gig=None,
            data_missing=None,
            aquarium=None,
        )
        update = mocker.Mock(spec=Update)
        update.effective_user.id = 1001
        update.message.reply_text = mocker.AsyncMock()
        context = mocker.Mock(spec=ContextTypes.DEFAULT_TYPE)
        context.args = ["Merlthor"]
        context.bot_data = {BOT_DATA_KEY: fd}

        from ff14_fish_telegram.bot.handlers import caught

        await caught(update, context)
        msg = update.message.reply_text.call_args[0][0]
        assert "Multiple fish match" in msg


class TestUncaughtHandler:
    """Tests for the /uncaught command handler."""

    @pytest.mark.asyncio
    async def test_no_fish_data(self, mocker):
        update = mocker.Mock(spec=Update)
        update.effective_user.id = 1001
        update.message.reply_text = mocker.AsyncMock()
        context = mocker.Mock(spec=ContextTypes.DEFAULT_TYPE)
        context.args = []
        context.bot_data = {}

        from ff14_fish_telegram.bot.handlers import uncaught

        await uncaught(update, context)
        update.message.reply_text.assert_awaited_once_with(
            "Fish data not loaded yet. Try again shortly."
        )

    @pytest.mark.asyncio
    async def test_no_args_shows_all_fish(self, mocker):
        update = mocker.Mock(spec=Update)
        update.effective_user.id = 1001
        update.message.reply_text = mocker.AsyncMock()
        context = mocker.Mock(spec=ContextTypes.DEFAULT_TYPE)
        context.args = []
        context.bot_data = {BOT_DATA_KEY: _make_fish_data()}

        from ff14_fish_telegram.bot.handlers import uncaught

        await uncaught(update, context)
        msg = update.message.reply_text.call_args[0][0]
        assert "Merlthor Goby" in msg
        assert "Uncaught fish" in msg

    @pytest.mark.asyncio
    async def test_no_args_all_caught(self, mocker):
        from ff14_fish_telegram.db.database import mark_caught

        mark_caught(1001, 4898)
        update = mocker.Mock(spec=Update)
        update.effective_user.id = 1001
        update.message.reply_text = mocker.AsyncMock()
        context = mocker.Mock(spec=ContextTypes.DEFAULT_TYPE)
        context.args = []
        context.bot_data = {BOT_DATA_KEY: _make_fish_data()}

        from ff14_fish_telegram.bot.handlers import uncaught

        await uncaught(update, context)
        update.message.reply_text.assert_awaited_once_with("You've caught every fish!")

    @pytest.mark.asyncio
    async def test_match_all(self, mocker):
        from ff14_fish_telegram.db.database import mark_caught

        mark_caught(1001, 4898)
        update = mocker.Mock(spec=Update)
        update.effective_user.id = 1001
        update.message.reply_text = mocker.AsyncMock()
        context = mocker.Mock(spec=ContextTypes.DEFAULT_TYPE)
        context.args = ["all"]
        context.bot_data = {BOT_DATA_KEY: _make_fish_data()}

        from ff14_fish_telegram.bot.handlers import uncaught

        await uncaught(update, context)
        update.message.reply_text.assert_awaited_once_with("Marked all 1 fish as uncaught.")

        from ff14_fish_telegram.db.database import is_caught

        assert is_caught(1001, 4898) is False

    @pytest.mark.asyncio
    async def test_match_single_fish(self, mocker):
        update = mocker.Mock(spec=Update)
        update.effective_user.id = 1001
        update.message.reply_text = mocker.AsyncMock()
        context = mocker.Mock(spec=ContextTypes.DEFAULT_TYPE)
        context.args = ["Merlthor"]
        context.bot_data = {BOT_DATA_KEY: _make_fish_data()}

        from ff14_fish_telegram.bot.handlers import uncaught

        await uncaught(update, context)
        update.message.reply_text.assert_awaited_once_with("Marked 'Merlthor Goby' as uncaught.")

    @pytest.mark.asyncio
    async def test_no_match(self, mocker):
        update = mocker.Mock(spec=Update)
        update.effective_user.id = 1001
        update.message.reply_text = mocker.AsyncMock()
        context = mocker.Mock(spec=ContextTypes.DEFAULT_TYPE)
        context.args = ["nonexistent"]
        context.bot_data = {BOT_DATA_KEY: _make_fish_data()}

        from ff14_fish_telegram.bot.handlers import uncaught

        await uncaught(update, context)
        update.message.reply_text.assert_awaited_once_with("No fish found matching 'nonexistent'.")

    @pytest.mark.asyncio
    async def test_multiple_matches(self, mocker):
        fd = _make_fish_data()
        fd.fish[4911] = Fish(
            id=4911,
            name_en="Merlthor Clam",
            start_hour=0,
            end_hour=24,
            patch=2.0,
            big_fish=False,
            collectable=None,
            weather_set=[],
            previous_weather_set=[],
            location_id=52,
            best_catch_path=[],
            predators=[],
            intuition_length=None,
            fish_eyes=False,
            folklore=None,
            snagging=None,
            lure=None,
            hookset=None,
            tug=None,
            gig=None,
            data_missing=None,
            aquarium=None,
        )
        update = mocker.Mock(spec=Update)
        update.effective_user.id = 1001
        update.message.reply_text = mocker.AsyncMock()
        context = mocker.Mock(spec=ContextTypes.DEFAULT_TYPE)
        context.args = ["Merlthor"]
        context.bot_data = {BOT_DATA_KEY: fd}

        from ff14_fish_telegram.bot.handlers import uncaught

        await uncaught(update, context)
        msg = update.message.reply_text.call_args[0][0]
        assert "Multiple fish match" in msg


class TestDayHandler:
    """Tests for the /day command handler."""

    @pytest.mark.asyncio
    async def test_no_fish_data(self, mocker):
        update = mocker.Mock(spec=Update)
        update.effective_user.id = 1001
        update.message.reply_text = mocker.AsyncMock()
        context = mocker.Mock(spec=ContextTypes.DEFAULT_TYPE)
        context.args = []
        context.bot_data = {}

        from ff14_fish_telegram.bot.handlers import day

        await day(update, context)
        update.message.reply_text.assert_awaited_once_with(
            "Fish data not loaded yet. Try again shortly."
        )

    @pytest.mark.asyncio
    async def test_with_uncaught_fish_returns_windows(self, mocker):
        fd = _make_fish_data()
        fd.fish[4898].start_hour = 0
        fd.fish[4898].end_hour = 24
        update = mocker.Mock(spec=Update)
        update.effective_user.id = 1001
        update.message.reply_text = mocker.AsyncMock()
        context = mocker.Mock(spec=ContextTypes.DEFAULT_TYPE)
        context.args = []
        context.bot_data = {BOT_DATA_KEY: fd}

        from ff14_fish_telegram.bot.handlers import day

        await day(update, context)
        calls = update.message.reply_text.call_args_list
        assert len(calls) >= 1
        first_msg = calls[0][0][0]
        assert "Uncaught fish available" in first_msg

    @pytest.mark.asyncio
    async def test_all_caught_returns_no_windows(self, mocker):
        from ff14_fish_telegram.db.database import mark_caught

        mark_caught(1001, 4898)
        fd = _make_fish_data()
        update = mocker.Mock(spec=Update)
        update.effective_user.id = 1001
        update.message.reply_text = mocker.AsyncMock()
        context = mocker.Mock(spec=ContextTypes.DEFAULT_TYPE)
        context.args = []
        context.bot_data = {BOT_DATA_KEY: fd}

        from ff14_fish_telegram.bot.handlers import day

        await day(update, context)
        update.message.reply_text.assert_awaited_once_with(
            "No uncaught fish available in the next 24 hours."
        )

    @pytest.mark.asyncio
    async def test_fish_with_weather_shows_weather_info(self, mocker):
        from ff14_fish_telegram.data.models import WeatherRate

        fd = _make_fish_data()
        fd.fish[4898].weather_set = [1]
        fd.weather_rates = {
            134: WeatherRate(
                map_id=11, zone_id=31, region_id=22,
                weather_rates=[[3, 20], [1, 50], [2, 80], [4, 90], [7, 100]],
            ),
        }
        update = mocker.Mock(spec=Update)
        update.effective_user.id = 1001
        update.message.reply_text = mocker.AsyncMock()
        context = mocker.Mock(spec=ContextTypes.DEFAULT_TYPE)
        context.args = []
        context.bot_data = {BOT_DATA_KEY: fd}

        from ff14_fish_telegram.bot.handlers import day

        await day(update, context)
        calls = update.message.reply_text.call_args_list
        first_content = calls[0][0][0]
        assert "Uncaught fish available" in first_content

    @pytest.mark.asyncio
    async def test_fish_with_previous_weather_shows_prev_info(self, mocker):
        from ff14_fish_telegram.data.models import WeatherRate

        fd = _make_fish_data()
        fd.fish[4898].weather_set = [1]
        fd.fish[4898].previous_weather_set = [2]
        fd.weather_rates = {
            134: WeatherRate(
                map_id=11, zone_id=31, region_id=22,
                weather_rates=[[3, 20], [1, 50], [2, 80], [4, 90], [7, 100]],
            ),
        }
        update = mocker.Mock(spec=Update)
        update.effective_user.id = 1001
        update.message.reply_text = mocker.AsyncMock()
        context = mocker.Mock(spec=ContextTypes.DEFAULT_TYPE)
        context.args = []
        context.bot_data = {BOT_DATA_KEY: fd}

        from ff14_fish_telegram.bot.handlers import day

        await day(update, context)
        calls = update.message.reply_text.call_args_list
        first_content = calls[0][0][0]
        assert "Uncaught fish available" in first_content


class TestCaughtCallback:
    """Tests for inline button callback (caught:<fish_id>)."""

    @pytest.mark.asyncio
    async def test_valid_callback_marks_caught(self, mocker):
        query = mocker.Mock()
        query.answer = mocker.AsyncMock()
        query.edit_message_text = mocker.AsyncMock()
        query.data = "caught:4898"
        query.from_user.id = 1001
        update = mocker.Mock(spec=Update)
        update.callback_query = query
        context = mocker.Mock(spec=ContextTypes.DEFAULT_TYPE)
        context.bot_data = {BOT_DATA_KEY: _make_fish_data()}

        from ff14_fish_telegram.bot.handlers import caught_callback

        await caught_callback(update, context)
        query.answer.assert_awaited_once()
        query.edit_message_text.assert_awaited_once_with("Marked 'Merlthor Goby' as caught! ✅")

        from ff14_fish_telegram.db.database import is_caught

        assert is_caught(1001, 4898) is True

    @pytest.mark.asyncio
    async def test_invalid_callback_data(self, mocker):
        query = mocker.Mock()
        query.answer = mocker.AsyncMock()
        query.edit_message_text = mocker.AsyncMock()
        query.data = "invalid"
        query.from_user.id = 1001
        update = mocker.Mock(spec=Update)
        update.callback_query = query
        context = mocker.Mock(spec=ContextTypes.DEFAULT_TYPE)
        context.bot_data = {BOT_DATA_KEY: _make_fish_data()}

        from ff14_fish_telegram.bot.handlers import caught_callback

        await caught_callback(update, context)
        query.edit_message_text.assert_awaited_once_with("Invalid callback data.")

    @pytest.mark.asyncio
    async def test_already_caught(self, mocker):
        from ff14_fish_telegram.db.database import mark_caught

        mark_caught(1001, 4898)
        query = mocker.Mock()
        query.answer = mocker.AsyncMock()
        query.edit_message_text = mocker.AsyncMock()
        query.data = "caught:4898"
        query.from_user.id = 1001
        update = mocker.Mock(spec=Update)
        update.callback_query = query
        context = mocker.Mock(spec=ContextTypes.DEFAULT_TYPE)
        context.bot_data = {BOT_DATA_KEY: _make_fish_data()}

        from ff14_fish_telegram.bot.handlers import caught_callback

        await caught_callback(update, context)
        query.edit_message_text.assert_awaited_once_with(
            "'Merlthor Goby' was already marked as caught.",
        )

    @pytest.mark.asyncio
    async def test_fish_not_found(self, mocker):
        query = mocker.Mock()
        query.answer = mocker.AsyncMock()
        query.edit_message_text = mocker.AsyncMock()
        query.data = "caught:9999"
        query.from_user.id = 1001
        update = mocker.Mock(spec=Update)
        update.callback_query = query
        context = mocker.Mock(spec=ContextTypes.DEFAULT_TYPE)
        context.bot_data = {BOT_DATA_KEY: _make_fish_data()}

        from ff14_fish_telegram.bot.handlers import caught_callback

        await caught_callback(update, context)
        query.edit_message_text.assert_awaited_once_with("Fish not found in data.")

    @pytest.mark.asyncio
    async def test_no_fish_data(self, mocker):
        query = mocker.Mock()
        query.answer = mocker.AsyncMock()
        query.edit_message_text = mocker.AsyncMock()
        query.data = "caught:4898"
        query.from_user.id = 1001
        update = mocker.Mock(spec=Update)
        update.callback_query = query
        context = mocker.Mock(spec=ContextTypes.DEFAULT_TYPE)
        context.bot_data = {}

        from ff14_fish_telegram.bot.handlers import caught_callback

        await caught_callback(update, context)
        query.edit_message_text.assert_awaited_once_with(
            "Fish data not loaded yet. Try again shortly.",
        )


class TestGetHandlers:
    """Tests for get_handlers registration."""

    def test_returns_list_of_handlers(self):
        handlers = get_handlers()
        assert len(handlers) == 5
        names = [h.__class__.__name__ for h in handlers]
        assert "CommandHandler" in names
        assert "CallbackQueryHandler" in names

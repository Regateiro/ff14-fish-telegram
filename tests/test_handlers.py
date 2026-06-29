import pytest
from telegram import Update
from telegram.ext import ContextTypes

from ff14_fish_telegram.bot.handlers import _HELP_TEXT, BOT_DATA_KEY, _sanitize
from ff14_fish_telegram.data.models import FishData


class TestSanitize:
    def test_lowercase(self):
        assert _sanitize("Merlthor Goby") == "merlthor goby"

    def test_strip(self):
        assert _sanitize("  Fish  ") == "fish"

    def test_empty(self):
        assert _sanitize("") == ""


class TestCaughtHandler:
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
    async def test_no_args_empty(self, mocker):
        update = mocker.Mock(spec=Update)
        update.effective_user.id = 1001
        update.message.reply_text = mocker.AsyncMock()
        context = mocker.Mock(spec=ContextTypes.DEFAULT_TYPE)
        context.args = []
        context.bot_data = {
            BOT_DATA_KEY: FishData(
                fish={},
                fishing_spots={},
                items={},
                weather_rates={},
                weather_types={},
                regions={},
                zones={},
            )
        }

        from ff14_fish_telegram.bot.handlers import caught

        await caught(update, context)
        update.message.reply_text.assert_awaited_once_with("You haven't caught any fish yet.")

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
        context.bot_data = {
            BOT_DATA_KEY: FishData(
                fish={},
                fishing_spots={},
                items={},
                weather_rates={},
                weather_types={},
                regions={},
                zones={},
            )
        }

        from ff14_fish_telegram.bot.handlers import caught

        await caught(update, context)
        update.message.reply_text.assert_awaited_once_with("No fish found matching 'nonexistent'.")


class TestStartHandler:
    @pytest.mark.asyncio
    async def test_start(self, mocker):
        update = mocker.Mock(spec=Update)
        update.effective_user.id = 1001
        update.message.reply_text = mocker.AsyncMock()
        context = mocker.Mock(spec=ContextTypes.DEFAULT_TYPE)

        from ff14_fish_telegram.bot.handlers import start

        await start(update, context)
        update.message.reply_text.assert_awaited_once_with(_HELP_TEXT)


class TestDayHandler:
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

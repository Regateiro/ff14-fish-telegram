"""Tests for the periodic reminder logic."""

from datetime import datetime, timedelta, timezone

import pytest

from ff14_fish_telegram.data.models import Fish, FishData, FishingSpot


class TestLeadTimeSeconds:
    """Tests for _lead_time_seconds helper."""

    def test_lead_time_with_intuition(self, fish_with_intuition):
        from ff14_fish_telegram.bot.reminders import _lead_time_seconds

        assert _lead_time_seconds(fish_with_intuition) == 1800

    def test_lead_time_without_intuition(self, sample_fish):
        from ff14_fish_telegram.bot.reminders import _lead_time_seconds

        assert _lead_time_seconds(sample_fish) == 600

    def test_lead_time_with_predators(self):
        f = Fish(
            id=1, name_en="Test", start_hour=0, end_hour=24, patch=1,
            big_fish=False, collectable=None, weather_set=[], previous_weather_set=[],
            location_id=1, best_catch_path=[], predators=[4898], intuition_length=None,
            fish_eyes=None, folklore=None, snagging=None, lure=None, hookset=None,
            tug=None, gig=None, data_missing=None, aquarium=None,
        )
        from ff14_fish_telegram.bot.reminders import _lead_time_seconds

        assert _lead_time_seconds(f) == 1800


class TestCheckReminders:
    """Tests for check_reminders main logic."""

    @pytest.mark.asyncio
    async def test_no_fish_data_returns_early(self, mocker):
        app = mocker.Mock()
        app.bot_data = {}

        from ff14_fish_telegram.bot.reminders import check_reminders

        await check_reminders(app)
        # Should not raise and not call any DB functions
        app.bot.send_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_users_returns_early(self, mocker):
        fd = FishData(
            fish={}, fishing_spots={}, items={}, weather_rates={},
            weather_types={}, regions={}, zones={},
        )
        app = mocker.Mock()
        app.bot_data = {"fish_data": fd}

        mocker.patch("ff14_fish_telegram.bot.reminders.get_all_user_ids", return_value=set())

        from ff14_fish_telegram.bot.reminders import check_reminders

        await check_reminders(app)
        app.bot.send_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_sends_reminder_for_upcoming_window(self, mocker):
        now = datetime.now(timezone.utc)
        window_start = now + timedelta(minutes=5)

        fish = Fish(
            id=100, name_en="Test Fish", start_hour=18, end_hour=6, patch=2,
            big_fish=False, collectable=None, weather_set=[], previous_weather_set=[],
            location_id=52, best_catch_path=[], predators=[], intuition_length=None,
            fish_eyes=False, folklore=None, snagging=None, lure=None, hookset=None,
            tug=None, gig=None, data_missing=None, aquarium=None,
        )
        fd = FishData(
            fish={100: fish},
            fishing_spots={
                52: FishingSpot(
                    id=52, name_en="Test Spot", territory_id=134,
                    placename_id=52, zone_id=31, region_id=22,
                ),
            },
            items={},
            weather_rates={},
            weather_types={},
            regions={},
            zones={31: "Test Zone"},
        )

        app = mocker.Mock()
        app.bot_data = {"fish_data": fd}
        app.bot.send_message = mocker.AsyncMock()

        mocker.patch("ff14_fish_telegram.bot.reminders.get_all_user_ids", return_value={1001})
        mocker.patch("ff14_fish_telegram.bot.reminders.get_caught_fish_ids", return_value=set())

        from ff14_fish_telegram.data.availability import CatchableWindow

        mock_window = CatchableWindow(
            start_eorzea=100000.0,
            end_eorzea=200000.0,
            start_earth=window_start,
            end_earth=window_start + timedelta(hours=8),
        )
        mocker.patch("ff14_fish_telegram.bot.reminders.get_next_window", return_value=mock_window)
        mocker.patch("ff14_fish_telegram.bot.reminders.reminder_sent", return_value=False)
        mock_mark = mocker.patch("ff14_fish_telegram.bot.reminders.mark_reminder_sent")

        from ff14_fish_telegram.bot.reminders import check_reminders

        await check_reminders(app)
        app.bot.send_message.assert_awaited_once()
        args, kwargs = app.bot.send_message.call_args
        assert kwargs["chat_id"] == 1001
        assert "Test Fish" in kwargs["text"]
        mock_mark.assert_called_once_with(1001, 100, 100000)

    @pytest.mark.asyncio
    async def test_skips_caught_fish(self, mocker):
        fish = Fish(
            id=100, name_en="Test Fish", start_hour=0, end_hour=24, patch=2,
            big_fish=False, collectable=None, weather_set=[], previous_weather_set=[],
            location_id=52, best_catch_path=[], predators=[], intuition_length=None,
            fish_eyes=False, folklore=None, snagging=None, lure=None, hookset=None,
            tug=None, gig=None, data_missing=None, aquarium=None,
        )
        fd = FishData(
            fish={100: fish}, fishing_spots={}, items={}, weather_rates={},
            weather_types={}, regions={}, zones={},
        )

        app = mocker.Mock()
        app.bot_data = {"fish_data": fd}

        mocker.patch("ff14_fish_telegram.bot.reminders.get_all_user_ids", return_value={1001})
        mocker.patch("ff14_fish_telegram.bot.reminders.get_caught_fish_ids", return_value={100})

        from ff14_fish_telegram.bot.reminders import check_reminders

        await check_reminders(app)
        app.bot.send_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_skips_always_available_fish(self, mocker):
        fish = Fish(
            id=100, name_en="Always Fish", start_hour=0, end_hour=24, patch=2,
            big_fish=False, collectable=None, weather_set=[], previous_weather_set=[],
            location_id=52, best_catch_path=[], predators=[], intuition_length=None,
            fish_eyes=False, folklore=None, snagging=None, lure=None, hookset=None,
            tug=None, gig=None, data_missing=None, aquarium=None,
        )
        fd = FishData(
            fish={100: fish}, fishing_spots={}, items={}, weather_rates={},
            weather_types={}, regions={}, zones={},
        )

        app = mocker.Mock()
        app.bot_data = {"fish_data": fd}

        mocker.patch("ff14_fish_telegram.bot.reminders.get_all_user_ids", return_value={1001})
        mocker.patch("ff14_fish_telegram.bot.reminders.get_caught_fish_ids", return_value=set())

        from ff14_fish_telegram.bot.reminders import check_reminders

        await check_reminders(app)
        app.bot.send_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_skips_when_no_window(self, mocker):
        fish = Fish(
            id=100, name_en="No Window Fish", start_hour=18, end_hour=6, patch=2,
            big_fish=False, collectable=None, weather_set=[], previous_weather_set=[],
            location_id=999, best_catch_path=[], predators=[], intuition_length=None,
            fish_eyes=False, folklore=None, snagging=None, lure=None, hookset=None,
            tug=None, gig=None, data_missing=None, aquarium=None,
        )
        fd = FishData(
            fish={100: fish}, fishing_spots={}, items={}, weather_rates={},
            weather_types={}, regions={}, zones={},
        )

        app = mocker.Mock()
        app.bot_data = {"fish_data": fd}

        mocker.patch("ff14_fish_telegram.bot.reminders.get_all_user_ids", return_value={1001})
        mocker.patch("ff14_fish_telegram.bot.reminders.get_caught_fish_ids", return_value=set())

        from ff14_fish_telegram.bot.reminders import check_reminders

        await check_reminders(app)
        app.bot.send_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_skips_when_reminder_already_sent(self, mocker):
        now = datetime.now(timezone.utc)
        window_start = now + timedelta(minutes=5)

        fish = Fish(
            id=100, name_en="Test Fish", start_hour=18, end_hour=6, patch=2,
            big_fish=False, collectable=None, weather_set=[], previous_weather_set=[],
            location_id=52, best_catch_path=[], predators=[], intuition_length=None,
            fish_eyes=False, folklore=None, snagging=None, lure=None, hookset=None,
            tug=None, gig=None, data_missing=None, aquarium=None,
        )
        fd = FishData(
            fish={100: fish},
            fishing_spots={
                52: FishingSpot(
                    id=52, name_en="Test Spot", territory_id=134,
                    placename_id=52, zone_id=31, region_id=22,
                ),
            },
            items={},
            weather_rates={},
            weather_types={},
            regions={},
            zones={31: "Test Zone"},
        )

        app = mocker.Mock()
        app.bot_data = {"fish_data": fd}
        app.bot.send_message = mocker.AsyncMock()

        mocker.patch("ff14_fish_telegram.bot.reminders.get_all_user_ids", return_value={1001})
        mocker.patch("ff14_fish_telegram.bot.reminders.get_caught_fish_ids", return_value=set())

        from ff14_fish_telegram.data.availability import CatchableWindow

        mock_window = CatchableWindow(
            start_eorzea=100000.0,
            end_eorzea=200000.0,
            start_earth=window_start,
            end_earth=window_start + timedelta(hours=8),
        )
        mocker.patch("ff14_fish_telegram.bot.reminders.get_next_window", return_value=mock_window)
        mocker.patch("ff14_fish_telegram.bot.reminders.reminder_sent", return_value=True)

        from ff14_fish_telegram.bot.reminders import check_reminders

        await check_reminders(app)
        app.bot.send_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_send_failure_does_not_crash(self, mocker):
        now = datetime.now(timezone.utc)
        window_start = now + timedelta(minutes=5)

        fish = Fish(
            id=100, name_en="Test Fish", start_hour=18, end_hour=6, patch=2,
            big_fish=False, collectable=None, weather_set=[], previous_weather_set=[],
            location_id=52, best_catch_path=[], predators=[], intuition_length=None,
            fish_eyes=False, folklore=None, snagging=None, lure=None, hookset=None,
            tug=None, gig=None, data_missing=None, aquarium=None,
        )
        fd = FishData(
            fish={100: fish},
            fishing_spots={
                52: FishingSpot(
                    id=52, name_en="Test Spot", territory_id=134,
                    placename_id=52, zone_id=31, region_id=22,
                ),
            },
            items={},
            weather_rates={},
            weather_types={},
            regions={},
            zones={31: "Test Zone"},
        )

        app = mocker.Mock()
        app.bot_data = {"fish_data": fd}
        app.bot.send_message = mocker.AsyncMock(side_effect=Exception("Telegram API error"))

        mocker.patch("ff14_fish_telegram.bot.reminders.get_all_user_ids", return_value={1001})
        mocker.patch("ff14_fish_telegram.bot.reminders.get_caught_fish_ids", return_value=set())

        from ff14_fish_telegram.data.availability import CatchableWindow

        mock_window = CatchableWindow(
            start_eorzea=100000.0,
            end_eorzea=200000.0,
            start_earth=window_start,
            end_earth=window_start + timedelta(hours=8),
        )
        mocker.patch("ff14_fish_telegram.bot.reminders.get_next_window", return_value=mock_window)
        mocker.patch("ff14_fish_telegram.bot.reminders.reminder_sent", return_value=False)

        from ff14_fish_telegram.bot.reminders import check_reminders

        # Should not raise despite send_message failure
        await check_reminders(app)
        app.bot.send_message.assert_awaited_once()

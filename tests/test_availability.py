"""Tests for Eorzea time conversion, fish model properties, and catchable window computation."""

from datetime import datetime, timezone

import pytest

from ff14_fish_telegram.data.availability import (
    CatchableWindow,
    _available_time_ranges,
    _find_weather_windows,
    _forecast_target,
    _get_weather_at,
    _uint32,
    _weather_matches,
    _weather_period_start_eorzea,
    compute_catchable_windows,
    earth_to_eorzea,
    eorzea_to_earth,
    get_next_window,
    get_zone_name_for_spot,
)


class TestTimeConversion:
    """Tests for earth_to_eorzea and eorzea_to_earth roundtrip conversion."""

    def test_earth_to_eorzea(self):
        dt = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        et = earth_to_eorzea(dt)
        assert et > 0
        assert isinstance(et, float)

    def test_eorzea_to_earth(self):
        dt = eorzea_to_earth(1000000)
        assert isinstance(dt, datetime)

    def test_roundtrip(self):
        original = datetime(2024, 6, 15, 12, 30, 0, tzinfo=timezone.utc)
        eo = earth_to_eorzea(original)
        back = eorzea_to_earth(eo)
        assert abs((original - back).total_seconds()) < 1


class TestFishModelProperties:
    """Tests for Fish.always_available and Fish.has_intuition_or_predator."""

    def test_always_available_true(self, sample_fish):
        f = sample_fish
        f.start_hour = 0
        f.end_hour = 24
        assert f.always_available is True

    def test_always_available_false_time(self, sample_fish):
        assert sample_fish.always_available is False

    def test_has_intuition_or_predator_with_predators(self, fish_with_intuition):
        assert fish_with_intuition.has_intuition_or_predator is True

    def test_has_intuition_or_predator_without(self, sample_fish):
        assert sample_fish.has_intuition_or_predator is False

    def test_has_intuition_or_predator_with_length(self):
        from ff14_fish_telegram.data.models import Fish

        f = Fish(
            id=1,
            name_en="Test",
            start_hour=0,
            end_hour=24,
            patch=1,
            big_fish=False,
            collectable=None,
            weather_set=[],
            previous_weather_set=[],
            location_id=1,
            best_catch_path=[],
            predators=[],
            intuition_length=120,
            fish_eyes=True,
            folklore=None,
            snagging=None,
            lure=None,
            hookset=None,
            tug=None,
            gig=None,
            data_missing=None,
            aquarium=None,
        )
        assert f.has_intuition_or_predator is True


class TestCatchableWindows:
    """Tests for compute_catchable_windows and get_next_window."""

    def test_always_available_fish_returns_window(self, sample_fish, sample_fish_data):
        f = sample_fish
        f.start_hour = 0
        f.end_hour = 24
        windows = compute_catchable_windows(f, sample_fish_data, max_windows=1)
        assert len(windows) >= 1

    def test_time_restricted_fish(self, time_restricted_fish, sample_fish_data):
        windows = compute_catchable_windows(time_restricted_fish, sample_fish_data, max_windows=1)
        assert isinstance(windows, list)

    def test_get_next_window(self, sample_fish, sample_fish_data):
        f = sample_fish
        f.start_hour = 0
        f.end_hour = 24
        w = get_next_window(f, sample_fish_data)
        assert w is not None
        assert isinstance(w, CatchableWindow)

    def test_catchable_window_fields(self):
        now = datetime.now(timezone.utc)
        cw = CatchableWindow(
            start_eorzea=100000.0,
            end_eorzea=200000.0,
            start_earth=now,
            end_earth=now,
        )
        assert cw.start_eorzea == 100000.0
        assert cw.end_eorzea == 200000.0

    def test_always_available_returns_7_day_window(self, sample_fish, sample_fish_data):
        f = sample_fish
        f.start_hour = 0
        f.end_hour = 24
        windows = compute_catchable_windows(f, sample_fish_data, max_windows=1)
        assert len(windows) >= 1
        duration = (windows[0].end_earth - windows[0].start_earth).total_seconds()
        assert duration == pytest.approx(86400 * 7, abs=10)

    def test_fish_with_no_spot_and_restriction_returns_empty(self, sample_fish, sample_fish_data):
        f = sample_fish
        f.location_id = 99999
        windows = compute_catchable_windows(f, sample_fish_data, max_windows=1)
        assert windows == []

    def test_get_next_window_none(self, sample_fish, sample_fish_data):
        f = sample_fish
        f.location_id = 99999
        w = get_next_window(f, sample_fish_data)
        assert w is None


class TestWeatherFunctions:
    """Tests for FFXIV weather prediction internals."""

    def test_uint32_masks_correctly(self):
        assert _uint32(0xFFFFFFFF) == 0xFFFFFFFF
        assert _uint32(0x100000000) == 0
        assert _uint32(0x1FFFFFFFF) == 0xFFFFFFFF
        assert _uint32(42) == 42

    def test_weather_period_start_eorzea(self):
        et = _weather_period_start_eorzea(3600 * 10)
        assert et == 3600 * 8
        et2 = _weather_period_start_eorzea(3600 * 20)
        assert et2 == 3600 * 16

    def test_forecast_target_is_deterministic(self):
        ts = 1700000000.0
        result1 = _forecast_target(ts)
        result2 = _forecast_target(ts)
        assert result1 == result2
        assert 0 <= result1 < 100

    def test_forecast_target_different_times(self):
        r1 = _forecast_target(1700000000.0)
        r2 = _forecast_target(1701400.0)
        assert isinstance(r1, int)
        assert isinstance(r2, int)

    def test_get_weather_at_returns_weather(self, fish_data_with_weather):
        wr = fish_data_with_weather.weather_rates[134]
        ts = 1700000000.0
        weather_id = _get_weather_at(134, ts, fish_data_with_weather)
        assert weather_id is not None
        assert isinstance(weather_id, int)
        available_ids = {r[0] for r in wr.weather_rates}
        assert weather_id in available_ids

    def test_get_weather_at_missing_territory(self, fish_data_with_weather):
        result = _get_weather_at(999, 1700000000.0, fish_data_with_weather)
        assert result is None

    def test_get_weather_at_empty_rates(self, fish_data_with_weather):
        from ff14_fish_telegram.data.models import WeatherRate

        fish_data_with_weather.weather_rates[999] = WeatherRate(
            map_id=1, zone_id=1, region_id=1, weather_rates=[],
        )
        result = _get_weather_at(999, 1700000000.0, fish_data_with_weather)
        assert result is None

    def test_get_weather_at_falls_back_to_last_rate(
        self, fish_data_with_weather,
    ):
        from ff14_fish_telegram.data.models import WeatherRate

        # Rates with cumulative=0 never match any target (0-99), so loop falls
        # through to return rates[-1][0] (line 127).
        fish_data_with_weather.weather_rates[134] = WeatherRate(
            map_id=11, zone_id=31, region_id=22,
            weather_rates=[[1, 0]],
        )
        result = _get_weather_at(134, 1700000000.0, fish_data_with_weather)
        assert result == 1

    def test_weather_matches_empty_set(self):
        assert _weather_matches(1, []) is True

    def test_weather_matches_in_set(self):
        assert _weather_matches(1, [1, 2, 3]) is True

    def test_weather_matches_not_in_set(self):
        assert _weather_matches(5, [1, 2, 3]) is False


class TestAvailableTimeRanges:
    """Tests for _available_time_ranges intersection logic."""

    def test_unrestricted_fish_returns_full_period(self, sample_fish, fish_data_with_weather):
        sample_fish.start_hour = 0
        sample_fish.end_hour = 24
        result = _available_time_ranges(sample_fish, 100000.0, 200000.0)
        assert len(result) == 1
        assert result[0] == (100000.0, 200000.0)

    def test_restricted_fish_returns_overlap(self, time_restricted_fish):
        # Weather period from ET 10:00 to 18:00, fish window 17:00-22:00
        weather_start = 3600 * 10
        weather_end = 3600 * 18
        result = _available_time_ranges(time_restricted_fish, weather_start, weather_end)
        assert len(result) >= 1
        # Overlap should be from 17:00 to 18:00
        for s, e in result:
            assert s >= weather_start
            assert e <= weather_end

    def test_overnight_fish_two_candidates(self, sample_fish):
        # sample_fish is overnight 18:00-06:00
        weather_start = 3600 * 10
        weather_end = 3600 * 18
        result = _available_time_ranges(sample_fish, weather_start, weather_end)
        assert isinstance(result, list)

    def test_no_overlap_returns_empty(self, time_restricted_fish):
        # Fish 17:00-22:00, weather 08:00-10:00 → no overlap
        result = _available_time_ranges(time_restricted_fish, 3600 * 8, 3600 * 10)
        assert result == []


class TestWeatherWindows:
    """Tests for _find_weather_windows weather period iteration."""

    def test_find_weather_windows_yields_results(self, fish_data_with_weather):
        gen = _find_weather_windows(
            1700000000.0,
            134,
            [],
            [1],
            fish_data_with_weather,
            limit=300,
        )
        results = list(gen)
        assert len(results) >= 1
        for start, end in results:
            assert end > start

    def test_find_weather_windows_with_previous_weather(
        self, fish_with_previous_weather, fish_data_with_weather,
    ):
        gen = _find_weather_windows(
            1700000000.0,
            134,
            fish_with_previous_weather.previous_weather_set,
            fish_with_previous_weather.weather_set,
            fish_data_with_weather,
            limit=500,
        )
        results = list(gen)
        assert isinstance(results, list)


class TestComputeCatchableWindowsWithWeather:
    """Tests for compute_catchable_windows with weather-restricted fish."""

    def test_weather_restricted_fish_returns_windows(self, fish_data_with_weather):
        fish = fish_data_with_weather.fish[4898]
        fish.start_hour = 0
        fish.end_hour = 24
        fish.weather_set = [1]
        windows = compute_catchable_windows(fish, fish_data_with_weather, max_windows=3)
        assert len(windows) >= 1
        assert all(isinstance(w, CatchableWindow) for w in windows)

    def test_missing_territory_id_returns_empty(self, fish_data_with_weather):
        fish = fish_data_with_weather.fish[4898]
        fish.start_hour = 0
        fish.end_hour = 24
        fish.location_id = 52
        fish_data_with_weather.fishing_spots[52].territory_id = None
        windows = compute_catchable_windows(fish, fish_data_with_weather, max_windows=1)
        assert windows == []

    def test_no_weather_rate_returns_empty(self, fish_data_with_weather):
        fish = fish_data_with_weather.fish[4898]
        fish.start_hour = 0
        fish.end_hour = 24
        fish.location_id = 52
        fish_data_with_weather.fishing_spots[52].territory_id = 999
        windows = compute_catchable_windows(fish, fish_data_with_weather, max_windows=1)
        assert windows == []

    def test_empty_rate_list_causes_no_weather(
        self, fish_data_with_weather,
    ):
        fish = fish_data_with_weather.fish[4898]
        fish.start_hour = 0
        fish.end_hour = 24
        fish.weather_set = [1]
        fish.location_id = 52
        from ff14_fish_telegram.data.models import WeatherRate

        fish_data_with_weather.weather_rates[134] = WeatherRate(
            map_id=11, zone_id=31, region_id=22, weather_rates=[],
        )
        windows = compute_catchable_windows(fish, fish_data_with_weather, max_windows=3)
        assert windows == []


class TestGetZoneName:
    """Tests for get_zone_name_for_spot."""

    def test_valid_spot_returns_zone(self, fish_data_with_weather):
        zone = get_zone_name_for_spot(52, fish_data_with_weather)
        assert zone == "Lower La Noscea"

    def test_missing_spot_returns_empty(self, fish_data_with_weather):
        zone = get_zone_name_for_spot(999, fish_data_with_weather)
        assert zone == ""

    def test_missing_weather_rate_returns_empty(self, sample_fish_data):
        zone = get_zone_name_for_spot(52, sample_fish_data)
        assert zone == ""

    def test_no_territory_id(self, fish_data_with_weather):
        spot = fish_data_with_weather.fishing_spots[52]
        spot.territory_id = None
        zone = get_zone_name_for_spot(52, fish_data_with_weather)
        assert zone == ""

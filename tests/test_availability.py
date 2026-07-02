"""Tests for Eorzea time conversion, fish model properties, and catchable window computation."""

from datetime import datetime, timezone

from ff14_fish_telegram.data.availability import (
    CatchableWindow,
    compute_catchable_windows,
    earth_to_eorzea,
    eorzea_to_earth,
    get_next_window,
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

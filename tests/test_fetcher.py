"""Tests for the JS data parser and FishData builder."""

from ff14_fish_telegram.data.fetcher import (
    build_fish_data,
    parse_data_js,
    parse_fish_info_js,
)


class TestParseDataJs:
    """Tests for extracting the DATA object from the main JS file."""

    def test_parses_valid_js(self, sample_js_content: str):
        parsed = parse_data_js(sample_js_content)
        assert "FISH" in parsed
        assert "FISHING_SPOTS" in parsed
        assert "ITEMS" in parsed

    def test_parses_fish_ids(self, sample_js_content: str):
        parsed = parse_data_js(sample_js_content)
        assert "4898" in parsed["FISH"]
        assert "4911" in parsed["FISH"]

    def test_raises_on_invalid(self):
        import pytest

        with pytest.raises(ValueError):
            parse_data_js("not valid content")


class TestParseFishInfo:
    """Tests for extracting fish names from the FISH_INFO array."""

    def test_parses_fish_info(self, sample_info_content: str):
        names = parse_fish_info_js(sample_info_content)
        assert names[4898] == "Merlthor Goby"
        assert names[4911] == "Pebble Crab"

    def test_raises_on_invalid(self):
        import pytest

        with pytest.raises(ValueError):
            parse_fish_info_js("not valid content")


class TestBuildFishData:
    """Tests for assembling FishData from parsed JS dictionaries."""

    def test_builds_fish_data(self, sample_js_content: str, sample_info_content: str):
        parsed = parse_data_js(sample_js_content)
        names = parse_fish_info_js(sample_info_content)
        data = build_fish_data(parsed, names)
        assert 4898 in data.fish
        assert 4911 in data.fish

    def test_fish_fields(self, sample_js_content: str, sample_info_content: str):
        parsed = parse_data_js(sample_js_content)
        names = parse_fish_info_js(sample_info_content)
        data = build_fish_data(parsed, names)
        fish = data.fish[4898]
        assert fish.name_en == "Merlthor Goby"
        assert fish.start_hour == 18
        assert fish.end_hour == 6
        assert fish.patch == 2
        assert fish.big_fish is False
        assert fish.has_intuition_or_predator is False
        assert fish.always_available is False

    def test_fish_name_from_info(self, sample_js_content: str, sample_info_content: str):
        parsed = parse_data_js(sample_js_content)
        names = parse_fish_info_js(sample_info_content)
        data = build_fish_data(parsed, names)
        assert data.fish[4898].name_en == "Merlthor Goby"
        assert data.fish[4911].name_en == "Pebble Crab"

    def test_fallback_name_when_no_info(self, sample_js_content: str):
        parsed = parse_data_js(sample_js_content)
        data = build_fish_data(parsed, {})
        assert data.fish[4898].name_en == "Fish #4898"

    def test_fishing_spots(self, sample_js_content: str):
        parsed = parse_data_js(sample_js_content)
        data = build_fish_data(parsed)
        spot = data.fishing_spots[52]
        assert spot.name_en == "Moraby Bay"
        assert spot.territory_id == 134

    def test_items(self, sample_js_content: str):
        parsed = parse_data_js(sample_js_content)
        data = build_fish_data(parsed)
        item = data.items[2596]
        assert item.name_en == "Spoon Worm"

    def test_weather_types(self, sample_js_content: str):
        parsed = parse_data_js(sample_js_content)
        data = build_fish_data(parsed)
        assert data.weather_types[1] == "Clear Skies"

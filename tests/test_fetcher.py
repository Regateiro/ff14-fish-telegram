"""Tests for the JS data parser and FishData builder."""

import pytest

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


class TestSerialization:
    """Tests for JSON serialization/deserialization roundtrip."""

    def test_fish_to_dict_roundtrip(self, sample_fish):
        from ff14_fish_telegram.data.fetcher import _fish_to_dict, _parse_fish

        d = _fish_to_dict(sample_fish)
        restored = _parse_fish(d)
        assert restored.id == sample_fish.id
        assert restored.name_en == sample_fish.name_en
        assert restored.start_hour == sample_fish.start_hour
        assert restored.end_hour == sample_fish.end_hour
        assert restored.predators == sample_fish.predators
        assert restored.intuition_length == sample_fish.intuition_length
        assert restored.aquarium == sample_fish.aquarium

    def test_fish_to_dict_no_name(self):
        from ff14_fish_telegram.data.fetcher import _fish_to_dict, _parse_fish
        from ff14_fish_telegram.data.models import Fish

        f = Fish(
            id=999, name_en="", start_hour=0, end_hour=24, patch=1,
            big_fish=False, collectable=None, weather_set=[], previous_weather_set=[],
            location_id=1, best_catch_path=[], predators=[], intuition_length=None,
            fish_eyes=None, folklore=None, snagging=None, lure=None, hookset=None,
            tug=None, gig=None, data_missing=None, aquarium=None,
        )
        d = _fish_to_dict(f)
        restored = _parse_fish(d)
        assert restored.id == 999
        assert restored.name_en == "Fish #999"

    def test_spot_to_dict_roundtrip(self, sample_js_content: str):
        from ff14_fish_telegram.data.fetcher import _parse_fishing_spot, _spot_to_dict

        parsed = parse_data_js(sample_js_content)
        raw = parsed["FISHING_SPOTS"]["52"]
        spot = _parse_fishing_spot(raw)
        d = _spot_to_dict(spot)
        assert d["_id"] == 52
        assert d["name_en"] == "Moraby Bay"
        assert d["territory_id"] == 134

    def test_item_to_dict_roundtrip(self, sample_js_content: str):
        from ff14_fish_telegram.data.fetcher import _item_to_dict, _parse_item

        parsed = parse_data_js(sample_js_content)
        raw = parsed["ITEMS"]["2596"]
        item = _parse_item(raw)
        d = _item_to_dict(item)
        restored = _parse_item(d)
        assert restored.id == 2596
        assert restored.name_en == "Spoon Worm"

    def test_to_json_serializable_with_weather_rates(self, fish_data_with_weather):
        from ff14_fish_telegram.data.fetcher import from_json_serializable, to_json_serializable

        d = to_json_serializable(fish_data_with_weather)
        assert "weather_rates" in d
        assert "134" in d["weather_rates"]
        restored = from_json_serializable(d)
        assert 134 in restored.weather_rates
        assert restored.weather_rates[134].weather_rates == [[3, 20], [1, 50], [2, 80], [4, 90], [7, 100]]

    def test_to_json_serializable_roundtrip(self, sample_fish_data):
        from ff14_fish_telegram.data.fetcher import from_json_serializable, to_json_serializable

        d = to_json_serializable(sample_fish_data)
        assert "_fetched_at" in d
        restored = from_json_serializable(d)
        assert 4898 in restored.fish
        assert 52 in restored.fishing_spots
        assert 2596 in restored.items
        assert restored.fish[4898].name_en == "Merlthor Goby"
        assert restored.zones == sample_fish_data.zones

    def test_to_json_serializable_empty(self):
        from ff14_fish_telegram.data.fetcher import from_json_serializable, to_json_serializable
        from ff14_fish_telegram.data.models import FishData

        empty = FishData(
            fish={}, fishing_spots={}, items={}, weather_rates={},
            weather_types={}, regions={}, zones={},
        )
        d = to_json_serializable(empty)
        restored = from_json_serializable(d)
        assert restored.fish == {}
        assert restored.fishing_spots == {}

    def test_fallback_name_when_no_info_and_no_inline_name(self, sample_js_content: str):
        parsed = parse_data_js(sample_js_content)
        parsed["FISH"]["4898"].pop("name_en", None)
        data = build_fish_data(parsed, {})
        assert data.fish[4898].name_en == "Fish #4898"


class TestFetchRawData:
    """Tests for fetch_raw_data (requires mocking aiohttp)."""

    @pytest.mark.asyncio
    async def test_fetch_success(self, mocker):
        mock_resp = mocker.MagicMock()
        mock_resp.__aenter__.return_value = mock_resp
        mock_resp.text = mocker.AsyncMock(return_value="const DATA = {};")
        mock_session = mocker.MagicMock()
        mock_session.__aenter__.return_value = mock_session
        mock_session.get.return_value = mock_resp

        mocker.patch("aiohttp.ClientSession", return_value=mock_session)

        from ff14_fish_telegram.data.fetcher import fetch_raw_data

        result = await fetch_raw_data("http://example.com/test.js")
        assert result == "const DATA = {};"

    @pytest.mark.asyncio
    async def test_fetch_http_error(self, mocker):
        mock_resp = mocker.MagicMock()
        mock_resp.__aenter__.return_value = mock_resp
        mock_resp.raise_for_status.side_effect = Exception("HTTP 404")
        mock_session = mocker.MagicMock()
        mock_session.__aenter__.return_value = mock_session
        mock_session.get.return_value = mock_resp

        mocker.patch("aiohttp.ClientSession", return_value=mock_session)

        from ff14_fish_telegram.data.fetcher import fetch_raw_data

        with pytest.raises(Exception, match="HTTP 404"):
            await fetch_raw_data("http://example.com/test.js")


class TestLoadFishData:
    """Tests for load_fish_data (requires mocking fetch_raw_data)."""

    @pytest.mark.asyncio
    async def test_load_with_names(self, mocker, sample_js_content, sample_info_content):
        mocker.patch(
            "ff14_fish_telegram.data.fetcher.fetch_raw_data",
            side_effect=[sample_js_content, sample_info_content],
        )

        from ff14_fish_telegram.data.fetcher import load_fish_data

        data = await load_fish_data(data_url="http://example.com/data.js")
        assert 4898 in data.fish
        assert data.fish[4898].name_en == "Merlthor Goby"

    @pytest.mark.asyncio
    async def test_load_fails_gracefully_on_info_fetch_error(self, mocker, sample_js_content):
        mocker.patch(
            "ff14_fish_telegram.data.fetcher.fetch_raw_data",
            side_effect=[sample_js_content, Exception("Network error")],
        )

        from ff14_fish_telegram.data.fetcher import load_fish_data

        data = await load_fish_data(data_url="http://example.com/data.js")
        assert 4898 in data.fish
        assert data.fish[4898].name_en == "Fish #4898"

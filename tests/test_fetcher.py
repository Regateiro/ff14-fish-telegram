"""Tests for the JS data parser and FishData builder."""

import pytest

from ff14_fish_telegram.data.fetcher import (
    apply_adjustments,
    build_fish_data,
    fetch_adjustments,
    parse_data_js,
    parse_fish_info_js,
)
from ff14_fish_telegram.data.models import Item


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
        mocker.patch("ff14_fish_telegram.data.fetcher._save_cache")

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
        mocker.patch("ff14_fish_telegram.data.fetcher._save_cache")

        from ff14_fish_telegram.data.fetcher import load_fish_data

        data = await load_fish_data(data_url="http://example.com/data.js")
        assert 4898 in data.fish
        assert data.fish[4898].name_en == "Fish #4898"

    @pytest.mark.asyncio
    async def test_cache_saved_on_success(self, mocker, sample_js_content, sample_info_content):
        mocker.patch(
            "ff14_fish_telegram.data.fetcher.fetch_raw_data",
            side_effect=[sample_js_content, sample_info_content],
        )
        mock_save = mocker.patch("ff14_fish_telegram.data.fetcher._save_cache")

        from ff14_fish_telegram.data.fetcher import load_fish_data

        await load_fish_data(data_url="http://example.com/data.js")
        mock_save.assert_called_once_with(sample_js_content)

    @pytest.mark.asyncio
    async def test_fallback_to_cache_when_remote_fails(
        self, mocker, sample_js_content, sample_info_content,
    ):
        mocker.patch(
            "ff14_fish_telegram.data.fetcher._load_cache",
            return_value=sample_js_content,
        )
        # First fetch_raw_data call (data_url) raises; second (info_url) succeeds.
        mocker.patch(
            "ff14_fish_telegram.data.fetcher.fetch_raw_data",
            side_effect=[Exception("Network error"), sample_info_content],
        )

        from ff14_fish_telegram.data.fetcher import load_fish_data

        data = await load_fish_data(data_url="http://example.com/data.js")
        assert 4898 in data.fish
        assert data.fish[4898].name_en == "Merlthor Goby"

    @pytest.mark.asyncio
    async def test_raises_when_both_remote_and_cache_fail(self, mocker):
        mocker.patch(
            "ff14_fish_telegram.data.fetcher.fetch_raw_data",
            side_effect=Exception("Network error"),
        )
        mocker.patch(
            "ff14_fish_telegram.data.fetcher._load_cache",
            side_effect=FileNotFoundError("No cache"),
        )

        from ff14_fish_telegram.data.fetcher import load_fish_data

        with pytest.raises(RuntimeError, match="no usable cache"):
            await load_fish_data(data_url="http://example.com/data.js")


class TestFetchAdjustments:
    """Tests for fetching the adjustments YAML."""

    @pytest.mark.asyncio
    async def test_fetch_success(self, mocker):
        yaml_content = "- name: Test Fish\n  startHour: 10\n  endHour: 14\n"
        mock_resp = mocker.MagicMock()
        mock_resp.__aenter__.return_value = mock_resp
        mock_resp.text = mocker.AsyncMock(return_value=yaml_content)
        mock_resp.raise_for_status = mocker.MagicMock()
        mock_session = mocker.MagicMock()
        mock_session.__aenter__.return_value = mock_session
        mock_session.get.return_value = mock_resp

        mocker.patch("aiohttp.ClientSession", return_value=mock_session)

        result = await fetch_adjustments("http://example.com/adjustments.yaml")
        assert len(result) == 1
        assert result[0]["name"] == "Test Fish"
        assert result[0]["startHour"] == 10

    @pytest.mark.asyncio
    async def test_fetch_returns_empty_on_error(self, mocker):
        mock_resp = mocker.MagicMock()
        mock_resp.__aenter__.return_value = mock_resp
        mock_resp.raise_for_status.side_effect = Exception("HTTP 404")
        mock_session = mocker.MagicMock()
        mock_session.__aenter__.return_value = mock_session
        mock_session.get.return_value = mock_resp

        mocker.patch("aiohttp.ClientSession", return_value=mock_session)

        result = await fetch_adjustments("http://example.com/adjustments.yaml")
        assert result == []


class TestApplyAdjustments:
    """Tests for applying manual adjustments to fish data."""

    def test_apply_time_override(self, sample_fish_data):
        adjustments = [{"name": "Merlthor Goby", "startHour": 10, "endHour": 14}]
        patched = apply_adjustments(sample_fish_data, adjustments)
        assert patched == 1
        fish = sample_fish_data.fish[4898]
        assert fish.start_hour == 10
        assert fish.end_hour == 14

    def test_apply_weather_override(self, sample_fish_data):
        sample_fish_data.weather_types[5] = "Wind"
        adjustments = [{"name": "Merlthor Goby", "weatherSet": ["Wind"]}]
        patched = apply_adjustments(sample_fish_data, adjustments)
        assert patched == 1
        fish = sample_fish_data.fish[4898]
        assert fish.weather_set == [5]

    def test_apply_previous_weather_override(self, sample_fish_data):
        sample_fish_data.weather_types[3] = "Fog"
        adjustments = [{"name": "Merlthor Goby", "previousWeatherSet": ["Fog"]}]
        patched = apply_adjustments(sample_fish_data, adjustments)
        assert patched == 1
        fish = sample_fish_data.fish[4898]
        assert fish.previous_weather_set == [3]

    def test_apply_bait_override(self, sample_fish_data):
        sample_fish_data.items[2600] = Item(id=2600, name_en="Red Maggots")
        adjustments = [{"name": "Merlthor Goby", "bait": ["Red Maggots"]}]
        patched = apply_adjustments(sample_fish_data, adjustments)
        assert patched == 1
        fish = sample_fish_data.fish[4898]
        assert fish.best_catch_path == [2600]

    def test_apply_hookset_override(self, sample_fish_data):
        adjustments = [{"name": "Merlthor Goby", "hookset": "Powerful"}]
        patched = apply_adjustments(sample_fish_data, adjustments)
        assert patched == 1
        fish = sample_fish_data.fish[4898]
        assert fish.hookset == "Powerful"

    def test_apply_lure_override(self, sample_fish_data):
        adjustments = [{"name": "Merlthor Goby", "lure": "Modest"}]
        patched = apply_adjustments(sample_fish_data, adjustments)
        assert patched == 1
        fish = sample_fish_data.fish[4898]
        assert fish.lure == "Modest"

    def test_clears_data_missing_when_conditions_added(self, sample_fish_data):
        sample_fish_data.fish[4898].data_missing = {
            "timeRestricted": True,
            "weatherRestricted": True,
        }
        adjustments = [{"name": "Merlthor Goby", "startHour": 10, "endHour": 14}]
        patched = apply_adjustments(sample_fish_data, adjustments)
        assert patched == 1
        fish = sample_fish_data.fish[4898]
        assert fish.data_missing is None
        assert fish.restrictions_unknown is False

    def test_skips_unknown_fish(self, sample_fish_data):
        adjustments = [{"name": "Nonexistent Fish", "startHour": 10}]
        patched = apply_adjustments(sample_fish_data, adjustments)
        assert patched == 0

    def test_skips_missing_name(self, sample_fish_data):
        adjustments = [{"startHour": 10}]
        patched = apply_adjustments(sample_fish_data, adjustments)
        assert patched == 0

    def test_returns_zero_for_empty_adjustments(self, sample_fish_data):
        patched = apply_adjustments(sample_fish_data, [])
        assert patched == 0

    def test_ignores_unknown_weather_names(self, sample_fish_data):
        adjustments = [{"name": "Merlthor Goby", "weatherSet": ["Unknown Weather"]}]
        patched = apply_adjustments(sample_fish_data, adjustments)
        assert patched == 1
        fish = sample_fish_data.fish[4898]
        assert fish.weather_set == []

    def test_ignores_unknown_bait_names(self, sample_fish_data):
        adjustments = [{"name": "Merlthor Goby", "bait": ["Unknown Bait"]}]
        patched = apply_adjustments(sample_fish_data, adjustments)
        assert patched == 1
        fish = sample_fish_data.fish[4898]
        assert fish.best_catch_path == []

"""pytest fixtures shared across all test modules."""

from pathlib import Path

import pytest

from ff14_fish_telegram.data.models import Fish, FishData, FishingSpot, Item, WeatherRate

SAMPLE_DATA_JS = Path(__file__).parent / "sample_data.js"
SAMPLE_INFO_JS = Path(__file__).parent / "sample_fish_info.js"


@pytest.fixture
def sample_js_content() -> str:
    """Return the content of sample_data.js for testing parser."""
    return SAMPLE_DATA_JS.read_text()


@pytest.fixture
def sample_info_content() -> str:
    """Return the content of sample_fish_info.js for testing parser."""
    return SAMPLE_INFO_JS.read_text()


@pytest.fixture
def sample_fish() -> Fish:
    """A fish with an overnight time restriction (18:00-06:00) and no weather requirements."""
    return Fish(
        id=4898,
        name_en="Merlthor Goby",
        start_hour=18,
        end_hour=6,
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
        aquarium={"water": "Saltwater", "size": 2},
    )


@pytest.fixture
def time_restricted_fish() -> Fish:
    """A fish with a non-overnight time restriction (17:00-22:00)."""
    return Fish(
        id=4911,
        name_en="Pebble Crab",
        start_hour=17,
        end_hour=22,
        patch=2.0,
        big_fish=False,
        collectable=None,
        weather_set=[],
        previous_weather_set=[],
        location_id=71,
        best_catch_path=[2606],
        predators=[],
        intuition_length=None,
        fish_eyes=True,
        folklore=None,
        snagging=None,
        lure=None,
        hookset="Powerful",
        tug="medium",
        gig=None,
        data_missing=None,
        aquarium=None,
    )


@pytest.fixture
def fish_with_intuition() -> Fish:
    """A fish requiring both predators (mooch) and intuition, with no time restrictions."""
    return Fish(
        id=5000,
        name_en="Intuition Fish",
        start_hour=0,
        end_hour=24,
        patch=2.0,
        big_fish=True,
        collectable=None,
        weather_set=[],
        previous_weather_set=[],
        location_id=52,
        best_catch_path=[2596],
        predators=[4898],
        intuition_length=120,
        fish_eyes=True,
        folklore=None,
        snagging=None,
        lure=None,
        hookset="Powerful",
        tug="medium",
        gig=None,
        data_missing=None,
        aquarium=None,
    )


@pytest.fixture
def sample_fish_data() -> FishData:
    """A minimal FishData with one always-available fish, one spot, and one item."""
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
        items={
            2596: Item(id=2596, name_en="Spoon Worm"),
        },
        weather_rates={},
        weather_types={1: "Clear Skies", 2: "Fair Skies"},
        regions={22: "La Noscea"},
    zones={31: "Lower La Noscea"},
)


@pytest.fixture
def fish_data_with_weather() -> FishData:
    """A FishData with weather rates, used for testing weather-dependent window computation."""
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
                weather_set=[1],
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
        items={
            2596: Item(id=2596, name_en="Spoon Worm"),
        },
        weather_rates={
            134: WeatherRate(
                map_id=11,
                zone_id=31,
                region_id=22,
                weather_rates=[[3, 20], [1, 50], [2, 80], [4, 90], [7, 100]],
            ),
        },
        weather_types={1: "Clear Skies", 2: "Fair Skies", 3: "Clouds"},
        regions={22: "La Noscea"},
        zones={31: "Lower La Noscea"},
    )


@pytest.fixture
def fish_with_previous_weather() -> Fish:
    """A fish requiring specific previous weather condition."""
    return Fish(
        id=5001,
        name_en="Prev Weather Fish",
        start_hour=0,
        end_hour=24,
        patch=2.0,
        big_fish=False,
        collectable=None,
        weather_set=[1],
        previous_weather_set=[2],
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

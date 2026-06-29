from pathlib import Path

import pytest

from ff14_fish_telegram.data.models import Fish, FishData, FishingSpot, Item

SAMPLE_DATA_JS = Path(__file__).parent / "sample_data.js"
SAMPLE_INFO_JS = Path(__file__).parent / "sample_fish_info.js"


@pytest.fixture
def sample_js_content() -> str:
    return SAMPLE_DATA_JS.read_text()


@pytest.fixture
def sample_info_content() -> str:
    return SAMPLE_INFO_JS.read_text()


@pytest.fixture
def sample_fish() -> Fish:
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

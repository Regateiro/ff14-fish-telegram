from dataclasses import dataclass
from typing import Any


@dataclass
class Fish:
    id: int
    name_en: str
    start_hour: float
    end_hour: float
    patch: float
    big_fish: bool
    collectable: bool | None
    weather_set: list[int]
    previous_weather_set: list[int]
    location_id: int
    best_catch_path: list[int]
    predators: list[int]
    intuition_length: int | None
    fish_eyes: bool | None
    folklore: int | None
    snagging: str | None
    lure: str | None
    hookset: str | None
    tug: str | None
    gig: str | None
    data_missing: Any | None
    aquarium: dict | None

    @property
    def has_intuition_or_predator(self) -> bool:
        return bool(self.predators) or self.intuition_length is not None

    @property
    def always_available(self) -> bool:
        return (
            self.start_hour == 0
            and self.end_hour == 24
            and not self.weather_set
            and not self.previous_weather_set
        )


@dataclass
class FishingSpot:
    id: int
    name_en: str
    territory_id: int
    placename_id: int
    zone_id: int | None
    region_id: int | None


@dataclass
class Item:
    id: int
    name_en: str


@dataclass
class WeatherRate:
    map_id: int
    zone_id: int
    region_id: int
    weather_rates: list[list[int]]


@dataclass
class FishData:
    fish: dict[int, Fish]
    fishing_spots: dict[int, FishingSpot]
    items: dict[int, Item]
    weather_rates: dict[int, WeatherRate]
    weather_types: dict[int, str]
    regions: dict[int, str]
    zones: dict[int, str]

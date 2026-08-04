"""Data models representing FFXIV fish, fishing spots, weather, and related data.

These pure @dataclass types are the shared vocabulary across all layers:
  - data/fetcher.py   builds these from raw JS
  - data/availability.py   reads them to compute catchable windows
  - bot/handlers.py   reads them to format Telegram replies
  - bot/reminders.py   reads them to build reminder messages

No business logic lives here — only type definitions and computed properties.
"""

from dataclasses import dataclass
from typing import Any


@dataclass
class Fish:
    """A fish species in FFXIV with its catch conditions.

    This is the central domain object. Every feature (reminders, /day,
    /caught) ultimately revolves around Fish instances stored in FishData.

    Attributes:
        id: Unique fish identifier.
        name_en: English name.
        start_hour: Earliest Eorzea hour (0-24) this fish can be caught.
        end_hour: Latest Eorzea hour (0-24) this fish can be caught.
        patch: Game patch the fish was introduced in.
        big_fish: Whether this is a "big fish" (legendary).
        collectable: Whether this fish can be collected for turn-ins.
        weather_set: Required weather type IDs for this fish to appear.
        previous_weather_set: Required weather type IDs in the preceding weather period.
        location_id: ID of the fishing spot where this fish is caught.
        best_catch_path: Recommended mooching chain IDs.
        predators: IDs of predator fish used to mooch this fish.
        intuition_length: Seconds of intuition buff needed to catch (if any).
        fish_eyes: Whether the Fish Eyes ability is needed.
        folklore: ID of the folklore tome required.
        snagging: Snagging type required ("None", "Snagging", etc.).
        lure: Lure type required.
        hookset: Hookset type required ("Precision", "Powerful", etc.).
        tug: Tug strength indicator ("Light", "Medium", "Heavy").
        gig: Spearfishing gig type if applicable.
        data_missing: Placeholder for incomplete data fields.
        aquarium: Aquarium display slot metadata if applicable.
    """

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
        """Whether catching this fish requires mooching or an intuition buff.

        Used by bot/reminders.py to determine lead time: complex fish
        get 30 min notice so the user can prepare bait/mooch chains.
        """
        return bool(self.predators) or self.intuition_length is not None

    @property
    def restrictions_unknown(self) -> bool:
        """Whether this fish's time/weather restrictions are not yet documented.

        The tracker repo marks newly added legendary fish with a
        dataMissing dict (e.g. {"timeRestricted": True,
        "weatherRestricted": True}) while their exact catch windows are
        still being researched. Their start/end hours and weather sets
        are empty placeholders, so they must not be treated as always
        available or scheduled for windows.

        Used by:
          - data/availability.py to short-circuit window computation
          - bot/handlers.py's /day command to flag undetermined fish
        """
        missing = self.data_missing
        if not isinstance(missing, dict):
            return False
        return bool(missing.get("timeRestricted") or missing.get("weatherRestricted"))

    @property
    def always_available(self) -> bool:
        """Whether this fish has no time or weather restrictions.

        A fish whose restrictions are still being researched
        (restrictions_unknown) is never treated as always available.

        Used by:
          - data/availability.py to short-circuit window computation
          - bot/reminders.py to skip reminders (always-available fish
            don't need proactive alerts)
        """
        return (
            self.start_hour == 0
            and self.end_hour == 24
            and not self.weather_set
            and not self.previous_weather_set
            and not self.restrictions_unknown
        )


@dataclass
class FishingSpot:
    """A named fishing location in FFXIV.

    Connects a Fish (via location_id) to a territory, which in turn
    links to WeatherRate data in availability.py.

    Attributes:
        id: Unique spot identifier.
        name_en: English name of the spot.
        territory_id: ID of the territory this spot belongs to.
        placename_id: ID of the placename (sub-location).
        zone_id: ID of the zone this spot belongs to (optional).
        region_id: ID of the region (optional).
    """

    id: int
    name_en: str
    territory_id: int
    placename_id: int
    zone_id: int | None
    region_id: int | None


@dataclass
class Item:
    """An in-game item, typically used for bait or mooching.

    Attributes:
        id: Unique item identifier.
        name_en: English name.
    """

    id: int
    name_en: str


@dataclass
class WeatherRate:
    """Weather rate table for a territory, used to compute weather probabilities.

    availability.py uses this to determine which weather is active at a
    given time via the FFXIV XOR-shift forecast algorithm.

    Attributes:
        map_id: ID of the map this rate belongs to.
        zone_id: ID of the zone.
        region_id: ID of the region.
        weather_rates: List of [weather_type_id, cumulative_rate] pairs
            defining weather chances (cumulative 0-99).
    """

    map_id: int
    zone_id: int
    region_id: int
    weather_rates: list[list[int]]


@dataclass
class FishData:
    """Top-level container holding all parsed FFXIV fish data.

    This is the single object passed around by the application:
      - Built by data/fetcher.py after parsing remote JS files
      - Stored in bot_data["fish_data"] by __main__.py
      - Retrieved by bot/handlers.py and bot/reminders.py for lookups
      - Used by data/availability.py for weather and location queries

    Attributes:
        fish: Map of fish ID to Fish.
        fishing_spots: Map of spot ID to FishingSpot.
        items: Map of item ID to Item.
        weather_rates: Map of territory ID to WeatherRate.
        weather_types: Map of weather type ID to English name.
        regions: Map of region ID to English name.
        zones: Map of zone ID to English name.
    """

    fish: dict[int, Fish]
    fishing_spots: dict[int, FishingSpot]
    items: dict[int, Item]
    weather_rates: dict[int, WeatherRate]
    weather_types: dict[int, str]
    regions: dict[int, str]
    zones: dict[int, str]

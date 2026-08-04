"""Fetch, parse, and deserialize FFXIV fish data from the ff14-fish-tracker-app repository.

This module is the data ingestion layer. It:
  1. Downloads JavaScript data files from the tracker repo via HTTP (aiohttp)
  2. Parses lenient JS objects into Python dicts (demjson3)
  3. Converts each raw dict into the typed dataclasses from models.py
  4. Assembles everything into a single FishData container

The main entry point, load_fish_data(), is called by __main__.py on
startup and on a recurring schedule (every FETCH_INTERVAL_HOURS).
"""

import logging
import re
import time

import aiohttp
import demjson3
import yaml

from ff14_fish_telegram.config import ADJUSTMENTS_URL, DATA_CACHE_PATH, DATA_URL
from ff14_fish_telegram.data.models import (
    Fish,
    FishData,
    FishingSpot,
    Item,
    WeatherRate,
)

logger = logging.getLogger(__name__)

# Derive the fish-info URL by replacing data.js with fish_info_data.js
# in the base URL. This secondary file provides English name overrides.
FISH_INFO_URL = DATA_URL.replace("data.js", "fish_info_data.js")


def _cache_bust(url: str) -> str:
    separator = "&" if "?" in url else "?"
    return f"{url}{separator}_={int(time.time())}"


async def fetch_raw_data(url: str = DATA_URL) -> str:
    """Fetch the raw JavaScript content from the given URL with a 30-second timeout.

    Uses aiohttp for async HTTP, compatible with the telegram.ext async
    framework and APScheduler's async scheduler.
    """
    async with aiohttp.ClientSession() as session:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
            resp.raise_for_status()
            return await resp.text()


def _js_to_dict(content: str) -> dict:
    """Decode lenient JavaScript object syntax into a Python dict via demjson3.

    The tracker repo uses raw JS object/array syntax (not strict JSON),
    so standard json.loads() would fail. demjson3 handles trailing commas,
    single quotes, unquoted keys, etc.
    """
    return demjson3.decode(content, strict=False)


def parse_data_js(content: str) -> dict:
    """Extract and parse the `const DATA = ...` JS object from the main data file.

    The regex isolates the large JS object literal after 'const DATA ='
    before demjson3 parses it. Raises ValueError if the pattern is not found.
    """
    match = re.search(r"const DATA\s*=\s*(\{.+\});?\s*$", content, re.DOTALL)
    if not match:
        raise ValueError("Could not find DATA constant in JS file")
    return _js_to_dict(match.group(1))


def parse_fish_info_js(content: str) -> dict[int, str]:
    """Extract and parse FISH_INFO array, returning a map of fish ID to English name.

    The fish_info_data.js file contains richer name data that may differ
    from the names embedded in the main DATA object. These names are merged
    as overrides in build_fish_data().
    """
    match = re.search(r"const FISH_INFO\s*=\s*(\[.+?\]);?\s*$", content, re.DOTALL)
    if not match:
        raise ValueError("Could not find FISH_INFO constant in JS file")
    info_list = _js_to_dict(match.group(1))
    return {entry["id"]: entry.get("name_en", "") for entry in info_list}


async def fetch_adjustments(url: str = ADJUSTMENTS_URL) -> list[dict]:
    """Fetch the adjustments YAML from the gh-pages branch.

    The tracker repo maintains a Jekyll data file (_data/adjustments.yaml)
    that contains manual overrides for newly added fish whose conditions
    are not yet in the main data.js. The site renders this into inline JS
    at build time; the bot fetches it directly to apply the same overrides.

    Returns an empty list if the fetch fails (non-fatal).
    """
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                resp.raise_for_status()
                text = await resp.text()
                data = yaml.safe_load(text)
                return data if isinstance(data, list) else []
    except Exception as e:
        logger.warning("Failed to fetch adjustments from %s: %s", url, e)
        return []


def apply_adjustments(fish_data: FishData, adjustments: list[dict]) -> int:
    """Apply manual adjustments to fish data, returning the number of fish patched.

    The adjustments YAML uses weather/bait names; this function converts them
    to IDs using fish_data.weather_types and fish_data.items. Fish are matched
    by name_en.

    Adjustments override: start_hour, end_hour, weather_set, previous_weather_set,
    hookset, lure, tug, snagging, best_catch_path. The data_missing flag is
    cleared when conditions are patched.
    """
    if not adjustments:
        return 0

    weather_name_to_id = {name: wid for wid, name in fish_data.weather_types.items()}
    item_name_to_id = {item.name_en: item.id for item in fish_data.items.values()}
    fish_by_name = {fish.name_en: fish for fish in fish_data.fish.values()}

    patched = 0
    for adj in adjustments:
        name = adj.get("name")
        if not name or name not in fish_by_name:
            continue
        fish = fish_by_name[name]

        if "startHour" in adj:
            fish.start_hour = float(adj["startHour"])
        if "endHour" in adj:
            fish.end_hour = float(adj["endHour"])
        if "weatherSet" in adj:
            weather_ids = []
            for wname in adj["weatherSet"]:
                if wname in weather_name_to_id:
                    weather_ids.append(weather_name_to_id[wname])
            fish.weather_set = weather_ids
        if "previousWeatherSet" in adj:
            weather_ids = []
            for wname in adj["previousWeatherSet"]:
                if wname in weather_name_to_id:
                    weather_ids.append(weather_name_to_id[wname])
            fish.previous_weather_set = weather_ids
        if "hookset" in adj:
            fish.hookset = adj["hookset"]
        if "lure" in adj:
            fish.lure = adj["lure"]
        if "tug" in adj:
            fish.tug = adj["tug"]
        if "snagging" in adj:
            fish.snagging = adj["snagging"]
        if "bait" in adj:
            item_ids = []
            for bname in adj["bait"]:
                if bname in item_name_to_id:
                    item_ids.append(item_name_to_id[bname])
            fish.best_catch_path = item_ids

        has_conditions = (
            fish.weather_set
            or fish.previous_weather_set
            or fish.start_hour != 0
            or fish.end_hour != 24
        )
        if has_conditions:
            fish.data_missing = None

        patched += 1

    return patched


# ── Raw → dataclass converters ──────────────────────────────────────
# Each converter maps the JS naming convention (camelCase) to the
# Python dataclass field names (snake_case).


def _parse_fish(raw: dict, name_en: str = "") -> Fish:
    """Convert a raw dict from the JS data into a Fish dataclass instance.

    Falls back to the JS-provided name_en, then to a placeholder
    "Fish #<id>" if both the override and inline name are missing.
    """
    return Fish(
        id=raw["_id"],
        name_en=name_en or raw.get("name_en", "") or f"Fish #{raw['_id']}",
        start_hour=float(raw["startHour"]),
        end_hour=float(raw["endHour"]),
        patch=float(raw.get("patch", 0)),
        big_fish=raw.get("bigFish", False),
        collectable=raw.get("collectable"),
        weather_set=raw.get("weatherSet", []),
        previous_weather_set=raw.get("previousWeatherSet", []),
        location_id=raw["location"],
        best_catch_path=raw.get("bestCatchPath", []),
        predators=raw.get("predators", []),
        intuition_length=raw.get("intuitionLength"),
        fish_eyes=raw.get("fishEyes"),
        folklore=raw.get("folklore"),
        snagging=raw.get("snagging"),
        lure=raw.get("lure"),
        hookset=raw.get("hookset"),
        tug=raw.get("tug"),
        gig=raw.get("gig"),
        data_missing=raw.get("dataMissing"),
        aquarium=raw.get("aquarium"),
    )


def _parse_fishing_spot(raw: dict) -> FishingSpot:
    """Convert a raw dict into a FishingSpot dataclass instance."""
    return FishingSpot(
        id=raw["_id"],
        name_en=raw.get("name_en", ""),
        territory_id=raw["territory_id"],
        placename_id=raw["placename_id"],
        zone_id=raw.get("zone_id"),
        region_id=raw.get("region_id"),
    )


def _parse_item(raw: dict) -> Item:
    """Convert a raw dict into an Item dataclass instance."""
    return Item(
        id=raw["_id"],
        name_en=raw.get("name_en", ""),
    )


def _parse_weather_rate(raw: dict) -> WeatherRate:
    """Convert a raw dict into a WeatherRate dataclass instance."""
    return WeatherRate(
        map_id=raw["map_id"],
        zone_id=raw["zone_id"],
        region_id=raw["region_id"],
        weather_rates=raw["weather_rates"],
    )


def build_fish_data(parsed: dict, fish_names: dict[int, str] | None = None) -> FishData:
    """Construct a FishData container from the parsed DATA dict and optional fish name overrides.

    This is the assembly step: raw parser output → typed domain model.
    Fishing spots missing required keys (territory_id, placename_id) are
    silently skipped since they are unusable for weather lookups.
    """
    fish_names = fish_names or {}
    fish = {}
    for k, v in parsed["FISH"].items():
        fid = int(k)
        fish[fid] = _parse_fish(v, fish_names.get(fid, ""))

    from_raw = parsed.get("FISHING_SPOTS", {})
    supply_keys = ("territory_id", "placename_id")
    fishing_spots = {}
    for k, v in from_raw.items():
        if all(key in v for key in supply_keys):
            fishing_spots[int(k)] = _parse_fishing_spot(v)

    items = {int(k): _parse_item(v) for k, v in parsed.get("ITEMS", {}).items()}
    weather_rates = {
        int(k): _parse_weather_rate(v) for k, v in parsed.get("WEATHER_RATES", {}).items()
    }
    weather_types = {
        int(k): v.get("name_en", "") for k, v in parsed.get("WEATHER_TYPES", {}).items()
    }
    regions = {int(k): v.get("name_en", "") for k, v in parsed.get("REGIONS", {}).items()}
    zones = {int(k): v.get("name_en", "") for k, v in parsed.get("ZONES", {}).items()}

    return FishData(
        fish=fish,
        fishing_spots=fishing_spots,
        items=items,
        weather_rates=weather_rates,
        weather_types=weather_types,
        regions=regions,
        zones=zones,
    )


def _save_cache(raw_js: str) -> None:
    """Save raw JS content to the local cache file for offline fallback."""
    try:
        DATA_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        DATA_CACHE_PATH.write_text(raw_js, encoding="utf-8")
    except Exception as e:
        logger.warning("Failed to cache fish data: %s", e)


def _load_cache() -> str:
    """Load raw JS content from the local cache file.

    Raises FileNotFoundError if the cache does not exist.
    """
    return DATA_CACHE_PATH.read_text(encoding="utf-8")


async def load_fish_data(
    data_url: str = DATA_URL,
    info_url: str | None = None,
) -> FishData:
    """Fetch, parse, and build a FishData object from the tracker repo's JS files.

    This is the main entry point, called by __main__.py:
      1. Fetch main data.js → parse_data_js
      2. Fetch fish_info_data.js → parse_fish_info_js (non-fatal if fails)
      3. Merge both into a FishData via build_fish_data

    On fetch success the raw JS is saved to a local cache (DATA_CACHE_PATH).
    If the remote source is unavailable, the cache is used as a fallback.
    A RuntimeError is raised when both remote and cache are unavailable.

    Fish names from the fish_info_data.js file are merged in as an enrichment
    pass; failure to fetch names is non-fatal (fish will use their inline name).
    """
    info_url = info_url or FISH_INFO_URL

    raw_js: str | None = None
    try:
        raw_js = await fetch_raw_data(_cache_bust(data_url))
        _save_cache(raw_js)
    except Exception as e:
        logger.warning("Failed to fetch data from %s: %s", data_url, e)
        try:
            raw_js = _load_cache()
            logger.info("Loaded fish data from local cache: %s", DATA_CACHE_PATH)
        except Exception as cache_e:
            raise RuntimeError(
                f"Failed to fetch remote data and no usable cache at {DATA_CACHE_PATH}"
            ) from cache_e

    parsed = parse_data_js(raw_js)
    fish_names: dict[int, str] = {}
    try:
        raw_info = await fetch_raw_data(_cache_bust(info_url))
        fish_names = parse_fish_info_js(raw_info)
    except Exception as e:
        logger.warning("Failed to fetch fish names from %s: %s", info_url, e)

    fish_data = build_fish_data(parsed, fish_names)

    adjustments = await fetch_adjustments()
    if adjustments:
        patched = apply_adjustments(fish_data, adjustments)
        logger.info("Applied %d fish adjustments from %s", patched, ADJUSTMENTS_URL)

    return fish_data



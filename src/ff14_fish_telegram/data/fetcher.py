import re
from datetime import datetime, timezone

import aiohttp
import demjson3

from ff14_fish_telegram.config import DATA_CACHE_PATH, DATA_URL
from ff14_fish_telegram.data.models import (
    Fish,
    FishData,
    FishingSpot,
    Item,
    WeatherRate,
)

FISH_INFO_URL = DATA_URL.replace("data.js", "fish_info_data.js")


async def fetch_raw_data(url: str = DATA_URL) -> str:
    async with aiohttp.ClientSession() as session:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
            resp.raise_for_status()
            return await resp.text()


def _js_to_dict(content: str) -> dict:
    return demjson3.decode(content, strict=False)


def parse_data_js(content: str) -> dict:
    match = re.search(r"const DATA\s*=\s*(\{.+\});?\s*$", content, re.DOTALL)
    if not match:
        raise ValueError("Could not find DATA constant in JS file")
    return _js_to_dict(match.group(1))


def parse_fish_info_js(content: str) -> dict[int, str]:
    match = re.search(r"const FISH_INFO\s*=\s*(\[.+?\]);?\s*$", content, re.DOTALL)
    if not match:
        raise ValueError("Could not find FISH_INFO constant in JS file")
    info_list = _js_to_dict(match.group(1))
    return {entry["id"]: entry.get("name_en", "") for entry in info_list}


def _parse_fish(raw: dict, name_en: str = "") -> Fish:
    return Fish(
        id=raw["_id"],
        name_en=name_en or raw.get("name_en", ""),
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
    return FishingSpot(
        id=raw["_id"],
        name_en=raw.get("name_en", ""),
        territory_id=raw["territory_id"],
        placename_id=raw["placename_id"],
        zone_id=raw.get("zone_id"),
        region_id=raw.get("region_id"),
    )


def _parse_item(raw: dict) -> Item:
    return Item(
        id=raw["_id"],
        name_en=raw.get("name_en", ""),
    )


def _parse_weather_rate(k: str, raw: dict) -> WeatherRate:
    return WeatherRate(
        map_id=raw["map_id"],
        zone_id=raw["zone_id"],
        region_id=raw["region_id"],
        weather_rates=raw["weather_rates"],
    )


def build_fish_data(parsed: dict, fish_names: dict[int, str] | None = None) -> FishData:
    fish_names = fish_names or {}
    fish = {int(k): _parse_fish(v, fish_names.get(int(k), "")) for k, v in parsed["FISH"].items()}

    from_raw = parsed.get("FISHING_SPOTS", {})
    supply_keys = ("territory_id", "placename_id")
    fishing_spots = {}
    for k, v in from_raw.items():
        if all(key in v for key in supply_keys):
            fishing_spots[int(k)] = _parse_fishing_spot(v)

    items = {int(k): _parse_item(v) for k, v in parsed.get("ITEMS", {}).items()}
    weather_rates = {
        int(k): _parse_weather_rate(k, v) for k, v in parsed.get("WEATHER_RATES", {}).items()
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


async def load_fish_data(
    data_url: str = DATA_URL,
    info_url: str | None = None,
) -> FishData:
    info_url = info_url or FISH_INFO_URL
    raw_js = await fetch_raw_data(data_url)
    parsed = parse_data_js(raw_js)
    fish_names: dict[int, str] = {}
    try:
        raw_info = await fetch_raw_data(info_url)
        fish_names = parse_fish_info_js(raw_info)
    except Exception:
        pass
    return build_fish_data(parsed, fish_names)


def save_cache(data: FishData, path: str | None = None) -> None:
    path = path or str(DATA_CACHE_PATH)


def _fish_to_dict(f: Fish) -> dict:
    return {
        "id": f.id,
        "name_en": f.name_en,
        "start_hour": f.start_hour,
        "end_hour": f.end_hour,
        "patch": f.patch,
        "big_fish": f.big_fish,
        "collectable": f.collectable,
        "weather_set": f.weather_set,
        "previous_weather_set": f.previous_weather_set,
        "location_id": f.location_id,
        "best_catch_path": f.best_catch_path,
        "predators": f.predators,
        "intuition_length": f.intuition_length,
        "fish_eyes": f.fish_eyes,
        "folklore": f.folklore,
        "snagging": f.snagging,
        "lure": f.lure,
        "hookset": f.hookset,
        "tug": f.tug,
        "gig": f.gig,
        "data_missing": f.data_missing,
        "aquarium": f.aquarium,
    }


def _spot_to_dict(s: FishingSpot) -> dict:
    return {
        "id": s.id,
        "name_en": s.name_en,
        "territory_id": s.territory_id,
        "placename_id": s.placename_id,
        "zone_id": s.zone_id,
        "region_id": s.region_id,
    }


def _item_to_dict(i: Item) -> dict:
    return {"id": i.id, "name_en": i.name_en}


def _wr_to_dict(k: int, wr: WeatherRate) -> dict:
    return {
        "map_id": wr.map_id,
        "zone_id": wr.zone_id,
        "region_id": wr.region_id,
        "weather_rates": wr.weather_rates,
    }


def to_json_serializable(data: FishData) -> dict:
    return {
        "fish": {str(k): _fish_to_dict(v) for k, v in data.fish.items()},
        "fishing_spots": {str(k): _spot_to_dict(v) for k, v in data.fishing_spots.items()},
        "items": {str(k): _item_to_dict(v) for k, v in data.items.items()},
        "weather_rates": {str(k): _wr_to_dict(k, v) for k, v in data.weather_rates.items()},
        "weather_types": data.weather_types,
        "regions": data.regions,
        "zones": data.zones,
        "_fetched_at": datetime.now(timezone.utc).isoformat(),
    }


def from_json_serializable(d: dict) -> FishData:
    fish = {int(k): _parse_fish(v) for k, v in d["fish"].items()}
    fishing_spots = {int(k): _parse_fishing_spot(v) for k, v in d.get("fishing_spots", {}).items()}
    items = {int(k): _parse_item(v) for k, v in d.get("items", {}).items()}
    wrs = d.get("weather_rates", {})
    weather_rates = {int(k): _parse_weather_rate(k, v) for k, v in wrs.items()}
    weather_types = {int(k): v for k, v in d.get("weather_types", {}).items()}
    regions = {int(k): v for k, v in d.get("regions", {}).items()}
    zones = {int(k): v for k, v in d.get("zones", {}).items()}
    return FishData(
        fish=fish,
        fishing_spots=fishing_spots,
        items=items,
        weather_rates=weather_rates,
        weather_types=weather_types,
        regions=regions,
        zones=zones,
    )

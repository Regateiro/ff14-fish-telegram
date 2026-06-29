from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from ff14_fish_telegram.data.models import Fish, FishData

_ET_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)

_WEATHER_PERIOD_EARTH_S = 1400


def _uint32(x: int) -> int:
    return x & 0xFFFFFFFF


def earth_to_eorzea(dt: datetime) -> float:
    return dt.timestamp() * (3600.0 / 175.0)


def eorzea_to_earth(eorzea_ts: float) -> datetime:
    return _ET_EPOCH + timedelta(seconds=eorzea_ts / (3600.0 / 175.0))


def _eorzea_day_floor(eorzea_ts: float) -> float:
    return (eorzea_ts // 86400) * 86400


def _eorzea_hour_floor(eorzea_ts: float) -> float:
    return (eorzea_ts // 3600) * 3600


def _weather_period_start_eorzea(eorzea_ts: float) -> float:
    bell = eorzea_ts / 3600.0
    period_start_bell = (bell // 8) * 8
    return period_start_bell * 3600.0


def _forecast_target(earth_ts: float) -> int:
    bell = earth_ts / 175
    increment = int(bell + 8 - (bell % 8)) % 24
    total_days = _uint32(int(earth_ts / 4200))
    calc_base = _uint32(total_days * 0x64 + increment)
    step1 = _uint32((calc_base << 11) ^ calc_base)
    step2 = _uint32((step1 >> 8) ^ step1)
    return step2 % 100


def _get_weather_at(territory_id: int, earth_ts: float, fish_data: FishData) -> int | None:
    wr_entry = fish_data.weather_rates.get(territory_id)
    if not wr_entry:
        return None
    rates = wr_entry.weather_rates
    if not rates:
        return None
    target = _forecast_target(earth_ts)
    for weather_id, cumulative in rates:
        if target < cumulative:
            return weather_id
    return rates[-1][0]


def _weather_matches(weather: int, weather_set: list[int]) -> bool:
    return not weather_set or weather in weather_set


def _find_weather_windows(
    base_earth_ts: float,
    territory_id: int,
    previous_weather_set: list[int],
    weather_set: list[int],
    fish_data: FishData,
    limit: int = 10000,
) -> Iterator[tuple[float, float]]:
    base_eorzea_ts = earth_to_eorzea(datetime.fromtimestamp(base_earth_ts, tz=timezone.utc))
    current_period_start = _weather_period_start_eorzea(base_eorzea_ts)

    if previous_weather_set:
        current_period_start -= _WEATHER_PERIOD_EARTH_S * (3600.0 / 175.0)
        limit += 1

    last_earth_ts = eorzea_to_earth(current_period_start).timestamp()

    cache: dict[float, int | None] = {}
    prev_weather: int | None = None

    for _ in range(limit):
        period_earth_ts = last_earth_ts
        period_end_earth_ts = period_earth_ts + _WEATHER_PERIOD_EARTH_S
        last_earth_ts = period_end_earth_ts

        if period_earth_ts not in cache:
            weather = _get_weather_at(territory_id, period_earth_ts, fish_data)
            cache[period_earth_ts] = weather

        current_weather = cache[period_earth_ts]
        if current_weather is None:
            continue

        if previous_weather_set and prev_weather is not None:
            if not _weather_matches(prev_weather, previous_weather_set):
                prev_weather = current_weather
                continue

        prev_weather = current_weather

        if _weather_matches(current_weather, weather_set):
            start_eorzea = earth_to_eorzea(datetime.fromtimestamp(period_earth_ts, tz=timezone.utc))
            end_eorzea = start_eorzea + 8 * 3600
            yield (start_eorzea, end_eorzea)


def _available_time_ranges(
    fish: Fish,
    weather_start_eorzea: float,
    weather_end_eorzea: float,
) -> list[tuple[float, float]]:
    if fish.start_hour == 0 and fish.end_hour == 24:
        return [(weather_start_eorzea, weather_end_eorzea)]

    daily_duration = fish.end_hour - fish.start_hour
    if daily_duration <= 0:
        daily_duration += 24

    ranges: list[tuple[float, float]] = []

    day_start = _eorzea_day_floor(weather_start_eorzea)
    window_start_eorzea = day_start + fish.start_hour * 3600
    window_end_eorzea = window_start_eorzea + daily_duration * 3600

    if fish.end_hour < fish.start_hour:
        cand_a = (window_start_eorzea - 86400, window_end_eorzea - 86400)
        cand_b = (window_start_eorzea, window_end_eorzea)
        candidates = [cand_a, cand_b]
    else:
        candidates = [(window_start_eorzea, window_end_eorzea)]

    for ws, we in candidates:
        overlap_start = max(ws, weather_start_eorzea)
        overlap_end = min(we, weather_end_eorzea)
        if overlap_start < overlap_end:
            ranges.append((overlap_start, overlap_end))

    return ranges


@dataclass
class CatchableWindow:
    start_eorzea: float
    end_eorzea: float
    start_earth: datetime
    end_earth: datetime


def compute_catchable_windows(
    fish: Fish,
    fish_data: FishData,
    from_time: datetime | None = None,
    max_windows: int = 10,
) -> list[CatchableWindow]:
    if fish.always_available:
        now = from_time or datetime.now(timezone.utc)
        earth_ts = now.timestamp()
        end = earth_ts + 86400 * 7
        return [
            CatchableWindow(
                start_eorzea=earth_to_eorzea(now),
                end_eorzea=earth_to_eorzea(datetime.fromtimestamp(end, tz=timezone.utc)),
                start_earth=now,
                end_earth=datetime.fromtimestamp(end, tz=timezone.utc),
            )
        ]

    base_time = from_time or datetime.now(timezone.utc)
    base_ts = base_time.timestamp()

    spot = fish_data.fishing_spots.get(fish.location_id)
    if not spot:
        return []

    territory_id = spot.territory_id
    if territory_id is None:
        return []

    if territory_id not in fish_data.weather_rates:
        return []

    results: list[CatchableWindow] = []

    weather_iter = _find_weather_windows(
        base_ts,
        territory_id,
        fish.previous_weather_set,
        fish.weather_set,
        fish_data,
    )

    for weather_start_eo, weather_end_eo in weather_iter:
        if len(results) >= max_windows:
            break

        time_ranges = _available_time_ranges(fish, weather_start_eo, weather_end_eo)
        for tr_start, tr_end in time_ranges:
            catch_start = max(tr_start, weather_start_eo)
            catch_end = min(tr_end, weather_end_eo)
            if catch_start < catch_end:
                catch_start_earth = eorzea_to_earth(catch_start)
                catch_end_earth = eorzea_to_earth(catch_end)
                if catch_end_earth > base_time:
                    results.append(
                        CatchableWindow(
                            start_eorzea=catch_start,
                            end_eorzea=catch_end,
                            start_earth=catch_start_earth,
                            end_earth=catch_end_earth,
                        )
                    )

    return results


def get_next_window(
    fish: Fish,
    fish_data: FishData,
    from_time: datetime | None = None,
) -> CatchableWindow | None:
    windows = compute_catchable_windows(fish, fish_data, from_time, max_windows=1)
    return windows[0] if windows else None


def get_zone_name_for_spot(spot_id: int, fish_data: FishData) -> str:
    spot = fish_data.fishing_spots.get(spot_id)
    if not spot or spot.territory_id is None:
        return ""
    wr = fish_data.weather_rates.get(spot.territory_id)
    if not wr:
        return ""
    return fish_data.zones.get(wr.zone_id, "")

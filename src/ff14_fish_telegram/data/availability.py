"""Eorzea time conversion, weather prediction, and fish availability window computation.

This module implements the core domain logic:
  1. Time conversions between Earth UTC and Eorzea time
  2. FFXIV's XOR-shift weather forecasting algorithm
  3. Computing catchable windows by intersecting time-of-day restrictions
     with weather conditions

These functions are consumed by:
  - bot/handlers.py  — to display upcoming windows in /day
  - bot/reminders.py — to find the next window for reminder scheduling

The weather algorithm is based on reverse-engineered FFXIV game data
and matches the official server's weather computation.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from ff14_fish_telegram.data.models import Fish, FishData

# The Eorzea epoch: Eorzea time 0 = Unix epoch (1970-01-01 00:00:00 UTC)
_ET_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)

# Duration of one FFXIV weather period in Earth seconds (1 Eorzea bell ≈ 175 Earth s).
# 8 Eorzea hours per weather period → 8 × 175 = 1400 Earth seconds.
# This constant is used to step through weather periods when searching for matches.
_WEATHER_PERIOD_EARTH_S = 1400


def _uint32(x: int) -> int:
    """Mask a value to an unsigned 32-bit integer.

    FFXIV's weather RNG uses uint32 arithmetic (overflow wraps).
    Python ints are arbitrary precision, so we explicitly mask.
    """
    return x & 0xFFFFFFFF


def earth_to_eorzea(dt: datetime) -> float:
    """Convert a UTC datetime to an Eorzea timestamp (seconds since ET epoch).

    One Earth second equals 3600/175 Eorzea seconds (~20.57 ET seconds).
    This factor comes from the game's time scale: 1 real minute = 20.57 ET minutes.

    Used to convert catchable window boundaries between Earth and Eorzea
    representations throughout this module and by callers in handlers.py.
    """
    return dt.timestamp() * (3600.0 / 175.0)


def eorzea_to_earth(eorzea_ts: float) -> datetime:
    """Convert an Eorzea timestamp back to a UTC datetime.

    Inverse of earth_to_eorzea. Used to present window times to users
    in human-readable UTC format.
    """
    return _ET_EPOCH + timedelta(seconds=eorzea_ts / (3600.0 / 175.0))


def _eorzea_day_floor(eorzea_ts: float) -> float:
    """Round an Eorzea timestamp down to the start of its Eorzea day.

    An Eorzea day is 86400 ET seconds (24 Eorzea hours × 3600).
    Used by _available_time_ranges to anchor time-of-day window calculations.
    """
    return (eorzea_ts // 86400) * 86400


def _weather_period_start_eorzea(eorzea_ts: float) -> float:
    """Return the Eorzea timestamp of the 8-hour weather period containing eorzea_ts.

    Weather in FFXIV changes every 8 Eorzea hours (1400 Earth seconds).
    This function rounds down to the start of whichever 8-hour block
    the given timestamp falls in.
    """
    bell = eorzea_ts / 3600.0
    period_start_bell = (bell // 8) * 8
    return period_start_bell * 3600.0


def _forecast_target(earth_ts: float) -> int:
    """Compute a weather forecast target (0-99) for a given Earth timestamp.

    Implements FFXIV's weather prediction algorithm:
      1. Calculate the "increment" (bell of day, 0-23) for the midpoint
         of the current weather period.
      2. Combine it with the number of days since epoch using the formula:
         calc_base = total_days * 0x64 + increment
      3. Apply XOR-shift: ((calc_base << 11) ^ calc_base) >> 8 ^ calc_base
      4. Return result % 100 as the forecast value used to index into
         weather rate tables.

    This algorithm is deterministic: given the same Earth timestamp,
    it always produces the same forecast value, matching the game server.
    """
    bell = earth_ts / 175
    increment = int(bell + 8 - (bell % 8)) % 24
    total_days = _uint32(int(earth_ts / 4200))
    calc_base = _uint32(total_days * 0x64 + increment)
    step1 = _uint32((calc_base << 11) ^ calc_base)
    step2 = _uint32((step1 >> 8) ^ step1)
    return step2 % 100


def _get_weather_at(territory_id: int, earth_ts: float, fish_data: FishData) -> int | None:
    """Determine the weather type ID active in a territory at a given Earth timestamp.

    Looks up the territory's WeatherRate from fish_data, computes the
    forecast target, and walks the cumulative rate table to find which
    weather type is active. Returns None if the territory has no weather
    rate entry or the rate list is empty.
    """
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
    """Return True if the given weather is in weather_set.

    An empty weather_set means "any weather" (no restriction), so
    the function returns True in that case.
    """
    return not weather_set or weather in weather_set


def _find_weather_windows(
    base_earth_ts: float,
    territory_id: int,
    previous_weather_set: list[int],
    weather_set: list[int],
    fish_data: FishData,
    limit: int = 10000,
) -> Iterator[tuple[float, float]]:
    """Yield (start_eorzea, end_eorzea) pairs for weather periods matching requirements.

    This is the core weather search. It iterates forward from base_earth_ts,
    checking each 8-hour weather period to find those matching the fish's
    weather_set (and optional previous_weather_set).

    When previous_weather_set is non-empty, the period before the matching
    one must have had a weather type from previous_weather_set. This handles
    conditions like "Clear Skies → Fog" where the transition matters.

    Results are cached since adjacent weather periods may fall within the
    same 1400-second Earth-time window and produce the same forecast.
    """
    base_eorzea_ts = earth_to_eorzea(datetime.fromtimestamp(base_earth_ts, tz=timezone.utc))
    current_period_start = _weather_period_start_eorzea(base_eorzea_ts)

    # If previous weather is required, step back one period so we can check the condition
    # on the first iteration rather than waiting for period N+1.
    if previous_weather_set:
        current_period_start -= _WEATHER_PERIOD_EARTH_S * (3600.0 / 175.0)
        limit += 1

    last_earth_ts = eorzea_to_earth(current_period_start).timestamp()

    # Cache weather lookups since adjacent periods may hit the same forecast target.
    cache: dict[float, int | None] = {}
    prev_weather: int | None = None

    for i in range(limit):
        period_earth_ts = last_earth_ts
        period_end_earth_ts = period_earth_ts + _WEATHER_PERIOD_EARTH_S
        last_earth_ts = period_end_earth_ts

        if period_earth_ts not in cache:
            weather = _get_weather_at(territory_id, period_earth_ts, fish_data)
            cache[period_earth_ts] = weather

        current_weather = cache[period_earth_ts]
        if current_weather is None:
            continue

        if previous_weather_set:
            if prev_weather is None:
                # First iteration: prime prev_weather and skip — we need a preceding period
                # to validate the previous-weather condition.
                prev_weather = current_weather
                continue
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
    """Intersect a fish's time-of-day window with a weather period.

    A fish may only be catchable during specific Eorzea hours (e.g. 18:00-06:00).
    This function computes the overlap between that daily window and the
    given weather period.

    Handles overnight windows (end_hour < start_hour, e.g. 18:00-06:00)
    by checking both the current day and the previous day's candidate,
    since a weather period may span midnight.

    Returns a list of (start_eorzea, end_eorzea) overlaps (usually 0 or 1).
    """
    if fish.start_hour == 0 and fish.end_hour == 24:
        return [(weather_start_eorzea, weather_end_eorzea)]

    daily_duration = fish.end_hour - fish.start_hour
    if daily_duration <= 0:
        daily_duration += 24

    ranges: list[tuple[float, float]] = []

    day_start = _eorzea_day_floor(weather_start_eorzea)
    window_start_eorzea = day_start + fish.start_hour * 3600
    window_end_eorzea = window_start_eorzea + daily_duration * 3600

    # For overnight windows, also check the candidate starting one day earlier
    # because the window wraps around midnight.
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
    """A time range during which a fish can be caught.

    This is the result type returned by compute_catchable_windows and
    get_next_window. It represents the intersection of weather conditions,
    time-of-day restrictions, and the current time.

    Attributes:
        start_eorzea: Start of the window in Eorzea seconds since epoch.
        end_eorzea: End of the window in Eorzea seconds since epoch.
        start_earth: Start of the window as a UTC datetime.
        end_earth: End of the window as a UTC datetime.
    """

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
    """Compute upcoming catchable windows for a fish.

    This is the main public API for availability computation:
      - For always-available fish: returns a single 7-day window from now.
      - For restricted fish: finds weather windows matching the fish's
        weather conditions via _find_weather_windows, then intersects
        each with the fish's time-of-day range via _available_time_ranges.

    Called by:
      - bot/handlers.py's /day command to list today's opportunities
      - bot/reminders.py's get_next_window to find the next reminder trigger

    Args:
        fish: The fish to compute windows for.
        fish_data: Full game data context (spots, weather rates).
        from_time: Start searching from this time (defaults to now UTC).
        max_windows: Maximum number of windows to return.

    Returns:
        A list of CatchableWindow sorted chronologically.
    """
    if fish.restrictions_unknown:
        return []

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
                # Only include windows that end in the future
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
    """Return the single next catchable window for a fish, or None if none exist.

    Convenience wrapper around compute_catchable_windows used by
    bot/reminders.py to determine the upcoming window for each fish.
    """
    windows = compute_catchable_windows(fish, fish_data, from_time, max_windows=1)
    return windows[0] if windows else None


def get_zone_name_for_spot(spot_id: int, fish_data: FishData) -> str:
    """Look up the zone name for a fishing spot via its territory's weather rate entry.

    The zone name is extracted from the WeatherRate's zone_id, which
    maps into fish_data.zones. This is used by bot/handlers.py's /day
    command to display a human-readable location for each fish.

    Returns an empty string if the spot, territory, or zone cannot be found.
    """
    spot = fish_data.fishing_spots.get(spot_id)
    if not spot or spot.territory_id is None:
        return ""
    wr = fish_data.weather_rates.get(spot.territory_id)
    if not wr:
        return ""
    return fish_data.zones.get(wr.zone_id, "")

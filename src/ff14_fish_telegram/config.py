"""Application configuration loaded from environment variables and .env file.

This module is the single source of truth for all configurable parameters.
Every other module in the project imports from here rather than reading
environment variables directly, ensuring consistency and testability.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env file from project root before accessing env vars.
# python-dotenv does not override existing environment variables.
load_dotenv()


# Telegram bot API token (required — will raise KeyError if missing).
# Used by __main__.py to authenticate with the Telegram Bot API.
TELEGRAM_TOKEN: str = os.environ["TELEGRAM_TOKEN"]

# URL for the FFXIV fish tracker data files.
# Used by data/fetcher.py to download raw fish/spot/weather data.
DATA_URL: str = os.environ.get(
    "DATA_URL",
    "https://ff14fish.carbuncleplushy.com/js/app/data.js",
)

# Path to local cache file for fish data JSON serialization.
# Currently reserved for future use (fetcher builds data in memory).
DATA_CACHE_PATH: Path = Path(
    os.environ.get("DATA_CACHE_PATH", "data_cache.json"),
)

# Path to the SQLite database file.
# Used by db/database.py for all CRUD operations.
DATABASE_PATH: str = os.environ.get("DATABASE_PATH", "fish_tracker.db")

# How often to re-fetch fish data from the remote source (hours).
# Used by __main__.py to schedule the recurring data refresh job.
FETCH_INTERVAL_HOURS: int = int(os.environ.get("FETCH_INTERVAL_HOURS", "6"))

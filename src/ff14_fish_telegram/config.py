"""Application configuration loaded from environment variables and .env file."""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


# Telegram bot API token (required)
TELEGRAM_TOKEN: str = os.environ["TELEGRAM_TOKEN"]

# URL for the FFXIV fish tracker data files
DATA_URL: str = os.environ.get(
    "DATA_URL",
    "https://ff14fish.carbuncleplushy.com/js/app/data.js",
)

# Path to local cache file for fish data
DATA_CACHE_PATH: Path = Path(
    os.environ.get("DATA_CACHE_PATH", "data_cache.json"),
)

# Path to the SQLite database file
DATABASE_PATH: str = os.environ.get("DATABASE_PATH", "fish_tracker.db")

# How often to re-fetch fish data from the remote source (hours)
FETCH_INTERVAL_HOURS: int = int(os.environ.get("FETCH_INTERVAL_HOURS", "6"))

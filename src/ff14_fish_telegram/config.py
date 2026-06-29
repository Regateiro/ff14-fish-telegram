import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


TELEGRAM_TOKEN: str = os.environ["TELEGRAM_TOKEN"]
DATA_URL: str = os.environ.get(
    "DATA_URL",
    "https://ff14fish.carbuncleplushy.com/js/app/data.js",
)
DATA_CACHE_PATH: Path = Path(
    os.environ.get("DATA_CACHE_PATH", "data_cache.json"),
)
DATABASE_PATH: str = os.environ.get("DATABASE_PATH", "fish_tracker.db")
FETCH_INTERVAL_HOURS: int = int(os.environ.get("FETCH_INTERVAL_HOURS", "6"))

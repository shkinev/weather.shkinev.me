from __future__ import annotations

import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
DATABASE_PATH = Path(os.getenv("WEATHER_DB_PATH", BASE_DIR / "weather.sqlite3"))
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
WEATHER_TIMEZONE = os.getenv("WEATHER_TIMEZONE", "Asia/Omsk")
LOG_DIR = Path(os.getenv("LOG_DIR", BASE_DIR / "logs"))


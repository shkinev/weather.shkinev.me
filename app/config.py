from __future__ import annotations

import os
from pathlib import Path


def _parse_int_list(value: str) -> list[int]:
    result: list[int] = []
    for chunk in value.split(","):
        raw = chunk.strip()
        if not raw:
            continue
        try:
            result.append(int(raw))
        except ValueError:
            continue
    return result


def _parse_times(value: str) -> list[str]:
    result: list[str] = []
    for chunk in value.split(","):
        raw = chunk.strip()
        if not raw:
            continue
        parts = raw.split(":")
        if len(parts) != 2:
            continue
        try:
            hour = int(parts[0])
            minute = int(parts[1])
        except ValueError:
            continue
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            result.append(f"{hour:02d}:{minute:02d}")
    return result


def _parse_bool(value: str, default: bool = False) -> bool:
    raw = (value or "").strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on", "y", "да"}


BASE_DIR = Path(__file__).resolve().parent.parent
DATABASE_PATH = Path(os.getenv("WEATHER_DB_PATH", BASE_DIR / "weather.sqlite3"))
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
WEATHER_TIMEZONE = os.getenv("WEATHER_TIMEZONE", "UTC")
LOG_DIR = Path(os.getenv("LOG_DIR", BASE_DIR / "logs"))
WEATHER_SITE_URL = os.getenv("WEATHER_SITE_URL", "").strip()

APP_TITLE = os.getenv("APP_TITLE", "Weather Station").strip() or "Weather Station"
SITE_BRAND = os.getenv("SITE_BRAND", "Weather Dashboard").strip() or "Weather Dashboard"
WEATHER_PLACE_NAME = os.getenv("WEATHER_PLACE_NAME", "Локальная станция").strip() or "Локальная станция"
YANDEX_METRIKA_ID = os.getenv("YANDEX_METRIKA_ID", "").strip()
YANDEX_METRIKA_ENABLED = bool(YANDEX_METRIKA_ID)

TELEGRAM_ADMIN_IDS = _parse_int_list(os.getenv("TELEGRAM_ADMIN_IDS", ""))
TELEGRAM_DAILY_USER_IDS = _parse_int_list(os.getenv("TELEGRAM_DAILY_USER_IDS", ""))
TELEGRAM_DAILY_TIMES = _parse_times(os.getenv("TELEGRAM_DAILY_TIMES", "07:00,20:00"))
TELEGRAM_STALE_MINUTES = int(os.getenv("TELEGRAM_STALE_MINUTES", "5"))
TELEGRAM_MONITOR_INTERVAL_SECONDS = int(os.getenv("TELEGRAM_MONITOR_INTERVAL_SECONDS", "60"))
TELEGRAM_DYNAMIC_NAME_ENABLED = _parse_bool(os.getenv("TELEGRAM_DYNAMIC_NAME_ENABLED", "1"), default=True)
TELEGRAM_DYNAMIC_NAME_PREFIX = (
    os.getenv("TELEGRAM_DYNAMIC_NAME_PREFIX", f"Погода: {WEATHER_PLACE_NAME}").strip() or f"Погода: {WEATHER_PLACE_NAME}"
)
TELEGRAM_DYNAMIC_NAME_INTERVAL_MINUTES = int(os.getenv("TELEGRAM_DYNAMIC_NAME_INTERVAL_MINUTES", "10"))

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Iterator
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .config import DATABASE_PATH, WEATHER_TIMEZONE
from .sensor_map import PRIMARY_SENSOR_IDS, sensor_label, sensor_unit

try:
    LOCAL_TZ = ZoneInfo(WEATHER_TIMEZONE)
except ZoneInfoNotFoundError:
    LOCAL_TZ = UTC


def dict_factory(cursor: sqlite3.Cursor, row: tuple[Any, ...]) -> dict[str, Any]:
    return {column[0]: row[index] for index, column in enumerate(cursor.description)}


@contextmanager
def get_connection() -> Iterator[sqlite3.Connection]:
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = dict_factory
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        yield connection
        connection.commit()
    finally:
        connection.close()


def init_db(db_path: Path | None = None) -> None:
    target = db_path or DATABASE_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(target)
    try:
        connection.executescript(
            """
            PRAGMA journal_mode = WAL;

            CREATE TABLE IF NOT EXISTS ingest_batches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                device_mac TEXT NOT NULL,
                received_at TEXT NOT NULL,
                payload_json TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS observations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                batch_id INTEGER NOT NULL REFERENCES ingest_batches(id) ON DELETE CASCADE,
                device_mac TEXT NOT NULL,
                observed_at TEXT NOT NULL,
                sensor_id TEXT NOT NULL,
                sensor_name TEXT NOT NULL,
                value REAL NOT NULL,
                unit TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_observations_sensor_time
                ON observations(sensor_id, observed_at DESC);

            CREATE INDEX IF NOT EXISTS idx_observations_device_time
                ON observations(device_mac, observed_at DESC);
            """
        )
        connection.commit()
    finally:
        connection.close()


def parse_timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def to_local_timestamp(value: str) -> datetime:
    return parse_timestamp(value).astimezone(LOCAL_TZ)


def format_relative_age(value: str, now: datetime | None = None) -> str:
    try:
        observed_at = parse_timestamp(value)
    except ValueError:
        return value

    current = now or datetime.now(UTC)
    seconds = max(0, int((current - observed_at).total_seconds()))
    if seconds < 60:
        return "только что"

    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes} мин назад"

    hours = minutes // 60
    if hours < 24:
        return f"{hours} ч назад"

    days = hours // 24
    return f"{days} дн назад"


def freshness_emoji(value: str, now: datetime | None = None) -> str:
    try:
        observed_at = parse_timestamp(value)
    except ValueError:
        return "⚪"
    current = now or datetime.now(UTC)
    seconds = max(0, int((current - observed_at).total_seconds()))
    if seconds <= 10 * 60:
        return "🟢"
    if seconds <= 60 * 60:
        return "🟡"
    return "🔴"


def save_payload(payload: dict[str, Any], received_at: datetime | None = None) -> dict[str, Any]:
    timestamp = (received_at or datetime.now(UTC)).replace(microsecond=0)
    devices = payload.get("devices") or []
    inserted_batches = 0
    inserted_rows = 0

    with get_connection() as connection:
        for device in devices:
            mac = str(device.get("mac") or "unknown")
            sensors = device.get("sensors") or []
            batch_cursor = connection.execute(
                """
                INSERT INTO ingest_batches(device_mac, received_at, payload_json)
                VALUES (?, ?, ?)
                """,
                (mac, timestamp.isoformat(), json.dumps(device, ensure_ascii=False)),
            )
            batch_id = int(batch_cursor.lastrowid)
            inserted_batches += 1

            for sensor in sensors:
                sensor_id = str(sensor.get("id") or "").strip().upper()
                value = sensor.get("value")
                if not sensor_id or value is None:
                    continue

                try:
                    numeric_value = float(value)
                except (TypeError, ValueError):
                    continue

                connection.execute(
                    """
                    INSERT INTO observations(
                        batch_id, device_mac, observed_at, sensor_id, sensor_name, value, unit
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        batch_id,
                        mac,
                        timestamp.isoformat(),
                        sensor_id,
                        sensor_label(sensor_id),
                        numeric_value,
                        sensor_unit(sensor_id, sensor.get("unit")),
                    ),
                )
                inserted_rows += 1

    return {
        "received_at": timestamp.isoformat(),
        "devices": inserted_batches,
        "measurements": inserted_rows,
    }


def get_latest_snapshot() -> dict[str, Any] | None:
    with get_connection() as connection:
        batch = connection.execute(
            """
            SELECT id, device_mac, received_at
            FROM ingest_batches
            ORDER BY received_at DESC, id DESC
            LIMIT 1
            """
        ).fetchone()
        if not batch:
            return None

        rows = connection.execute(
            """
            SELECT sensor_id, sensor_name, value, unit
            FROM observations
            WHERE batch_id = ?
            ORDER BY sensor_name
            """,
            (batch["id"],),
        ).fetchall()

    readings: list[dict[str, Any]] = []
    lookup: dict[str, dict[str, Any]] = {}
    for row in rows:
        entry = {
            "sensor_id": row["sensor_id"],
            "sensor_name": row["sensor_name"],
            "value": row["value"],
            "unit": row["unit"],
        }
        readings.append(entry)
        lookup[row["sensor_id"].upper()] = entry

    primary = [lookup[sensor_id] for sensor_id in PRIMARY_SENSOR_IDS if sensor_id in lookup]
    local_dt = to_local_timestamp(batch["received_at"])
    return {
        "batch_id": batch["id"],
        "device_mac": batch["device_mac"],
        "received_at": batch["received_at"],
        "received_local": local_dt.strftime("%Y-%m-%d %H:%M:%S"),
        "received_ago": format_relative_age(batch["received_at"]),
        "received_freshness": freshness_emoji(batch["received_at"]),
        "primary_readings": primary,
        "readings": readings,
    }


def get_chart_series(days: int) -> dict[str, Any]:
    period = max(1, min(days, 90))
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT upper(sensor_id) AS sensor_id, sensor_name, observed_at, value, unit
            FROM observations
            WHERE julianday(observed_at) >= julianday('now', ?)
              AND sensor_id <> ''
            ORDER BY observed_at ASC
            """,
            (f"-{period} days",),
        ).fetchall()

    series: dict[str, dict[str, Any]] = {}
    for row in rows:
        bucket = series.setdefault(
            row["sensor_id"],
            {"label": row["sensor_name"], "unit": row["unit"], "points": []},
        )
        bucket["points"].append({"x": row["observed_at"], "y": row["value"]})

    return {"days": period, "series": series}


def _value_by_ids(reading_lookup: dict[str, dict[str, Any]], ids: tuple[str, ...]) -> str:
    for sensor_id in ids:
        item = reading_lookup.get(sensor_id)
        if item:
            unit = f" {item['unit']}" if item["unit"] else ""
            return f"{item['value']:.2f}{unit}"
    return "—"


def get_history_for_date(target_date: str) -> list[dict[str, Any]]:
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT
                b.id AS batch_id,
                b.device_mac,
                b.received_at,
                o.sensor_id,
                o.sensor_name,
                o.value,
                o.unit
            FROM ingest_batches AS b
            JOIN observations AS o ON o.batch_id = b.id
            WHERE date(b.received_at) = date(?)
            ORDER BY b.received_at DESC, o.sensor_name ASC
            """,
            (target_date,),
        ).fetchall()

    grouped: dict[int, dict[str, Any]] = {}
    for row in rows:
        bucket = grouped.setdefault(
            row["batch_id"],
            {
                "batch_id": row["batch_id"],
                "device_mac": row["device_mac"],
                "received_at": row["received_at"],
                "readings": [],
            },
        )
        bucket["readings"].append(
            {
                "sensor_id": row["sensor_id"].upper(),
                "sensor_name": row["sensor_name"],
                "value": row["value"],
                "unit": row["unit"],
            }
        )

    result: list[dict[str, Any]] = []
    core_ids = {"T1", "T2", "T3", "T4", "T5", "T6", "RH", "H1", "H2", "PRESS", "HPA"}

    for item in grouped.values():
        reading_lookup = {reading["sensor_id"]: reading for reading in item["readings"]}
        local_dt = to_local_timestamp(item["received_at"])
        extra = []
        for reading in item["readings"]:
            if reading["sensor_id"] in core_ids:
                continue
            unit = f" {reading['unit']}" if reading["unit"] else ""
            extra.append(f"{reading['sensor_name']}: {reading['value']:.2f}{unit}")

        result.append(
            {
                **item,
                "date": local_dt.strftime("%Y-%m-%d"),
                "time": local_dt.strftime("%H:%M:%S"),
                "temperature": _value_by_ids(reading_lookup, ("T1", "T2", "T3", "T4", "T5", "T6")),
                "humidity": _value_by_ids(reading_lookup, ("RH", "H1", "H2")),
                "pressure": _value_by_ids(reading_lookup, ("PRESS", "HPA")),
                "other_data": " | ".join(extra) if extra else "—",
            }
        )

    return result


def get_uptime_monitor(hours: int = 24) -> dict[str, Any]:
    period = max(6, min(hours, 72))
    now_utc = datetime.now(UTC)
    start_utc = now_utc - timedelta(hours=period)

    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT received_at
            FROM ingest_batches
            WHERE julianday(received_at) >= julianday(?)
            ORDER BY received_at ASC
            """,
            (start_utc.isoformat(),),
        ).fetchall()
        latest = connection.execute(
            """
            SELECT received_at
            FROM ingest_batches
            ORDER BY received_at DESC, id DESC
            LIMIT 1
            """
        ).fetchone()

    now_local = now_utc.astimezone(LOCAL_TZ)
    hour_starts = [now_local.replace(minute=0, second=0, microsecond=0) - timedelta(hours=period - 1 - i) for i in range(period)]
    labels = [moment.strftime("%H:%M") for moment in hour_starts]
    points = [0 for _ in range(period)]

    for row in rows:
        observed_local = to_local_timestamp(row["received_at"]).replace(minute=0, second=0, microsecond=0)
        delta = int((observed_local - hour_starts[0]).total_seconds() // 3600)
        if 0 <= delta < period:
            points[delta] += 1

    active_hours = sum(1 for value in points if value > 0)
    availability = round((active_hours / period) * 100, 1)
    latest_received = latest["received_at"] if latest else None

    return {
        "hours": period,
        "labels": labels,
        "points": points,
        "availability": availability,
        "last_seen_ago": format_relative_age(latest_received) if latest_received else "нет данных",
        "freshness": freshness_emoji(latest_received) if latest_received else "⚪",
    }


def get_today_temperature_extremes() -> dict[str, Any]:
    now_local = datetime.now(LOCAL_TZ)
    day_start_local = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end_local = day_start_local + timedelta(days=1)
    day_start_utc = day_start_local.astimezone(UTC).isoformat()
    day_end_utc = day_end_local.astimezone(UTC).isoformat()

    with get_connection() as connection:
        min_row = connection.execute(
            """
            SELECT observed_at, value, unit
            FROM observations
            WHERE upper(sensor_id) = 'T1'
              AND julianday(observed_at) >= julianday(?)
              AND julianday(observed_at) < julianday(?)
            ORDER BY value ASC, observed_at ASC
            LIMIT 1
            """,
            (day_start_utc, day_end_utc),
        ).fetchone()
        max_row = connection.execute(
            """
            SELECT observed_at, value, unit
            FROM observations
            WHERE upper(sensor_id) = 'T1'
              AND julianday(observed_at) >= julianday(?)
              AND julianday(observed_at) < julianday(?)
            ORDER BY value DESC, observed_at ASC
            LIMIT 1
            """,
            (day_start_utc, day_end_utc),
        ).fetchone()

    def serialize(row: dict[str, Any] | None) -> dict[str, Any] | None:
        if not row:
            return None
        local_time = to_local_timestamp(row["observed_at"])
        return {
            "value": row["value"],
            "unit": row["unit"] or "°C",
            "time": local_time.strftime("%H:%M"),
            "datetime_local": local_time.strftime("%Y-%m-%d %H:%M:%S"),
        }

    return {
        "date": day_start_local.strftime("%Y-%m-%d"),
        "min": serialize(min_row),
        "max": serialize(max_row),
    }


def _reading_emoji(sensor_id: str) -> str:
    sid = sensor_id.upper()
    if sid.startswith("T"):
        return "🌡️"
    if sid in {"RH", "H1", "H2"}:
        return "💧"
    if sid in {"PRESS", "HPA"}:
        return "🧭"
    if sid.startswith("WS") or sid == "1DIR":
        return "💨"
    if sid.startswith("RAIN"):
        return "🌧️"
    if sid.startswith("PM"):
        return "🌫️"
    return "•"


def _format_t1_title(snapshot: dict[str, Any]) -> str:
    t1_reading: dict[str, Any] | None = None
    for reading in snapshot.get("readings", []):
        if str(reading.get("sensor_id", "")).upper() == "T1":
            t1_reading = reading
            break
    if not t1_reading:
        return "⚪ --"
    try:
        value = float(t1_reading["value"])
    except (TypeError, ValueError, KeyError):
        return "⚪ --"
    icon = "☀️" if value >= 0 else "❄️"
    return f"{icon} {value:+.1f}°"


def _format_temp_with_icon(value: float) -> str:
    icon = "☀️" if value >= 0 else "❄️"
    return f"{icon} {value:+.2f}°"


def format_telegram_snapshot(snapshot: dict[str, Any] | None) -> str:
    if not snapshot:
        return '🏡 Погода в КП "Аист"\n⚪ --\n\n📭 Данных пока нет. Станция еще ничего не отправляла.'

    freshness = snapshot.get("received_freshness") or freshness_emoji(snapshot["received_at"])
    updated_ago = snapshot.get("received_ago") or format_relative_age(snapshot["received_at"])
    lines = [
        '🏡 Погода в КП "Аист"',
        f"🕒 Обновлено: {freshness} {updated_ago}",
        "",
        "Показатели:",
    ]

    for reading in snapshot["primary_readings"]:
        sensor_id = str(reading.get("sensor_id", "")).upper()
        if sensor_id == "T1":
            lines.append(f"{_reading_emoji(sensor_id)} {reading['sensor_name']}: {_format_temp_with_icon(float(reading['value']))}")
        else:
            unit = f" {reading['unit']}" if reading["unit"] else ""
            lines.append(f"{_reading_emoji(sensor_id)} {reading['sensor_name']}: {reading['value']:.2f}{unit}")

    extremes = get_today_temperature_extremes()
    if extremes.get("min") and extremes.get("max"):
        t_min = extremes["min"]
        t_max = extremes["max"]
        lines.extend(
            [
                "",
                "📉📈 T1 за сегодня:",
                f"Мин: {_format_temp_with_icon(float(t_min['value']))} в {t_min['time']}",
                f"Макс: {_format_temp_with_icon(float(t_max['value']))} в {t_max['time']}",
            ]
        )

    return "\n".join(lines)

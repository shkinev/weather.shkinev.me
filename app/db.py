from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterator

from .config import DATABASE_PATH
from .sensor_map import PRIMARY_SENSOR_IDS, sensor_label, sensor_unit


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
                sensor_id = str(sensor.get("id") or "").strip()
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

    readings = []
    lookup: dict[str, dict[str, Any]] = {}
    for row in rows:
        entry = {
            "sensor_id": row["sensor_id"],
            "sensor_name": row["sensor_name"],
            "value": row["value"],
            "unit": row["unit"],
        }
        readings.append(entry)
        lookup[row["sensor_id"]] = entry

    primary = [lookup[sensor_id] for sensor_id in PRIMARY_SENSOR_IDS if sensor_id in lookup]
    return {
        "batch_id": batch["id"],
        "device_mac": batch["device_mac"],
        "received_at": batch["received_at"],
        "received_ago": format_relative_age(batch["received_at"]),
        "primary_readings": primary,
        "readings": readings,
    }


def get_chart_series(days: int) -> dict[str, Any]:
    period = max(1, min(days, 90))
    tracked = (
        "T1",
        "T2",
        "T3",
        "T4",
        "RH",
        "H1",
        "H2",
        "PRESS",
        "HPA",
        "WS",
        "WS1",
        "PM2",
        "PM10",
        "RAIN2",
    )

    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT sensor_id, sensor_name, observed_at, value, unit
            FROM observations
            WHERE julianday(observed_at) >= julianday('now', ?)
              AND sensor_id IN ({placeholders})
            ORDER BY observed_at ASC
            """.format(placeholders=",".join("?" for _ in tracked)),
            (f"-{period} days", *tracked),
        ).fetchall()

    series: dict[str, dict[str, Any]] = {}
    for row in rows:
        bucket = series.setdefault(
            row["sensor_id"],
            {"label": row["sensor_name"], "unit": row["unit"], "points": []},
        )
        bucket["points"].append({"x": row["observed_at"], "y": row["value"]})

    return {"days": period, "series": series}


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
                "sensor_id": row["sensor_id"],
                "sensor_name": row["sensor_name"],
                "value": row["value"],
                "unit": row["unit"],
            }
        )

    return list(grouped.values())


def format_telegram_snapshot(snapshot: dict[str, Any] | None) -> str:
    if not snapshot:
        return "Данных пока нет. Станция еще ничего не отправляла."

    lines = [
        "Текущая погода",
        f"Станция: {snapshot['device_mac']}",
        f"Обновлено: {snapshot.get('received_ago') or format_relative_age(snapshot['received_at'])}",
        "",
    ]

    for reading in snapshot["primary_readings"]:
        unit = f" {reading['unit']}" if reading["unit"] else ""
        lines.append(f"{reading['sensor_name']}: {reading['value']:.2f}{unit}")

    return "\n".join(lines)

"""Простая миграционная система на PRAGMA user_version.

Каждый элемент MIGRATIONS — SQL-скрипт, выполняемый ровно один раз.
Индекс в массиве — это целевая user_version. После выполнения скрипта
PRAGMA user_version устанавливается в (index + 1).

Существующие БД с user_version = 0 поднимутся в актуальную версию на
старте: в v1 все CREATE стоят с IF NOT EXISTS, поэтому повторное
применение к развёрнутой схеме безопасно.

Добавляя новую миграцию — просто допиши строку в конец списка.
"""
from __future__ import annotations

import sqlite3


MIGRATIONS: list[str] = [
    # v1: исходная схема (идемпотентная для уже развёрнутых БД)
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
    """,
]


def current_version(connection: sqlite3.Connection) -> int:
    return int(connection.execute("PRAGMA user_version").fetchone()[0])


def run_migrations(connection: sqlite3.Connection) -> tuple[int, int]:
    """Применяет все недостающие миграции. Возвращает (from_version, to_version)."""
    start = current_version(connection)
    target = len(MIGRATIONS)
    for index in range(start, target):
        connection.executescript(MIGRATIONS[index])
        # PRAGMA user_version = N не принимает параметры — формируем литералом из доверенного int
        connection.execute(f"PRAGMA user_version = {index + 1}")
        connection.commit()
    return start, target

"""CRUD над таблицей stations и резолвинг активной станции для дашборда.

Состояние станции:
- enabled=1 — ingest принимается, станция видна на главной.
- enabled=0 — ingest отклоняется (или auto-зарегистрирована, но не разрешена
  владельцем).
- is_primary=1 — выбрана на главной по умолчанию (только одна).
"""
from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from typing import Any

from .db import use_connection


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _normalize_mac(mac: str) -> str:
    return mac.strip()


def list_stations(conn: sqlite3.Connection | None = None) -> list[dict[str, Any]]:
    with use_connection(conn) as connection:
        rows = connection.execute(
            """
            SELECT id, mac, name, sensor, location, battery_pct,
                   enabled, is_primary, created_at, updated_at
            FROM stations
            ORDER BY is_primary DESC, enabled DESC, name COLLATE NOCASE
            """
        ).fetchall()
    return [dict(row) for row in rows]


def list_enabled(conn: sqlite3.Connection | None = None) -> list[dict[str, Any]]:
    with use_connection(conn) as connection:
        rows = connection.execute(
            """
            SELECT id, mac, name, sensor, location, battery_pct,
                   enabled, is_primary, created_at, updated_at
            FROM stations
            WHERE enabled = 1
            ORDER BY is_primary DESC, name COLLATE NOCASE
            """
        ).fetchall()
    return [dict(row) for row in rows]


def get_by_id(station_id: int, conn: sqlite3.Connection | None = None) -> dict[str, Any] | None:
    with use_connection(conn) as connection:
        row = connection.execute(
            "SELECT * FROM stations WHERE id = ?",
            (station_id,),
        ).fetchone()
    return dict(row) if row else None


def get_by_mac(mac: str, conn: sqlite3.Connection | None = None) -> dict[str, Any] | None:
    with use_connection(conn) as connection:
        row = connection.execute(
            "SELECT * FROM stations WHERE mac = ?",
            (_normalize_mac(mac),),
        ).fetchone()
    return dict(row) if row else None


def get_primary(conn: sqlite3.Connection | None = None) -> dict[str, Any] | None:
    with use_connection(conn) as connection:
        row = connection.execute(
            """
            SELECT * FROM stations
            WHERE enabled = 1
            ORDER BY is_primary DESC, id ASC
            LIMIT 1
            """
        ).fetchone()
    return dict(row) if row else None


def create(
    *,
    mac: str,
    name: str,
    sensor: str = "",
    location: str = "",
    enabled: bool = True,
    is_primary: bool = False,
    conn: sqlite3.Connection | None = None,
) -> int:
    mac_n = _normalize_mac(mac)
    if not mac_n:
        raise ValueError("Mac is required")
    if not name.strip():
        raise ValueError("Name is required")
    now = _now()
    with use_connection(conn) as connection:
        if is_primary:
            connection.execute("UPDATE stations SET is_primary = 0")
        cursor = connection.execute(
            """
            INSERT INTO stations(mac, name, sensor, location, enabled, is_primary, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (mac_n, name.strip(), sensor.strip(), location.strip(),
             1 if enabled else 0, 1 if is_primary else 0, now, now),
        )
        new_id = int(cursor.lastrowid)
        # Если это первая станция — она автоматически становится primary,
        # даже если флаг не выставлен явно.
        cnt = connection.execute("SELECT COUNT(*) AS c FROM stations").fetchone()["c"]
        if cnt == 1 and not is_primary:
            connection.execute("UPDATE stations SET is_primary = 1 WHERE id = ?", (new_id,))
    return new_id


def update(
    station_id: int,
    *,
    name: str | None = None,
    sensor: str | None = None,
    location: str | None = None,
    enabled: bool | None = None,
    is_primary: bool | None = None,
    conn: sqlite3.Connection | None = None,
) -> bool:
    fields: list[str] = []
    values: list[Any] = []
    if name is not None:
        if not name.strip():
            raise ValueError("Name cannot be empty")
        fields.append("name = ?")
        values.append(name.strip())
    if sensor is not None:
        fields.append("sensor = ?")
        values.append(sensor.strip())
    if location is not None:
        fields.append("location = ?")
        values.append(location.strip())
    if enabled is not None:
        fields.append("enabled = ?")
        values.append(1 if enabled else 0)
    if not fields and is_primary is None:
        return False
    fields.append("updated_at = ?")
    values.append(_now())
    values.append(station_id)
    with use_connection(conn) as connection:
        if fields[:-1]:  # всё кроме updated_at
            connection.execute(
                f"UPDATE stations SET {', '.join(fields)} WHERE id = ?",
                values,
            )
        if is_primary is True:
            connection.execute("UPDATE stations SET is_primary = 0")
            connection.execute(
                "UPDATE stations SET is_primary = 1, updated_at = ? WHERE id = ?",
                (_now(), station_id),
            )
        elif is_primary is False:
            connection.execute(
                "UPDATE stations SET is_primary = 0, updated_at = ? WHERE id = ?",
                (_now(), station_id),
            )
    return True


def delete(station_id: int, conn: sqlite3.Connection | None = None) -> bool:
    with use_connection(conn) as connection:
        cursor = connection.execute("DELETE FROM stations WHERE id = ?", (station_id,))
        deleted = cursor.rowcount > 0
        # Если удалили primary — назначаем primary первой оставшейся enabled.
        if deleted:
            row = connection.execute(
                "SELECT id FROM stations WHERE is_primary = 1 LIMIT 1"
            ).fetchone()
            if not row:
                fallback = connection.execute(
                    "SELECT id FROM stations WHERE enabled = 1 ORDER BY id ASC LIMIT 1"
                ).fetchone()
                if fallback:
                    connection.execute(
                        "UPDATE stations SET is_primary = 1, updated_at = ? WHERE id = ?",
                        (_now(), fallback["id"]),
                    )
    return deleted


def upsert_unknown(mac: str, conn: sqlite3.Connection | None = None) -> dict[str, Any]:
    """Создаёт disabled-запись для нового mac (auto-register режим).

    Если mac уже есть — возвращает существующую запись без изменений.
    """
    mac_n = _normalize_mac(mac)
    existing = get_by_mac(mac_n, conn=conn)
    if existing:
        return existing
    now = _now()
    with use_connection(conn) as connection:
        connection.execute(
            """
            INSERT INTO stations(mac, name, sensor, location, enabled, is_primary, created_at, updated_at)
            VALUES (?, ?, '', '', 0, 0, ?, ?)
            """,
            (mac_n, mac_n, now, now),
        )
    return get_by_mac(mac_n, conn=conn) or {}

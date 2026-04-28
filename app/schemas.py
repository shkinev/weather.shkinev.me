"""Pydantic-модели для API-ответов.

Используются как response_model в FastAPI: дают строгий JSON-контракт,
автодокументацию /docs и валидацию выхода. Шаблоны Jinja продолжают
работать с dict-ами, которые возвращают функции в db.py — модели
применяются только на API-границе.
"""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class _Loose(BaseModel):
    # Разрешаем лишние поля: db.py может расширяться без обязательной
    # синхронизации со схемами.
    model_config = ConfigDict(extra="allow")


# ---------- Sensor / snapshot ----------

class SensorReading(_Loose):
    sensor_id: str
    sensor_name: str
    value: float
    unit: str


class Snapshot(_Loose):
    batch_id: int
    device_mac: str
    received_at: str
    received_local: str
    received_ago: str
    received_freshness: str
    primary_readings: list[SensorReading]
    readings: list[SensorReading]


class CurrentResponse(_Loose):
    status: str
    snapshot: Optional[Snapshot] = None


# ---------- Extremes ----------

class ExtremeValue(_Loose):
    value: float
    unit: str
    time: str
    datetime_local: str


class Extremes(_Loose):
    date: str
    sensor_id: Optional[str] = None
    min: Optional[ExtremeValue] = None
    max: Optional[ExtremeValue] = None


# ---------- Comfort ----------

class _Measurement(_Loose):
    value: float
    unit: str


class ComfortRisk(_Loose):
    level: str
    state: str
    description: str
    score: int
    reasons: list[str]
    risk: Optional[str] = None
    temperature: _Measurement
    humidity: _Measurement
    pressure: _Measurement


# ---------- Chart series ----------

class ChartPoint(_Loose):
    x: str
    y: float


class ChartSeriesItem(_Loose):
    label: str
    unit: str
    points: list[ChartPoint]


class ChartSeries(_Loose):
    hours: int
    days: float
    series: dict[str, ChartSeriesItem]


# ---------- Uptime ----------

class UptimeMonitor(_Loose):
    hours: int
    labels: list[str]
    points: list[int]
    availability: float
    last_seen_ago: str
    freshness: str


# ---------- Period comparison ----------

class ComparisonRow(_Loose):
    label: str
    date: str
    avg: Optional[float] = None
    count: int
    delta: Optional[float] = None


class ComparisonBlock(_Loose):
    today_avg: Optional[float] = None
    today_count: int
    rows: list[ComparisonRow]


class HourValue(_Loose):
    hour: int
    value: Optional[float] = None


class _TodayAggregate(_Loose):
    avg: Optional[float] = None
    count: int


class PeriodComparison(_Loose):
    today_date: str
    today: _TodayAggregate
    day: ComparisonBlock
    night: ComparisonBlock
    series: dict[str, list[HourValue]] = Field(default_factory=dict)


# ---------- Heatmap ----------

class Heatmap(_Loose):
    labels: list[str]
    hours: list[str]
    matrix: list[list[Optional[float]]]


# ---------- Anomaly calendar ----------

class AnomalyDay(_Loose):
    date: str
    day: int
    level: str
    reasons: list[str]
    has_data: bool


class AnomalyCalendar(_Loose):
    month: str
    days: list[AnomalyDay]


# ---------- Station status ----------

class StationStatus(_Loose):
    last_seen: str
    last_seen_ago: str
    freshness: str
    packets_24h: int
    packets_7d: int
    avg_interval_min: Optional[float] = None
    gaps_24h: int
    sensor_count: int
    missing_primary: list[str]


# ---------- Misc ----------

class StatusOk(_Loose):
    status: str = "ok"


class IngestResult(_Loose):
    status: str
    received_at: str
    devices: int
    measurements: int

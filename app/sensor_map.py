from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SensorMeta:
    label: str
    unit: str | None = None


SENSOR_MAP: dict[str, SensorMeta] = {
    "T1": SensorMeta("Температура (BME280)", "°C"),
    "T2": SensorMeta("Температура (DS18B20)", "°C"),
    "T3": SensorMeta("Температура (SHT3x)", "°C"),
    "T4": SensorMeta("Температура (BME680)", "°C"),
    "T5": SensorMeta("Температура чипа", "°C"),
    "DEW": SensorMeta("Точка росы", "°C"),
    "1": SensorMeta("Абсолютная влажность", "г/м³"),
    "RH": SensorMeta("Влажность", "%"),
    "H1": SensorMeta("Влажность (SHT3x)", "%"),
    "H2": SensorMeta("Влажность (BME680)", "%"),
    "PRESS": SensorMeta("Давление", "мм рт. ст."),
    "HPA": SensorMeta("Давление (BME680)", "мм рт. ст."),
    "1DIR": SensorMeta("Направление ветра", "°"),
    "WS": SensorMeta("Скорость ветра", "м/с"),
    "WS1": SensorMeta("Скорость ветра (ср. 5 мин)", "м/с"),
    "VOLT": SensorMeta("Напряжение", "В"),
    "PM2": SensorMeta("PM2.5", "мкг/м³"),
    "PM10": SensorMeta("PM10", "мкг/м³"),
    "RAD1": SensorMeta("Радиация (динамич.)", "мкР/ч"),
    "RAD2": SensorMeta("Радиация (статич.)", "мкР/ч"),
    "3": SensorMeta("CPM (текущее)"),
    "4": SensorMeta("CPM (макс.)"),
    "RAIN": SensorMeta("Осадки за 5 мин", "мм"),
    "RAIN2": SensorMeta("Осадки за 24 ч", "мм"),
    "L1": SensorMeta("Освещенность (TSL2561)", "лк"),
    "L2": SensorMeta("Освещенность (BH1750)", "лк"),
    "L3": SensorMeta("Освещенность (LTR390)", "лк"),
    "UV1": SensorMeta("УФ-индекс", "UV"),
}


PRIMARY_SENSOR_IDS = ("T1", "RH", "PRESS", "WS", "RAIN2", "PM2", "PM10")


def sensor_label(sensor_id: str) -> str:
    return SENSOR_MAP.get(sensor_id, SensorMeta(sensor_id)).label


def sensor_unit(sensor_id: str, payload_unit: str | None = None) -> str:
    meta = SENSOR_MAP.get(sensor_id)
    if payload_unit:
        return payload_unit
    if meta and meta.unit:
        return meta.unit
    return ""

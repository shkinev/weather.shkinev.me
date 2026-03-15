from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SensorMeta:
    label: str
    unit: str | None = None


SENSOR_MAP: dict[str, SensorMeta] = {
    "T1": SensorMeta("Temperature (BME280)", "C"),
    "T2": SensorMeta("Temperature (DS18B20)", "C"),
    "T3": SensorMeta("Temperature (SHT3x)", "C"),
    "T4": SensorMeta("Temperature (BME680)", "C"),
    "T5": SensorMeta("Device Chip Temperature", "C"),
    "DEW": SensorMeta("Dew Point", "C"),
    "1": SensorMeta("Absolute Humidity", "g/m3"),
    "RH": SensorMeta("Humidity", "%"),
    "H1": SensorMeta("Humidity (SHT3x)", "%"),
    "H2": SensorMeta("Humidity (BME680)", "%"),
    "PRESS": SensorMeta("Pressure", "mmHg"),
    "HPA": SensorMeta("Pressure (BME680)", "mmHg"),
    "1DIR": SensorMeta("Wind Direction", "deg"),
    "WS": SensorMeta("Wind Speed", "m/s"),
    "WS1": SensorMeta("Wind Speed 5m Avg", "m/s"),
    "VOLT": SensorMeta("Voltage", "V"),
    "PM2": SensorMeta("PM2.5", "ug/m3"),
    "PM10": SensorMeta("PM10", "ug/m3"),
    "RAD1": SensorMeta("Radiation Dynamic", "uR/h"),
    "RAD2": SensorMeta("Radiation Static", "uR/h"),
    "3": SensorMeta("CPM Current"),
    "4": SensorMeta("CPM Max"),
    "RAIN": SensorMeta("Rain 5m", "mm"),
    "RAIN2": SensorMeta("Rain 24h", "mm"),
    "L1": SensorMeta("Light (TSL2561)", "lux"),
    "L2": SensorMeta("Light (BH1750)", "lux"),
    "L3": SensorMeta("Light (LTR390)", "lux"),
    "UV1": SensorMeta("UV Index", "UV"),
}


PRIMARY_SENSOR_IDS = ("T1", "T2", "RH", "PRESS", "WS", "WS1", "1DIR", "RAIN2", "PM2", "PM10")


def sensor_label(sensor_id: str) -> str:
    return SENSOR_MAP.get(sensor_id, SensorMeta(sensor_id)).label


def sensor_unit(sensor_id: str, payload_unit: str | None = None) -> str:
    meta = SENSOR_MAP.get(sensor_id)
    if payload_unit:
        return payload_unit
    if meta and meta.unit:
        return meta.unit
    return ""

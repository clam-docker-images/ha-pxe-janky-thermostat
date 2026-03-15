import json
import os
from pathlib import Path
from typing import Any, Optional


DEFAULT_CONFIG_PATH = "/config/config.json"

DEFAULT_CONFIG: dict[str, Any] = {
    "mqtt_broker": "localhost",
    "mqtt_port": 1883,
    "mqtt_username": None,
    "mqtt_password": None,
    "schedule": [],
    "min_temp": 20.0,
    "max_temp": 28.0,
    "posmin": 1034,
    "posmax": 24600,
    "posmargin": 50,
    "speed": 50.0,
    "lograte": 10,
    "updaterate": 15,
    "updir": 1,
    "i2c_bus": 0,
    "rgpio_addr": "localhost",
    "rgpio_port": 8889,
    "loglevel": "WARNING",
}


def _parse_optional_str(value: str) -> Optional[str]:
    value = value.strip()
    return value or None


def _parse_schedule(value: str) -> list[str]:
    parsed = json.loads(value)
    if not isinstance(parsed, list) or not all(isinstance(entry, str) for entry in parsed):
        raise ValueError("THERMOSTAT_SCHEDULE must be a JSON array of strings")
    return parsed


ENV_OVERRIDES = {
    "mqtt_broker": ("MQTT_BROKER", str),
    "mqtt_port": ("MQTT_PORT", int),
    "mqtt_username": ("MQTT_USERNAME", _parse_optional_str),
    "mqtt_password": ("MQTT_PASSWORD", _parse_optional_str),
    "schedule": ("THERMOSTAT_SCHEDULE", _parse_schedule),
    "min_temp": ("THERMOSTAT_MIN_TEMP", float),
    "max_temp": ("THERMOSTAT_MAX_TEMP", float),
    "posmin": ("THERMOSTAT_POSMIN", float),
    "posmax": ("THERMOSTAT_POSMAX", float),
    "posmargin": ("THERMOSTAT_POSMARGIN", float),
    "speed": ("THERMOSTAT_SPEED", float),
    "lograte": ("THERMOSTAT_LOGRATE", int),
    "updaterate": ("THERMOSTAT_UPDATERATE", int),
    "updir": ("THERMOSTAT_UPDIR", int),
    "i2c_bus": ("I2C_BUS", int),
    "rgpio_addr": ("RGPIO_ADDR", str),
    "rgpio_port": ("RGPIO_PORT", int),
    "loglevel": ("THERMOSTAT_LOGLEVEL", str),
}


def load_runtime_config(config_path: str, config_required: bool = False) -> dict[str, Any]:
    config: dict[str, Any] = dict(DEFAULT_CONFIG)
    path = Path(config_path)
    if path.exists():
        with path.open("r", encoding="utf-8") as handle:
            file_config = json.load(handle)
        if not isinstance(file_config, dict):
            raise ValueError(f"Config file must contain a JSON object: {path}")
        config.update(file_config)
    elif config_required:
        raise FileNotFoundError(f"Config file not found: {path}")

    apply_env_overrides(config)
    return normalize_config(config)


def apply_env_overrides(config: dict[str, Any]) -> None:
    for key, (env_name, parser) in ENV_OVERRIDES.items():
        raw_value = os.getenv(env_name)
        if raw_value is None:
            continue
        config[key] = parser(raw_value)


def normalize_config(config: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(config)
    normalized["mqtt_broker"] = str(normalized["mqtt_broker"]).strip()
    normalized["mqtt_port"] = int(normalized["mqtt_port"])
    normalized["mqtt_username"] = _normalize_optional_string(normalized["mqtt_username"])
    normalized["mqtt_password"] = _normalize_optional_string(normalized["mqtt_password"])
    normalized["min_temp"] = float(normalized["min_temp"])
    normalized["max_temp"] = float(normalized["max_temp"])
    normalized["posmin"] = float(normalized["posmin"])
    normalized["posmax"] = float(normalized["posmax"])
    normalized["posmargin"] = float(normalized["posmargin"])
    normalized["speed"] = _normalize_speed(normalized["speed"])
    normalized["lograte"] = int(normalized["lograte"])
    normalized["updaterate"] = int(normalized["updaterate"])
    normalized["updir"] = int(normalized["updir"])
    normalized["i2c_bus"] = int(normalized["i2c_bus"])
    normalized["rgpio_addr"] = str(normalized["rgpio_addr"]).strip()
    normalized["rgpio_port"] = int(normalized["rgpio_port"])
    normalized["loglevel"] = str(normalized["loglevel"]).upper().strip()
    normalized["schedule"] = _normalize_schedule(normalized.get("schedule", []))

    if normalized["updir"] not in (-1, 1):
        raise ValueError("updir must be either 1 or -1")

    if not normalized["mqtt_broker"]:
        raise ValueError("mqtt_broker cannot be empty")

    if not normalized["rgpio_addr"]:
        raise ValueError("rgpio_addr cannot be empty")

    if normalized["mqtt_port"] < 1:
        raise ValueError("mqtt_port must be at least 1")

    if normalized["rgpio_port"] < 1:
        raise ValueError("rgpio_port must be at least 1")

    if normalized["speed"] > 100:
        raise ValueError("speed must not exceed 100")

    if normalized["lograte"] < 1:
        raise ValueError("lograte must be at least 1")

    if normalized["updaterate"] < 1:
        raise ValueError("updaterate must be at least 1")

    if normalized["loglevel"] not in {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"}:
        raise ValueError("loglevel must be one of CRITICAL, ERROR, WARNING, INFO, DEBUG")

    return normalized


def apply_runtime_environment(config: dict[str, Any]) -> None:
    os.environ["I2C_BUS"] = str(config["i2c_bus"])
    os.environ["RGPIO_ADDR"] = str(config["rgpio_addr"])
    os.environ["RGPIO_PORT"] = str(config["rgpio_port"])


def _normalize_optional_string(value: Any) -> Optional[str]:
    if value is None:
        return None
    return _parse_optional_str(str(value))


def _normalize_speed(value: Any) -> float:
    speed = float(value)
    if speed < 0:
        raise ValueError("speed must be non-negative")
    if speed > 1000:
        speed /= 10000.0
    return speed


def _normalize_schedule(schedule: Any) -> list[dict[str, Any]]:
    if not isinstance(schedule, list):
        raise ValueError("schedule must be a list of strings")

    normalized_schedule: list[dict[str, Any]] = []
    for row in schedule:
        if not isinstance(row, str):
            raise ValueError("schedule entries must be strings")
        row = row.strip()
        if not row:
            continue
        parts = row.split(maxsplit=1)
        if len(parts) != 2:
            raise ValueError(f"Invalid schedule entry: {row!r}")
        timestamp, temp = parts
        normalized_schedule.append(
            {
                "timestamp": timestamp.strip()[0:5],
                "temp": float(temp.lower().replace("c", "")),
            }
        )

    normalized_schedule.sort(key=lambda entry: entry["timestamp"])
    return normalized_schedule

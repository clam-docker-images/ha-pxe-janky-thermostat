import json
import os
from pathlib import Path
from typing import Any, Optional

from internals.schedule import normalize_schedule


DEFAULT_CONFIG_PATH = "/config/config.json"

DEFAULT_CONFIG: dict[str, Any] = {
    "mqtt_broker": "localhost",
    "mqtt_port": 1883,
    "mqtt_username": None,
    "mqtt_password": None,
    "schedule": [],
    "schedule_slots": 6,
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

MQTT_ENV_IMPORTS: dict[str, tuple[str, ...]] = {
    "mqtt_broker": ("MQTT_BROKER", "MQTT_HOST"),
    "mqtt_port": ("MQTT_PORT",),
    "mqtt_username": ("MQTT_USERNAME",),
    "mqtt_password": ("MQTT_PASSWORD",),
}


def _parse_optional_str(value: str) -> Optional[str]:
    value = value.strip()
    return value or None


def load_runtime_config(config_path: str = DEFAULT_CONFIG_PATH) -> dict[str, Any]:
    config: dict[str, Any] = dict(DEFAULT_CONFIG)
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    with path.open("r", encoding="utf-8") as handle:
        file_config = json.load(handle)
    if not isinstance(file_config, dict):
        raise ValueError(f"Config file must contain a JSON object: {path}")
    config.update(file_config)
    apply_mqtt_env_imports(config, file_config)

    return normalize_config(config)


def apply_mqtt_env_imports(config: dict[str, Any], file_config: dict[str, Any]) -> None:
    for key, env_names in MQTT_ENV_IMPORTS.items():
        if key in file_config and file_config[key] is not None:
            continue
        for env_name in env_names:
            raw_value = os.getenv(env_name)
            if raw_value is None:
                continue
            config[key] = raw_value
            break


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
    normalized["schedule_slots"] = int(normalized["schedule_slots"])

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

    if normalized["schedule_slots"] < 1:
        raise ValueError("schedule_slots must be at least 1")

    if normalized["lograte"] < 1:
        raise ValueError("lograte must be at least 1")

    if normalized["updaterate"] < 1:
        raise ValueError("updaterate must be at least 1")

    if normalized["loglevel"] not in {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"}:
        raise ValueError("loglevel must be one of CRITICAL, ERROR, WARNING, INFO, DEBUG")

    return normalized


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
    return normalize_schedule(schedule)

from typing import Any


def normalize_schedule(schedule: Any) -> list[dict[str, Any]]:
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
                "timestamp": normalize_schedule_timestamp(timestamp),
                "temp": float(temp.lower().replace("c", "")),
            }
        )

    normalized_schedule.sort(key=lambda entry: entry["timestamp"])
    return normalized_schedule


def normalize_schedule_timestamp(value: Any) -> str:
    text = str(value).strip()
    if not text:
        return ""
    if len(text) < 5 or text[2] != ":":
        raise ValueError(f"Invalid schedule timestamp: {value!r}")

    timestamp = text[:5]
    hour = int(timestamp[:2])
    minute = int(timestamp[3:5])
    if hour < 0 or hour > 23 or minute < 0 or minute > 59:
        raise ValueError(f"Invalid schedule timestamp: {value!r}")
    return timestamp


def format_schedule_row(row: dict[str, Any]) -> str:
    return f'{row["timestamp"]} {float(row["temp"]):.1f}'


def summarize_schedule(schedule: list[dict[str, Any]]) -> str:
    if not schedule:
        return "empty"
    return ", ".join(format_schedule_row(row) for row in schedule)

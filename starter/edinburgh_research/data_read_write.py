#
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from sovereign_agent.errors import ToolError
from sovereign_agent.session.directory import Session

SAMPLE_DATA = Path(__file__).parent / "sample_data"
DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
TIME_PATTERN = re.compile(r"^\d{2}:\d{2}$")


def _tool_error(code: str, message: str) -> ToolError:
    """Create ToolError with the message argument required by sovereign-agent."""
    return ToolError(code, message)


def _load_json(file_path: Path) -> Any:
    if not file_path.exists():
        raise _tool_error(
            "SA_TOOL_DEPENDENCY_MISSING",
            f"Required JSON fixture does not exist: {file_path}",
        )

    with file_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _lowercase_strings(obj: Any) -> Any:
    """Recursively lowercase all string values."""
    if isinstance(obj, dict):
        return {key: _lowercase_strings(value) for key, value in obj.items()}

    if isinstance(obj, list):
        return [_lowercase_strings(item) for item in obj]

    if isinstance(obj, str):
        return obj.lower()

    return obj


def _validate_date(value: str) -> str:
    """Validate a YYYY-MM-DD date string."""
    date = value.strip()

    if not DATE_PATTERN.fullmatch(date):
        raise _tool_error(
            "SA_TOOL_INVALID_INPUT",
            f"date must use YYYY-MM-DD format, got: {value!r}",
        )

    return date


def _validate_time(value: str) -> str:
    """Validate a HH:MM time string."""
    time_value = value.strip()

    if not TIME_PATTERN.fullmatch(time_value):
        raise _tool_error(
            "SA_TOOL_INVALID_INPUT",
            f"time must use HH:MM format, got: {value!r}",
        )

    hour, minute = time_value.split(":")
    if int(hour) > 23 or int(minute) > 59:
        raise _tool_error(
            "SA_TOOL_INVALID_INPUT",
            f"time must be a valid 24-hour time, got: {value!r}",
        )

    return time_value


def load_venues() -> list[dict]:
    data = _load_json(SAMPLE_DATA / "venues.json")
    return _lowercase_strings(data)


def load_catering() -> dict:
    data = _load_json(SAMPLE_DATA / "catering.json")
    return _lowercase_strings(data)


def check_flyer_event_details(event_details: dict) -> dict:
    """Validate and normalise flyer event details.

    Required string fields are trimmed. Display text is lowercased to preserve
    previous behaviour. Date and time are format-validated. Numeric fields may
    be int/float or numeric strings.
    """
    required_fields = {
        "venue_name": str,
        "venue_address": str,
        "date": str,
        "time": str,
        "condition": str,
        "party_size": int,
        "temperature_c": int,
        "total_gbp": int,
        "deposit_required_gbp": int,
    }

    if not isinstance(event_details, dict):
        raise _tool_error(
            "SA_TOOL_INVALID_INPUT",
            "event_details must be a dictionary",
        )

    normalised = {}

    for key, expected_type in required_fields.items():
        if key not in event_details:
            raise _tool_error(
                "SA_TOOL_INVALID_INPUT",
                f"event_details is missing required field: {key}",
            )

        value = event_details[key]

        if expected_type is str:
            if value is None or not isinstance(value, str) or not value.strip():
                raise _tool_error(
                    "SA_TOOL_INVALID_INPUT",
                    f"event_details.{key} must be a non-empty string",
                )

            if key == "date":
                normalised[key] = _validate_date(value)
            elif key == "time":
                normalised[key] = _validate_time(value)
            else:
                normalised[key] = value.strip().lower()

        elif expected_type is int:
            if isinstance(value, bool):
                raise _tool_error(
                    "SA_TOOL_INVALID_INPUT",
                    f"event_details.{key} must be a number, not a boolean",
                )

            if isinstance(value, int):
                normalised[key] = value

            elif isinstance(value, float):
                normalised[key] = round(value)

            elif isinstance(value, str):
                stripped = value.strip()

                if stripped.replace(".", "", 1).isdigit():
                    normalised[key] = round(float(stripped))
                else:
                    raise _tool_error(
                        "SA_TOOL_INVALID_INPUT",
                        f"event_details.{key} must be numeric, got: {value!r}",
                    )

            else:
                raise _tool_error(
                    "SA_TOOL_INVALID_INPUT",
                    f"event_details.{key} must be numeric",
                )

    return normalised


def write_flyer(session: Session, html: str) -> dict:
    """Write flyer HTML to workspace and return metadata."""
    flyer_path = session.workspace_dir / "flyer.html"
    flyer_path.parent.mkdir(parents=True, exist_ok=True)
    flyer_path.write_text(html, encoding="utf-8")

    return {
        "path": "workspace/flyer.html",
        "bytes_written": len(html.encode("utf-8")),
    }


__all__ = [
    "check_flyer_event_details",
    "load_catering",
    "load_venues",
    "write_flyer",
]


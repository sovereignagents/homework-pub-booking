"""Ex6 — booking payload normaliser.

Bridges the sovereign-agent data-dict conventions and Rasa's expected
message shape. RasaStructuredHalf calls normalise_booking_payload()
before sending anything over HTTP.

The validator normalises:
  * date       → YYYY-MM-DD
  * currency   → "£500" / "500 gbp" / 500 → int deposit_gbp
  * party_size → "6" / "6 people" / 6 → int
  * time       → "7:30pm" / "19:30" / "noon" → HH:MM
  * venue_id   → "Haymarket Tap" → "haymarket_tap"
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass
from typing import Any

DEFAULT_DATE_TODAY = "2026-04-25"
DEFAULT_DATE_TOMORROW = "2026-04-26"
DEFAULT_DURATION_HOURS = 3
DEFAULT_CATERING_TIER = "bar_snacks"

VALID_CATERING_TIERS = frozenset(
    {
        "drinks_only",
        "bar_snacks",
        "sit_down_meal",
        "three_course_meal",
    }
)

MONTH_NAMES = {
    "january": 1,
    "jan": 1,
    "february": 2,
    "feb": 2,
    "march": 3,
    "mar": 3,
    "april": 4,
    "apr": 4,
    "may": 5,
    "june": 6,
    "jun": 6,
    "july": 7,
    "jul": 7,
    "august": 8,
    "aug": 8,
    "september": 9,
    "sep": 9,
    "sept": 9,
    "october": 10,
    "oct": 10,
    "november": 11,
    "nov": 11,
    "december": 12,
    "dec": 12,
}

GBP_PATTERN = re.compile(
    r"^\s*£?\s*(\d+(?:\.\d+)?)\s*(?:gbp)?\s*$",
    re.IGNORECASE,
)
ISO_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
TEXT_DATE_PATTERN = re.compile(
    r"^(\d{1,2})(?:st|nd|rd|th)?\s+(\w+)(?:\s+(\d{4}))?$",
)
TIME_24H_PATTERN = re.compile(r"^(\d{1,2}):?(\d{2})$")
TIME_12H_PATTERN = re.compile(r"^(\d{1,2})(?:[:.]?(\d{2}))?\s*(am|pm)$")
PARTY_SIZE_PATTERN = re.compile(r"^\s*(\d+)")


@dataclass(frozen=True)
class NormalisedBooking:
    """Clean, Rasa-ready booking payload. All fields are present."""

    action: str
    venue_id: str
    date: str
    time: str
    party_size: int
    deposit_gbp: int
    duration_hours: int = DEFAULT_DURATION_HOURS
    catering_tier: str = DEFAULT_CATERING_TIER


class ValidationFailed(ValueError):  # noqa: N818
    """Raised when a booking payload cannot be normalised safely."""


def normalise_booking_payload(raw: dict) -> dict:
    """Normalise loop-half handoff data into Rasa's REST webhook message shape."""
    if not isinstance(raw, dict):
        raise ValidationFailed(f"expected booking payload dict, got {type(raw).__name__}")

    booking = NormalisedBooking(
        action=str(raw.get("action") or "confirm_booking"),
        venue_id=canonicalise_venue_id(_required(raw, "venue_id")),
        date=parse_date_iso(_required(raw, "date")),
        time=parse_time_24h(_required(raw, "time")),
        party_size=parse_party_size(_required(raw, "party_size")),
        deposit_gbp=parse_deposit_gbp(raw),
        duration_hours=parse_duration_hours(raw.get("duration_hours")),
        catering_tier=parse_catering_tier(raw.get("catering_tier")),
    )

    return build_rasa_message(booking)


def build_rasa_message(booking: NormalisedBooking) -> dict:
    """Build Rasa REST webhook payload from a normalised booking."""
    stable_suffix = hashlib.sha1(
        f"{booking.venue_id}-{booking.date}-{booking.time}".encode()
    ).hexdigest()[:8]

    return {
        "sender": f"homework-{stable_suffix}",
        "message": "/confirm_booking",
        "metadata": {
            "booking": asdict(booking),
        },
    }


def _required(raw: dict, field_name: str) -> Any:
    """Return a required field or raise a clear validation error."""
    value = raw.get(field_name)

    if value is None:
        raise ValidationFailed(f"missing {field_name}")

    if isinstance(value, str) and not value.strip():
        raise ValidationFailed(f"{field_name} must not be empty")

    return value


def parse_date_iso(raw: Any) -> str:
    """Parse supported date inputs into YYYY-MM-DD."""
    value = str(raw).strip().lower()

    if not value:
        raise ValidationFailed("date must not be empty")

    if value == "today":
        return DEFAULT_DATE_TODAY

    if value == "tomorrow":
        return DEFAULT_DATE_TOMORROW

    if ISO_DATE_PATTERN.fullmatch(value):
        return value

    match = TEXT_DATE_PATTERN.fullmatch(value)
    if not match:
        raise ValidationFailed(f"cannot parse date: {raw!r}")

    day = int(match.group(1))
    month_name = match.group(2)
    year = int(match.group(3)) if match.group(3) else 2026

    month = MONTH_NAMES.get(month_name)
    if month is None:
        raise ValidationFailed(f"unknown month in date: {month_name!r}")

    if day < 1 or day > 31:
        raise ValidationFailed(f"invalid day in date: {day}")

    return f"{year:04d}-{month:02d}-{day:02d}"


def parse_currency_gbp(raw: str | int | float) -> int:
    """Parse GBP values into integer pounds."""
    if isinstance(raw, bool):
        raise ValidationFailed("currency must be numeric, not boolean")

    if isinstance(raw, int | float):
        if raw < 0:
            raise ValidationFailed(f"negative currency: {raw!r}")
        return int(raw)

    match = GBP_PATTERN.fullmatch(str(raw))
    if not match:
        raise ValidationFailed(f"cannot parse currency: {raw!r}")

    value = float(match.group(1))
    if value < 0:
        raise ValidationFailed(f"negative currency: {raw!r}")

    return int(value)


def parse_deposit_gbp(raw: dict) -> int:
    """Read deposit_gbp or deposit from raw booking data."""
    if raw.get("deposit_gbp") is not None:
        return parse_currency_gbp(raw["deposit_gbp"])

    if raw.get("deposit") is not None:
        return parse_currency_gbp(raw["deposit"])

    return 0


def parse_time_24h(raw: Any) -> str:
    """Parse time values into HH:MM 24-hour format."""
    value = str(raw).strip().lower()

    if not value:
        raise ValidationFailed("time must not be empty")

    if value in {"noon", "midday"}:
        return "12:00"

    if value == "midnight":
        return "00:00"

    match = TIME_24H_PATTERN.fullmatch(value)
    if match:
        hour = int(match.group(1))
        minute = int(match.group(2))
        return _format_valid_time(hour, minute, raw)

    match = TIME_12H_PATTERN.fullmatch(value)
    if match:
        hour = int(match.group(1))
        minute = int(match.group(2) or 0)
        meridiem = match.group(3)

        if hour < 1 or hour > 12:
            raise ValidationFailed(f"invalid 12-hour time: {raw!r}")

        if meridiem == "pm" and hour < 12:
            hour += 12

        if meridiem == "am" and hour == 12:
            hour = 0

        return _format_valid_time(hour, minute, raw)

    raise ValidationFailed(f"cannot parse time: {raw!r}")


def _format_valid_time(hour: int, minute: int, raw: Any) -> str:
    """Validate hour/minute values and format as HH:MM."""
    if hour < 0 or hour > 23 or minute < 0 or minute > 59:
        raise ValidationFailed(f"invalid time: {raw!r}")

    return f"{hour:02d}:{minute:02d}"


def canonicalise_venue_id(raw: Any) -> str:
    """Canonicalise venue identifiers for policy/Rasa processing."""
    value = str(raw).strip().lower()

    if not value:
        raise ValidationFailed("venue_id must not be empty")

    value = re.sub(r"[\s\-]+", "_", value)
    value = re.sub(r"[^a-z0-9_]", "", value)
    value = re.sub(r"_+", "_", value).strip("_")

    if not value:
        raise ValidationFailed(f"cannot canonicalise venue_id: {raw!r}")

    return value


def parse_party_size(raw: Any) -> int:
    """Parse party size into a positive integer."""
    if isinstance(raw, bool):
        raise ValidationFailed("party size must be numeric, not boolean")

    if isinstance(raw, int):
        party_size = raw
    else:
        match = PARTY_SIZE_PATTERN.match(str(raw))
        if not match:
            raise ValidationFailed(f"cannot parse party size: {raw!r}")
        party_size = int(match.group(1))

    if party_size < 1:
        raise ValidationFailed(f"party size must be >= 1, got {party_size}")

    return party_size


def parse_duration_hours(raw: Any) -> int:
    """Parse duration_hours, defaulting safely when absent."""
    if raw is None or raw == "":
        return DEFAULT_DURATION_HOURS

    if isinstance(raw, bool):
        raise ValidationFailed("duration_hours must be numeric, not boolean")

    try:
        duration = int(raw)
    except (TypeError, ValueError) as exc:
        raise ValidationFailed(f"cannot parse duration_hours: {raw!r}") from exc

    if duration < 1:
        raise ValidationFailed(f"duration_hours must be >= 1, got {duration}")

    return duration


def parse_catering_tier(raw: Any) -> str:
    """Parse and validate catering tier."""
    if raw is None or raw == "":
        return DEFAULT_CATERING_TIER

    tier = str(raw).strip().lower()

    if tier not in VALID_CATERING_TIERS:
        raise ValidationFailed(f"unsupported catering_tier: {raw!r}")

    return tier


__all__ = [
    "NormalisedBooking",
    "ValidationFailed",
    "build_rasa_message",
    "canonicalise_venue_id",
    "normalise_booking_payload",
    "parse_catering_tier",
    "parse_currency_gbp",
    "parse_date_iso",
    "parse_deposit_gbp",
    "parse_duration_hours",
    "parse_party_size",
    "parse_time_24h",
]

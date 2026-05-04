"""Ex6 — booking payload normaliser.

Bridges the sovereign-agent data-dict conventions and Rasa's expected
message shape. Your RasaStructuredHalf calls normalise_booking_payload()
before sending anything over HTTP.

The grader checks that your validator normalises at least 3 of these
5 fields:
  * date           → 'YYYY-MM-DD' ISO-8601, Edinburgh timezone assumed
  * currency       → '£500' or '500 gbp' → int (500) in deposit_gbp
  * party_size     → str '6' → int 6; reject < 1
  * time           → '7:30pm' / '19:30' → 'HH:MM' 24-hour
  * venue_id       → canonicalise whitespace and case; e.g. 'Haymarket Tap' → 'haymarket_tap'
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class NormalisedBooking:
    """Clean, Rasa-ready booking payload. All fields are present."""

    action: str
    venue_id: str
    date: str
    time: str
    party_size: int
    deposit_gbp: int
    duration_hours: int = 3
    catering_tier: str = "bar_snacks"


class ValidationFailed(ValueError):  # noqa: N818
    """Raised by normalise_booking_payload when input is beyond saving.

    The run() method in RasaStructuredHalf catches this and returns a
    HalfResult with next_action=escalate rather than crashing.

    Named `ValidationFailed` (not `ValidationError`) to match the
    dialogue-language convention used in Rasa's own codebase. The
    noqa above suppresses ruff's N818 rule, which prefers the
    `Error` suffix.
    """


# ---------------------------------------------------------------------------
# TODO — normalise_booking_payload
# ---------------------------------------------------------------------------
def normalise_booking_payload(raw: dict) -> dict:
    """Take a data dict from the loop half's handoff and produce a Rasa-shaped message."""
    import hashlib

    if not isinstance(raw, dict):
        raise ValidationFailed(f"expected dict, got {type(raw).__name__}")

    venue_id_raw = raw.get("venue_id")
    if not venue_id_raw:
        raise ValidationFailed("missing venue_id")
    venue_id = canonicalise_venue_id(venue_id_raw)

    # TODO: Extract and normalise 'date' using _normalise_date. If missing, raise ValidationFailed("missing date").
    
    # TODO: Extract and parse 'time' using parse_time_24h. If missing, raise ValidationFailed("missing time").

    # TODO: Extract and parse 'party_size' using parse_party_size.

    # TODO: Extract and parse 'deposit' (as deposit_gbp) using parse_currency_gbp. Remember to handle if it's not present (default to 0).

    duration = raw.get("duration_hours", 3)
    if isinstance(duration, str) and duration.isdigit():
        duration = int(duration)
    if not isinstance(duration, int) or duration < 1:
        duration = 3

    catering = raw.get("catering_tier", "bar_snacks")
    if catering not in ("drinks_only", "bar_snacks", "sit_down_meal", "three_course_meal"):
        catering = "bar_snacks"

    # TODO: Generate a 'stable_suffix' string using hashlib.sha1 on f"{venue_id}-{date}-{time}".encode().
    # Take the first 8 characters of the hex digest.
    
    # TODO: Return a dictionary structured for Rasa:
    # {
    #     "sender": f"homework-{stable_suffix}",
    #     "message": "/confirm_booking",
    #     "metadata": {
    #         "booking": {
    #             "venue_id": venue_id,
    #             "date": <your date var>,
    #             "time": <your time var>,
    #             "party_size": <your party var>,
    #             "deposit_gbp": <your deposit var>,
    #             "duration_hours": duration,
    #             "catering_tier": catering,
    #         }
    #     },
    # }
    raise NotImplementedError("TODO: Implement the rest of normalise_booking_payload")


# ---------------------------------------------------------------------------
# Date helper — added by solution
# ---------------------------------------------------------------------------
_MONTH_NAMES = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "sept": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}


def _normalise_date(raw: str) -> str:
    s = str(raw).strip().lower()
    if s == "today":
        return "2026-04-25"
    if s == "tomorrow":
        return "2026-04-26"
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
        return s
    m = re.match(r"(\d{1,2})(?:st|nd|rd|th)?\s+(\w+)(?:\s+(\d{4}))?", s)
    if m:
        day = int(m.group(1))
        month_name = m.group(2)
        year = int(m.group(3)) if m.group(3) else 2026
        if month_name not in _MONTH_NAMES:
            raise ValidationFailed(f"unknown month: {month_name!r}")
        return f"{year:04d}-{_MONTH_NAMES[month_name]:02d}-{day:02d}"
    raise ValidationFailed(f"cannot parse date: {raw!r}")


# ---------------------------------------------------------------------------
# Helpers — provided. You may use them or write your own.
# ---------------------------------------------------------------------------
_GBP_PATTERN = re.compile(r"£?\s*(\d+(?:\.\d+)?)\s*(?:gbp|GBP)?", re.IGNORECASE)


def parse_currency_gbp(raw: str | int | float) -> int:
    """Parse '£500', '500', '500 GBP', 500, 500.0 → 500 (int pounds).
    Rejects negative and non-numeric input."""
    if isinstance(raw, (int, float)):
        if raw < 0:
            raise ValidationFailed(f"negative currency: {raw!r}")
        return int(raw)
    m = _GBP_PATTERN.search(str(raw).strip())
    if not m:
        raise ValidationFailed(f"cannot parse currency: {raw!r}")
    value = float(m.group(1))
    if value < 0:
        raise ValidationFailed(f"negative currency: {raw!r}")
    return int(value)


def parse_time_24h(raw: str) -> str:
    """'7:30pm' → '19:30'. '19:30' → '19:30'. 'noon' → '12:00'."""
    s = str(raw).strip().lower()
    if s in ("noon", "midday"):
        return "12:00"
    if s in ("midnight",):
        return "00:00"
    # 24-hour: '19:30' or '1930'
    if m := re.fullmatch(r"(\d{1,2}):?(\d{2})", s):
        h, mm = int(m.group(1)), int(m.group(2))
        if 0 <= h <= 23 and 0 <= mm <= 59:
            return f"{h:02d}:{mm:02d}"
    # 12-hour with am/pm: '7:30pm', '7pm', '7.30pm'
    if m := re.fullmatch(r"(\d{1,2})(?:[:.]?(\d{2}))?\s*(am|pm)", s):
        h = int(m.group(1))
        mm = int(m.group(2) or 0)
        ampm = m.group(3)
        if ampm == "pm" and h < 12:
            h += 12
        if ampm == "am" and h == 12:
            h = 0
        return f"{h:02d}:{mm:02d}"
    raise ValidationFailed(f"cannot parse time: {raw!r}")


def canonicalise_venue_id(raw: str) -> str:
    """'Haymarket Tap' → 'haymarket_tap'. Leaves 'haymarket_tap' unchanged."""
    # TODO: Convert the raw string to lowercase and strip whitespace.
    # TODO: Replace spaces and hyphens with underscores.
    # TODO: Remove any character that is not a lowercase letter, number, or underscore.
    raise NotImplementedError("TODO: Implement canonicalise_venue_id")


def parse_party_size(raw: str | int) -> int:
    """'6' → 6. 6 → 6. '6 people' → 6. Rejects < 1 or non-numeric."""
    if isinstance(raw, int):
        if raw < 1:
            raise ValidationFailed(f"party size must be >= 1, got {raw}")
        return raw
    s = str(raw).strip()
    if m := re.match(r"(\d+)", s):
        n = int(m.group(1))
        if n < 1:
            raise ValidationFailed(f"party size must be >= 1, got {n}")
        return n
    raise ValidationFailed(f"cannot parse party size: {raw!r}")


__all__ = [
    "NormalisedBooking",
    "ValidationFailed",
    "canonicalise_venue_id",
    "normalise_booking_payload",
    "parse_currency_gbp",
    "parse_party_size",
    "parse_time_24h",
]

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
    """Take a data dict from the loop half's handoff and produce a
    Rasa-shaped message payload.

    Input example (from a handoff):
        {
          "action": "confirm_booking",
          "venue_id": "Haymarket Tap",      # free-form from LLM
          "date": "25th April",             # free-form
          "time": "7:30pm",
          "party_size": "6",
          "deposit": "£200"
        }

    Output (your function should return this):
        {
          "sender": "homework-<stable-id>",
          "message": "/confirm_booking",
          "metadata": {
            "booking": {
              "venue_id": "haymarket_tap",
              "date": "2026-04-25",
              "time": "19:30",
              "party_size": 6,
              "deposit_gbp": 200,
              "duration_hours": 3,
              "catering_tier": "bar_snacks"
            }
          }
        }

    Rules:
      * Use the normalisation helpers below (or write your own).
      * At least 3 of {date, currency, party_size, time, venue_id} must
        be normalised for full marks.
      * If the input cannot be normalised (missing venue_id, e.g.),
        raise ValidationFailed with a specific reason.

    Assumptions you may bake in:
      * "today" means 2026-04-25 (the scripted demo date).
      * Year is 2026 unless stated otherwise.
      * Default duration is 3 hours.
      * Default catering tier is bar_snacks.
    """
    raise NotImplementedError(
        "TODO Ex6: implement normalise_booking_payload. "
        "The grader checks at least 3 of {date, currency, party_size, time, venue_id} "
        "are normalised."
    )


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
    s = str(raw).strip().lower()
    s = re.sub(r"[\s\-]+", "_", s)
    s = re.sub(r"[^a-z0-9_]", "", s)
    return s


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

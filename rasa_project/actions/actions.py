"""Rasa custom actions — reference implementation.

ActionValidateBooking reads booking data from the UserUttered message's
`metadata.booking` dict (which is how RasaStructuredHalf POSTs data) and
validates it against the homework's business rules.

Why metadata, not slots?
  Our caller POSTs this payload to Rasa's REST webhook:
    {"sender": ..., "message": "/confirm_booking",
     "metadata": {"booking": {"venue_id": ..., "party_size": 6, ...}}}

  CALM's LLM command generator turns "/confirm_booking" into a
  StartFlow(confirm_booking) command. But it does NOT read metadata
  into slots — that's our job. This action does it explicitly.

  The action also SETS the slots it read, so downstream flow steps
  (like the "booking_reference" response template) can use them.
"""

from __future__ import annotations

import hashlib
from typing import Any

from rasa_sdk import Action, Tracker
from rasa_sdk.events import SlotSet
from rasa_sdk.executor import CollectingDispatcher

MAX_PARTY_SIZE_FOR_AUTO_BOOKING = 8
MAX_DEPOSIT_FOR_AUTO_BOOKING_GBP = 300


def _read_booking(tracker: Tracker) -> dict[str, Any]:
    """Extract booking dict from metadata (primary) or slots (fallback)."""
    latest = tracker.latest_message or {}
    meta = latest.get("metadata") or {}
    from_meta = meta.get("booking") if isinstance(meta, dict) else None
    if isinstance(from_meta, dict):
        return from_meta

    # Fallback — assemble from slots if the caller populated them directly
    return {
        "venue_id": tracker.get_slot("venue_id"),
        "date": tracker.get_slot("date"),
        "time": tracker.get_slot("time"),
        "party_size": tracker.get_slot("party_size"),
        "deposit_gbp": tracker.get_slot("deposit_gbp"),
    }


class ActionValidateBooking(Action):
    """Validate the proposed booking against policy rules.

    Rules:
      * party_size > 8         → reject ("party_too_large")
      * deposit_gbp > 300      → reject ("deposit_too_high")
      * missing required field → reject ("missing_<field>")
      * otherwise              → success, set booking_reference
    """

    def name(self) -> str:
        return "action_validate_booking"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: dict[str, Any],
    ) -> list[dict[str, Any]]:
        booking = _read_booking(tracker)

        venue_id = booking.get("venue_id")
        date = booking.get("date")
        time_slot = booking.get("time")
        party_size = booking.get("party_size")
        deposit_gbp = booking.get("deposit_gbp", 0)

        # All the slot-sets we'll emit — start with populating from metadata
        # so downstream responses can reference {venue_id}, {party_size}, etc.
        # Cast to the types domain.yml declares so Rasa doesn't reject.
        def _to_float(v: Any) -> float | None:
            if v is None or v == "":
                return None
            try:
                return float(v)
            except (TypeError, ValueError):
                return None

        slot_events: list[dict[str, Any]] = [
            SlotSet("venue_id", str(venue_id) if venue_id is not None else None),
            SlotSet("date", str(date) if date is not None else None),
            SlotSet("time", str(time_slot) if time_slot is not None else None),
            SlotSet("party_size", _to_float(party_size)),
            SlotSet("deposit_gbp", _to_float(deposit_gbp)),
        ]

        # Required-field check
        for field_name, value in [
            ("venue_id", venue_id),
            ("date", date),
            ("time", time_slot),
            ("party_size", party_size),
        ]:
            if value is None or value == "":
                return slot_events + [SlotSet("validation_error", f"missing_{field_name}")]

        # Cast numeric fields (they may arrive as strings from handoff JSON)
        try:
            party_int = int(float(party_size))
        except (TypeError, ValueError):
            return slot_events + [SlotSet("validation_error", "invalid_party_size")]

        try:
            deposit_int = int(float(deposit_gbp)) if deposit_gbp is not None else 0
        except (TypeError, ValueError):
            return slot_events + [SlotSet("validation_error", "invalid_deposit")]

        # TODO: Implement Rule checks
        # 1. Check if party_int is greater than MAX_PARTY_SIZE_FOR_AUTO_BOOKING. If so, return slot_events with a SlotSet for validation_error = "party_too_large".
        # 2. Check if deposit_int is greater than MAX_DEPOSIT_FOR_AUTO_BOOKING_GBP. If so, return slot_events with a SlotSet for validation_error = "deposit_too_high".
        
        # TODO: Success case
        # Generate a deterministic booking reference (e.g. using hashlib.sha1 on venue_id, date, time_slot, party_int).
        # Return slot_events + [SlotSet("validation_error", None), SlotSet("booking_reference", ref)]
        raise NotImplementedError("TODO: Implement Rule checks in ActionValidateBooking")

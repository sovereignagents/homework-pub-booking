"""Public tests for Ex6 — Rasa structured half.

No Rasa server required here; we test the Python-side validator and
the subclass's structure. Real Rasa integration is tested by the
private suite with a live container.
"""

from __future__ import annotations

import pytest


def test_structured_half_subclass_exists() -> None:
    from sovereign_agent.halves.structured import StructuredHalf

    from starter.rasa_half.structured_half import RasaStructuredHalf

    assert issubclass(RasaStructuredHalf, StructuredHalf)


def test_structured_half_has_discover() -> None:
    from sovereign_agent.discovery import validate_schema

    from starter.rasa_half.structured_half import RasaStructuredHalf

    half = RasaStructuredHalf()
    validate_schema(half.discover())


# ─── validator ─────────────────────────────────────────────────────


def test_parse_currency_gbp_accepts_multiple_forms() -> None:
    from starter.rasa_half.validator import parse_currency_gbp

    assert parse_currency_gbp("£500") == 500
    assert parse_currency_gbp("500 GBP") == 500
    assert parse_currency_gbp(500) == 500
    assert parse_currency_gbp("500.0") == 500


def test_parse_currency_gbp_rejects_negative() -> None:
    from starter.rasa_half.validator import ValidationFailed, parse_currency_gbp

    with pytest.raises(ValidationFailed):
        parse_currency_gbp(-100)
    with pytest.raises(ValidationFailed):
        parse_currency_gbp("not-a-number")


def test_parse_time_24h() -> None:
    from starter.rasa_half.validator import parse_time_24h

    assert parse_time_24h("19:30") == "19:30"
    assert parse_time_24h("7:30pm") == "19:30"
    assert parse_time_24h("7pm") == "19:00"
    assert parse_time_24h("noon") == "12:00"
    assert parse_time_24h("7.30pm") == "19:30"


def test_canonicalise_venue_id() -> None:
    from starter.rasa_half.validator import canonicalise_venue_id

    assert canonicalise_venue_id("Haymarket Tap") == "haymarket_tap"
    assert canonicalise_venue_id("haymarket_tap") == "haymarket_tap"
    assert canonicalise_venue_id("The Royal Oak!") == "the_royal_oak"


def test_parse_party_size_rejects_zero() -> None:
    from starter.rasa_half.validator import ValidationFailed, parse_party_size

    with pytest.raises(ValidationFailed):
        parse_party_size(0)
    with pytest.raises(ValidationFailed):
        parse_party_size("0")


def test_normalise_booking_payload_produces_rasa_shape() -> None:
    """Once implemented, the normaliser returns the sender/message/metadata shape."""
    from starter.rasa_half.validator import normalise_booking_payload

    raw = {
        "action": "confirm_booking",
        "venue_id": "Haymarket Tap",
        "date": "2026-04-25",
        "time": "7:30pm",
        "party_size": "6",
        "deposit": "£200",
    }
    try:
        out = normalise_booking_payload(raw)
    except NotImplementedError:
        pytest.skip("normalise_booking_payload not implemented yet — do Ex6 first")

    assert "sender" in out
    assert "message" in out
    assert "metadata" in out
    booking = out["metadata"]["booking"]
    # At least 3 of the 5 normalisations must be present.
    normalisations_applied = sum(
        [
            booking.get("venue_id") == "haymarket_tap",
            booking.get("time") == "19:30",
            isinstance(booking.get("party_size"), int),
            isinstance(booking.get("deposit_gbp"), int),
            booking.get("date") == "2026-04-25",
        ]
    )
    assert normalisations_applied >= 3, (
        f"only {normalisations_applied}/5 normalisations applied; grader wants ≥ 3"
    )

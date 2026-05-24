"""Conversation-control checks for Ex8 voice loop."""

from __future__ import annotations

from starter.voice_pipeline.manager_persona import ManagerTurn
from starter.voice_pipeline.voice_loop import (
    _is_confirmation_acknowledgement,
    _is_redirect_acknowledgement,
    _is_terminal_hard_decline,
)


class StubPersona:
    def __init__(self, last_response: str) -> None:
        self.history = [ManagerTurn(user_utterance="15", manager_response=last_response)]


def test_ok_after_large_party_redirect_closes() -> None:
    persona = StubPersona(
        "I'm afraid we can't take bookings for parties that large. "
        "Might I suggest The Royal Oak or Bennet's Bar instead?"
    )

    assert _is_redirect_acknowledgement("ok", persona)


def test_ok_without_redirect_does_not_close() -> None:
    persona = StubPersona("What time were you thinking of?")

    assert not _is_redirect_acknowledgement("ok", persona)


def test_capacity_hard_decline_is_terminal() -> None:
    assert _is_terminal_hard_decline(
        "Sorry, we cannot accommodate 15 people at Haymarket Tap. "
        "You can always try The Royal Oak or Bennet's Bar for a larger booking."
    )


def test_deposit_signoff_is_terminal() -> None:
    assert _is_terminal_hard_decline(
        "That deposit is at or above our £300 auto-approval limit, so I can't confirm "
        "it myself. I need to consult my manager; please call later to confirm. Thanks, goodbye."
    )


def test_yes_after_final_confirmation_closes() -> None:
    persona = StubPersona(
        "Aye, happy to. I can confirm a booking at Haymarket Tap for 5 people "
        "on 12th May at 7pm, with a £100 deposit, under M.K. Are you happy with that?"
    )

    assert _is_confirmation_acknowledgement("yes", persona)


def test_yes_before_final_confirmation_does_not_close() -> None:
    persona = StubPersona("Just to confirm, it's Haymarket Tap you're booking, aye?")

    assert not _is_confirmation_acknowledgement("yes", persona)

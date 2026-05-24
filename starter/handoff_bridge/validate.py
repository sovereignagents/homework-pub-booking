"""Validation helpers for the Ex7 handoff bridge."""

from __future__ import annotations

from sovereign_agent.halves import HalfResult
from sovereign_agent.handoff import Handoff

LOOP_HALF = "loop"
STRUCTURED_HALF = "structured"
REQUIRED_BOOKING_FIELDS = frozenset({"venue_id", "date", "time", "party_size"})


def validate_max_rounds(max_rounds: int) -> None:
    """Validate bridge retry configuration."""
    if not isinstance(max_rounds, int):
        raise ValueError("max_rounds must be an integer")

    if max_rounds <= 0:
        raise ValueError("max_rounds must be greater than zero")


def validate_initial_task(initial_task: dict) -> None:
    """Validate the first task passed into the bridge."""
    validate_task_input(initial_task, label="initial_task")


def validate_loop_input(loop_input: dict) -> None:
    """Validate input before sending it to the loop half."""
    validate_task_input(loop_input, label="loop input")


def validate_task_input(task_input: dict, *, label: str) -> None:
    """Validate a task dictionary before it is sent to the loop half."""
    if not isinstance(task_input, dict):
        raise ValueError(f"{label} must be a dictionary")

    if not task_input:
        raise ValueError(f"{label} must not be empty")

    task = task_input.get("task")
    if not isinstance(task, str) or not task.strip():
        raise ValueError(f"{label} must contain a non-empty 'task' string")


def validate_structured_input(structured_input: dict) -> None:
    """Validate input before sending it to the structured half."""
    if not isinstance(structured_input, dict):
        raise ValueError("structured input must be a dictionary")

    data = structured_input.get("data")
    if not isinstance(data, dict):
        raise ValueError("structured input must contain dictionary field 'data'")

    if not data:
        raise ValueError("structured input data must not be empty")

    validate_required_booking_fields(
        data,
        error_prefix="structured input data",
    )


def validate_required_booking_fields(data: dict, *, error_prefix: str) -> None:
    """Validate that booking data contains all required fields."""
    missing_fields = sorted(
        field for field in REQUIRED_BOOKING_FIELDS if not data.get(field)
    )

    if missing_fields:
        raise ValueError(
            f"{error_prefix} is missing required field(s): "
            + ", ".join(missing_fields)
        )


def validate_half_result(result: HalfResult, *, actor: str) -> None:
    """Validate the result returned by a half."""
    if result is None:
        raise ValueError(f"{actor} half returned None")

    next_action = getattr(result, "next_action", None)
    if not isinstance(next_action, str) or not next_action.strip():
        raise ValueError(f"{actor} half returned an empty next_action")

    summary = getattr(result, "summary", None)
    output = getattr(result, "output", None)
    handoff_payload = getattr(result, "handoff_payload", None)

    if output is None and handoff_payload is None and not summary:
        raise ValueError(
            f"{actor} half result must contain output, handoff_payload, or summary"
        )


def validate_forward_handoff(handoff: Handoff) -> None:
    """Validate the handoff before writing it to IPC."""
    if handoff.from_half != LOOP_HALF:
        raise ValueError("forward handoff must come from loop")

    if handoff.to_half != STRUCTURED_HALF:
        raise ValueError("forward handoff must go to structured")

    if not handoff.session_id:
        raise ValueError("forward handoff must include session_id")

    if not isinstance(handoff.data, dict) or not handoff.data:
        raise ValueError("forward handoff data must be a non-empty dictionary")

    validate_required_booking_fields(
        handoff.data,
        error_prefix="forward handoff data",
    )


__all__ = [
    "validate_forward_handoff",
    "validate_half_result",
    "validate_initial_task",
    "validate_loop_input",
    "validate_max_rounds",
    "validate_structured_input",
]
"""Ex7 — handoff bridge.

Routes between the loop half and the Rasa-backed structured half,
supporting reverse handoffs from structured back to loop when the
structured half rejects a proposal.
"""

from __future__ import annotations

from sovereign_agent.halves import HalfResult
from sovereign_agent.halves.loop import LoopHalf
from sovereign_agent.halves.structured import StructuredHalf
from sovereign_agent.handoff import Handoff, write_handoff
from sovereign_agent.session.directory import Session
from sovereign_agent.session.state import now_utc


from starter.handoff_bridge.types import BridgeOutcome, BridgeResult



"""Routing helpers for Ex7 handoff bridge."""


from sovereign_agent.halves import HalfResult
from sovereign_agent.session.directory import Session

from starter.handoff_bridge.types import BridgeResult


def route_bridge_exception(
    *,
    session: Session,
    rounds: int,
    exc: ValueError,
    final_half_result: HalfResult | None,
) -> BridgeResult:
    """Route bridge -> failed when bridge validation fails."""
    reason = str(exc)
    session.mark_failed(reason)
    session.append_trace_event(
        {
            "event_type": "session.state_changed",
            "actor": "bridge",
            "payload": {
                "from": "bridge",
                "to": "failed",
                "rounds": rounds,
                "reason": reason,
            },
        }
    )

    return BridgeResult(
        outcome="failed",
        rounds=rounds,
        final_half_result=final_half_result,
        summary=reason,
    )


def route_loop_completed(
    *,
    session: Session,
    rounds: int,
    loop_result: HalfResult,
) -> BridgeResult:
    """Route loop -> complete."""
    session.mark_complete(loop_result.output)
    session.append_trace_event(
        {
            "event_type": "session.state_changed",
            "actor": "bridge",
            "payload": {
                "from": "loop",
                "to": "complete",
                "round": rounds,
            },
        }
    )

    return BridgeResult(
        outcome="completed",
        rounds=rounds,
        final_half_result=loop_result,
        summary=f"loop half completed in round {rounds}",
    )


def route_loop_to_structured(
    *,
    session: Session,
    rounds: int,
    handoff_reason: str,
) -> None:
    """Record route loop -> structured."""
    session.append_trace_event(
        {
            "event_type": "session.state_changed",
            "actor": "bridge",
            "payload": {
                "from": "loop",
                "to": "structured",
                "round": rounds,
                "handoff_reason": handoff_reason,
            },
        }
    )


def route_unexpected_loop_outcome(
    *,
    session: Session,
    rounds: int,
    loop_result: HalfResult,
) -> BridgeResult:
    """Route loop -> failed when loop returns an unsupported next_action."""
    reason = f"unexpected loop outcome: {loop_result.next_action}"
    session.mark_failed(reason)
    session.append_trace_event(
        {
            "event_type": "session.state_changed",
            "actor": "bridge",
            "payload": {
                "from": "loop",
                "to": "failed",
                "round": rounds,
                "reason": reason,
            },
        }
    )

    return BridgeResult(
        outcome="failed",
        rounds=rounds,
        final_half_result=loop_result,
        summary=reason,
    )


def route_structured_completed(
    *,
    session: Session,
    rounds: int,
    structured_result: HalfResult,
) -> BridgeResult:
    """Route structured -> complete."""
    session.mark_complete(structured_result.output)
    session.append_trace_event(
        {
            "event_type": "session.state_changed",
            "actor": "bridge",
            "payload": {
                "from": "structured",
                "to": "complete",
                "round": rounds,
            },
        }
    )

    return BridgeResult(
        outcome="completed",
        rounds=rounds,
        final_half_result=structured_result,
        summary=f"structured half confirmed booking in round {rounds}",
    )


def route_structured_rejected(
    *,
    session: Session,
    rounds: int,
    rejection_reason: str,
) -> None:
    """Record route structured -> loop after structured rejects the proposal."""
    session.append_trace_event(
        {
            "event_type": "session.state_changed",
            "actor": "bridge",
            "payload": {
                "from": "structured",
                "to": "loop",
                "round": rounds,
                "rejection_reason": rejection_reason,
            },
        }
    )


def route_unexpected_structured_outcome(
    *,
    session: Session,
    rounds: int,
    structured_result: HalfResult,
) -> BridgeResult:
    """Route structured -> failed when structured returns an unsupported next_action."""
    reason = f"unexpected structured outcome: {structured_result.next_action}"
    session.mark_failed(reason)
    session.append_trace_event(
        {
            "event_type": "session.state_changed",
            "actor": "bridge",
            "payload": {
                "from": "structured",
                "to": "failed",
                "round": rounds,
                "reason": reason,
            },
        }
    )

    return BridgeResult(
        outcome="failed",
        rounds=rounds,
        final_half_result=structured_result,
        summary=reason,
    )


def route_max_rounds_exceeded(
    *,
    session: Session,
    rounds: int,
    max_rounds: int,
    final_half_result: HalfResult | None,
) -> BridgeResult:
    """Route bridge -> failed after max_rounds is exhausted."""
    reason = f"max_rounds={max_rounds} exceeded"
    session.mark_failed(reason)
    session.append_trace_event(
        {
            "event_type": "session.state_changed",
            "actor": "bridge",
            "payload": {
                "from": "bridge",
                "to": "failed",
                "rounds": rounds,
                "reason": reason,
            },
        }
    )

    return BridgeResult(
        outcome="max_rounds_exceeded",
        rounds=rounds,
        final_half_result=final_half_result,
        summary=f"bridge exhausted {max_rounds} rounds without resolution",
    )



def build_forward_handoff(session: Session, loop_result: HalfResult) -> Handoff:
    """Package a loop result into a forward handoff for the structured half."""
    handoff_payload = loop_result.handoff_payload or {}
    handoff_data = handoff_payload.get("data") or loop_result.output or {}

    if not isinstance(handoff_data, dict):
        raise ValueError("forward handoff data must be a dictionary")

    if not handoff_data:
        raise ValueError("forward handoff data must not be empty")

    return Handoff(
        from_half="loop",
        to_half="structured",
        written_at=now_utc(),
        session_id=session.session_id,
        reason=handoff_payload.get("reason") or "loop-half requested confirmation",
        context=handoff_payload.get("context") or loop_result.summary,
        data=handoff_data,
        return_instructions=(
            "Validate the proposed booking under structured policy rules. "
            "If the booking cannot be confirmed, return next_action=escalate "
            "or next_action=handoff_to_loop and include a human-readable "
            "rejection reason in output.reason."
        ),
    )


def build_reverse_task(loop_result: HalfResult, struct_result: HalfResult) -> dict:
    """Build the next loop-half task after structured rejects a proposal."""
    reason = _extract_rejection_reason(struct_result)

    return {
        "task": (
            "The structured half rejected the previous booking proposal. "
            f"Reason: {reason}. Research and propose an alternative venue "
            "or adjusted booking that satisfies the structured policy."
        ),
        "context": {
            "prior_loop_output": loop_result.output,
            "prior_loop_summary": loop_result.summary,
            "structured_output": struct_result.output,
            "structured_summary": struct_result.summary,
            "rejection_reason": reason,
            "retry": True,
        },
    }


def _extract_rejection_reason(struct_result: HalfResult) -> str:
    """Extract a stable rejection reason from a structured-half result."""
    output = struct_result.output or {}

    if isinstance(output, dict):
        reason = output.get("reason") or output.get("validation_error")
        if reason:
            return str(reason)

    if struct_result.summary:
        return struct_result.summary

    return "structured half rejected the proposal"


__all__ = [
    "route_bridge_exception",
    "route_loop_completed",
    "route_loop_to_structured",
    "route_max_rounds_exceeded",
    "route_structured_completed",
    "route_structured_rejected",
    "route_unexpected_loop_outcome",
    "route_unexpected_structured_outcome",
]

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


from starter.handoff_bridge.routing import (
    route_bridge_exception,
    route_loop_completed,
    route_loop_to_structured,
    route_max_rounds_exceeded,
    route_structured_completed,
    route_structured_rejected,
    route_unexpected_loop_outcome,
    route_unexpected_structured_outcome,
)
from starter.handoff_bridge.types import BridgeOutcome, BridgeResult
from starter.handoff_bridge.validate import (
    validate_forward_handoff,
    validate_half_result,
    validate_initial_task,
    validate_loop_input,
    validate_max_rounds,
    validate_structured_input,
)


def _archive_timestamp() -> str:
    """Return a filesystem-safe UTC timestamp for archive filenames."""
    return now_utc().isoformat().replace(":", "-")


class HandoffBridge:
    """Orchestrates round-trips between LoopHalf and StructuredHalf.

    The bridge is not a sovereign-agent Half itself. It sits above the two
    halves and decides which one should run next.
    """

    LOOP_HALF = "loop"
    STRUCTURED_HALF = "structured"

    ACTION_COMPLETE = "complete"
    ACTION_HANDOFF_TO_STRUCTURED = "handoff_to_structured"
    ACTION_HANDOFF_TO_LOOP = "handoff_to_loop"
    ACTION_ESCALATE = "escalate"

    def __init__(
            self,
            *,
            loop_half: LoopHalf,
            structured_half: StructuredHalf,
            max_rounds: int = 3,
    ) -> None:
        self.loop_half = loop_half
        self.structured_half = structured_half
        self.max_rounds = max_rounds

    async def run(self, session: Session, initial_task: dict) -> BridgeResult:
        """Run loop/structured round-trips until completion or failure."""
        try:
            validate_initial_task(initial_task)
            validate_max_rounds(self.max_rounds)
        except ValueError as exc:
            return route_bridge_exception(
                session=session,
                rounds=0,
                exc=exc,
                final_half_result=None,
            )

        rounds = 0
        current_input: dict = initial_task
        last_loop_result: HalfResult | None = None
        last_structured_result: HalfResult | None = None

        while rounds < self.max_rounds:
            rounds += 1

            try:
                self._record_round_start(session, rounds)
                validate_loop_input(current_input)

                loop_result = await self.loop_half.run(session, current_input)
                validate_half_result(loop_result, actor=self.LOOP_HALF)
                last_loop_result = loop_result

                if loop_result.next_action == self.ACTION_COMPLETE:
                    return route_loop_completed(
                        session=session,
                        rounds=rounds,
                        loop_result=loop_result,
                    )

                elif loop_result.next_action == self.ACTION_HANDOFF_TO_STRUCTURED:
                    handoff = build_forward_handoff(session, loop_result)
                    validate_forward_handoff(handoff)
                    self._write_forward_handoff(session, handoff)

                    route_loop_to_structured(
                        session=session,
                        rounds=rounds,
                        handoff_reason=handoff.reason,
                    )

                    structured_input = {"data": handoff.data}
                    validate_structured_input(structured_input)

                    structured_result = await self.structured_half.run(
                        session,
                        structured_input,
                    )
                    validate_half_result(
                        structured_result,
                        actor=self.STRUCTURED_HALF,
                    )
                    last_structured_result = structured_result

                    if structured_result.next_action == self.ACTION_COMPLETE:
                        self._archive_forward_handoff(session, rounds)
                        return route_structured_completed(
                            session=session,
                            rounds=rounds,
                            structured_result=structured_result,
                        )

                    elif structured_result.next_action in {
                        self.ACTION_ESCALATE,
                        self.ACTION_HANDOFF_TO_LOOP,
                    }:
                        rejection_reason = _extract_rejection_reason(structured_result)
                        current_input = build_reverse_task(loop_result, structured_result)

                        route_structured_rejected(
                            session=session,
                            rounds=rounds,
                            rejection_reason=rejection_reason,
                        )

                        self._archive_forward_handoff(session, rounds)
                        continue

                    else:
                        return route_unexpected_structured_outcome(
                            session=session,
                            rounds=rounds,
                            structured_result=structured_result,
                        )

                else:
                    return route_unexpected_loop_outcome(
                        session=session,
                        rounds=rounds,
                        loop_result=loop_result,
                    )

            except ValueError as exc:
                return route_bridge_exception(
                    session=session,
                    rounds=rounds,
                    exc=exc,
                    final_half_result=last_structured_result or last_loop_result,
                )

        return route_max_rounds_exceeded(
            session=session,
            rounds=rounds,
            max_rounds=self.max_rounds,
            final_half_result=last_structured_result or last_loop_result,
        )

    def _record_round_start(self, session: Session, round_number: int) -> None:
        """Record the start of a bridge round."""
        session.append_trace_event(
            {
                "event_type": "bridge.round_start",
                "actor": "bridge",
                "payload": {
                    "round": round_number,
                    "half": self.LOOP_HALF,
                },
            }
        )

    def _write_forward_handoff(self, session: Session, handoff: Handoff) -> None:
        """Write a forward handoff while enforcing the visible-IPC rule."""
        self._clear_visible_handoff_files(session)
        write_handoff(session, self.STRUCTURED_HALF, handoff)

    def _clear_visible_handoff_files(self, session: Session) -> None:
        """Archive stale visible handoff files before writing a new one.

        Ex7's fail-closed IPC rule requires at most one handoff file to be
        visible in ipc/ at any time.
        """
        for visible_dir in (session.ipc_dir, session.ipc_input_dir):
            visible_dir.mkdir(parents=True, exist_ok=True)

            for path in visible_dir.glob("handoff_to_*.json"):
                archive = session.handoffs_audit_dir / f"stale_{path.name}"
                archive.parent.mkdir(parents=True, exist_ok=True)

                if archive.exists():
                    archive = session.handoffs_audit_dir / (
                        f"stale_{_archive_timestamp()}_{path.name}"
                    )

                path.rename(archive)

    def _archive_forward_handoff(self, session: Session, round_number: int) -> None:
        """Move the visible forward handoff out of ipc/ after it is consumed."""
        forward_file = session.ipc_dir / "handoff_to_structured.json"

        if not forward_file.exists():
            forward_file = session.ipc_input_dir / "handoff_to_structured.json"

        if not forward_file.exists():
            return

        archive = session.handoffs_audit_dir / f"round_{round_number}_forward.json"
        archive.parent.mkdir(parents=True, exist_ok=True)

        if archive.exists():
            archive = session.handoffs_audit_dir / (
                f"round_{round_number}_forward_{_archive_timestamp()}.json"
            )

        forward_file.rename(archive)


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
    "BridgeOutcome",
    "BridgeResult",
    "HandoffBridge",
    "build_forward_handoff",
    "build_reverse_task",
]

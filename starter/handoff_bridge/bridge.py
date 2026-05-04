"""Ex7 — handoff bridge.

Routes between the loop half and the Rasa-backed structured half,
supporting REVERSE handoffs (structured → loop) when the structured
half rejects.

The base sovereign-agent LoopHalf only knows how to request a handoff
FORWARD. The bridge you're building here is the thing that decides
what to do when the structured half says "no, go back and try again".
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from sovereign_agent.halves import HalfResult
from sovereign_agent.halves.loop import LoopHalf
from sovereign_agent.halves.structured import StructuredHalf
from sovereign_agent.handoff import Handoff
from sovereign_agent.session.directory import Session
from sovereign_agent.session.state import now_utc

BridgeOutcome = Literal["completed", "failed", "max_rounds_exceeded"]


@dataclass
class BridgeResult:
    outcome: BridgeOutcome
    rounds: int
    final_half_result: HalfResult | None
    summary: str


class HandoffBridge:
    """Orchestrates round-trips between LoopHalf and a StructuredHalf.

    Not a sovereign-agent Half itself — it lives one level up, deciding
    which half should run next.
    """

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

    # ------------------------------------------------------------------
    # TODO — the main run method
    # ------------------------------------------------------------------
    async def run(self, session: Session, initial_task: dict) -> BridgeResult:
        """Run the bridge until the session completes, fails, or hits max_rounds."""
        from sovereign_agent.handoff import write_handoff

        rounds = 0
        current_input: dict = initial_task
        last_loop = last_struct = None

        # TODO: Implement the bridge orchestration loop here.
        # It should loop up to `self.max_rounds` times.
        
        # --- ROUND START ---
        # 1. Increment the `rounds` counter.
        # 2. Append a trace event indicating the round has started.
        # Example schema:
        # session.append_trace_event({
        #     "event_type": "bridge.round_start",
        #     "actor": "bridge",
        #     "payload": {"round": rounds, "half": "loop"}
        # })
        
        # --- RUN LOOP HALF ---
        # 3. Run the loop_half using `current_input` (see `LoopHalf.run` which returns a `HalfResult`).
        # 4. Handle Loop Half Outcomes:
        #    a) If `loop_result.next_action == "complete"`, mark the session complete with `loop_result.output`,
        #       append a "session.state_changed" trace event (from "executing" to "complete" via "loop"), 
        #       and return a `BridgeResult` with outcome="completed".
        #    b) If `loop_result.next_action != "handoff_to_structured"`, something went wrong.
        #       Use `session.mark_failed({"reason": ...})` and return a `BridgeResult` with outcome="failed".
        
        # --- FORWARD HANDOFF ---
        # 5. If handoff is requested, build it using `build_forward_handoff`.
        # 6. Write the handoff to disk: `write_handoff(session, "structured", handoff)`
        # 7. Append a "session.state_changed" trace event (from "loop" to "structured").
        
        # --- RUN STRUCTURED HALF ---
        # 8. Run the structured_half passing `{"data": handoff.data}` as input.
        #    (See `RasaStructuredHalf.run` for return value schemas).
        # 9. Handle Structured Half Outcomes:
        #    a) If `struct_result.next_action == "complete"`, mark session complete, log the state change,
        #       and return outcome="completed".
        #    b) If `struct_result.next_action == "escalate"`, it means Rasa rejected the booking.
        #       - Use `build_reverse_task` to generate the new input for the next loop round.
        #       - Append a state change event (from "structured" to "loop") including the rejection reason
        #         (`struct_result.output.get("reason") or struct_result.summary`).
        #       - **Crucial File Management:** The bridge needs to archive the old handoff file to prevent
        #         stale data on the next round. Move `session.ipc_input_dir / "handoff_to_structured.json"`
        #         to `session.handoffs_audit_dir / f"round_{rounds}_forward.json"`.
        #       - `continue` to the next round.
        #    c) Any other action: mark failed and return outcome="failed".
        
        # --- LOOP EXHAUSTION ---
        # 10. If the loop exits because `rounds >= self.max_rounds`, use `session.mark_failed`
        #     and return outcome="max_rounds_exceeded".
        
        raise NotImplementedError("TODO: Implement the bidirectional orchestration loop in HandoffBridge.run()")


# ---------------------------------------------------------------------------
# Helper constructors — you may use these or write your own
# ---------------------------------------------------------------------------
def build_forward_handoff(session: Session, loop_result: HalfResult) -> Handoff:
    """Package a loop result into a forward-handoff payload for structured."""
    return Handoff(
        from_half="loop",
        to_half="structured",
        written_at=now_utc(),
        session_id=session.session_id,
        reason="loop-half requested confirmation",
        context=loop_result.summary,
        data=(loop_result.handoff_payload or {}).get("data") or loop_result.output,
        return_instructions=(
            "If you cannot confirm (party too large, deposit too high, etc.), "
            "respond with next_action=escalate and include a human-readable "
            "'reason' in output so the loop half can adapt."
        ),
    )


def build_reverse_task(loop_result: HalfResult, struct_result: HalfResult) -> dict:
    """Build the task dict to pass back to the loop half after a reject."""
    reason = struct_result.output.get("reason") or struct_result.summary
    return {
        "task": (
            "The structured half rejected the previous proposal. "
            f"Reason: {reason}. Produce an alternative."
        ),
        "context": {
            "prior_result": loop_result.output,
            "rejection_reason": reason,
            "retry": True,
        },
    }


__all__ = [
    "BridgeOutcome",
    "BridgeResult",
    "HandoffBridge",
    "build_forward_handoff",
    "build_reverse_task",
]

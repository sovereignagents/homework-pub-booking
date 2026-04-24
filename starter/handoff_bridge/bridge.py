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
        """Run the bridge until the session completes, fails, or hits max_rounds.

        Algorithm:
          rounds = 0
          current_input = initial_task
          while rounds < max_rounds:
              rounds += 1
              loop_result = await self.loop_half.run(session, current_input)

              if loop_result.next_action == "complete":
                  return BridgeResult(outcome="completed", ...)

              if loop_result.next_action == "handoff_to_structured":
                  # write the handoff, then let structured half read it back
                  handoff = build_forward_handoff(session, loop_result)
                  write_handoff(session, "structured", handoff)

                  struct_result = await self.structured_half.run(
                      session, {"data": handoff.data}
                  )

                  if struct_result.next_action == "complete":
                      session.mark_complete(struct_result.output)
                      return BridgeResult(outcome="completed", ...)

                  if struct_result.next_action == "escalate":
                      # REVERSE handoff: go back to loop with the reason
                      current_input = build_reverse_task(loop_result, struct_result)
                      # IMPORTANT: the forward handoff file has already
                      # been archived by the orchestrator; don't leave
                      # a stale one. See docs/troubleshooting.md
                      # "multiple handoff files" entry.
                      continue

              # Unknown loop outcome — fail fast.
              return BridgeResult(outcome="failed", ...)

          return BridgeResult(outcome="max_rounds_exceeded", ...)

        You MUST emit a 'session.state_changed' trace event for each
        transition (loop → structured, structured → loop). The grader
        checks the trace for these.
        """
        raise NotImplementedError(
            "TODO Ex7: implement HandoffBridge.run(). See the docstring for the expected algorithm."
        )


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
        data=loop_result.handoff_payload or loop_result.output,
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

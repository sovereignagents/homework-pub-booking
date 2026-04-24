"""Ex7 — handoff bridge end-to-end demo.

Offline mode scripts the full round-trip:
  1. Loop finds haymarket_tap (8 seats, party of 12 won't fit).
  2. Structured half rejects (party > 8 cap).
  3. Bridge returns to loop with rejection reason.
  4. Loop finds royal_oak (16 seats).
  5. Structured half approves.
"""

from __future__ import annotations

import asyncio
import sys

from sovereign_agent._internal.paths import user_data_dir
from sovereign_agent.session.directory import create_session

# NOTE: we import from the starter packages — this forces your code to
# actually work end-to-end rather than relying on framework defaults.


async def run_scenario(real: bool) -> int:
    sessions_root = user_data_dir() / "homework" / "ex7"
    sessions_root.mkdir(parents=True, exist_ok=True)

    session = create_session(
        scenario="ex7-handoff-bridge",
        task="Book a venue for 12 people in Haymarket, Friday 19:30.",
        sessions_dir=sessions_root,
    )
    print(f"Session {session.session_id}")
    print(f"  dir: {session.directory}")

    # TODO: construct the loop half and structured half, wire them into
    # a HandoffBridge, and call bridge.run().
    #
    # Hint:
    #   from starter.edinburgh_research.tools import build_tool_registry
    #   from starter.rasa_half.structured_half import RasaStructuredHalf
    #   from sovereign_agent.halves.loop import LoopHalf
    #   from sovereign_agent.planner import DefaultPlanner
    #   from sovereign_agent.executor import DefaultExecutor
    #   from sovereign_agent._internal.llm_client import FakeLLMClient, ScriptedResponse, ToolCall
    #
    # The offline script must produce a sequence where the first
    # round's chosen venue fails the party-size cap and the second
    # round's choice passes.

    raise NotImplementedError(
        "TODO Ex7: wire the LoopHalf + RasaStructuredHalf into a HandoffBridge "
        "and drive the full round-trip. See bridge.py docstring for the "
        "algorithm and this file's docstring for the expected sequence."
    )


def main() -> None:
    real = "--real" in sys.argv
    sys.exit(asyncio.run(run_scenario(real=real)))


if __name__ == "__main__":
    main()

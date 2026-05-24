"""Ex6 — runner (reference solution).

Three modes:

  python -m starter.rasa_half.run          (mock, no services) → tier 1
  python -m starter.rasa_half.run --real   (assume Rasa is up)  → tier 2
  python -m starter.rasa_half.run --real --auto  (auto-spawn)    → tier 3

Tier 1 uses a stdlib mock that matches Rasa's HTTP shape. Students can
validate their normalise_booking_payload + structured_half code without
installing Rasa Pro or obtaining a license.

Tier 2 assumes Rasa is already running on localhost:5005 (rasa serve)
and localhost:5055 (actions). Students start these themselves in two
other terminals — this teaches the multi-process coordination pattern
that real agent systems use in production.

Tier 3 auto-spawns both Rasa processes via RasaHostLifecycle, runs the
scenario, and tears them down. Convenient for CI / demos but hides
what tier 2 teaches.
"""

from __future__ import annotations

import asyncio
import json
import sys

from sovereign_agent._internal.paths import example_sessions_dir
from sovereign_agent.session.directory import create_session

from starter.rasa_half.structured_half import (
    RasaHostLifecycle,
    RasaStructuredHalf,
    spawn_mock_rasa,
)


async def run_scenario(real: bool, auto: bool) -> int:
    with example_sessions_dir("ex6-rasa-half", persist=real) as sessions_root:
        session = create_session(
            scenario="ex6-rasa",
            task="Confirm a booking through the Rasa structured half.",
            sessions_dir=sessions_root,
        )
        print(f"📂 Session {session.session_id}")
        print(f"   dir: {session.directory}")

        sample_booking = {
            "data": {
                "action": "confirm_booking",
                "venue_id": "Haymarket Tap",
                "date": "25th April 2026",
                "time": "7:30pm",
                "party_size": "10",
                "deposit": "£200",
            }
        }

        if real and auto:
            # Tier 3 — auto-spawn.
            log_dir = session.logs_dir / "rasa"
            log_dir.mkdir(parents=True, exist_ok=True)
            print(f"   Rasa logs: {log_dir}")
            print(
                "   (tier 3 auto-spawn mode — the scenario spawns Rasa + action\n"
                "    server subprocesses, runs, then tears them down)"
            )
            async with RasaHostLifecycle(log_dir=log_dir) as rasa_url:
                print(f"   Rasa URL: {rasa_url}")
                half = RasaStructuredHalf(rasa_url=rasa_url, request_timeout_s=30.0)
                result = await half.run(session, sample_booking)

        elif real:
            # Tier 2 — assume Rasa is already running.
            print(
                "   (tier 2: assuming rasa-actions + rasa-serve are already\n"
                "    running in two other terminals. If you see a connection\n"
                "    error below, run `make ex6-help` for the setup recipe.)"
            )
            rasa_url = "http://localhost:5005/webhooks/rest/webhook"
            print(f"   Rasa URL: {rasa_url}")
            half = RasaStructuredHalf(rasa_url=rasa_url, request_timeout_s=30.0)
            result = await half.run(session, sample_booking)

        else:
            # Tier 1 — mock.
            print("   (tier 1: stdlib mock Rasa on :5905 — no license needed)")
            server, _thread, mock_url = spawn_mock_rasa(port=5905)
            try:
                print(f"   Mock URL: {mock_url}")
                half = RasaStructuredHalf(rasa_url=mock_url)
                result = await half.run(session, sample_booking)
            finally:
                server.shutdown()

        print(f"\nStructured half outcome: {result.next_action}")
        print(f"  summary: {result.summary}")
        print(f"  output:  {result.output}")

        result_path = session.workspace_dir / "structured_result.json"
        result_path.parent.mkdir(parents=True, exist_ok=True)
        result_path.write_text(
            json.dumps(
                {
                    "success": result.success,
                    "next_action": result.next_action,
                    "summary": result.summary,
                    "output": result.output,
                },
                indent=2,
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        print(f"  saved:   {result_path}")

        if real:
            print(f"\n📂 Session artifacts: {session.directory}")
            print(f"📜 Narrate this run:   make narrate SESSION={session.session_id}")

        return 0 if result.success else 1


def main() -> None:
    real = "--real" in sys.argv
    auto = "--auto" in sys.argv
    if auto and not real:
        print("✗ --auto requires --real", file=sys.stderr)
        sys.exit(2)
    sys.exit(asyncio.run(run_scenario(real=real, auto=auto)))


if __name__ == "__main__":
    main()

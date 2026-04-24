"""Ex5 — Edinburgh research scenario entrypoint.

Usage:
    make ex5            # offline, FakeLLMClient
    make ex5-real       # uses Nebius (burns tokens)

The structure mirrors examples/pub_booking/run.py in the sovereign-agent
repo. If you're unsure how to wire something up, read that file — the
pedagogical model is "copy from the reference, change the scenario".

What's different from the reference:
  * This runner uses `Config.from_env()` to read your `.env` — so the
    planner/executor models come from YOUR config, not hardcoded ones.
  * The session directory is managed by `example_sessions_dir()` so
    offline runs go to a tempdir (auto-cleans) and --real runs persist
    under the platform user-data directory. Same pattern sovereign-agent
    uses for its own examples — worth studying.
  * Before running the loop, we check whether the tools are implemented.
    If they're not, we print a friendly message instead of letting the
    framework blow up with SA_EXT_UNEXPECTED_RESPONSE.
"""

from __future__ import annotations

import asyncio
import json
import sys

from sovereign_agent._internal.llm_client import (
    FakeLLMClient,
    OpenAICompatibleClient,
    ScriptedResponse,
    ToolCall,
)
from sovereign_agent._internal.paths import example_sessions_dir
from sovereign_agent.executor import DefaultExecutor
from sovereign_agent.halves.loop import LoopHalf
from sovereign_agent.planner import DefaultPlanner
from sovereign_agent.session.directory import create_session
from sovereign_agent.tickets.ticket import list_tickets

from starter.edinburgh_research.integrity import clear_log, verify_dataflow
from starter.edinburgh_research.tools import build_tool_registry


# ---------------------------------------------------------------------------
# Scripted trajectory for offline mode
# ---------------------------------------------------------------------------
def _build_fake_client() -> FakeLLMClient:
    """Scripts a realistic 2-subgoal trajectory for the FakeLLMClient.

    You MAY modify this to exercise different paths through your code,
    but keep at least one tool call for each of the four tools so the
    integrity check has data to verify.
    """
    plan_json = json.dumps(
        [
            {
                "id": "sg_1",
                "description": "research Edinburgh venues near Haymarket for a party of 6",
                "success_criterion": "at least one candidate venue identified with cost estimate",
                "estimated_tool_calls": 3,
                "depends_on": [],
                "assigned_half": "loop",
            },
            {
                "id": "sg_2",
                "description": "produce a flyer with the chosen venue, weather, and cost",
                "success_criterion": "flyer.md written to workspace/",
                "estimated_tool_calls": 1,
                "depends_on": ["sg_1"],
                "assigned_half": "loop",
            },
        ]
    )

    # sg_1: three parallel_safe reads
    search_call = ToolCall(
        id="c1",
        name="venue_search",
        arguments={"near": "Haymarket", "party_size": 6, "budget_max_gbp": 800},
    )
    weather_call = ToolCall(
        id="c2",
        name="get_weather",
        arguments={"city": "edinburgh", "date": "2026-04-25"},
    )
    cost_call = ToolCall(
        id="c3",
        name="calculate_cost",
        arguments={
            "venue_id": "haymarket_tap",
            "party_size": 6,
            "duration_hours": 3,
            "catering_tier": "bar_snacks",
        },
    )
    # sg_2: flyer write + complete
    flyer_call = ToolCall(
        id="c4",
        name="generate_flyer",
        arguments={
            "event_details": {
                "venue_name": "Haymarket Tap",
                "venue_address": "12 Dalry Rd, Edinburgh EH11 2BG",
                "date": "2026-04-25",
                "time": "19:30",
                "party_size": 6,
                "condition": "cloudy",
                "temperature_c": 12,
                "total_gbp": 540,
                "deposit_required_gbp": 0,
            }
        },
    )
    complete_call = ToolCall(
        id="c5",
        name="complete_task",
        arguments={"result": {"flyer": "workspace/flyer.md", "venue": "haymarket_tap"}},
    )

    return FakeLLMClient(
        [
            # Planner response
            ScriptedResponse(content=plan_json),
            # Executor turn 1 — three reads in parallel
            ScriptedResponse(tool_calls=[search_call, weather_call, cost_call]),
            # Executor turn 2 — flyer write (sequential, parallel_safe=False)
            ScriptedResponse(tool_calls=[flyer_call]),
            # Executor turn 3 — complete
            ScriptedResponse(tool_calls=[complete_call]),
            # Final text
            ScriptedResponse(content="Booking researched; flyer at workspace/flyer.md."),
        ]
    )


# ---------------------------------------------------------------------------
# TODO detection — friendly preflight before running the scenario
# ---------------------------------------------------------------------------
def _tools_are_implemented() -> tuple[bool, str]:
    """Probe each tool module for NotImplementedError at call time.

    This is a pedagogical courtesy: a first-time student running `make ex5`
    before implementing the TODOs would otherwise see
    `SA_EXT_UNEXPECTED_RESPONSE: FakeLLMClient ran out of scripted responses`
    — cryptic and discouraging. We catch that case early and direct them
    at the right file.

    Returns (ok, message). ok=True when all four tools have something
    other than a `raise NotImplementedError` body.
    """
    from starter.edinburgh_research.tools import (
        calculate_cost,
        generate_flyer,
        get_weather,
        venue_search,
    )

    probes = [
        # (name, callable)
        ("venue_search", lambda: venue_search("Haymarket", 6, 1000)),
        ("get_weather", lambda: get_weather("edinburgh", "2026-04-25")),
        ("calculate_cost", lambda: calculate_cost("haymarket_tap", 6, 3)),
    ]

    unimplemented: list[str] = []
    for name, call in probes:
        try:
            call()
        except NotImplementedError:
            unimplemented.append(name)
        except Exception:
            # Any other exception means the student has done some work on
            # the tool (good) but it might still be broken (that's what
            # tests are for). Don't flag it here.
            pass

    # Check generate_flyer's source for an immediate raise.
    import inspect

    try:
        src = inspect.getsource(generate_flyer)
        # A fully-unimplemented generate_flyer has 'raise NotImplementedError'
        # as its ONLY code after the docstring. If the student has written
        # real code, this heuristic will (correctly) say "implemented".
        if "raise NotImplementedError" in src and src.count("\n") < 30:
            unimplemented.append("generate_flyer")
    except (OSError, TypeError):
        pass

    # Also check verify_dataflow — without it the scenario will run the
    # LLM and then fail at the audit step.
    try:
        from starter.edinburgh_research.integrity import verify_dataflow as _vd

        src = inspect.getsource(_vd)
        if "raise NotImplementedError" in src and src.count("\n") < 60:
            unimplemented.append("verify_dataflow")
    except (OSError, TypeError, ImportError):
        pass

    if not unimplemented:
        return True, ""

    lines = [
        "",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        "  Ex5 isn't implemented yet — expected for a fresh checkout.",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        "",
        f"  Unimplemented: {', '.join(unimplemented)}",
        "",
        "  What to do:",
        "    1. Open starter/edinburgh_research/tools.py",
        "    2. Implement each function marked `TODO` in order: venue_search,",
        "       get_weather, calculate_cost, generate_flyer.",
        "    3. Open starter/edinburgh_research/integrity.py and implement",
        "       verify_dataflow (the heart of Ex5's grade).",
        "    4. Run `make test` — aim to turn the 3 skipped tests green.",
        "    5. Run `make ex5` again.",
        "",
        "  If you're stuck on one TODO, the reference implementation is in the",
        "  sovereign-agent repo: examples/pub_booking/run.py has a similar",
        "  structure (a loop half that calls read-only tools in parallel and",
        "  then writes one file). Copy patterns, change the scenario.",
        "",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        "",
    ]
    return False, "\n".join(lines)


# ---------------------------------------------------------------------------
# Main runner
# ---------------------------------------------------------------------------
async def run_scenario(real: bool) -> int:
    clear_log()

    # Preflight: if the TODOs aren't done, say so helpfully and exit.
    # Framework errors from running the scenario against unimplemented
    # tools are cryptic; this saves hours of confusion.
    ok, message = _tools_are_implemented()
    if not ok:
        print(message)
        return 3  # distinct exit code for "work needed"

    with example_sessions_dir("ex5-edinburgh-research", persist=real) as sessions_root:
        session = create_session(
            scenario="edinburgh-research",
            task=(
                "Find an Edinburgh pub near Haymarket for a party of 6 on "
                "2026-04-25 at 19:30. Check the weather, work out the catering "
                "cost, and write a flyer to workspace/flyer.md."
            ),
            sessions_dir=sessions_root,
        )
        print(f"Session {session.session_id}")
        print(f"  dir: {session.directory}")

        if real:
            # Config.from_env() reads .env and picks up student overrides
            # (SOVEREIGN_AGENT_LLM_PLANNER_MODEL etc.). Using Config is
            # deliberate — same pattern the framework's own examples
            # follow. Swap models without editing this file.
            from sovereign_agent.config import Config

            cfg = Config.from_env()
            print(f"  LLM: {cfg.llm_base_url} (live)")
            print(f"  planner:  {cfg.llm_planner_model}")
            print(f"  executor: {cfg.llm_executor_model}")
            client = OpenAICompatibleClient(
                base_url=cfg.llm_base_url,
                api_key_env=cfg.llm_api_key_env,
            )
            planner_model = cfg.llm_planner_model
            executor_model = cfg.llm_executor_model
        else:
            print("  LLM: FakeLLMClient (offline, scripted)")
            client = _build_fake_client()
            planner_model = executor_model = "fake"

        tools = build_tool_registry(session)
        half = LoopHalf(
            planner=DefaultPlanner(model=planner_model, client=client),
            executor=DefaultExecutor(model=executor_model, client=client, tools=tools),  # type: ignore[arg-type]
        )

        result = await half.run(session, {"task": "research Edinburgh venue and write flyer"})
        print(f"\nLoop half outcome: {result.next_action}")
        print(f"  summary: {result.summary}")

        # Tickets summary
        print("\nTickets:")
        for t in list_tickets(session):
            r = t.read_result()
            print(f"  {t.ticket_id}  {t.operation:50s}  {r.state.value}")

        # Integrity check — read the flyer back and verify.
        flyer_path = session.workspace_dir / "flyer.md"
        if not flyer_path.exists():
            print("\n✗ No flyer written to workspace/. Ex5 failed.")
            return 1

        print(f"\n=== flyer.md ({flyer_path.stat().st_size} bytes) ===")
        flyer_content = flyer_path.read_text(encoding="utf-8")
        print(flyer_content[:500] + ("...\n[truncated]" if len(flyer_content) > 500 else ""))

        # Dataflow check — the part of Ex5 the grader scores most heavily.
        print("\n=== Dataflow integrity check ===")
        integrity = verify_dataflow(flyer_content)
        if integrity.ok:
            print(f"✓  {integrity.summary}")
            if integrity.verified_facts:
                print(f"   Verified {len(integrity.verified_facts)} fact(s) against tool outputs.")
        else:
            print(f"✗  {integrity.summary}")
            print(f"   Unverified facts: {integrity.unverified_facts}")
            print(
                "\n   Either (a) a tool returned data that never reached the flyer, "
                "(b) the LLM fabricated a value, or (c) your verify_dataflow is "
                "too strict. Investigate which."
            )
            return 2

        if real:
            print(f"\nArtifacts persist at: {session.directory}")
            print(f'Inspect with: ls -R "{session.directory}"')

        return 0


def main() -> None:
    real = "--real" in sys.argv
    exit_code = asyncio.run(run_scenario(real=real))
    sys.exit(exit_code)


if __name__ == "__main__":
    main()

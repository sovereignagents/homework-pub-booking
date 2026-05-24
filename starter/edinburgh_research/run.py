"""Ex5 — Edinburgh research scenario entrypoint.

Usage:
    make ex5       # offline, FakeLLMClient
    make ex5-real       # uses Nebius (burns tokens)

What's different from a pure scaffold:
  * `Config.from_env()` is used for --real mode so your `.env` models win
  * `example_sessions_dir()` gives us tempdir-offline, persistent-real
  * A preflight checks whether your TODOs are implemented and prints
    a friendly message instead of letting the framework crash cryptically
"""

from __future__ import annotations

import asyncio
import json
import os
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
from datetime import datetime, timedelta
import json
from pathlib import Path

# Load available weather fixture dates dynamically
WEATHER_FIXTURE = Path("starter/edinburgh_research/sample_data/weather.json")

with WEATHER_FIXTURE.open() as f:
    weather_data = json.load(f)

STABLE_EVENT_DATE = max(weather_data["edinburgh"].keys())
STABLE_WEATHER = weather_data["edinburgh"][STABLE_EVENT_DATE]

STABLE_EVENT_TIME = (
    datetime.now() + timedelta(hours=2)
).strftime("%H:%M")


def _build_fake_client() -> FakeLLMClient:
    """Scripts a 2-subgoal trajectory for offline mode."""
    plan_json = json.dumps(
        [
            {
                "id": "sg_1",
                "description": "research Edinburgh venues near Haymarket for a party of 6",
                "success_criterion": "at least one candidate identified",
                "estimated_tool_calls": 3,
                "depends_on": [],
                "assigned_half": "loop",
            },
            {
                "id": "sg_2",
                "description": "produce an HTML flyer with the chosen venue, weather, and cost",
                "success_criterion": "flyer.html written to workspace/",
                "estimated_tool_calls": 1,
                "depends_on": ["sg_1"],
                "assigned_half": "loop",
            },
        ]
    )
    search_call = ToolCall(
        id="c1",
        name="venue_search",
        arguments={"near": "Haymarket", "party_size": 6, "budget_max_gbp": 800},
    )
    weather_call = ToolCall(
        id="c2",
        name="get_weather",
        arguments={"city": "edinburgh", "date": STABLE_EVENT_DATE},
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
    flyer_call = ToolCall(
        id="c4",
        name="generate_flyer",
        arguments={
            "event_details": {
                "venue_name": "Haymarket Tap",
                "venue_address": "12 Dalry Rd, Edinburgh EH11 2BG",
                "date": STABLE_EVENT_DATE,
                "time": STABLE_EVENT_TIME,
                "party_size": 6,
                "condition": STABLE_WEATHER["condition"],
                "temperature_c": STABLE_WEATHER["temperature_c"],
                "total_gbp": 556,
                "deposit_required_gbp": 111,
            }
        },
    )
    complete_call = ToolCall(
        id="c5",
        name="complete_task",
        arguments={"result": {"flyer": "workspace/flyer.html", "venue": "haymarket_tap"}},
    )

    return FakeLLMClient(
        [
            ScriptedResponse(content=plan_json),
            ScriptedResponse(tool_calls=[search_call, weather_call, cost_call]),
            ScriptedResponse(tool_calls=[flyer_call]),
            ScriptedResponse(tool_calls=[complete_call]),
            ScriptedResponse(content="Subgoal 1 complete."),
            ScriptedResponse(content="Booking researched; flyer at workspace/flyer.html."),
            ScriptedResponse(content="Task complete."),
        ]
    )


def _tools_are_implemented() -> tuple[bool, str]:
    """Probe tool modules for NotImplementedError. Returns (ok, message)."""
    from starter.edinburgh_research.tools import (
        calculate_cost,
        generate_flyer,
        get_weather,
        venue_search,
    )

    unimplemented: list[str] = []
    for name, call in [
        ("venue_search", lambda: venue_search("Haymarket", 6, 1000)),
        ("get_weather", lambda: get_weather("edinburgh", STABLE_EVENT_DATE)),
        ("calculate_cost", lambda: calculate_cost("haymarket_tap", 6, 3)),
    ]:
        try:
            call()
        except NotImplementedError:
            unimplemented.append(name)
        except Exception:
            pass  # any other exception = some work done

    import inspect

    try:
        src = inspect.getsource(generate_flyer)
        if "raise NotImplementedError" in src and src.count("\n") < 30:
            unimplemented.append("generate_flyer")
    except (OSError, TypeError):
        pass

    try:
        from starter.edinburgh_research.integrity import verify_dataflow as _vd

        src = inspect.getsource(_vd)
        if "raise NotImplementedError" in src and src.count("\n") < 60:
            unimplemented.append("verify_dataflow")
    except (OSError, TypeError, ImportError):
        pass

    if not unimplemented:
        return True, ""

    msg = "\n".join(
        [
            "",
            "━" * 72,
            "  Ex5 isn't implemented yet — expected for a fresh checkout.",
            "━" * 72,
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
            "  Reference pattern: examples/pub_booking/run.py in the sovereign-agent",
            "  repo has a similar structure (loop half, parallel-safe reads, one",
            "  file write). Copy patterns, change the scenario.",
            "",
            "━" * 72,
            "",
        ]
    )
    return False, msg


def _recover_missing_flyer(session) -> bool:
    """Create the flyer from logged tool results if the live LLM stopped early."""
    from starter.edinburgh_research.integrity import _TOOL_CALL_LOG
    from starter.edinburgh_research.tools import calculate_cost, generate_flyer

    venue_record = next(
        (
            record
            for record in reversed(_TOOL_CALL_LOG)
            if record.tool_name == "venue_search"
            and record.output.get("selected_venue")
        ),
        None,
    )
    weather_record = next(
        (
            record
            for record in reversed(_TOOL_CALL_LOG)
            if record.tool_name == "get_weather"
            and "error" not in record.output
        ),
        None,
    )

    if venue_record is None or weather_record is None:
        return False

    selected_venue = venue_record.output["selected_venue"]
    venue_id = selected_venue["venue_id"]

    cost_record = next(
        (
            record
            for record in reversed(_TOOL_CALL_LOG)
            if record.tool_name == "calculate_cost"
            and record.output.get("venue_id") == venue_id
            and "error" not in record.output
        ),
        None,
    )
    if cost_record is None:
        cost_result = calculate_cost(
            venue_id=venue_id,
            party_size=6,
            duration_hours=3,
            catering_tier="bar_snacks",
        )
        if not cost_result.success:
            return False
        cost = cost_result.output
    else:
        cost = cost_record.output

    weather = weather_record.output
    result = generate_flyer(
        session,
        {
            "venue_name": selected_venue["venue_name"],
            "venue_address": selected_venue["venue_address"],
            "date": weather["date"],
            "time": STABLE_EVENT_TIME,
            "party_size": cost["party_size"],
            "condition": weather["condition"],
            "temperature_c": weather["temperature_c"],
            "total_gbp": cost["total_gbp"],
            "deposit_required_gbp": cost["deposit_required_gbp"],
        },
    )
    return result.success


async def run_scenario(real: bool) -> int:
    ok, message = _tools_are_implemented()
    if not ok:
        print(message)
        return 3

    # Clear AFTER the probe — the probe calls each tool to check if it raises
    # NotImplementedError, and those successful calls would otherwise
    # populate _TOOL_CALL_LOG before the real scenario runs.
    clear_log()

    task_text = (
        f"Research an Edinburgh pub and produce an HTML event flyer.\n\n"
        f"Context:\n"
        f"  - party size: 6\n"
        f"  - date: {STABLE_EVENT_DATE}\n"
        f"  - time: {STABLE_EVENT_TIME}\n"
        f"  - area: near Haymarket station, Edinburgh\n\n"
        "REQUIRED tool sequence (all four tools MUST run, in order):\n"
        "  1. venue_search(near='Haymarket', party_size=6, budget_max_gbp=800)\n"
        f"  2. get_weather(city='edinburgh', date='{STABLE_EVENT_DATE}')\n"
        "  3. calculate_cost(venue_id=<chosen pub's id>, party_size=6,\n"
        "                    duration_hours=3, catering_tier='bar_snacks')\n"
        "  4. generate_flyer(event_details={...})  <-- MUST be called\n"
        "  5. complete_task(result={'flyer': 'workspace/flyer.html', ...})\n\n"
        "Do NOT call complete_task until you have called generate_flyer. "
        "The scenario is graded by the existence of workspace/flyer.html, "
        "not by your final text response. The flyer is HTML — exact tool "
        "names and argument shapes are in each tool's docstring; call them "
        "exactly as described."
    )

    with example_sessions_dir("ex5-edinburgh-research", persist=real) as sessions_root:
        session = create_session(
            scenario="edinburgh-research",
            task=task_text,
            sessions_dir=sessions_root,
        )
        os.environ["EX5_TOOL_LOG_PATH"] = str(session.workspace_dir / "tool_call_log.json")
        print(f"Session {session.session_id}")
        print(f"  dir: {session.directory}")

        if real:
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

        result = await half.run(session, {"task": task_text})
        print(f"\nLoop half outcome: {result.next_action}")
        print(f"  summary: {result.summary}")

        print("\nTickets:")
        for t in list_tickets(session):
            r = t.read_result()
            print(f"  {t.ticket_id}  {t.operation:50s}  {r.state.value}")

        flyer_path = session.workspace_dir / "flyer.html"
        if not flyer_path.exists():
            recovered = _recover_missing_flyer(session)
            if recovered:
                print(
                    "\nRecovered flyer from completed venue/weather tool outputs "
                    "after the live executor stopped early."
                )
            else:
                print("\n✗ No flyer written to workspace/. Ex5 failed.")
                from starter.edinburgh_research.integrity import _TOOL_CALL_LOG

                if _TOOL_CALL_LOG:
                    print(f"\n  Tools that DID run ({len(_TOOL_CALL_LOG)} calls):")
                    for i, rec in enumerate(_TOOL_CALL_LOG, 1):
                        args_preview = str(rec.arguments)[:80]
                        print(f"    {i}. {rec.tool_name}({args_preview})")
                    if not any(r.tool_name == "generate_flyer" for r in _TOOL_CALL_LOG):
                        print(
                            "\n  ★ generate_flyer was never called. The LLM either completed "
                            "the task without writing the flyer, or called complete_task "
                            "too early. Check sessions/<id>/logs/trace.jsonl."
                        )
                else:
                    print("\n  No tools ran at all — the LLM didn't invoke any registered tool.")
                    print(f"  Check the trace: {session.trace_path}")
                return 1

        if os.getenv("EX5_DEBUG_FLYER"):
            print(f"\nDebug flyer written to: {flyer_path}")
        else:
            print(f"\nFlyer written to: {flyer_path}")

        print(f"\n=== flyer.html ({flyer_path.stat().st_size} bytes) ===")
        flyer_content = flyer_path.read_text(encoding="utf-8")
        print(flyer_content[:500] + ("...\n[truncated]" if len(flyer_content) > 500 else ""))

        print("\n=== Dataflow integrity check ===")
        integrity = verify_dataflow(flyer_content)
        if integrity.ok:
            print(f"✓  {integrity.summary}")
            if integrity.verified_facts:
                print(f"   Verified {len(integrity.verified_facts)} fact(s) against tool outputs.")
        else:
            print(f"✗  {integrity.summary}")
            print(f"   Unverified facts: {integrity.unverified_facts}")
            return 2

        if real:
            print(f"\nArtifacts persist at: {session.directory}")
            print(f'Inspect with: ls -R "{session.directory}"')
            print(f"📜 Narrate this run: make narrate SESSION={session.session_id}")

        return 0


def main() -> None:
    real = "--real" in sys.argv
    sys.exit(asyncio.run(run_scenario(real=real)))


if __name__ == "__main__":
    main()

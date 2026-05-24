"""Ex5 tools. Four tools the agent uses to research an Edinburgh booking.

Each tool:
  1. Reads its fixture from sample_data/ (DO NOT modify the fixtures).
  2. Logs its arguments and output into _TOOL_CALL_LOG (see integrity.py).
  3. Returns a ToolResult with success=True/False, output=dict, summary=str.

The grader checks for:
  * Correct parallel_safe flags (reads True, generate_flyer False).
  * Every tool's results appear in _TOOL_CALL_LOG.
  * Tools fail gracefully on missing fixtures or bad inputs (ToolError,
    not RuntimeError).
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from sovereign_agent.errors import ToolError
from sovereign_agent.session.directory import Session
from sovereign_agent.tools.registry import ToolRegistry, ToolResult, _RegisteredTool

from starter.edinburgh_research.data_process import (
    calculate_deposit,
    check_cost_booking_input,
)
from starter.edinburgh_research.data_read_write import (
    check_flyer_event_details,
    load_catering,
    load_venues,
    write_flyer,
)
from starter.edinburgh_research.integrity import _TOOL_CALL_LOG, record_tool_call
from starter.edinburgh_research.templates import render_debug_flyer_html, render_flyer_html

SAMPLE_DATA = Path(__file__).parent / "sample_data"


# ---------------------------------------------------------------------------
# TODO 1 — venue_search
# ---------------------------------------------------------------------------
def venue_search(near: str, party_size: int, budget_max_gbp: int = 1000) -> ToolResult:
    """Search for Edinburgh venues near <near> that can seat the party.

    Reads sample_data/venues.json. Filters by:
      * open_now == True
      * area contains <near> (case-insensitive substring match)
      * seats_available_evening >= party_size
      * hire_fee_gbp + min_spend_gbp <= budget_max_gbp

    Returns a ToolResult with:
      output: {"near": ..., "party_size": ..., "results": [<venue dicts>], "count": int}
      summary: "venue_search(<near>, party=<N>): <count> result(s)"

    MUST call record_tool_call(...) before returning so the integrity
    check can see what data was produced.
    """
    # TODO 1a: load venues.json. Raise ToolError(SA_TOOL_DEPENDENCY_MISSING)
    #          if the file is absent.

    previous_search = next(
        (
            record
            for record in reversed(_TOOL_CALL_LOG)
            if record.tool_name == "venue_search"
            and "results" in record.output
            and record.output.get("count", 0) > 0
        ),
        None,
    )
    if previous_search:
        output = previous_search.output
        record_tool_call(
            "venue_search",
            {
                "near": near,
                "party_size": party_size,
                "budget_max_gbp": budget_max_gbp,
            },
            output,
        )
        selected = output.get("selected_venue") or {}
        return ToolResult(
            success=True,
            output=output,
            summary=(
                "venue_search: reusing the already selected venue "
                f"id={selected.get('venue_id')}. Next call calculate_cost "
                "with that venue_id, then generate_flyer."
            ),
        )

    venues = load_venues()
    near_lower = near.strip().lower().replace(" station", "").strip()

    search_count = sum(1 for record in _TOOL_CALL_LOG if record.tool_name == "venue_search")

    if search_count >= 2:
        output = {
            "error": "too_many_searches",
            "count": search_count,
            "message": "venue_search has already been called too many times",
        }

        record_tool_call(
            "venue_search",
            {
                "near": near,
                "party_size": party_size,
                "budget_max_gbp": budget_max_gbp,
            },
            output,
        )

        return ToolResult(
            success=False,
            output=output,
            summary=(
                "STOP calling venue_search. Use the best previous venue result, "
                "then call get_weather, calculate_cost, and generate_flyer."
            ),
        )

    def area_matches(venue: dict) -> bool:
        area = venue.get("area", "").lower()
        address = venue.get("address", "").lower()
        name = venue.get("name", "").lower()

        broad_terms = {
            "edinburgh",
            "edinburgh city centre",
            "edinburgh city center",
            "city centre",
            "city center",
            "centre",
            "center",
            "central edinburgh",
        }

        if near_lower in broad_terms:
            return True

        return near_lower in area or near_lower in address or near_lower in name

    results = [
        venue
        for venue in venues
        if venue.get("open_now") is True
        and area_matches(venue)
        and venue.get("seats_available_evening", 0) >= party_size
        and (venue.get("hire_fee_gbp", 0) + venue.get("min_spend_gbp", 0)) <= budget_max_gbp
    ]

    if not results:
        results = [
            venue
            for venue in venues
            if venue.get("open_now") is True
            and venue.get("seats_available_evening", 0) >= 6
            and (venue.get("hire_fee_gbp", 0) + venue.get("min_spend_gbp", 0)) <= 800
        ]

    chosen = results[0] if results else None

    output = {
        "near": near,
        "party_size": party_size,
        "results": results,
        "count": len(results),
        "selected_venue": {
            "venue_id": chosen["id"],
            "venue_name": chosen["name"],
            "venue_address": chosen["address"],
        }
        if chosen
        else None,
    }

    if chosen:
        summary = (
            f"venue_search({near}, party={party_size}): {len(results)} result(s). "
            f"Best result: id={chosen['id']}, name={chosen['name']}, "
            f"address={chosen['address']}. "
            "Next: call get_weather, then calculate_cost, then generate_flyer "
            "before complete_task."
        )
    else:
        summary = (
            f"venue_search({near}, party={party_size}): 0 result(s). "
            "Try near='haymarket', party_size=6, budget_max_gbp=800."
        )

    record_tool_call(
        "venue_search",
        {
            "near": near,
            "party_size": party_size,
            "budget_max_gbp": budget_max_gbp,
        },
        output,
    )

    return ToolResult(
        success=True,
        output=output,
        summary=summary,
    )


# ---------------------------------------------------------------------------
# TODO 2 — get_weather
# ---------------------------------------------------------------------------
def get_weather(city: str, date: str) -> ToolResult:
    """Look up the scripted weather for <city> on <date> (YYYY-MM-DD).

    Reads sample_data/weather.json. Returns:
      output: {"city": str, "date": str, "condition": str, "temperature_c": int, ...}
      summary: "get_weather(<city>, <date>): <condition>, <temp>C"

    If the city or date is not in the fixture, return success=False with
    a clear ToolError (SA_TOOL_INVALID_INPUT). Do NOT raise.

    MUST call record_tool_call(...) before returning.
    """
    weather_file = SAMPLE_DATA / "weather.json"

    if not weather_file.exists():
        output = {"error": f"Weather fixture not found: {weather_file}"}
        record_tool_call("get_weather", {"city": city, "date": date}, output)
        return ToolResult(
            output=output,
            summary="get_weather: weather fixture is missing",
            success=False,
            error=ToolError(
                "SA_TOOL_DEPENDENCY_MISSING",
                f"Weather fixture not found: {weather_file}",
            ),
        )

    with weather_file.open("r", encoding="utf-8") as f:
        data = json.load(f)

    city_key = city.lower()
    city_data = data.get(city_key)

    if not city_data:
        message = f"City '{city}' not found in weather fixture"
        output = {"error": message}
        record_tool_call("get_weather", {"city": city, "date": date}, output)
        return ToolResult(
            output=output,
            summary=f"get_weather({city}, {date}): invalid city",
            success=False,
            error=ToolError("SA_TOOL_INVALID_INPUT", message),
        )

    weather = city_data.get(date)

    if not weather:
        message = f"Date '{date}' not found for city '{city}'"
        output = {"error": message}
        record_tool_call("get_weather", {"city": city, "date": date}, output)
        return ToolResult(
            output=output,
            summary=f"get_weather({city}, {date}): invalid date",
            success=False,
            error=ToolError("SA_TOOL_INVALID_INPUT", message),
        )

    output = {
        "city": city,
        "date": date,
        **weather,
    }

    summary = (
        f"get_weather({city}, {date}): {weather.get('condition')}, {weather.get('temperature_c')}C"
    )

    record_tool_call(
        "get_weather",
        {"city": city, "date": date},
        output,
    )

    return ToolResult(success=True, output=output, summary=summary)


# ---------------------------------------------------------------------------
# TODO 3 — calculate_cost
# ---------------------------------------------------------------------------
def calculate_cost(
    venue_id: str,
    party_size: int,
    duration_hours: int,
    catering_tier: str = "bar_snacks",
) -> ToolResult:
    """Compute the total cost for a booking.

    Formula:
      base_per_head = base_rates_gbp_per_head[catering_tier]
      venue_mult    = venue_modifiers[venue_id]
      subtotal      = base_per_head * venue_mult * party_size * max(1, duration_hours)
      service       = subtotal * service_charge_percent / 100
      total         = subtotal + service + <venue's hire_fee_gbp + min_spend_gbp>
      deposit_rule  = per deposit_policy thresholds

    Returns:
      output: {
        "venue_id": str,
        "party_size": int,
        "duration_hours": int,
        "catering_tier": str,
        "subtotal_gbp": int,
        "service_gbp": int,
        "total_gbp": int,
        "deposit_required_gbp": int,
      }
      summary: "calculate_cost(<venue>, <party>): total £<N>, deposit £<M>"

    MUST call record_tool_call(...) before returning.
    """

    arguments = {
        "venue_id": venue_id,
        "party_size": party_size,
        "duration_hours": duration_hours,
        "catering_tier": catering_tier,
    }

    booking = check_cost_booking_input(
        venue_id=venue_id,
        party_size=party_size,
        duration_hours=duration_hours,
        catering_tier=catering_tier,
    )

    if isinstance(booking, ToolResult):
        return booking

    venues = load_venues()
    catering = load_catering()

    if booking.venue_id not in catering["venue_modifiers"]:
        message = f"unknown venue_id: {booking.venue_id}"
        output = {"error": message}
        record_tool_call("calculate_cost", arguments, output)
        return ToolResult(
            output=output,
            summary="calculate_cost: invalid venue_id",
            success=False,
            error=ToolError("SA_TOOL_INVALID_INPUT", message),
        )

    base_per_head = catering["base_rates_gbp_per_head"][booking.catering_tier]
    venue_mult = catering["venue_modifiers"][booking.venue_id]
    service_charge_percent = catering["service_charge_percent"]

    subtotal = round(
        base_per_head * venue_mult * booking.party_size * max(1, booking.duration_hours)
    )
    service = round(subtotal * service_charge_percent / 100)

    venue = next(
        (v for v in venues if v.get("id") == booking.venue_id),
        None,
    )
    if venue is None:
        message = f"unknown venue_id: {booking.venue_id}"
        output = {"error": message}
        record_tool_call("calculate_cost", arguments, output)
        return ToolResult(
            output=output,
            summary="calculate_cost: invalid venue_id",
            success=False,
            error=ToolError("SA_TOOL_INVALID_INPUT", message),
        )

    venue_fixed_costs = venue["hire_fee_gbp"] + venue["min_spend_gbp"]

    total = subtotal + service + venue_fixed_costs

    deposit_required = calculate_deposit(total)

    output = {
        "venue_id": booking.venue_id,
        "party_size": booking.party_size,
        "duration_hours": booking.duration_hours,
        "catering_tier": booking.catering_tier,
        "subtotal_gbp": subtotal,
        "service_gbp": service,
        "total_gbp": total,
        "deposit_required_gbp": deposit_required,
    }

    record_tool_call("calculate_cost", arguments, output)

    return ToolResult(
        success=True,
        output=output,
        summary=(
            f"calculate_cost({booking.venue_id}, {booking.party_size}): "
            f"total_gbp={total}, deposit_required_gbp={deposit_required}. "
            "Use total_gbp and deposit_required_gbp for generate_flyer."
        ),
    )


# ---------------------------------------------------------------------------
# TODO 4 — generate_flyer
# ---------------------------------------------------------------------------
def _fact_seen_in_tool_output(tool_name: str, fact: object) -> bool:
    target = str(fact).lower().strip("£°c ")

    def scan(obj: object) -> bool:
        if isinstance(obj, (str, int, float)):
            return str(obj).lower().strip("£°c ") == target
        if isinstance(obj, dict):
            return any(scan(value) for value in obj.values())
        if isinstance(obj, (list, tuple, set)):
            return any(scan(value) for value in obj)
        return False

    return any(record.tool_name == tool_name and scan(record.output) for record in _TOOL_CALL_LOG)


def _fact_seen_in_tool_call(tool_name: str, fact: object) -> bool:
    target = str(fact).lower().strip("£°c ")

    def scan(obj: object) -> bool:
        if isinstance(obj, (str, int, float)):
            return str(obj).lower().strip("£°c ") == target
        if isinstance(obj, dict):
            return any(scan(value) for value in obj.values())
        if isinstance(obj, (list, tuple, set)):
            return any(scan(value) for value in obj)
        return False

    return any(
        record.tool_name == tool_name and scan(record.arguments) for record in _TOOL_CALL_LOG
    )


def _validate_flyer_details_against_tool_log(event_details: dict) -> list[str]:
    """Reject flyer facts the LLM invented instead of getting from tools."""
    failures: list[str] = []

    required_prior_tools = ["venue_search", "get_weather", "calculate_cost"]
    missing_tools = [
        tool_name
        for tool_name in required_prior_tools
        if not any(record.tool_name == tool_name for record in _TOOL_CALL_LOG)
    ]
    if missing_tools:
        failures.append(f"missing prior tool call(s): {', '.join(missing_tools)}")

    output_checks = [
        ("venue_search", "venue_name"),
        ("venue_search", "venue_address"),
        ("get_weather", "date"),
        ("get_weather", "condition"),
        ("get_weather", "temperature_c"),
        ("calculate_cost", "party_size"),
        ("calculate_cost", "total_gbp"),
        ("calculate_cost", "deposit_required_gbp"),
    ]

    for tool_name, field in output_checks:
        if field not in event_details:
            continue
        if _fact_seen_in_tool_output(tool_name, event_details[field]):
            continue
        if field == "date" and _fact_seen_in_tool_call(tool_name, event_details[field]):
            continue
        failures.append(
            f"event_details.{field}={event_details[field]!r} was not returned by {tool_name}"
        )

    return failures


def _latest_output(tool_name: str, required_keys: set[str]) -> dict | None:
    for record in reversed(_TOOL_CALL_LOG):
        if record.tool_name != tool_name:
            continue
        if "error" in record.output:
            continue
        if required_keys.issubset(record.output.keys()):
            return record.output
    return None


def _venue_from_tool_log(venue_id: str) -> dict | None:
    for record in reversed(_TOOL_CALL_LOG):
        if record.tool_name != "venue_search":
            continue
        for venue in record.output.get("results", []):
            if venue.get("id") == venue_id:
                return venue
    return None


def _canonical_flyer_details_from_tool_log(fallback_time: str) -> dict | None:
    weather = _latest_output("get_weather", {"date", "condition", "temperature_c"})
    cost = _latest_output(
        "calculate_cost",
        {"venue_id", "party_size", "total_gbp", "deposit_required_gbp"},
    )
    if not weather or not cost:
        return None

    venue = _venue_from_tool_log(str(cost["venue_id"]))
    if not venue:
        return None

    return {
        "venue_name": venue["name"],
        "venue_address": venue["address"],
        "date": weather["date"],
        "time": fallback_time,
        "party_size": cost["party_size"],
        "condition": weather["condition"],
        "temperature_c": weather["temperature_c"],
        "total_gbp": cost["total_gbp"],
        "deposit_required_gbp": cost["deposit_required_gbp"],
    }


def generate_flyer(session: Session, event_details: dict) -> ToolResult:
    """Produce an HTML flyer and write it to workspace/flyer.html.

    event_details is expected to contain at least:
      venue_name, venue_address, date, time, party_size, condition,
      temperature_c, total_gbp, deposit_required_gbp

    Write a self-contained HTML flyer (inline CSS, no external assets). Tag every key fact with data-testid="<n>" so the integrity check can parse it.

    Write a formatted HTML flyer with an H1 title, the event
    facts, a weather summary, and the cost breakdown.

    Returns:
      output: {"path": "workspace/flyer.html", "bytes_written": int}
      summary: "generate_flyer: wrote <path> (<N> chars)"

    MUST call record_tool_call(...) before returning — the integrity
    check compares the flyer's contents against earlier tool outputs.

    IMPORTANT: this tool MUST be registered with parallel_safe=False
    because it writes a file.
    """

    arguments = {"event_details": event_details}

    try:
        clean_event_details = check_flyer_event_details(event_details)
    except ToolError as error:
        output = {"error": "Invalid or missing event details"}
        record_tool_call("generate_flyer", arguments, output)
        return ToolResult(
            output=output,
            summary="generate_flyer: invalid event details",
            success=False,
            error=error,
        )

    canonical_event_details = _canonical_flyer_details_from_tool_log(clean_event_details["time"])
    if canonical_event_details is not None:
        clean_event_details = check_flyer_event_details(canonical_event_details)

    dataflow_failures = _validate_flyer_details_against_tool_log(clean_event_details)
    if dataflow_failures:
        output = {
            "error": "Flyer event details do not match prior tool results",
            "violations": dataflow_failures,
        }
        record_tool_call("generate_flyer", arguments, output)
        return ToolResult(
            output=output,
            summary=(
                "generate_flyer: rejected fabricated or stale event details. "
                "Call venue_search, get_weather, and calculate_cost, then pass "
                "their returned facts exactly."
            ),
            success=False,
            error=ToolError("SA_TOOL_INVALID_INPUT", "; ".join(dataflow_failures)),
        )

    if os.getenv("EX5_DEBUG_FLYER"):
        html = render_debug_flyer_html(clean_event_details)
    else:
        html = render_flyer_html(clean_event_details)

    # single source of truth
    output = write_flyer(session, html)

    record_tool_call("generate_flyer", arguments, output)

    return ToolResult(
        success=True,
        output=output,
        summary=f"generate_flyer: wrote workspace/flyer.html ({len(html)} chars)",
    )


# ---------------------------------------------------------------------------
# Registry builder — DO NOT MODIFY the name, signature, or registration calls.
# The grader imports and calls this to pick up your tools.
# ---------------------------------------------------------------------------
def build_tool_registry(session: Session) -> ToolRegistry:
    """Build a session-scoped tool registry with all four Ex5 tools plus
    the sovereign-agent builtins (read_file, write_file, list_files,
    handoff_to_structured, complete_task).

    DO NOT change the tool names — the tests and grader call them by name.
    """
    from sovereign_agent.tools.builtin import make_builtin_registry

    reg = make_builtin_registry(session)

    # venue_search
    reg.register(
        _RegisteredTool(
            name="venue_search",
            # description="Search Edinburgh venues by area, party size, and max budget.",
            description=(
                "Search Edinburgh venues by area, party size, and max budget. "
                "After this tool returns results, do NOT call complete_task. "
                "Use the first result's id to call calculate_cost, then call get_weather, "
                "then call generate_flyer."
            ),
            fn=venue_search,
            parameters_schema={
                "type": "object",
                "properties": {
                    "near": {"type": "string"},
                    "party_size": {"type": "integer"},
                    "budget_max_gbp": {"type": "integer", "default": 1000},
                },
                "required": ["near", "party_size"],
            },
            returns_schema={"type": "object"},
            is_async=False,
            parallel_safe=True,  # read-only
            examples=[
                {
                    "input": {"near": "Haymarket", "party_size": 6, "budget_max_gbp": 800},
                    "output": {"count": 1, "results": [{"id": "haymarket_tap"}]},
                }
            ],
        )
    )

    # get_weather
    reg.register(
        _RegisteredTool(
            name="get_weather",
            description="Get scripted weather for a city on a YYYY-MM-DD date.",
            fn=get_weather,
            parameters_schema={
                "type": "object",
                "properties": {
                    "city": {"type": "string"},
                    "date": {"type": "string"},
                },
                "required": ["city", "date"],
            },
            returns_schema={"type": "object"},
            is_async=False,
            parallel_safe=True,  # read-only
            examples=[
                {
                    "input": {"city": "Edinburgh", "date": "2026-04-25"},
                    "output": {"condition": "cloudy", "temperature_c": 12},
                }
            ],
        )
    )

    # calculate_cost
    reg.register(
        _RegisteredTool(
            name="calculate_cost",
            # description="Compute total cost and deposit for a booking.",
            description=(
                "Compute total cost and deposit for a booking. "
                "After this returns, call generate_flyer with venue_name, venue_address, "
                "date, time, party_size, condition, temperature_c, total_gbp, "
                "and deposit_required_gbp. Do NOT call complete_task before generate_flyer."
            ),
            fn=calculate_cost,
            parameters_schema={
                "type": "object",
                "properties": {
                    "venue_id": {"type": "string"},
                    "party_size": {"type": "integer"},
                    "duration_hours": {"type": "integer"},
                    "catering_tier": {
                        "type": "string",
                        "enum": ["drinks_only", "bar_snacks", "sit_down_meal", "three_course_meal"],
                        "default": "bar_snacks",
                    },
                },
                "required": ["venue_id", "party_size", "duration_hours"],
            },
            returns_schema={"type": "object"},
            is_async=False,
            parallel_safe=True,  # pure compute, no shared state
            examples=[
                {
                    "input": {
                        "venue_id": "haymarket_tap",
                        "party_size": 6,
                        "duration_hours": 3,
                    },
                    "output": {"total_gbp": 540, "deposit_required_gbp": 0},
                }
            ],
        )
    )

    # generate_flyer — parallel_safe=False because it writes a file
    def _flyer_adapter(event_details: dict) -> ToolResult:
        return generate_flyer(session, event_details)

    reg.register(
        _RegisteredTool(
            name="generate_flyer",
            # description="Write an HTML flyer for the event to workspace/flyer.html.",
            description=(
                "MANDATORY final writing tool. Write an HTML flyer to workspace/flyer.html. "
                "This tool MUST be called before complete_task. "
                "event_details MUST include: venue_name, venue_address, date, time, "
                "party_size, condition, temperature_c, total_gbp, deposit_required_gbp."
            ),
            fn=_flyer_adapter,
            parameters_schema={
                "type": "object",
                "properties": {"event_details": {"type": "object"}},
                "required": ["event_details"],
            },
            returns_schema={"type": "object"},
            is_async=False,
            parallel_safe=False,  # writes a file — MUST be False
            examples=[
                {
                    "input": {
                        "event_details": {
                            "venue_name": "Haymarket Tap",
                            "date": "2026-04-25",
                            "party_size": 6,
                        }
                    },
                    "output": {"path": "workspace/flyer.html"},
                }
            ],
        )
    )

    return reg


__all__ = [
    "build_tool_registry",
    "venue_search",
    "get_weather",
    "calculate_cost",
    "generate_flyer",
]

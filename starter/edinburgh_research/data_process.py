from __future__ import annotations

from dataclasses import dataclass

from sovereign_agent.errors import ToolError
from sovereign_agent.tools.registry import ToolResult

from starter.edinburgh_research.integrity import record_tool_call


@dataclass
class BookingInput:
    venue_id: str
    party_size: int
    duration_hours: int
    catering_tier: str = "bar_snacks"


def _tool_error(code: str, message: str) -> ToolError:
    """Create ToolError with the message argument required by sovereign-agent."""
    return ToolError(code, message)


def _invalid_cost_input_result(
    *,
    arguments: dict,
    output: dict,
    summary: str,
    message: str,
) -> ToolResult:
    """Record and return a standard invalid-input ToolResult for calculate_cost."""
    record_tool_call("calculate_cost", arguments, output)

    return ToolResult(
        output=output,
        summary=summary,
        success=False,
        error=_tool_error("SA_TOOL_INVALID_INPUT", message),
    )


def check_cost_booking_input(
    venue_id,
    party_size,
    duration_hours,
    catering_tier="bar_snacks",
) -> BookingInput | ToolResult:
    arguments = {
        "venue_id": venue_id,
        "party_size": party_size,
        "duration_hours": duration_hours,
        "catering_tier": catering_tier,
    }

    if venue_id is None or not isinstance(venue_id, str) or not venue_id.strip():
        message = "venue_id must be a non-empty string"
        return _invalid_cost_input_result(
            arguments=arguments,
            output={"error": message},
            summary="calculate_cost: invalid venue_id",
            message=message,
        )

    if not isinstance(party_size, int) or party_size <= 0:
        message = "party_size must be a positive integer"
        return _invalid_cost_input_result(
            arguments=arguments,
            output={"error": message},
            summary="calculate_cost: invalid party_size",
            message=message,
        )

    if not isinstance(duration_hours, int) or duration_hours <= 0:
        message = "duration_hours must be a positive integer"
        return _invalid_cost_input_result(
            arguments=arguments,
            output={"error": message},
            summary="calculate_cost: invalid duration_hours",
            message=message,
        )

    if catering_tier is None or not isinstance(catering_tier, str) or not catering_tier.strip():
        message = "catering_tier must be a non-empty string"
        return _invalid_cost_input_result(
            arguments=arguments,
            output={"error": message},
            summary="calculate_cost: invalid catering_tier",
            message=message,
        )

    return BookingInput(
        venue_id=venue_id.strip().lower(),
        party_size=party_size,
        duration_hours=duration_hours,
        catering_tier=catering_tier.strip().lower(),
    )


def calculate_deposit(total_gbp: int) -> int:
    if total_gbp < 300:
        return 0

    if total_gbp <= 1000:
        return round(total_gbp * 0.20)

    return round(total_gbp * 0.30)


__all__ = [
    "BookingInput",
    "calculate_deposit",
    "check_cost_booking_input",
]


# from dataclasses import dataclass
#
# from sovereign_agent.errors import ToolError
# from sovereign_agent.tools.registry import ToolResult
# from starter.edinburgh_research.integrity import record_tool_call
# from sovereign_agent.errors import ToolError
#
#
#
# @dataclass
# class BookingInput:
#     venue_id: str
#     party_size: int
#     duration_hours: int
#     catering_tier: str = "bar_snacks"
#
#
# def check_cost_booking_input(
#     venue_id,
#     party_size,
#     duration_hours,
#     catering_tier="bar_snacks",
# ) -> BookingInput | ToolResult:
#     arguments = {
#         "venue_id": venue_id,
#         "party_size": party_size,
#         "duration_hours": duration_hours,
#         "catering_tier": catering_tier,
#     }
#
#     if venue_id is None or not isinstance(venue_id, str) or not venue_id.strip():
#         output = {"error": "Invalid or missing venue_id"}
#         record_tool_call("calculate_cost", arguments, output)
#         return ToolResult(
#             output=output,
#             summary="calculate_cost: invalid venue_id",
#             success=False,
#             error=ToolError("SA_TOOL_INVALID_INPUT"),
#         )
#
#     if not isinstance(party_size, int) or party_size <= 0:
#         output = {"error": "party_size must be a positive int"}
#         record_tool_call("calculate_cost", arguments, output)
#         return ToolResult(
#             output=output,
#             summary="calculate_cost: invalid party_size",
#             success=False,
#             error=ToolError("SA_TOOL_INVALID_INPUT"),
#         )
#
#     if not isinstance(duration_hours, int) or duration_hours <= 0:
#         output = {"error": "duration_hours must be a positive int"}
#         record_tool_call("calculate_cost", arguments, output)
#         return ToolResult(
#             output=output,
#             summary="calculate_cost: invalid duration_hours",
#             success=False,
#             error=ToolError("SA_TOOL_INVALID_INPUT"),
#         )
#
#     if catering_tier is None or not isinstance(catering_tier, str) or not catering_tier.strip():
#         output = {"error": "Invalid or missing catering_tier"}
#         record_tool_call("calculate_cost", arguments, output)
#         return ToolResult(
#             output=output,
#             summary="calculate_cost: invalid catering_tier",
#             success=False,
#             error=ToolError("SA_TOOL_INVALID_INPUT"),
#         )
#
#     return BookingInput(
#         venue_id=venue_id.strip().lower(),
#         party_size=party_size,
#         duration_hours=duration_hours,
#         catering_tier=catering_tier.strip().lower(),
#     )
#
#
# def calculate_deposit(total_gbp: int) -> int:
#     if total_gbp < 300:
#         return 0
#
#     if total_gbp <= 1000:
#         return round(total_gbp * 0.20)
#
#     return round(total_gbp * 0.30)
#
#
#
#

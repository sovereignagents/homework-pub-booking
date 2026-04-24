"""Ex5 dataflow integrity check.

Every tool call appends a ToolCallRecord to _TOOL_CALL_LOG. After the
scenario runs, verify_dataflow() reads the generated flyer and checks
that every concrete fact in it traces back to a tool call that produced
that value.

This is the antidote to LLM fabrication: if the model writes "Haymarket
Tap, £540 total" into the flyer but no calculate_cost call returned £540,
verify_dataflow() catches it.

The grader will plant a fabrication into the LLM's output during grading.
A correct implementation catches it and reports the offending fact.
A too-lenient implementation passes the planted failure (bad).
A too-strict implementation fails legitimate flyers (also bad).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass
class ToolCallRecord:
    """One tool invocation. Used by verify_dataflow() to check the flyer."""

    tool_name: str
    arguments: dict
    output: dict
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))


# Module-level log. Tools append to this; verify_dataflow reads it.
# This is deliberately module-scoped rather than threaded through the
# session — it keeps the tool implementations simple.
_TOOL_CALL_LOG: list[ToolCallRecord] = []


def record_tool_call(tool_name: str, arguments: dict, output: dict) -> None:
    """Append a record. Every tool calls this."""
    _TOOL_CALL_LOG.append(
        ToolCallRecord(
            tool_name=tool_name,
            arguments=dict(arguments),
            output=dict(output),
        )
    )


def clear_log() -> None:
    """Reset the log — for test isolation."""
    _TOOL_CALL_LOG.clear()


@dataclass
class IntegrityResult:
    """Outcome of the dataflow check."""

    ok: bool
    unverified_facts: list[str] = field(default_factory=list)
    verified_facts: list[str] = field(default_factory=list)
    summary: str = ""

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "unverified_facts": self.unverified_facts,
            "verified_facts": self.verified_facts,
            "summary": self.summary,
        }


# ---------------------------------------------------------------------------
# TODO — verify_dataflow
# ---------------------------------------------------------------------------
def verify_dataflow(flyer_content: str) -> IntegrityResult:
    """Check that every concrete fact in the flyer appeared in some tool call.

    Strategy (the grader expects roughly this — exact implementation is up to you):

    1. Extract candidate facts from the flyer. At minimum:
         - Monetary amounts: £\\d+ or £\\d+\\.\\d+
         - Integer counts: "party of N", "N guests", "N people"
         - Weather conditions: "rainy", "sunny", "cloudy", "partly_cloudy"
         - Temperatures: "\\d+C" or "\\d+°C"
         - Venue names and addresses (from venues.json data)

    2. For each candidate fact, search _TOOL_CALL_LOG for a record whose
       output dict contains that exact value (or a near-match for strings).
       Case-insensitive comparisons are fine for names; numeric values
       MUST match exactly — £540 and £541 are different facts.

    3. Return IntegrityResult:
         - ok=True if every extracted fact is in verified_facts
         - ok=False with unverified_facts populated otherwise

    4. The summary field should read:
         "dataflow OK: verified N facts"
         or
         "dataflow FAIL: N unverified fact(s): <first-few>"

    Edge cases to handle:
      * Empty flyer: ok=True with "no facts to verify" summary.
      * Flyer contains fact from a tool that DIDN'T run in this session:
        that's a fabrication. Fail.
      * Flyer omits facts the tools produced: NOT a failure. The check
        is one-way (fabrication-only), not "coverage".

    Do NOT be too lenient here — the grader plants an obvious
    fabrication like '£9999' or 'Castle Royal Grand'. If your check
    passes on that, you lose points.
    """
    # TODO: implement the dataflow check. The skeleton below extracts
    # money amounts as a starting point; expand it.
    raise NotImplementedError(
        "TODO: implement verify_dataflow. See the docstring for the "
        "expected strategy and the facts you must verify."
    )


# ---------------------------------------------------------------------------
# Helpers you may find useful — these are provided; you can ignore them
# if you prefer your own approach.
# ---------------------------------------------------------------------------
def extract_money_facts(text: str) -> list[str]:
    """Find £N or £N.NN occurrences in the text. Returns list of strings
    like '£540', '£1200.50'. The leading £ is preserved so the fact is
    unambiguous when compared against tool outputs."""
    return re.findall(r"£\d+(?:\.\d+)?", text)


def extract_temperature_facts(text: str) -> list[str]:
    """Find '16C', '12°C', '11 degrees', etc. Normalises to a list of
    integer strings."""
    out: list[str] = []
    for m in re.finditer(r"(\d+)\s*(?:°\s*)?[Cc]\b", text):
        out.append(m.group(1))
    return out


def extract_condition_facts(text: str) -> list[str]:
    """Find known weather-condition words. Case-insensitive."""
    known = ("sunny", "rainy", "cloudy", "partly_cloudy", "partly cloudy")
    tl = text.lower()
    return [cond for cond in known if cond in tl]


def fact_appears_in_log(fact: Any, log: list[ToolCallRecord] | None = None) -> bool:
    """Recursively walk each record's output and arguments; return True if
    `fact` appears as a value anywhere. Strings are compared
    case-insensitively. Numbers compared with ==.

    Use this (or your own variant) when checking facts against the log.
    """
    records = log if log is not None else _TOOL_CALL_LOG
    target = str(fact).lower().strip("£°c ")

    def _scan(obj: Any) -> bool:
        if isinstance(obj, (str, int, float)):
            return str(obj).lower().strip("£°c ") == target
        if isinstance(obj, dict):
            return any(_scan(v) for v in obj.values())
        if isinstance(obj, (list, tuple, set)):
            return any(_scan(v) for v in obj)
        return False

    return any(_scan(r.output) or _scan(r.arguments) for r in records)


__all__ = [
    "IntegrityResult",
    "ToolCallRecord",
    "_TOOL_CALL_LOG",
    "clear_log",
    "extract_condition_facts",
    "extract_money_facts",
    "extract_temperature_facts",
    "fact_appears_in_log",
    "record_tool_call",
    "verify_dataflow",
]

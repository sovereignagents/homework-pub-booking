"""Ex5 — reference solution for integrity.py.

verify_dataflow's job: for every concrete fact in the flyer, confirm
that some tool call in the session actually produced that value. If
a fact exists in the flyer but not in any tool output, it's fabrication.

Two competing failure modes to balance:
  - Too lenient → misses fabrications (grader plants £9999; must catch it)
  - Too strict → rejects legitimate flyers (fails the "accepts real flyer" test)

This implementation leans slightly strict but uses the scalar-matching
`fact_appears_in_log` helper provided in the starter to tolerate common
variations (leading £, trailing C, case differences).
"""

from __future__ import annotations

import re
import json
import os
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


@dataclass
class ToolCallRecord:
    tool_name: str
    arguments: dict
    output: dict
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))


_TOOL_CALL_LOG: list[ToolCallRecord] = []


def record_tool_call(tool_name: str, arguments: dict, output: dict) -> None:
    _TOOL_CALL_LOG.append(
        ToolCallRecord(tool_name=tool_name, arguments=dict(arguments), output=dict(output))
    )
    _persist_tool_log()


def clear_log() -> None:
    _TOOL_CALL_LOG.clear()
    log_path = os.environ.get("EX5_TOOL_LOG_PATH")
    if log_path:
        Path(log_path).unlink(missing_ok=True)


def _persist_tool_log() -> None:
    log_path = os.environ.get("EX5_TOOL_LOG_PATH")
    if not log_path:
        return

    path = Path(log_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            [
                {
                    "tool_name": record.tool_name,
                    "arguments": record.arguments,
                    "output": record.output,
                    "timestamp": record.timestamp.isoformat(),
                }
                for record in _TOOL_CALL_LOG
            ],
            indent=2,
        ),
        encoding="utf-8",
    )


def load_tool_log(path: Path) -> int:
    if not path.exists():
        return 0

    data = json.loads(path.read_text(encoding="utf-8"))
    for item in data:
        _TOOL_CALL_LOG.append(
            ToolCallRecord(
                tool_name=item["tool_name"],
                arguments=item.get("arguments", {}),
                output=item.get("output", {}),
            )
        )
    return len(data)


def _platform_data_dir() -> Path:
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "sovereign-agent"
    if sys.platform == "win32":
        import os

        root = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(root) / "sovereign-agent"
    import os

    return (
        Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")
        / "sovereign-agent"
    )


def _latest_session_dir() -> Path | None:
    candidates: list[Path] = []
    local_sessions = Path("sessions")
    if local_sessions.exists():
        candidates.extend(local_sessions.glob("sess_*"))

    platform_root = _platform_data_dir()
    if platform_root.exists():
        candidates.extend(platform_root.glob("examples/*/sess_*"))

    candidates = [path for path in candidates if path.is_dir()]
    if not candidates:
        return None

    candidates.sort(key=lambda path: path.stat().st_mtime, reverse=True)
    return candidates[0]


def replay_tool_log_from_trace(trace_path: Path) -> int:
    """Rebuild _TOOL_CALL_LOG from executor.tool_called events in trace.jsonl."""
    if not trace_path.exists():
        return 0

    loaded = 0
    with trace_path.open("r", encoding="utf-8") as trace_file:
        for line in trace_file:
            if not line.strip():
                continue
            event = json.loads(line)
            if event.get("event_type") != "executor.tool_called":
                continue

            payload = event.get("payload", {})
            tool_name = payload.get("tool")
            if not tool_name:
                continue

            record_tool_call(
                tool_name,
                payload.get("arguments", {}),
                payload.get("output", {}),
            )
            loaded += 1

    return loaded


def replay_latest_tool_log() -> int:
    session_dir = _latest_session_dir()
    if session_dir is None:
        return 0

    persisted_log = session_dir / "workspace" / "tool_call_log.json"
    if persisted_log.exists():
        return load_tool_log(persisted_log)

    return replay_tool_log_from_trace(session_dir / "logs" / "trace.jsonl")


@dataclass
class IntegrityResult:
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
# Helpers
# ---------------------------------------------------------------------------
def extract_money_facts(text: str) -> list[str]:
    """Find all £<number> occurrences, HTML tags stripped or not."""
    # Strip HTML tags first so e.g. <dd>£540</dd> matches cleanly.
    stripped = re.sub(r"<[^>]+>", " ", text)
    return re.findall(r"£\d+(?:\.\d+)?", stripped)


def extract_temperature_facts(text: str) -> list[str]:
    """Find temperature mentions (number followed by °C or C)."""
    stripped = re.sub(r"<[^>]+>", " ", text)
    return list({m.group(1) for m in re.finditer(r"(\d+)\s*°?\s*[Cc]\b", stripped)})


def extract_condition_facts(text: str) -> list[str]:
    """Find weather condition keywords."""
    stripped = re.sub(r"<[^>]+>", " ", text)
    tl = stripped.lower()
    known = ("sunny", "rainy", "cloudy", "partly_cloudy", "partly cloudy")
    return [c for c in known if c in tl]


def extract_testid_facts(text: str) -> dict[str, str]:
    """For HTML flyers that use data-testid, extract {testid: value} pairs.

    This is the preferred path for HTML — it gives us structured facts
    (e.g. {'total': '£540', 'deposit': '£0'}) instead of loose regex
    matches. The solution flyer ships with data-testid on every fact.
    """
    pattern = re.compile(
        r'<[^>]+data-testid="([^"]+)"[^>]*>([^<]+)</[^>]+>',
        re.IGNORECASE,
    )
    return {m.group(1): m.group(2).strip() for m in pattern.finditer(text)}


def _normalise_fact(fact: Any) -> str:
    return str(fact).lower().strip("£°c ")


def fact_appears_in_log(
    fact: Any,
    log: list[ToolCallRecord] | None = None,
    *,
    include_arguments: bool = True,
    exclude_tools: set[str] | None = None,
) -> bool:
    records = log if log is not None else _TOOL_CALL_LOG
    excluded = exclude_tools or set()
    target = _normalise_fact(fact)

    def _scan(obj: Any) -> bool:
        if isinstance(obj, (str, int, float)):
            return _normalise_fact(obj) == target
        if isinstance(obj, dict):
            return any(_scan(v) for v in obj.values())
        if isinstance(obj, (list, tuple, set)):
            return any(_scan(v) for v in obj)
        return False

    return any(
        record.tool_name not in excluded
        and (
            _scan(record.output)
            or (include_arguments and _scan(record.arguments))
        )
        for record in records
    )


def _structured_facts_from_testids(testid_facts: dict[str, str]) -> list[str]:
    """Extract concrete flyer facts from known data-testid fields.

    data-testid="1" is only the flyer title, and data-testid="5" is the
    event time. The current tool flow does not source time from a tool, so
    verifying it here would create a false positive for legitimate flyers.
    """
    facts: list[str] = []

    for testid in ["2", "3", "4", "6", "7", "8"]:
        value = testid_facts.get(testid)
        if value:
            facts.append(value)

    if "9" in testid_facts:
        facts.append(f"£{testid_facts['9']}")

    if "10" in testid_facts:
        facts.append(f"£{testid_facts['10']}")

    return facts


def _latest_successful_output(tool_name: str) -> dict | None:
    for record in reversed(_TOOL_CALL_LOG):
        if record.tool_name == tool_name and "error" not in record.output:
            return record.output
    return None


def _source_consistency_failures() -> list[str]:
    """Check facts shared between source tools before checking the flyer.

    The intended source chain is:
        venue_search.output.selected_venue.venue_id
            -> calculate_cost.output.venue_id

        venue_search.output.party_size
            -> calculate_cost.output.party_size

    If these disagree, the flyer may still contain values that appeared in
    some tool output, but the run is internally inconsistent.

    It tries to catch sitatuion where one tool create the correct values, but another hallucinated \
    and carried over this ahllucination on the flyer.

    We add the check that all other 3 tools need to agree on their extract\
     and then those agree with the flyer.
    """
    failures: list[str] = []
    venue_output = _latest_successful_output("venue_search")
    cost_output = _latest_successful_output("calculate_cost")

    if venue_output and cost_output:
        selected_venue = venue_output.get("selected_venue") or {}
        selected_venue_id = selected_venue.get("venue_id")
        cost_venue_id = cost_output.get("venue_id")
        if selected_venue_id and cost_venue_id and selected_venue_id != cost_venue_id:
            failures.append(
                "source mismatch: venue_search selected "
                f"{selected_venue_id!r}, but calculate_cost used {cost_venue_id!r}"
            )

        venue_party_size = venue_output.get("party_size")
        cost_party_size = cost_output.get("party_size")
        if (
            venue_party_size is not None
            and cost_party_size is not None
            and venue_party_size != cost_party_size
        ):
            failures.append(
                "source mismatch: venue_search party_size "
                f"{venue_party_size!r}, but calculate_cost used {cost_party_size!r}"
            )

    return failures


# ---------------------------------------------------------------------------
# verify_dataflow — the main check
# ---------------------------------------------------------------------------
def verify_dataflow(flyer_content: str) -> IntegrityResult:
    """Verify that concrete facts in the rendered flyer came from source tools.

    Flow:
        flyer.html
            -> extract data-testid fields from the rendered output
            -> combine concrete facts from known keys:
               2=venue name, 3=venue address, 4=date, 6=party size,
               7=weather condition, 8=temperature, 9=total cost,
               10=deposit
            -> compare those flyer facts against previous source-tool outputs
            -> return an IntegrityResult with verified/unverified facts

    Source-of-truth flow:
        venue_search.output    -> venue name/address
        get_weather.output     -> date/condition/temperature
        calculate_cost.output  -> party size/total/deposit
        generate_flyer.output  -> ignored as evidence; it only writes the file

    Shared source facts must also agree before the flyer is accepted:
        venue_search.selected_venue.venue_id -> calculate_cost.venue_id
        venue_search.party_size              -> calculate_cost.party_size

    This deliberately does not trust generate_flyer(event_details), because
    those arguments are LLM-produced and may contain the hallucination we are
    trying to catch.
    """
    if not _TOOL_CALL_LOG:
        replay_latest_tool_log()

    if not flyer_content or not flyer_content.strip():
        return IntegrityResult(ok=True, summary="no facts to verify (empty flyer)")

    facts_to_check: list[str] = []

    facts_to_check.extend(extract_money_facts(flyer_content))
    facts_to_check.extend(extract_temperature_facts(flyer_content))
    facts_to_check.extend(extract_condition_facts(flyer_content))

    # IMPORTANT: catch values inside data-testid spans, especially:
    # £<span data-testid="9">9999</span>. The HTML flyer uses these
    # fields for venue, address, date, party size, weather, and costs.
    testid_facts = extract_testid_facts(flyer_content)
    facts_to_check.extend(_structured_facts_from_testids(testid_facts))

    # De-dupe while preserving order
    seen: set[str] = set()
    deduped: list[str] = []
    for f in facts_to_check:
        key = _normalise_fact(f)
        if key not in seen:
            seen.add(key)
            deduped.append(f)

    if not deduped:
        return IntegrityResult(
            ok=True,
            summary="no extractable facts in flyer (verified vacuously)",
        )

    verified: list[str] = []
    unverified: list[str] = _source_consistency_failures()
    source_records = [
        record
        for record in _TOOL_CALL_LOG
        if record.tool_name != "generate_flyer"
    ]

    for fact in deduped:
        if fact_appears_in_log(fact, source_records, include_arguments=False):
            verified.append(fact)
        else:
            unverified.append(fact)

    if unverified:
        return IntegrityResult(
            ok=False,
            unverified_facts=unverified,
            verified_facts=verified,
            summary=(
                f"dataflow FAIL: {len(unverified)} unverified fact(s): "
                f"{unverified[:5]}" + ("..." if len(unverified) > 5 else "")
            ),
        )

    return IntegrityResult(
        ok=True,
        verified_facts=verified,
        summary=f"dataflow OK: verified {len(verified)} fact(s) against tool outputs",
    )

__all__ = [
    "IntegrityResult",
    "ToolCallRecord",
    "_TOOL_CALL_LOG",
    "clear_log",
    "extract_condition_facts",
    "extract_money_facts",
    "extract_temperature_facts",
    "extract_testid_facts",
    "fact_appears_in_log",
    "record_tool_call",
    "load_tool_log",
    "replay_latest_tool_log",
    "replay_tool_log_from_trace",
    "verify_dataflow",
]

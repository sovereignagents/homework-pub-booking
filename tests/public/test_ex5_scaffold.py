"""Public tests for Ex5 — Edinburgh research scenario.

These run under `make test` and as part of `make ci`. Passing them
does NOT guarantee you're done — the hidden tests (tests/private/)
exercise subtler failure modes. But failing here means you're not
on track, so fix these first.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from starter.edinburgh_research import integrity

SAMPLE_DATA = Path(__file__).resolve().parents[2] / "starter" / "edinburgh_research" / "sample_data"


# ─── fixtures exist and are sane ────────────────────────────────────


def test_venues_fixture_has_expected_entries() -> None:
    data = json.loads((SAMPLE_DATA / "venues.json").read_text())
    assert isinstance(data, list) and len(data) >= 5
    ids = {v["id"] for v in data}
    assert "haymarket_tap" in ids
    assert "royal_oak" in ids


def test_weather_fixture_has_edinburgh() -> None:
    data = json.loads((SAMPLE_DATA / "weather.json").read_text())
    assert "edinburgh" in data
    assert len(data["edinburgh"]) >= 3


def test_catering_fixture_has_base_rates() -> None:
    data = json.loads((SAMPLE_DATA / "catering.json").read_text())
    assert "base_rates_gbp_per_head" in data
    assert data["maximum_party_size_for_auto_booking"] == 8


# ─── integrity module exists and has the expected API ──────────────


def test_integrity_module_exposes_required_names() -> None:
    for name in [
        "_TOOL_CALL_LOG",
        "ToolCallRecord",
        "record_tool_call",
        "clear_log",
        "verify_dataflow",
        "IntegrityResult",
    ]:
        assert hasattr(integrity, name), f"integrity.{name} missing"


def test_record_tool_call_appends() -> None:
    integrity.clear_log()
    assert integrity._TOOL_CALL_LOG == []
    integrity.record_tool_call("test_tool", {"a": 1}, {"b": 2})
    assert len(integrity._TOOL_CALL_LOG) == 1
    assert integrity._TOOL_CALL_LOG[0].tool_name == "test_tool"
    integrity.clear_log()


def test_fact_appears_in_log_helper() -> None:
    """The provided helper should find scalar values nested anywhere."""
    integrity.clear_log()
    integrity.record_tool_call("t", {}, {"nested": {"total_gbp": 540}})
    assert integrity.fact_appears_in_log(540)
    assert integrity.fact_appears_in_log("£540")  # leading £ stripped
    assert not integrity.fact_appears_in_log(999)
    integrity.clear_log()


# ─── tools module structure ─────────────────────────────────────────


def test_tools_module_registers_four_tools() -> None:
    """build_tool_registry() must produce a registry with our four
    tools plus the sovereign-agent builtins."""
    import tempfile

    from sovereign_agent.session.directory import create_session

    from starter.edinburgh_research.tools import build_tool_registry

    with tempfile.TemporaryDirectory() as td:
        session_root = Path(td) / "sessions"
        session_root.mkdir()
        session = create_session(scenario="test", sessions_dir=session_root)

        reg = build_tool_registry(session)
        names = {t.name for t in reg.list()}

        for required in ["venue_search", "get_weather", "calculate_cost", "generate_flyer"]:
            assert required in names, f"{required} not registered"

        # Builtins should also be there (loop half needs complete_task / handoff).
        assert "complete_task" in names
        assert "handoff_to_structured" in names


def test_generate_flyer_is_not_parallel_safe() -> None:
    """Writes must never be parallelised — grader checks this explicitly."""
    import tempfile

    from sovereign_agent.session.directory import create_session

    from starter.edinburgh_research.tools import build_tool_registry

    with tempfile.TemporaryDirectory() as td:
        session_root = Path(td) / "sessions"
        session_root.mkdir()
        session = create_session(scenario="test", sessions_dir=session_root)
        reg = build_tool_registry(session)
        flyer = reg.get("generate_flyer")
        assert flyer.parallel_safe is False, (
            "generate_flyer writes a file; it must be registered with "
            "parallel_safe=False. Penalty: grader deducts Mechanical points."
        )


def test_read_only_tools_are_parallel_safe() -> None:
    """venue_search, get_weather, calculate_cost should be parallel-safe."""
    import tempfile

    from sovereign_agent.session.directory import create_session

    from starter.edinburgh_research.tools import build_tool_registry

    with tempfile.TemporaryDirectory() as td:
        session_root = Path(td) / "sessions"
        session_root.mkdir()
        session = create_session(scenario="test", sessions_dir=session_root)
        reg = build_tool_registry(session)
        for name in ["venue_search", "get_weather", "calculate_cost"]:
            assert reg.get(name).parallel_safe is True, (
                f"{name} is a read-only tool; it should be parallel_safe=True "
                f"so the executor can batch concurrent calls."
            )


# ─── verify_dataflow contract ───────────────────────────────────────


def test_verify_dataflow_returns_integrity_result() -> None:
    """Once implemented, verify_dataflow returns an IntegrityResult.
    This test will fail with NotImplementedError until you implement
    it — that's expected; make it pass as the first step."""
    integrity.clear_log()
    integrity.record_tool_call("calculate_cost", {}, {"total_gbp": 540, "deposit_required_gbp": 0})

    try:
        result = integrity.verify_dataflow("Total: £540. Deposit: £0.")
    except NotImplementedError:
        pytest.skip("verify_dataflow not implemented yet — do Ex5 first")

    assert isinstance(result, integrity.IntegrityResult)
    assert hasattr(result, "ok")
    assert hasattr(result, "unverified_facts")
    assert hasattr(result, "verified_facts")
    integrity.clear_log()


def test_verify_dataflow_catches_obvious_fabrication() -> None:
    """If the flyer says £9999 but no tool ever returned 9999, fail."""
    integrity.clear_log()
    integrity.record_tool_call("calculate_cost", {}, {"total_gbp": 540, "deposit_required_gbp": 0})

    try:
        result = integrity.verify_dataflow("Total: £9999 (this was never computed).")
    except NotImplementedError:
        pytest.skip("verify_dataflow not implemented yet")

    assert result.ok is False, "£9999 was not in any tool output — should be flagged"
    assert any("9999" in uf for uf in result.unverified_facts)
    integrity.clear_log()

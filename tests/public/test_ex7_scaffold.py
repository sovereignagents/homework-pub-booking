"""Public tests for Ex7 — handoff bridge.

Structure-only; real round-trip execution is in tests/private/.
"""

from __future__ import annotations


def test_bridge_module_exposes_expected_api() -> None:
    from starter.handoff_bridge import bridge

    for name in [
        "HandoffBridge",
        "BridgeResult",
        "BridgeOutcome",
        "build_forward_handoff",
        "build_reverse_task",
    ]:
        assert hasattr(bridge, name), f"bridge.{name} missing"


def test_build_forward_handoff_produces_valid_handoff() -> None:
    """Helper from bridge.py must produce a Handoff with required fields."""
    import tempfile
    from pathlib import Path

    from sovereign_agent.halves import HalfResult
    from sovereign_agent.handoff import Handoff
    from sovereign_agent.session.directory import create_session

    from starter.handoff_bridge.bridge import build_forward_handoff

    with tempfile.TemporaryDirectory() as td:
        sessions_dir = Path(td) / "sessions"
        sessions_dir.mkdir()
        session = create_session(scenario="test", sessions_dir=sessions_dir)

        loop_result = HalfResult(
            success=True,
            output={"venue": "haymarket_tap"},
            summary="found a venue",
            next_action="handoff_to_structured",
            handoff_payload={"venue_id": "haymarket_tap", "party_size": 12},
        )
        handoff = build_forward_handoff(session, loop_result)
        assert isinstance(handoff, Handoff)
        assert handoff.from_half == "loop"
        assert handoff.to_half == "structured"
        assert handoff.data


def test_build_reverse_task_carries_rejection_reason() -> None:
    from sovereign_agent.halves import HalfResult

    from starter.handoff_bridge.bridge import build_reverse_task

    loop_result = HalfResult(success=True, output={"venue": "haymarket_tap"}, summary="")
    struct_result = HalfResult(
        success=False,
        output={"reason": "party_too_large"},
        summary="rejected: party > cap",
        next_action="escalate",
    )
    task = build_reverse_task(loop_result, struct_result)
    assert "rejection_reason" in task["context"]
    assert task["context"]["rejection_reason"] == "party_too_large"
    assert task["context"]["retry"] is True

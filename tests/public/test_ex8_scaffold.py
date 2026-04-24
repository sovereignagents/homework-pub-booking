"""Public tests for Ex8 — voice pipeline.

Text mode is tested here end-to-end with a scripted manager. Voice
mode (real Speechmatics) is only tested in CI if SPEECHMATICS_KEY is set.
"""

from __future__ import annotations

import pytest


def test_manager_persona_module_exists() -> None:
    from starter.voice_pipeline import manager_persona

    for name in ["ManagerPersona", "MANAGER_SYSTEM_PROMPT", "ManagerTurn"]:
        assert hasattr(manager_persona, name), f"manager_persona.{name} missing"


def test_voice_loop_module_exists() -> None:
    from starter.voice_pipeline import voice_loop

    for name in ["run_text_mode", "run_voice_mode"]:
        assert hasattr(voice_loop, name), f"voice_loop.{name} missing"


@pytest.mark.asyncio
async def test_text_mode_appends_trace_events(tmp_path, monkeypatch) -> None:
    """Text mode should append voice.utterance_in and _out events for each turn."""
    import io

    from sovereign_agent.session.directory import create_session

    from starter.voice_pipeline.manager_persona import ManagerTurn

    # Stub persona — doesn't call the LLM.
    class StubPersona:
        history: list[ManagerTurn] = []

        async def respond(self, utterance: str) -> str:
            r = f"(echo) {utterance}"
            self.history.append(ManagerTurn(user_utterance=utterance, manager_response=r))
            return r

    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    session = create_session(scenario="test", sessions_dir=sessions_dir)

    # Feed 2 lines then EOF.
    monkeypatch.setattr("sys.stdin", io.StringIO("hello\nbook for 6\n\n"))

    from starter.voice_pipeline.voice_loop import run_text_mode

    await run_text_mode(session, StubPersona(), max_turns=4)

    trace = session.trace_path.read_text(encoding="utf-8")
    assert "voice.utterance_in" in trace
    assert "voice.utterance_out" in trace


@pytest.mark.asyncio
async def test_voice_mode_falls_back_when_no_speechmatics_key(tmp_path, monkeypatch) -> None:
    """--voice without SPEECHMATICS_KEY should not crash — it falls back to text."""
    import io

    from sovereign_agent.session.directory import create_session

    from starter.voice_pipeline.manager_persona import ManagerTurn

    monkeypatch.delenv("SPEECHMATICS_KEY", raising=False)

    class StubPersona:
        history: list[ManagerTurn] = []

        async def respond(self, utterance: str) -> str:
            r = f"(echo) {utterance}"
            self.history.append(ManagerTurn(user_utterance=utterance, manager_response=r))
            return r

    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    session = create_session(scenario="test", sessions_dir=sessions_dir)

    monkeypatch.setattr("sys.stdin", io.StringIO("hi\n\n"))

    # Must NOT raise — should degrade to text mode.
    from starter.voice_pipeline.voice_loop import run_voice_mode

    await run_voice_mode(session, StubPersona(), max_turns=2)


def test_manager_system_prompt_mentions_rules() -> None:
    """The persona prompt should include the two caps (party size, deposit).
    Without these, the grader's LLM judge will find the manager too permissive."""
    from starter.voice_pipeline.manager_persona import MANAGER_SYSTEM_PROMPT

    low = MANAGER_SYSTEM_PROMPT.lower()
    assert "8" in MANAGER_SYSTEM_PROMPT or "eight" in low, "party-size cap missing"
    assert "300" in MANAGER_SYSTEM_PROMPT, "deposit cap missing"

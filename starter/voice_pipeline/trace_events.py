"""Trace-event helpers for the Ex8 voice pipeline."""

from __future__ import annotations

from sovereign_agent.session.directory import Session
from sovereign_agent.session.state import now_utc


def log_utterance_in(session: Session, text: str, turn: int, mode: str) -> None:
    """Append a user utterance trace event."""
    _log_utterance(
        session=session,
        event_type="voice.utterance_in",
        actor="user",
        text=text,
        turn=turn,
        mode=mode,
    )


def log_utterance_out(session: Session, text: str, turn: int, mode: str) -> None:
    """Append a manager/system utterance trace event."""
    _log_utterance(
        session=session,
        event_type="voice.utterance_out",
        actor="manager",
        text=text,
        turn=turn,
        mode=mode,
    )


def _log_utterance(
    *,
    session: Session,
    event_type: str,
    actor: str,
    text: str,
    turn: int,
    mode: str,
) -> None:
    session.append_trace_event(
        {
            "event_type": event_type,
            "actor": actor,
            "timestamp": now_utc().isoformat(),
            "payload": {"text": text, "turn": turn, "mode": mode},
        }
    )


__all__ = ["log_utterance_in", "log_utterance_out"]

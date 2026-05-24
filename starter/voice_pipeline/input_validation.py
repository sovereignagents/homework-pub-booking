"""Non-LLM validation for user utterances before manager handling."""

from __future__ import annotations

from dataclasses import dataclass, field


CLARIFICATION_TEXT = "Sorry, I didnae catch that clearly. Could you say it again?"


@dataclass
class EntryValidation:
    """Validation result for one raw user utterance."""

    usable: bool
    text: str
    issues: list[str] = field(default_factory=list)
    clarification: str = CLARIFICATION_TEXT


def validate_entry_message(text: str) -> EntryValidation:
    """Validate an utterance without rewriting or inferring any details.

    The checks are intentionally conservative: unclear input is rejected, but
    valid short phrases like "hi" or "bye" are allowed through.
    """
    cleaned = " ".join(text.strip().split())
    issues: list[str] = []

    if not cleaned:
        issues.append("empty")

    if cleaned and not any(ch.isalnum() for ch in cleaned):
        issues.append("no_content")

    if cleaned and _replacement_character_ratio(cleaned) > 0.1:
        issues.append("transcription_noise")

    if cleaned and _looks_unsupported_language(cleaned):
        issues.append("unsupported_language")

    return EntryValidation(
        usable=not issues,
        text=cleaned,
        issues=issues,
    )


def _replacement_character_ratio(text: str) -> float:
    if not text:
        return 0.0
    return text.count("\ufffd") / len(text)


def _looks_unsupported_language(text: str) -> bool:
    """Return true when the utterance appears mostly non-English-script text."""
    letters = [ch for ch in text if ch.isalpha()]
    if len(letters) < 3:
        return False
    ascii_letters = [ch for ch in letters if "a" <= ch.lower() <= "z"]
    return len(ascii_letters) / len(letters) < 0.5


__all__ = ["CLARIFICATION_TEXT", "EntryValidation", "validate_entry_message"]

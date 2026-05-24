"""Input validation checks for Ex8 voice pipeline."""

from __future__ import annotations

from starter.voice_pipeline.input_validation import validate_entry_message


def test_numeric_deposit_answer_is_usable() -> None:
    result = validate_entry_message("300")

    assert result.usable
    assert result.text == "300"


def test_punctuation_only_answer_is_not_usable() -> None:
    result = validate_entry_message("???")

    assert not result.usable
    assert "no_content" in result.issues

"""Manager judge parsing checks for Ex8."""

from __future__ import annotations

from starter.voice_pipeline.manager_judge import parse_judgement


def test_parse_judgement_accepts_fenced_json() -> None:
    judgement = parse_judgement(
        """```json
{"approved": false, "reason": "missing venue clarity", "final_response": "Which venue did ye want?"}
```""",
        "draft",
    )

    assert not judgement.approved
    assert judgement.reason == "missing venue clarity"
    assert judgement.final_response == "Which venue did ye want?"


def test_parse_judgement_caps_reason_words() -> None:
    judgement = parse_judgement(
        '{"approved": true, "reason": "one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen twenty twentyone", "final_response": "draft"}',
        "draft",
    )

    assert len(judgement.reason.split()) == 20

"""Integrity check — confirms every student scenario ships with a
dataflow integrity check.

Crude but effective: for each scenario directory, grep for
`verify_dataflow` in Python files. Any scenario without one
loses 10 points (per the rubric penalty).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

SCENARIO_DIRS = [
    "starter/edinburgh_research",
    "starter/handoff_bridge",
    # starter/rasa_half doesn't need its own integrity check — it's
    # downstream of edinburgh_research. starter/voice_pipeline's
    # integrity check is per-utterance (trace events), not dataflow.
]


@dataclass
class IntegrityCheckResult:
    all_present: bool
    missing: list[str] = field(default_factory=list)
    found_in: list[str] = field(default_factory=list)


def check_all_scenarios(repo_root: Path) -> IntegrityCheckResult:
    missing: list[str] = []
    found_in: list[str] = []
    for rel in SCENARIO_DIRS:
        d = repo_root / rel
        if not d.exists():
            missing.append(rel)
            continue
        found = False
        for py in d.rglob("*.py"):
            if "verify_dataflow" in py.read_text(encoding="utf-8"):
                found = True
                found_in.append(str(py.relative_to(repo_root)))
                break
        if not found:
            missing.append(rel)
    return IntegrityCheckResult(
        all_present=not missing,
        missing=missing,
        found_in=found_in,
    )


if __name__ == "__main__":
    repo_root = Path(__file__).resolve().parent.parent
    r = check_all_scenarios(repo_root)
    print(f"Integrity checks present in: {r.found_in}")
    if r.missing:
        print(f"MISSING from: {r.missing}")
        raise SystemExit(1)

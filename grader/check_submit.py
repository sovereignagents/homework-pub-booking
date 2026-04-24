"""Local grader — advisory only, NOT the authoritative grade.

`make check-submit` invokes this. It runs the mechanical layer fully,
the parts of the behavioural layer that don't require private tests,
and stops short of the reasoning layer (that needs an LLM judge).

Usage:
    python -m grader.check_submit
    python -m grader.check_submit --only ex5
    python -m grader.check_submit --verbose
    python -m grader.check_submit --json > report.json
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

from grader.rubric import (
    REASONING_MAX,
    CheckResult,
    GradeReport,
    LayerResult,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
ANSWERS_DIR = REPO_ROOT / "answers"
STARTER_DIR = REPO_ROOT / "starter"


# ─── helpers ────────────────────────────────────────────────────────


def _run(cmd: list[str], timeout: int = 120) -> tuple[int, str, str]:
    try:
        r = subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True, timeout=timeout)
        return r.returncode, r.stdout, r.stderr
    except subprocess.TimeoutExpired:
        return 124, "", f"timed out after {timeout}s"
    except FileNotFoundError:
        return 127, "", f"command not found: {cmd[0]}"


def _check(name: str, ok: bool, possible: float, detail: str = "") -> CheckResult:
    return CheckResult(
        name=name,
        passed=ok,
        points_earned=possible if ok else 0.0,
        points_possible=possible,
        detail=detail,
    )


# ─── Mechanical layer ───────────────────────────────────────────────


def run_mechanical(only: str | None) -> LayerResult:
    layer = LayerResult(name="mechanical")

    # Top-level files
    required = ["README.md", "ASSIGNMENT.md", "pyproject.toml", "Makefile", "SETUP.md"]
    missing = [f for f in required if not (REPO_ROOT / f).exists()]
    layer.checks.append(
        _check(
            "repo_has_required_top_level_files",
            not missing,
            2,
            f"missing: {missing}" if missing else "all present",
        )
    )

    # pyproject pin
    pyproj = (REPO_ROOT / "pyproject.toml").read_text()
    has_pin = re.search(r"sovereign-agent\s*==\s*0\.2\.0", pyproj) is not None
    layer.checks.append(
        _check(
            "pyproject_pins_sovereign_agent_0_2_0",
            has_pin,
            2,
            "found == 0.2.0 pin" if has_pin else "pin not found",
        )
    )

    # ruff
    rc, _, _ = _run(["uv", "run", "ruff", "check", "starter/", "grader/", "tests/"])
    layer.checks.append(_check("ruff_lint_clean", rc == 0, 3))

    rc, _, _ = _run(["uv", "run", "ruff", "format", "--check", "starter/", "grader/", "tests/"])
    layer.checks.append(_check("ruff_format_clean", rc == 0, 2))

    # pytest collection
    rc, _, _ = _run(["uv", "run", "pytest", "--collect-only", "-q"])
    layer.checks.append(_check("pytest_collects", rc == 0, 3))

    # public tests
    rc, out, _ = _run(["uv", "run", "pytest", "tests/public", "-q", "--no-header"])
    layer.checks.append(_check("public_tests_pass", rc == 0, 5, f"pytest rc={rc}"))

    # answers
    expected = [
        "ex5_loop_scenario.md",
        "ex6_rasa_integration.md",
        "ex7_handoff_bridge.md",
        "ex8_voice_pipeline.md",
        "ex9_reflection.md",
    ]
    missing_answers = [a for a in expected if not (ANSWERS_DIR / a).exists()]
    layer.checks.append(
        _check(
            "answers_files_exist",
            not missing_answers,
            2,
            f"missing: {missing_answers}" if missing_answers else "all present",
        )
    )

    # Answers not empty / still placeholder. We look under "Your answer"
    # headings and require ≥40 chars of substance after stripping the
    # template placeholder text.
    empty: list[str] = []
    for a in expected:
        path = ANSWERS_DIR / a
        if not path.exists():
            empty.append(a)
            continue
        text = path.read_text(encoding="utf-8")
        # Strip everything after "## Your answer" headings and see if
        # anything substantive remains. Very defensive — false-negatives
        # are better than false-positives on the local grader.
        under_headings = re.findall(
            r"(?:## Your answer|### Your answer)\s*\n(.*?)(?=\n## |\n### |\Z)",
            text,
            re.DOTALL,
        )
        has_substance = False
        for block in under_headings:
            stripped = block.strip()
            # Drop the template placeholder sentences.
            cleaned = re.sub(r"\*\([^)]*\)\*", "", stripped).strip()
            if len(cleaned) > 40:
                has_substance = True
                break
        if not has_substance:
            empty.append(a)
    layer.checks.append(
        _check(
            "answers_not_empty",
            not empty,
            3,
            f"still placeholder: {empty}" if empty else "all answered",
        )
    )

    # Integrity check presence — look for verify_dataflow-shaped helpers
    # in each scenario that has a scaffold. Crude grep, but the grader
    # repo does the real check.
    scenario_dirs = [
        STARTER_DIR / "edinburgh_research",
        STARTER_DIR / "handoff_bridge",
    ]
    missing_integrity: list[str] = []
    for d in scenario_dirs:
        if not d.exists():
            continue
        found = False
        for py in d.glob("*.py"):
            if "verify_dataflow" in py.read_text(encoding="utf-8"):
                found = True
                break
        if not found:
            missing_integrity.append(d.name)
    layer.checks.append(
        _check(
            "all_scenarios_have_integrity_check",
            not missing_integrity,
            5,
            f"missing in: {missing_integrity}" if missing_integrity else "every scenario checked",
        )
    )

    return layer


# ─── Behavioural layer (partial — private parts skipped) ───────────


def run_behavioural(only: str | None) -> LayerResult:
    layer = LayerResult(name="behavioural")

    if only in (None, "ex5"):
        rc, _, _ = _run(["uv", "run", "python", "-m", "starter.edinburgh_research.run"])
        layer.checks.append(_check("ex5_scenario_runs_end_to_end", rc == 0, 6))

    if only in (None, "ex6"):
        # Local doesn't spin Rasa; we run the validator normalisation tests
        # as a proxy.
        rc, _, _ = _run(["uv", "run", "pytest", "tests/public/test_ex6_scaffold.py", "-q"])
        layer.checks.append(_check("ex6_structured_half_accepts_valid_booking", rc == 0, 4))

    if only in (None, "ex7"):
        rc, _, _ = _run(["uv", "run", "pytest", "tests/public/test_ex7_scaffold.py", "-q"])
        layer.checks.append(_check("ex7_round_trip_completes", rc == 0, 6))

    if only in (None, "ex8"):
        rc, _, _ = _run(["uv", "run", "pytest", "tests/public/test_ex8_scaffold.py", "-q"])
        layer.checks.append(_check("ex8_trace_has_utterance_events", rc == 0, 3))

    return layer


# ─── Reasoning layer (local: skipped, notes only) ──────────────────


def run_reasoning(only: str | None) -> LayerResult:
    layer = LayerResult(name="reasoning")
    # Local can't score reasoning (no LLM judge). Present a not-scored placeholder.
    layer.checks.append(
        CheckResult(
            name="reasoning_scored_by_ci",
            passed=False,
            points_earned=0.0,
            points_possible=REASONING_MAX,
            detail="Reasoning is scored by CI with LLM-as-judge, not locally.",
        )
    )
    return layer


# ─── render ─────────────────────────────────────────────────────────


def render_markdown(report: GradeReport) -> str:
    lines: list[str] = []
    lines.append("# Local grading report")
    lines.append("")
    lines.append(f"**Raw score:** {report.raw_score:.1f} / {report.possible:.0f}")
    if report.penalties:
        lines.append(f"**Penalties:** −{report.penalty_total:.1f}")
        for name, pts in report.penalties:
            lines.append(f"  - {name}: −{pts:.1f}")
    lines.append(f"**Final (local):** {report.final_score:.1f} / {report.possible:.0f}")
    lines.append("")
    lines.append(
        "> Local score excludes the reasoning layer (needs LLM-as-judge)"
        " and some hidden tests. CI at the deadline is the authoritative grade."
    )
    lines.append("")
    for layer in (report.mechanical, report.behavioural, report.reasoning):
        lines.append(f"## {layer.name.title()} ({layer.earned:.1f} / {layer.possible:.0f})")
        lines.append("")
        for c in layer.checks:
            icon = "✓" if c.passed else "✗"
            lines.append(
                f"- {icon} `{c.name}` — {c.points_earned:.1f}/{c.points_possible:.0f}"
                + (f" — {c.detail}" if c.detail else "")
            )
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", choices=["ex5", "ex6", "ex7", "ex8", "ex9"])
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    mechanical = run_mechanical(args.only)
    behavioural = run_behavioural(args.only)
    reasoning = run_reasoning(args.only)

    report = GradeReport(
        mechanical=mechanical,
        behavioural=behavioural,
        reasoning=reasoning,
    )

    # Penalty: integrity check missing → -10.
    for c in mechanical.checks:
        if c.name == "all_scenarios_have_integrity_check" and not c.passed:
            report.penalties.append(("missing_integrity_check", 10.0))

    if args.json:
        out = {
            "raw_score": report.raw_score,
            "final_score": report.final_score,
            "possible": report.possible,
            "penalties": [{"name": n, "points": p} for n, p in report.penalties],
            "layers": {
                layer.name: {
                    "earned": layer.earned,
                    "possible": layer.possible,
                    "checks": [
                        {
                            "name": c.name,
                            "passed": c.passed,
                            "points_earned": c.points_earned,
                            "points_possible": c.points_possible,
                            "detail": c.detail,
                        }
                        for c in layer.checks
                    ],
                }
                for layer in (mechanical, behavioural, reasoning)
            },
        }
        print(json.dumps(out, indent=2))
    else:
        print(render_markdown(report))

    # Exit 0 if any score was produced; exit 1 only on infrastructure failure
    # (nothing to score). Local grader is advisory.
    return 0 if report.raw_score >= 0 else 1


if __name__ == "__main__":
    sys.exit(main())
